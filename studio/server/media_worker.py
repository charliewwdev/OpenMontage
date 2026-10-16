#!/usr/bin/env python3
"""Standalone media worker: reserve Redis jobs and run Comfy / QA jobs.

Usage (compose / Coolify)::

    PYTHONPATH=/app/studio/server:/app python -m media_worker

Requires ``STUDIO_REDIS_URL`` or ``REDIS_URL``. Without Redis the process exits
non-zero (API falls back to in-process thread pool).

Crash safety:
- Jobs are reserved via queue→processing (BLMOVE / BRPOPLPUSH), not BLPOP.
- On startup, in-flight processing jobs are reclaimed back onto the queue.
- Stale ``imageStatus=generating`` entities are re-enqueued after a grace period.
"""

from __future__ import annotations

import logging
import os
import signal
import sys
import time

logging.basicConfig(
    level=os.environ.get("STUDIO_LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s [media-worker] %(message)s",
)
log = logging.getLogger("media_worker")

_STOP = False


def _handle_signal(signum, _frame) -> None:
    global _STOP
    log.info("signal %s received, draining current job then exit", signum)
    _STOP = True


def main() -> int:
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    # Ensure studio server modules import cleanly.
    root = os.environ.get("OPENMONTAGE_ROOT", "/app")
    server = os.path.join(root, "studio", "server")
    for path in (server, root):
        if path not in sys.path:
            sys.path.insert(0, path)

    from pathlib import Path

    from job_queue import (
        QUEUE_KEY,
        ack_job,
        dispatch_job,
        get_redis,
        reclaim_processing,
        recover_stale_generating,
        redis_enabled,
        redis_url,
        reserve_job,
    )
    from settings_store import load_and_apply

    if not redis_enabled():
        log.error("REDIS_URL / STUDIO_REDIS_URL not set — refuse to start")
        return 2

    projects_root = Path(os.environ.get("PROJECTS_ROOT") or "/data/projects")
    try:
        applied = load_and_apply(projects_root)
        log.info("secrets loaded keys=%s", sorted(applied.keys())[:12])
    except Exception as exc:  # noqa: BLE001
        log.warning("load_and_apply failed (will retry per job): %s", exc)

    r = get_redis()
    if r is None:
        log.error("cannot connect to redis at %s", redis_url().split("@")[-1])
        return 3

    # Crash recovery before accepting new work.
    reclaimed = reclaim_processing()
    try:
        recovered = recover_stale_generating(max_age_sec=int(os.environ.get("STUDIO_STALE_GEN_SEC") or "180"))
        log.info(
            "startup reclaim=%s stale_regen=%s",
            reclaimed,
            len((recovered or {}).get("recovered") or []),
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("recover_stale_generating failed: %s", exc)

    log.info("listening on %s (reliable reserve→processing)", QUEUE_KEY)
    last_reload = 0.0
    while not _STOP:
        # Refresh shared secrets periodically (ops restore / UI saves hit API only).
        now = time.time()
        if now - last_reload > 60:
            try:
                load_and_apply(projects_root)
                last_reload = now
            except Exception:
                pass
        job = reserve_job(timeout=2.0)
        if not job:
            continue
        job_id = job.get("id") or "?"
        kind = job.get("kind") or "?"
        log.info("start job=%s kind=%s attempt=%s", job_id, kind, job.get("attempts"))
        try:
            load_and_apply(projects_root)
        except Exception:
            pass
        t0 = time.time()
        try:
            dispatch_job(job)
            log.info("done job=%s kind=%s in %.1fs", job_id, kind, time.time() - t0)
        except Exception as exc:  # noqa: BLE001
            log.exception("fail job=%s kind=%s: %s", job_id, kind, exc)
        finally:
            # Always ack so a permanent failure does not loop forever after reclaim.
            ack_job(job)
    log.info("stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
