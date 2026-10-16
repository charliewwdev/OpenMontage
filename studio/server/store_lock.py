"""Cross-process project locks for multi-uvicorn / media-worker safety.

Disk ``studio_state.json`` and Postgres RMW both need a mutex spanning
load → mutate → save. In-process RLock + ``fcntl.flock`` covers threads
and multiple worker processes sharing the same volume.
"""

from __future__ import annotations

import fcntl
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

_GUARD = threading.Lock()
_THREAD_LOCKS: dict[str, threading.RLock] = {}


def _thread_lock(project_id: str) -> threading.RLock:
    with _GUARD:
        lock = _THREAD_LOCKS.get(project_id)
        if lock is None:
            lock = threading.RLock()
            _THREAD_LOCKS[project_id] = lock
        return lock


def _lock_path(projects_root: Path, project_id: str) -> Path:
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in (project_id or "unknown"))
    root = Path(projects_root) / ".locks"
    root.mkdir(parents=True, exist_ok=True)
    return root / f"{safe}.lock"


@contextmanager
def project_lock(projects_root: Path, project_id: str) -> Iterator[None]:
    """Exclusive lock for one project (thread + process safe)."""
    tlock = _thread_lock(project_id or "_")
    path = _lock_path(Path(projects_root), project_id or "_")
    with tlock:
        fh = open(path, "a+", encoding="utf-8")
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
            yield
        finally:
            try:
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
            except Exception:
                pass
            fh.close()
