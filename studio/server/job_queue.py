"""Unified media job queue: Redis (multi-process) with in-process pool fallback.

Production: set ``REDIS_URL`` / ``STUDIO_REDIS_URL`` and run ``media_worker``.
Dev / single-container: jobs run on the bounded ``job_pool`` ThreadPoolExecutor.

Reliability:
- Jobs move queue → processing via BRPOPLPUSH / BLMOVE (not destructive BLPOP).
- Worker crash / restart reclaims the processing list back onto the queue.
- Redis AOF should be enabled in compose so pending jobs survive Redis restart.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from typing import Any, Callable

log = logging.getLogger("studio.job_queue")

QUEUE_KEY = os.environ.get("STUDIO_REDIS_QUEUE", "om:studio:media:jobs")
PROCESSING_KEY = os.environ.get(
    "STUDIO_REDIS_PROCESSING",
    f"{QUEUE_KEY}:processing",
)
RESULT_PREFIX = os.environ.get("STUDIO_REDIS_RESULT_PREFIX", "om:studio:media:result:")

_redis = None
_redis_checked = False
_redis_lock = threading.Lock()


def redis_url() -> str:
    return (
        (os.environ.get("STUDIO_REDIS_URL") or "").strip()
        or (os.environ.get("REDIS_URL") or "").strip()
    )


def redis_enabled() -> bool:
    return bool(redis_url())


def get_redis():
    """Lazy Redis client; returns None when unset or unreachable."""
    global _redis, _redis_checked
    if not redis_enabled():
        return None
    with _redis_lock:
        if _redis is not None:
            return _redis
        if _redis_checked and _redis is None:
            return None
        _redis_checked = True
        try:
            import redis  # type: ignore

            client = redis.Redis.from_url(redis_url(), decode_responses=True, socket_connect_timeout=2)
            client.ping()
            _redis = client
            log.info("redis queue ready url=%s queue=%s", redis_url().split("@")[-1], QUEUE_KEY)
            return _redis
        except Exception as exc:  # noqa: BLE001
            log.warning("redis unavailable, falling back to in-process pool: %s", exc)
            _redis = None
            return None


def queue_backend() -> str:
    return "redis" if get_redis() is not None else "thread_pool"


def enqueue(kind: str, payload: dict[str, Any], *, priority: int = 0) -> dict[str, Any]:
    """Enqueue a media job. Returns stub ``{jobId, queued, backend}``."""
    job_id = uuid.uuid4().hex[:16]
    job = {
        "id": job_id,
        "kind": kind,
        "payload": payload or {},
        "priority": int(priority or 0),
        "enqueuedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "attempts": 0,
    }
    r = get_redis()
    if r is not None:
        r.rpush(QUEUE_KEY, json.dumps(job, ensure_ascii=False))
        return {"jobId": job_id, "queued": True, "async": True, "backend": "redis", "kind": kind}

    from job_pool import submit_media

    def _run() -> None:
        try:
            dispatch_job(job)
        except Exception as exc:  # noqa: BLE001
            log.exception("media job %s failed: %s", job_id, exc)

    submit_media(_run)
    return {"jobId": job_id, "queued": True, "async": True, "backend": "thread_pool", "kind": kind}


def reclaim_processing(*, max_items: int = 500) -> int:
    """Move in-flight processing jobs back to the main queue (crash recovery)."""
    r = get_redis()
    if r is None:
        return 0
    moved = 0
    for _ in range(max(1, int(max_items))):
        try:
            # RPOPLPUSH processing → queue (oldest in-flight first if we LPUSH'd).
            raw = r.rpoplpush(PROCESSING_KEY, QUEUE_KEY)
        except Exception as exc:  # noqa: BLE001
            log.warning("reclaim failed: %s", exc)
            break
        if not raw:
            break
        moved += 1
        try:
            job = json.loads(raw)
            log.info(
                "reclaimed job=%s kind=%s from processing",
                job.get("id"),
                job.get("kind"),
            )
        except Exception:
            log.info("reclaimed opaque job payload from processing")
    if moved:
        log.info("reclaimed %s in-flight job(s) → %s", moved, QUEUE_KEY)
    return moved


def reserve_job(*, timeout: float = 2.0) -> dict[str, Any] | None:
    """Atomically move one job from queue → processing. Returns job dict or None."""
    r = get_redis()
    if r is None:
        return None
    timeout = max(1, int(timeout or 2))
    raw = None
    try:
        # Redis 6.2+: BLMOVE; fall back to BRPOPLPUSH for older servers.
        try:
            raw = r.blmove(QUEUE_KEY, PROCESSING_KEY, timeout, "RIGHT", "LEFT")
        except Exception:
            raw = r.brpoplpush(QUEUE_KEY, PROCESSING_KEY, timeout=timeout)
    except Exception as exc:  # noqa: BLE001
        log.warning("reserve_job error: %s", exc)
        return None
    if not raw:
        return None
    try:
        job = json.loads(raw)
    except Exception as exc:  # noqa: BLE001
        log.error("bad job json (dropped from processing): %s", exc)
        try:
            r.lrem(PROCESSING_KEY, 1, raw)
        except Exception:
            pass
        return None
    job["_raw"] = raw
    job["attempts"] = int(job.get("attempts") or 0) + 1
    return job


def ack_job(job: dict[str, Any] | None) -> None:
    """Remove a finished/failed job from the processing list."""
    if not job:
        return
    raw = job.get("_raw")
    if not raw:
        try:
            raw = json.dumps({k: v for k, v in job.items() if k != "_raw"}, ensure_ascii=False)
        except Exception:
            return
    r = get_redis()
    if r is None:
        return
    try:
        r.lrem(PROCESSING_KEY, 1, raw)
    except Exception as exc:  # noqa: BLE001
        log.warning("ack_job lrem failed: %s", exc)


def dispatch_job(job: dict[str, Any]) -> Any:
    """Execute one job dict (worker process or thread pool)."""
    kind = str(job.get("kind") or "")
    payload = job.get("payload") or {}
    handlers: dict[str, Callable[[dict[str, Any]], Any]] = {
        "entity_image": _handle_entity_image,
        "shot_video": _handle_shot_video,
        "entity_recheck_qa": _handle_entity_recheck_qa,
        "fill_entity_stills": _handle_fill_stills,
    }
    fn = handlers.get(kind)
    if not fn:
        raise RuntimeError(f"unknown media job kind: {kind}")
    result = fn(payload)
    r = get_redis()
    if r is not None and job.get("id"):
        try:
            key = f"{RESULT_PREFIX}{job['id']}"
            r.setex(key, 3600, json.dumps({"ok": True, "kind": kind}, ensure_ascii=False))
        except Exception:
            pass
    return result


def recover_stale_generating(*, max_age_sec: int = 180) -> dict[str, Any]:
    """Re-enqueue entity stills stuck in ``imageStatus=generating`` after crash.

    Only touches rows whose ``updatedAt`` is older than ``max_age_sec`` so
    in-flight work is not double-queued.
    """
    from datetime import datetime, timezone
    from pathlib import Path

    from store import ProjectStore

    store = ProjectStore(Path(os.environ.get("PROJECTS_ROOT") or "/data/projects"))
    recovered: list[dict[str, Any]] = []
    skipped_fresh = 0
    now = datetime.now(timezone.utc)
    try:
        items = store.list_items()
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)[:160], "recovered": []}

    for meta in items or []:
        pid = str(meta.get("id") or "")
        if not pid or pid.startswith("_") or pid.startswith("."):
            continue
        try:
            state = store.load(pid)
        except Exception:
            continue
        if not state:
            continue
        dirty = False
        for ent in state.get("entities") or []:
            if ent.get("deletedAt"):
                continue
            if ent.get("imageStatus") != "generating":
                continue
            updated = str(ent.get("updatedAt") or "")
            age = 10**9
            try:
                ts = datetime.fromisoformat(updated.replace("Z", "+00:00"))
                age = (now - ts).total_seconds()
            except Exception:
                age = 10**9
            if age < max_age_sec:
                skipped_fresh += 1
                continue
            # Clear sticky lock then re-queue.
            ent["imageStatus"] = "failed"
            ent["imageError"] = "worker_restart_recovered"
            ent["updatedAt"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            dirty = True
            eid = str(ent.get("id") or "")
            if not eid:
                continue
            stub = enqueue(
                "entity_image",
                {
                    "projectId": pid,
                    "entityId": eid,
                    "threeView": False,
                    "redraw": True,
                    "forceIllustration": False,
                },
            )
            # Mark generating again so UI shows progress; worker owns completion.
            ent["imageStatus"] = "generating"
            ent["imageError"] = None
            ent.pop("qaFailed", None)
            ent.pop("qaFailReason", None)
            recovered.append(
                {
                    "projectId": pid,
                    "entityId": eid,
                    "name": ent.get("name"),
                    "variant": ent.get("variant") or "",
                    "jobId": stub.get("jobId"),
                    "ageSec": int(age),
                }
            )
        if dirty:
            try:
                store.save(state)
            except Exception as exc:  # noqa: BLE001
                log.warning("recover save failed project=%s: %s", pid, exc)
    log.info(
        "recover_stale_generating recovered=%s skipped_fresh=%s",
        len(recovered),
        skipped_fresh,
    )
    return {"ok": True, "recovered": recovered, "skippedFresh": skipped_fresh}


def _store():
    from pathlib import Path

    from store import ProjectStore

    root = Path(os.environ.get("PROJECTS_ROOT") or "/data/projects")
    return ProjectStore(root)


def _handle_entity_image(payload: dict[str, Any]) -> Any:
    from drama_service import generate_entity_image

    store = _store()
    project_id = str(payload["projectId"])
    entity_id = str(payload["entityId"])
    try:
        return generate_entity_image(
            store,
            project_id,
            entity_id,
            three_view=bool(payload.get("threeView")),
            redraw=bool(payload.get("redraw")),
            force_illustration=bool(payload.get("forceIllustration")),
            wait=True,
        )
    except Exception as exc:  # noqa: BLE001
        st = store.load(project_id)
        if st:
            row = next((e for e in (st.get("entities") or []) if e.get("id") == entity_id), None)
            if row:
                row["imageStatus"] = "failed"
                row["imageError"] = str(exc)[:300]
                row["updatedAt"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                store.save(st)
        raise


def _handle_shot_video(payload: dict[str, Any]) -> Any:
    from drama_service import run_shot_video_job

    return run_shot_video_job(
        _store(),
        str(payload["projectId"]),
        str(payload["shotId"]),
        model=str(payload.get("model") or ""),
        resolution=str(payload.get("resolution") or "720p"),
        backend=str(payload.get("backend") or ""),
        force_entity_qa=bool(payload.get("forceEntityQa")),
        base_prompt=str(payload.get("basePrompt") or ""),
        ratio=str(payload.get("ratio") or "9:16"),
        duration=int(payload.get("duration") or 5),
        ref_path=payload.get("refPath"),
        seedance_task_id=payload.get("seedanceTaskId"),
    )


def _handle_entity_recheck_qa(payload: dict[str, Any]) -> Any:
    from drama_service import recheck_entity_qa

    return recheck_entity_qa(
        _store(),
        str(payload["projectId"]),
        entity_ids=payload.get("entityIds"),
        clear_soft_pass=payload.get("clearSoftPass", True) is not False,
        regenerate_failed=bool(payload.get("regenerateFailed")),
    )


def _handle_fill_stills(payload: dict[str, Any]) -> Any:
    from drama_service import fill_entity_stills

    seg = payload.get("segmentOrder")
    return fill_entity_stills(
        _store(),
        str(payload["projectId"]),
        episode_id=payload.get("episodeId"),
        segment_order=int(seg) if seg is not None else None,
        kinds=payload.get("kinds") or ["character", "scene"],
        entity_ids=payload.get("entityIds"),
        only_missing=payload.get("onlyMissing", True) is not False,
        # Nested generates already enqueue; run fill coordinator inline.
        wait_generate=False,
    )


def queue_stats() -> dict[str, Any]:
    from job_pool import pool_stats

    stats: dict[str, Any] = {"backend": queue_backend(), "pool": pool_stats()}
    r = get_redis()
    if r is not None:
        try:
            stats["redisPending"] = int(r.llen(QUEUE_KEY))
            stats["redisProcessing"] = int(r.llen(PROCESSING_KEY))
        except Exception as exc:  # noqa: BLE001
            stats["redisError"] = str(exc)[:120]
    return stats
