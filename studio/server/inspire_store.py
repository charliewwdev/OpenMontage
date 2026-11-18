"""Localize inspiration media into Postgres (preferred) or disk cache.

Public API never exposes remote pinimg / pinterest URLs — only
``/api/inspire/media/{id}`` served from studio_inspire / disk.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
from pathlib import Path
from typing import Any

logger = logging.getLogger("studio.inspire")

_disk_lock = threading.RLock()
_ingest_lock = threading.Lock()


_BLOCKLIST_PATH = Path(__file__).resolve().parents[1] / "config" / "inspire_blocklist.json"
_blocklist_cache: dict[str, Any] | None = None


def blocklist() -> dict[str, Any]:
    """Removed advertising pins (ids / boards / paid-social link markers)."""
    global _blocklist_cache
    if _blocklist_cache is None:
        data: dict[str, Any] = {}
        try:
            loaded = json.loads(_BLOCKLIST_PATH.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                data = loaded
        except Exception:
            data = {}
        _blocklist_cache = {
            "ids": {str(x) for x in data.get("ids") or [] if str(x).strip()},
            "boards": {str(x).strip().lower() for x in data.get("boards") or [] if str(x).strip()},
            "linkPatterns": [str(x).lower() for x in data.get("linkPatterns") or [] if str(x).strip()],
        }
    return _blocklist_cache


def is_blocked(item: dict[str, Any] | None = None, *, item_id: str = "") -> bool:
    bl = blocklist()
    iid = str(item_id or (item or {}).get("id") or "").strip()
    if iid and iid in bl["ids"]:
        return True
    if not item:
        return False
    meta = item.get("meta") if isinstance(item.get("meta"), dict) else {}
    board = str(item.get("board") or meta.get("board") or "").strip().lower()
    if board and board in bl["boards"]:
        return True
    link = str(item.get("link") or "").lower()
    return bool(link) and any(p in link for p in bl["linkPatterns"])


def _projects_root() -> Path:
    return Path(os.environ.get("PROJECTS_ROOT") or "/data/projects").expanduser()


def _disk_dir() -> Path:
    root = _projects_root() / ".inspire"
    root.mkdir(parents=True, exist_ok=True)
    return root


def item_id_for_url(url: str) -> str:
    raw = (url or "").strip()
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:24] if raw else ""


def public_media_url(item_id: str) -> str:
    return f"/api/inspire/media/{item_id}"


def _disk_paths(item_id: str) -> tuple[Path, Path]:
    base = _disk_dir() / item_id
    return base.with_suffix(".bin"), base.with_suffix(".json")


def exists(item_id: str) -> bool:
    if not item_id:
        return False
    try:
        import pg_backend as pg

        if pg.enabled() and pg.inspire_exists(item_id):
            return True
    except Exception:
        pass
    try:
        import object_store as oss

        if oss.enabled() and oss.exists(oss.inspire_key(item_id)):
            return True
    except Exception:
        pass
    blob, meta = _disk_paths(item_id)
    return blob.is_file() and blob.stat().st_size > 0 and meta.is_file()


def load_blob(item_id: str) -> tuple[bytes, str] | None:
    if not item_id or is_blocked(item_id=item_id):
        return None
    try:
        import pg_backend as pg

        if pg.enabled():
            hit = pg.load_inspire_blob(item_id)
            if hit:
                return hit
    except Exception as exc:
        logger.warning("inspire pg load failed id=%s: %s", item_id, exc)
    try:
        import object_store as oss

        if oss.enabled():
            hit = oss.get_inspire(item_id)
            if hit:
                return hit
    except Exception as exc:
        logger.warning("inspire minio load failed id=%s: %s", item_id, exc)
    blob_path, meta_path = _disk_paths(item_id)
    if not blob_path.is_file():
        return None
    ctype = "image/jpeg"
    if meta_path.is_file():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            ctype = str(meta.get("contentType") or ctype)
        except Exception:
            pass
    data = blob_path.read_bytes()
    return (data, ctype) if data else None


def upsert_local(
    item_id: str,
    data: bytes,
    *,
    content_type: str = "image/jpeg",
    title: str = "",
    prompt: str = "",
    description: str = "",
    category: str = "style",
    media_type: str = "image",
    origin_hash: str = "",
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not item_id or not data:
        raise ValueError("inspire id/data required")
    record = {
        "id": item_id,
        "title": title or "",
        "prompt": prompt or "",
        "description": description or "",
        "category": category or "style",
        "mediaType": media_type or "image",
        "contentType": content_type or "image/jpeg",
        "byteSize": len(data),
        "imageUrl": public_media_url(item_id),
        "originHash": origin_hash or "",
        "meta": meta or {},
    }
    try:
        import pg_backend as pg

        if pg.enabled():
            pg.upsert_inspire(
                item_id,
                title=record["title"],
                prompt=record["prompt"],
                description=record["description"],
                category=record["category"],
                media_type=record["mediaType"],
                content_type=record["contentType"],
                origin_hash=record["originHash"],
                data=data,
                meta=record["meta"],
            )
    except Exception as exc:
        logger.warning("inspire pg upsert failed id=%s: %s", item_id, exc)

    blob_path, meta_path = _disk_paths(item_id)
    with _disk_lock:
        blob_path.write_bytes(data)
        meta_path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
    return record


def list_local(
    *,
    category: str = "all",
    media_type: str = "all",
    q: str = "",
    limit: int = 48,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    try:
        import pg_backend as pg

        if pg.enabled() and pg.inspire_count() > 0:
            bl = blocklist()
            rows, total = pg.list_inspire_meta(
                category=category,
                media_type=media_type,
                q=q,
                limit=limit,
                offset=offset,
                exclude_ids=sorted(bl["ids"]),
                exclude_boards=sorted(bl["boards"]),
            )
            for row in rows:
                row["imageUrl"] = public_media_url(str(row["id"]))
                row.pop("link", None)
                row.pop("originUrl", None)
            return rows, total
    except Exception as exc:
        logger.warning("inspire pg list failed: %s", exc)

    # Disk fallback index
    items: list[dict[str, Any]] = []
    root = _disk_dir()
    for meta_path in sorted(root.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            row = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        iid = str(row.get("id") or meta_path.stem)
        blob, _ = _disk_paths(iid)
        if not blob.is_file():
            continue
        row["id"] = iid
        if is_blocked(row):
            continue
        row["imageUrl"] = public_media_url(iid)
        row.pop("link", None)
        row.pop("originUrl", None)
        items.append(row)

    cat = (category or "all").strip().lower()
    if cat and cat not in ("all", "全部", "*"):
        items = [x for x in items if str(x.get("category") or "").lower() == cat]
    media = (media_type or "all").strip().lower()
    if media and media not in ("all", "全部", "*"):
        items = [x for x in items if str(x.get("mediaType") or "image").lower() == media]
    query = (q or "").strip().lower()
    if query:
        items = [
            x
            for x in items
            if query in str(x.get("prompt") or "").lower()
            or query in str(x.get("title") or "").lower()
            or query in str(x.get("description") or "").lower()
        ]
    total = len(items)
    page_size = max(1, min(int(limit or 48), 120))
    start = max(0, int(offset or 0))
    return items[start : start + page_size], total


def count_local() -> int:
    try:
        import pg_backend as pg

        if pg.enabled():
            n = pg.inspire_count()
            if n:
                return n
    except Exception:
        pass
    return sum(1 for p in _disk_dir().glob("*.bin") if p.stat().st_size > 0)


def ingest_remote_item(item: dict[str, Any], fetch_bytes) -> dict[str, Any] | None:
    """Download remote image once, persist, return public-safe record."""
    if is_blocked(item):
        return None
    origin = str(item.get("originUrl") or item.get("imageUrl") or "").strip()
    if origin.startswith("/api/inspire/"):
        # Already local
        iid = origin.rsplit("/", 1)[-1].split("?", 1)[0]
        if exists(iid):
            return {
                "id": iid,
                "title": item.get("title") or "",
                "prompt": item.get("prompt") or "",
                "description": item.get("description") or "",
                "category": item.get("category") or "style",
                "mediaType": item.get("mediaType") or "image",
                "imageUrl": public_media_url(iid),
            }
        return None
    if not origin.startswith("https://"):
        return None
    iid = str(item.get("id") or "").strip() or item_id_for_url(origin)
    if exists(iid):
        return {
            "id": iid,
            "title": item.get("title") or "",
            "prompt": item.get("prompt") or "",
            "description": item.get("description") or "",
            "category": item.get("category") or "style",
            "mediaType": item.get("mediaType") or "image",
            "imageUrl": public_media_url(iid),
        }
    try:
        blob, ctype = fetch_bytes(origin)
    except Exception as exc:
        logger.info("inspire ingest skip %s: %s", origin[:80], exc)
        return None
    if not blob:
        return None
    return upsert_local(
        iid,
        blob,
        content_type=ctype or "image/jpeg",
        title=str(item.get("title") or ""),
        prompt=str(item.get("prompt") or ""),
        description=str(item.get("description") or ""),
        category=str(item.get("category") or "style"),
        media_type=str(item.get("mediaType") or "image"),
        origin_hash=item_id_for_url(origin),
        meta={"board": item.get("board") or "", "source": item.get("source") or "seed"},
    )


def ingest_many(items: list[dict[str, Any]], fetch_bytes, *, max_items: int = 96) -> int:
    """Best-effort batch ingest; returns number newly stored."""
    if not items:
        return 0
    if not _ingest_lock.acquire(blocking=False):
        return 0
    stored = 0
    try:
        for item in items[: max(1, max_items)]:
            origin = str(item.get("originUrl") or item.get("imageUrl") or "")
            iid = str(item.get("id") or "").strip() or item_id_for_url(origin)
            if exists(iid):
                continue
            if ingest_remote_item(item, fetch_bytes):
                stored += 1
    finally:
        _ingest_lock.release()
    return stored
