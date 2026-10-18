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
# Stills run before videos: a failed reference image makes the clip fail QA.
IMAGE_QUEUE_KEY = os.environ.get("STUDIO_REDIS_IMAGE_QUEUE", f"{QUEUE_KEY}:images")
PROCESSING_KEY = os.environ.get(
    "STUDIO_REDIS_PROCESSING",
    f"{QUEUE_KEY}:processing",
)
IMAGE_JOB_KINDS = frozenset({"entity_image", "entity_recheck_qa", "fill_entity_stills"})
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
        key = IMAGE_QUEUE_KEY if kind in IMAGE_JOB_KINDS else QUEUE_KEY
        r.rpush(key, json.dumps(job, ensure_ascii=False))
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


def _move_to_processing(r: Any, source: str, timeout: int) -> str | None:
    """Pop one job from ``source`` onto the processing list. ``timeout`` 0 is non-blocking."""
    try:
        if timeout <= 0:
            try:
                return r.lmove(source, PROCESSING_KEY, "RIGHT", "LEFT")
            except Exception:
                return r.rpoplpush(source, PROCESSING_KEY)
        try:
            return r.blmove(source, PROCESSING_KEY, timeout, "RIGHT", "LEFT")
        except Exception:
            return r.brpoplpush(source, PROCESSING_KEY, timeout=timeout)
    except Exception as exc:  # noqa: BLE001
        log.warning("reserve from %s failed: %s", source, exc)
        return None


def promote_image_jobs(*, max_items: int = 2000) -> int:
    """Move still jobs sitting on the video queue onto the image queue."""
    r = get_redis()
    if r is None:
        return 0
    moved = 0
    try:
        items = r.lrange(QUEUE_KEY, 0, max(0, int(max_items) - 1)) or []
    except Exception as exc:  # noqa: BLE001
        log.warning("promote_image_jobs list failed: %s", exc)
        return 0
    for raw in items:
        try:
            job = json.loads(raw)
        except Exception:
            continue
        if str(job.get("kind") or "") not in IMAGE_JOB_KINDS:
            continue
        removed = r.lrem(QUEUE_KEY, 1, raw)
        if removed:
            r.rpush(IMAGE_QUEUE_KEY, raw)
            moved += int(removed)
    if moved:
        log.info("promoted %s still job(s) ahead of video", moved)
    return moved


def reserve_job(*, timeout: float = 2.0) -> dict[str, Any] | None:
    """Reserve one job. Prefer stills when light; do not let a still stampede starve video."""
    r = get_redis()
    if r is None:
        return None
    timeout = max(1, int(timeout or 2))
    raw = None
    try:
        try:
            img_n = int(r.llen(IMAGE_QUEUE_KEY) or 0)
            vid_n = int(r.llen(QUEUE_KEY) or 0)
        except Exception:
            img_n, vid_n = 0, 0
        # When videos are waiting behind a huge still backlog, pull video first.
        prefer_video = vid_n > 0 and img_n >= 8
        if prefer_video:
            raw = _move_to_processing(r, QUEUE_KEY, 0)
            if not raw:
                raw = _move_to_processing(r, IMAGE_QUEUE_KEY, timeout)
        else:
            raw = _move_to_processing(r, IMAGE_QUEUE_KEY, 0)
            if not raw:
                raw = _move_to_processing(r, QUEUE_KEY, timeout)
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


def _entity_selected_qa_ok(ent: dict[str, Any] | None) -> bool:
    if not ent or not ent.get("selectedImageId"):
        return False
    img = next(
        (i for i in (ent.get("images") or []) if i.get("id") == ent.get("selectedImageId")),
        None,
    )
    if not img:
        return False
    if img.get("qaPass") is True:
        return True
    qa = img.get("qa") or {}
    return bool(qa.get("skipped"))


def purge_satisfied_entity_image_jobs(*, max_scan: int = 4000) -> dict[str, Any]:
    """Drop queued entity_image jobs whose entity already has a QA-passed still.

    Speeds video without lowering the QA bar — duplicate / retry stills are waste.
    """
    r = get_redis()
    if r is None:
        return {"ok": False, "error": "redis unavailable", "removed": 0}
    store = _store()
    cache: dict[str, dict[str, Any] | None] = {}
    removed = 0
    kept = 0
    scanned = 0
    try:
        items = r.lrange(IMAGE_QUEUE_KEY, 0, max(0, int(max_scan) - 1)) or []
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)[:160], "removed": 0}
    for raw in items:
        scanned += 1
        try:
            job = json.loads(raw)
        except Exception:
            continue
        if str(job.get("kind") or "") != "entity_image":
            kept += 1
            continue
        payload = job.get("payload") or {}
        pid = str(payload.get("projectId") or "")
        eid = str(payload.get("entityId") or "")
        if not pid or not eid:
            kept += 1
            continue
        if pid not in cache:
            try:
                cache[pid] = store.load(pid)
            except Exception:
                cache[pid] = None
        state = cache.get(pid)
        ent = None
        if state:
            ent = next(
                (e for e in (state.get("entities") or []) if e.get("id") == eid and not e.get("deletedAt")),
                None,
            )
        if _entity_selected_qa_ok(ent) and not payload.get("force"):
            try:
                removed += int(r.lrem(IMAGE_QUEUE_KEY, 1, raw) or 0)
            except Exception:
                pass
        else:
            kept += 1
    if removed:
        log.info("purged %s satisfied entity_image job(s); kept≈%s scanned=%s", removed, kept, scanned)
    return {"ok": True, "removed": removed, "kept": kept, "scanned": scanned}


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
            # Already have a QA-passed still — clear sticky lock, do not re-flood the queue.
            if _entity_selected_qa_ok(ent):
                ent["imageStatus"] = "ready"
                ent["imageError"] = None
                ent["updatedAt"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                dirty = True
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
    # Skip no-op retries when a QA-passed still already exists (unless force).
    if not payload.get("force"):
        st0 = store.load(project_id)
        ent0 = next(
            (e for e in ((st0 or {}).get("entities") or []) if e.get("id") == entity_id),
            None,
        )
        if _entity_selected_qa_ok(ent0):
            if ent0.get("imageStatus") == "generating":
                ent0["imageStatus"] = "ready"
                ent0["imageError"] = None
                ent0["updatedAt"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                store.save(st0)
            return {"skipped": True, "reason": "already_qa_passed", "entityId": entity_id}
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


def _defer_video_for_stills(payload: dict[str, Any]) -> str | None:
    """Skip GPU video when referenced stills have not passed QA."""
    from drama_service import EntityQaBlockedError, assert_entity_refs_ready_for_video

    store = _store()
    project_id = str(payload.get("projectId") or "")
    shot_id = str(payload.get("shotId") or "")
    state = store.load(project_id)
    if not state or not shot_id:
        return None
    shot = next((s for s in state.get("shots") or [] if s.get("id") == shot_id), None)
    if not shot or payload.get("forceEntityQa") or payload.get("skipRefs"):
        return None
    try:
        assert_entity_refs_ready_for_video(state, list(shot.get("referenceEntityIds") or []))
    except EntityQaBlockedError as exc:
        reason = "定妆未达标，先出图再出片"
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        seg = shot.get("segmentOrder")
        episode_id = shot.get("episodeId")
        for item in state.get("shots") or []:
            same = item.get("id") == shot_id or (
                seg
                and item.get("episodeId") == episode_id
                and item.get("segmentOrder") == seg
                and item.get("status") == "generating"
            )
            if not same:
                continue
            item["status"] = "pending"
            item["error"] = reason
            item["providerTaskId"] = None
            item["updatedAt"] = now
        store.save(state)
        return f"{reason}: {exc}"
    return None


def _handle_shot_video(payload: dict[str, Any]) -> Any:
    from drama_service import run_shot_video_job

    deferred = _defer_video_for_stills(payload)
    if deferred:
        log.info("defer video shot=%s %s", payload.get("shotId"), deferred[:180])
        return {"deferred": True, "reason": deferred[:240]}
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
        force_refresh_kinds=payload.get("forceRefreshKinds") or [],
        # Nested generates already enqueue; run fill coordinator inline.
        wait_generate=False,
    )


def queue_stats() -> dict[str, Any]:
    from job_pool import pool_stats

    stats: dict[str, Any] = {"backend": queue_backend(), "pool": pool_stats()}
    r = get_redis()
    if r is not None:
        try:
            stats["redisPending"] = int(r.llen(QUEUE_KEY)) + int(r.llen(IMAGE_QUEUE_KEY))
            stats["redisImagePending"] = int(r.llen(IMAGE_QUEUE_KEY))
            stats["redisVideoPending"] = int(r.llen(QUEUE_KEY))
            stats["redisProcessing"] = int(r.llen(PROCESSING_KEY))
        except Exception as exc:  # noqa: BLE001
            stats["redisError"] = str(exc)[:120]
    return stats
