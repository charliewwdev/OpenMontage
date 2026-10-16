"""Bounded thread pool for Studio media jobs (entity stills, heavy QA).

Why not unbounded ``threading.Thread`` / bare ``async``?
- Comfy / Seedream / vision QA are blocking I/O + CPU; unbounded threads
  stampede the GPU and starve FastAPI request handlers (site looks "frozen").
- ``asyncio`` alone does not help unless we offload; a *bounded* pool both
  offloads and rate-limits.

Video generation already uses daemon threads in ``drama_service``; entity
stills historically ran inside the HTTP request — that was the main lag source.
"""

from __future__ import annotations

import os
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, Callable

_LOCK = threading.Lock()
_POOL: ThreadPoolExecutor | None = None
_MAX_WORKERS: int | None = None


def media_max_workers() -> int:
    raw = (os.environ.get("STUDIO_MEDIA_WORKERS") or "").strip()
    if raw.isdigit() and int(raw) > 0:
        return max(1, min(8, int(raw)))
    try:
        from platform_config import load_platform_config

        cfg = load_platform_config() or {}
        n = int((cfg.get("defaults") or {}).get("mediaJobWorkers") or 2)
        return max(1, min(8, n))
    except Exception:
        return 2


def get_media_pool() -> ThreadPoolExecutor:
    global _POOL, _MAX_WORKERS
    with _LOCK:
        want = media_max_workers()
        if _POOL is None or _MAX_WORKERS != want:
            old = _POOL
            _POOL = ThreadPoolExecutor(max_workers=want, thread_name_prefix="studio-media")
            _MAX_WORKERS = want
            if old is not None:
                old.shutdown(wait=False, cancel_futures=False)
        return _POOL


def submit_media(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Future:
    """Submit a blocking media job. Raises if the queue is saturated."""
    pool = get_media_pool()
    # Rough back-pressure: reject when pending work already >> workers.
    # (ThreadPoolExecutor has no public queue size; track via private attrs carefully.)
    try:
        pending = getattr(pool, "_work_queue").qsize()  # type: ignore[attr-defined]
    except Exception:
        pending = 0
    limit = media_max_workers() * 4
    if pending >= limit:
        raise RuntimeError(
            f"出图队列已满（排队 {pending}，上限 {limit}）。请等当前任务完成后再试，"
            "或调大 STUDIO_MEDIA_WORKERS / defaults.mediaJobWorkers。"
        )
    return pool.submit(fn, *args, **kwargs)


def pool_stats() -> dict[str, Any]:
    pool = get_media_pool()
    try:
        pending = getattr(pool, "_work_queue").qsize()  # type: ignore[attr-defined]
    except Exception:
        pending = -1
    return {
        "workers": media_max_workers(),
        "pending": pending,
    }
