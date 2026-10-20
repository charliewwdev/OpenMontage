#!/usr/bin/env python3
"""Standalone media worker: reserve Redis jobs and run Comfy / QA jobs.

Usage (compose / Coolify)::

    PYTHONPATH=/app/studio/server:/app python -m media_worker

Requires ``STUDIO_REDIS_URL`` or ``REDIS_URL``. Without Redis the process exits
non-zero (API falls back to in-process thread pool).

Concurrency:
- ``STUDIO_MEDIA_WORKERS`` (default 2, max 4) runs video jobs in parallel
  inside one process (bounded thread pool). Quality gates unchanged.
- ``STUDIO_IMAGE_WORKERS`` (default 2, max 4) runs NVIDIA / Seedream stills
  beside those video slots. ComfyUI stills stay on the video slots.

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
from concurrent.futures import Future, ThreadPoolExecutor, wait, FIRST_COMPLETED
from typing import Any

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


def _worker_concurrency() -> int:
    raw = (os.environ.get("STUDIO_MEDIA_WORKERS") or "").strip()
    if raw.isdigit() and int(raw) > 0:
        return max(1, min(4, int(raw)))
    try:
        from platform_config import load_platform_config

        n = int((load_platform_config() or {}).get("defaults", {}).get("mediaJobWorkers") or 2)
        return max(1, min(4, n))
    except Exception:
        return 2


def _run_one(job: dict[str, Any], projects_root) -> None:
    from job_queue import ack_job, dispatch_job
    from settings_store import load_and_apply

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
        get_redis,
        promote_image_jobs,
        reclaim_processing,
        recover_stale_generating,
        redis_enabled,
        redis_url,
        api_image_workers,
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
    promoted = promote_image_jobs()
    try:
        recovered = recover_stale_generating(max_age_sec=int(os.environ.get("STUDIO_STALE_GEN_SEC") or "180"))
        log.info(
            "startup reclaim=%s promoted_stills=%s stale_regen=%s",
            reclaimed,
            promoted,
            len((recovered or {}).get("recovered") or []),
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("recover_stale_generating failed: %s", exc)

    video_conc = _worker_concurrency()
    image_conc = api_image_workers()
    pool_size = max(1, video_conc + max(image_conc, 4))
    log.info(
        "listening on %s video_slots=%s image_slots=%s (reliable reserve→processing)",
        QUEUE_KEY,
        video_conc,
        image_conc,
    )
    last_reload = 0.0
    last_lane = 0.0
    video_inflight: set[Future] = set()
    image_inflight: set[Future] = set()

    with ThreadPoolExecutor(max_workers=pool_size, thread_name_prefix="media-job") as pool:
        while not _STOP:
            # Refresh shared secrets periodically (ops restore / UI saves hit API only).
            now = time.time()
            if now - last_reload > 60:
                try:
                    load_and_apply(projects_root)
                    last_reload = now
                except Exception:
                    pass
            if now - last_lane > 15:
                image_conc = api_image_workers()
                last_lane = now

            busy = video_inflight | image_inflight
            if busy:
                done, _pending = wait(busy, timeout=0.2, return_when=FIRST_COMPLETED)
                if done:
                    video_inflight -= done
                    image_inflight -= done

            video_lane = "video" if image_conc else "any"
            while not _STOP and len(video_inflight) < video_conc:
                timeout = 0.0 if video_inflight or image_inflight else 1.0
                job = reserve_job(timeout=timeout, lane=video_lane)
                if not job:
                    break
                video_inflight.add(pool.submit(_run_one, job, projects_root))

            while not _STOP and image_conc and len(image_inflight) < image_conc:
                timeout = 0.0 if video_inflight or image_inflight else 1.0
                job = reserve_job(timeout=timeout, lane="image")
                if not job:
                    break
                image_inflight.add(pool.submit(_run_one, job, projects_root))

            if not video_inflight and not image_inflight:
                time.sleep(0.05)

        inflight = video_inflight | image_inflight
        if inflight:
            log.info("draining %s in-flight job(s)…", len(inflight))
            wait(inflight, timeout=600)

    log.info("stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
