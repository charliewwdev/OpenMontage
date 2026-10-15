"""PostgreSQL persistence for Drama Studio project state, KV, and media blobs.

When DATABASE_URL (or STUDIO_DATABASE_URL) is set:
- studio_state JSON → studio_projects
- secrets / other KV → studio_kv
- images / videos / audio / exports → studio_media (BYTEA)

Disk under PROJECTS_ROOT is a cache; Postgres is the source of truth across
Coolify redeploys (even if drama_projects volume is wiped).
"""

from __future__ import annotations

import json
import logging
import mimetypes
import os
import threading
from contextlib import contextmanager
from typing import Any, Iterator
from urllib.parse import urlparse

logger = logging.getLogger("studio.pg")

_lock = threading.RLock()
_pool = None  # type: ignore[var-annotated]
_enabled: bool | None = None

# Soft cap per object (short-drama clips); override via STUDIO_MEDIA_MAX_BYTES
_DEFAULT_MEDIA_MAX = 250 * 1024 * 1024

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS studio_projects (
    id          TEXT PRIMARY KEY,
    owner_id    TEXT NOT NULL DEFAULT '',
    title       TEXT NOT NULL DEFAULT '',
    state       JSONB NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_studio_projects_owner
    ON studio_projects (owner_id);
CREATE INDEX IF NOT EXISTS idx_studio_projects_updated
    ON studio_projects (updated_at DESC);

CREATE TABLE IF NOT EXISTS studio_kv (
    key         TEXT PRIMARY KEY,
    value       JSONB NOT NULL,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS studio_media (
    project_id    TEXT NOT NULL,
    rel_path      TEXT NOT NULL,
    content_type  TEXT NOT NULL DEFAULT 'application/octet-stream',
    byte_size     BIGINT NOT NULL DEFAULT 0,
    data          BYTEA,
    object_key    TEXT NOT NULL DEFAULT '',
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (project_id, rel_path)
);
CREATE INDEX IF NOT EXISTS idx_studio_media_project
    ON studio_media (project_id);

CREATE TABLE IF NOT EXISTS studio_inspire (
    id            TEXT PRIMARY KEY,
    title         TEXT NOT NULL DEFAULT '',
    prompt        TEXT NOT NULL DEFAULT '',
    description   TEXT NOT NULL DEFAULT '',
    category      TEXT NOT NULL DEFAULT 'style',
    media_type    TEXT NOT NULL DEFAULT 'image',
    content_type  TEXT NOT NULL DEFAULT 'image/jpeg',
    origin_hash   TEXT NOT NULL DEFAULT '',
    byte_size     BIGINT NOT NULL DEFAULT 0,
    data          BYTEA,
    object_key    TEXT NOT NULL DEFAULT '',
    meta          JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_studio_inspire_category
    ON studio_inspire (category);
CREATE INDEX IF NOT EXISTS idx_studio_inspire_origin
    ON studio_inspire (origin_hash);
CREATE INDEX IF NOT EXISTS idx_studio_inspire_updated
    ON studio_inspire (updated_at DESC);
"""


def media_max_bytes() -> int:
    raw = (os.environ.get("STUDIO_MEDIA_MAX_BYTES") or "").strip()
    if raw.isdigit():
        return max(1_000_000, int(raw))
    return _DEFAULT_MEDIA_MAX


def database_url() -> str:
    return (
        (os.environ.get("STUDIO_DATABASE_URL") or "").strip()
        or (os.environ.get("DATABASE_URL") or "").strip()
    )


def enabled() -> bool:
    global _enabled
    if _enabled is None:
        _enabled = bool(database_url())
    return bool(_enabled)


def _connect_kwargs(url: str) -> dict[str, Any]:
    """Parse postgresql:// URL into psycopg2 connect kwargs."""
    # Accept postgres:// and postgresql://
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    parsed = urlparse(url)
    if parsed.scheme not in {"postgresql", "postgres"}:
        raise ValueError(f"unsupported DATABASE_URL scheme: {parsed.scheme}")
    db = (parsed.path or "/").lstrip("/") or "postgres"
    return {
        "host": parsed.hostname or "localhost",
        "port": parsed.port or 5432,
        "dbname": db,
        "user": parsed.username or "postgres",
        "password": parsed.password or "",
        "connect_timeout": 8,
        # Media upserts can be large; allow up to 5 minutes per statement.
        "options": "-c statement_timeout=300000",
    }


def _ensure_pool():
    global _pool
    if _pool is not None:
        return _pool
    url = database_url()
    if not url:
        return None
    try:
        import psycopg2
        from psycopg2 import pool as pg_pool
    except ImportError as exc:
        logger.error("psycopg2 not installed: %s", exc)
        return None
    kwargs = _connect_kwargs(url)
    # Drop empty password key noise
    if not kwargs.get("password"):
        kwargs.pop("password", None)
    _pool = pg_pool.ThreadedConnectionPool(1, 8, **kwargs)
    logger.info(
        "Postgres pool ready host=%s port=%s db=%s user=%s",
        kwargs.get("host"),
        kwargs.get("port"),
        kwargs.get("dbname"),
        kwargs.get("user"),
    )
    return _pool


@contextmanager
def connection() -> Iterator[Any]:
    p = _ensure_pool()
    if p is None:
        raise RuntimeError("postgres not configured")
    conn = p.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        p.putconn(conn)


def init_schema() -> bool:
    """Create tables if needed. Returns True when PG is usable."""
    if not enabled():
        return False
    with _lock:
        try:
            with connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(SCHEMA_SQL)
                    # Existing BYTEA-not-null tables: allow offloading blobs to MinIO.
                    cur.execute("ALTER TABLE studio_media ALTER COLUMN data DROP NOT NULL")
                    cur.execute(
                        "ALTER TABLE studio_media ADD COLUMN IF NOT EXISTS object_key TEXT NOT NULL DEFAULT ''"
                    )
                    cur.execute("ALTER TABLE studio_inspire ALTER COLUMN data DROP NOT NULL")
                    cur.execute(
                        "ALTER TABLE studio_inspire ADD COLUMN IF NOT EXISTS object_key TEXT NOT NULL DEFAULT ''"
                    )
            logger.info("Postgres schema ready")
            return True
        except Exception as exc:
            logger.error("Postgres init_schema failed: %s", exc)
            return False


def ping() -> dict[str, Any]:
    if not enabled():
        return {"enabled": False}
    try:
        with connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
                cur.execute("SELECT COUNT(*) FROM studio_projects")
                projects = int(cur.fetchone()[0])
                cur.execute("SELECT COUNT(*) FROM studio_media")
                media = int(cur.fetchone()[0])
                cur.execute("SELECT COUNT(*) FROM studio_kv")
                kv = int(cur.fetchone()[0])
                cur.execute("SELECT key FROM studio_kv ORDER BY key")
                kv_keys = [str(r[0]) for r in cur.fetchall()]
                inspire = 0
                inspire_bytea = 0
                inspire_object = 0
                media_bytea = 0
                media_object = 0
                try:
                    cur.execute("SELECT COUNT(*) FROM studio_inspire")
                    inspire = int(cur.fetchone()[0])
                    cur.execute(
                        """
                        SELECT
                          COUNT(*) FILTER (WHERE data IS NOT NULL AND octet_length(data) > 0),
                          COUNT(*) FILTER (WHERE COALESCE(object_key, '') <> '')
                        FROM studio_inspire
                        """
                    )
                    inspire_bytea, inspire_object = [int(x or 0) for x in cur.fetchone()]
                    cur.execute(
                        """
                        SELECT
                          COUNT(*) FILTER (WHERE data IS NOT NULL AND octet_length(data) > 0),
                          COUNT(*) FILTER (WHERE COALESCE(object_key, '') <> '')
                        FROM studio_media
                        """
                    )
                    media_bytea, media_object = [int(x or 0) for x in cur.fetchone()]
                except Exception:
                    pass
        return {
            "enabled": True,
            "ok": True,
            "projects": projects,
            "media": media,
            "kv": kv,
            "kvKeys": kv_keys,
            "inspire": inspire,
            "inspireBytea": inspire_bytea,
            "inspireObjectKey": inspire_object,
            "inspirePendingMinio": max(0, inspire_bytea),
            "mediaBytea": media_bytea,
            "mediaObjectKey": media_object,
            "mediaPendingMinio": max(0, media_bytea),
        }
    except Exception as exc:
        return {"enabled": True, "ok": False, "error": str(exc)[:200]}


def upsert_project(state: dict[str, Any]) -> None:
    if not enabled():
        return
    project = state.get("project") or {}
    pid = str(project.get("id") or "").strip()
    if not pid:
        raise ValueError("project.id required")
    owner = str(project.get("ownerId") or "").strip()
    title = str(project.get("title") or pid)
    payload = json.dumps(state, ensure_ascii=False)
    with _lock:
        with connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO studio_projects (id, owner_id, title, state, created_at, updated_at)
                    VALUES (%s, %s, %s, %s::jsonb, NOW(), NOW())
                    ON CONFLICT (id) DO UPDATE SET
                        owner_id = EXCLUDED.owner_id,
                        title = EXCLUDED.title,
                        state = EXCLUDED.state,
                        updated_at = NOW()
                    """,
                    (pid, owner, title, payload),
                )


def load_project(project_id: str) -> dict[str, Any] | None:
    if not enabled() or not project_id:
        return None
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT state FROM studio_projects WHERE id = %s",
                (project_id,),
            )
            row = cur.fetchone()
    if not row:
        return None
    state = row[0]
    if isinstance(state, str):
        return json.loads(state)
    return dict(state)


def delete_project(project_id: str) -> bool:
    if not enabled() or not project_id:
        return False
    with _lock:
        with connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM studio_media WHERE project_id = %s", (project_id,))
                cur.execute("DELETE FROM studio_projects WHERE id = %s", (project_id,))
                return cur.rowcount > 0


def upsert_media(
    project_id: str,
    rel_path: str,
    data: bytes,
    content_type: str | None = None,
) -> None:
    if not enabled() or not project_id or not rel_path:
        return
    if ".." in rel_path.replace("\\", "/").split("/"):
        raise ValueError("invalid media path")
    if len(data) > media_max_bytes():
        raise ValueError(f"media too large ({len(data)} > {media_max_bytes()})")
    ctype = (content_type or mimetypes.guess_type(rel_path)[0] or "application/octet-stream").strip()
    rel_norm = rel_path.replace("\\", "/")
    object_key = ""
    store_blob = data
    try:
        import object_store as _oss

        if _oss.enabled():
            object_key = _oss.media_key(project_id, rel_norm)
            _oss.put_media(project_id, rel_norm, data, ctype)
            store_blob = None  # keep PG row as pointer, not BYTEA
    except Exception as exc:
        logger.warning("minio media put %s/%s failed: %s", project_id, rel_norm, exc)
        object_key = ""
        store_blob = data
    from psycopg2 import Binary

    with _lock:
        with connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO studio_media (project_id, rel_path, content_type, byte_size, data, object_key, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, NOW())
                    ON CONFLICT (project_id, rel_path) DO UPDATE SET
                        content_type = EXCLUDED.content_type,
                        byte_size = EXCLUDED.byte_size,
                        data = EXCLUDED.data,
                        object_key = EXCLUDED.object_key,
                        updated_at = NOW()
                    """,
                    (
                        project_id,
                        rel_norm,
                        ctype,
                        len(data),
                        Binary(store_blob) if store_blob is not None else None,
                        object_key,
                    ),
                )


def load_media(project_id: str, rel_path: str) -> tuple[bytes, str] | None:
    if not enabled() or not project_id or not rel_path:
        return None
    rel_norm = rel_path.replace("\\", "/")
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT data, content_type, object_key FROM studio_media
                WHERE project_id = %s AND rel_path = %s
                """,
                (project_id, rel_norm),
            )
            row = cur.fetchone()
    if not row:
        try:
            import object_store as _oss

            if _oss.enabled():
                return _oss.get_media(project_id, rel_norm)
        except Exception:
            return None
        return None
    data, ctype, object_key = row
    if data is not None:
        if isinstance(data, memoryview):
            data = data.tobytes()
        if data:
            return bytes(data), str(ctype or "application/octet-stream")
    if object_key:
        try:
            import object_store as _oss

            hit = _oss.get_bytes(str(object_key))
            if hit:
                return hit
        except Exception as exc:
            logger.warning("minio media get %s failed: %s", object_key, exc)
    try:
        import object_store as _oss

        if _oss.enabled():
            return _oss.get_media(project_id, rel_norm)
    except Exception:
        return None
    return None


def media_exists(project_id: str, rel_path: str) -> bool:
    if not enabled() or not project_id or not rel_path:
        return False
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1 FROM studio_media
                WHERE project_id = %s AND rel_path = %s LIMIT 1
                """,
                (project_id, rel_path.replace("\\", "/")),
            )
            return cur.fetchone() is not None


def list_media_paths(project_id: str) -> list[str]:
    if not enabled() or not project_id:
        return []
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT rel_path FROM studio_media WHERE project_id = %s ORDER BY rel_path",
                (project_id,),
            )
            return [str(r[0]) for r in cur.fetchall()]


def delete_media(project_id: str, rel_path: str) -> bool:
    if not enabled() or not project_id or not rel_path:
        return False
    with _lock:
        with connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM studio_media WHERE project_id = %s AND rel_path = %s",
                    (project_id, rel_path.replace("\\", "/")),
                )
                return cur.rowcount > 0


def hydrate_media_to_disk(projects_root, project_id: str | None = None) -> int:
    """Restore media blobs from PG onto disk when the local file is missing."""
    from pathlib import Path

    root = Path(projects_root)
    if not enabled():
        return 0
    restored = 0
    with connection() as conn:
        with conn.cursor() as cur:
            if project_id:
                cur.execute(
                    "SELECT project_id, rel_path, data FROM studio_media WHERE project_id = %s",
                    (project_id,),
                )
            else:
                cur.execute("SELECT project_id, rel_path, data FROM studio_media")
            rows = cur.fetchall()
    for pid, rel, data in rows:
        if not pid or not rel or data is None:
            continue
        if ".." in str(rel).replace("\\", "/").split("/"):
            continue
        dest = root / str(pid) / str(rel)
        if dest.is_file() and dest.stat().st_size > 0:
            continue
        try:
            blob = data.tobytes() if isinstance(data, memoryview) else bytes(data)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(blob)
            restored += 1
        except Exception as exc:
            logger.warning("hydrate media %s/%s failed: %s", pid, rel, exc)
    if restored:
        logger.info("Hydrated %d media files from Postgres → %s", restored, root)
    return restored


def migrate_disk_media_to_pg(projects_root, project_id: str | None = None) -> int:
    """Upload local media/* files into PG when missing (or smaller/empty in PG)."""
    from pathlib import Path

    root = Path(projects_root)
    if not enabled() or not root.is_dir():
        return 0
    uploaded = 0
    projects = [root / project_id] if project_id else sorted(root.iterdir())
    for proj in projects:
        if not proj.is_dir() or proj.name.startswith("."):
            continue
        media_root = proj / "media"
        if not media_root.is_dir():
            continue
        pid = proj.name
        for f in media_root.rglob("*"):
            if not f.is_file():
                continue
            rel = f.relative_to(proj).as_posix()
            try:
                if media_exists(pid, rel) and f.stat().st_size > 0:
                    continue
                data = f.read_bytes()
                if not data:
                    continue
                upsert_media(pid, rel, data)
                uploaded += 1
            except Exception as exc:
                logger.warning("migrate media %s/%s failed: %s", pid, rel, exc)
    if uploaded:
        logger.info("Migrated %d media files disk → Postgres", uploaded)
    return uploaded


def list_project_ids() -> list[str]:
    if not enabled():
        return []
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM studio_projects ORDER BY id")
            return [str(r[0]) for r in cur.fetchall()]


def list_project_states() -> list[dict[str, Any]]:
    if not enabled():
        return []
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT state FROM studio_projects ORDER BY updated_at DESC")
            out: list[dict[str, Any]] = []
            for (state,) in cur.fetchall():
                if isinstance(state, str):
                    out.append(json.loads(state))
                else:
                    out.append(dict(state))
            return out


def upsert_kv(key: str, value: Any) -> None:
    if not enabled() or not key:
        return
    payload = json.dumps(value, ensure_ascii=False)
    with _lock:
        with connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO studio_kv (key, value, updated_at)
                    VALUES (%s, %s::jsonb, NOW())
                    ON CONFLICT (key) DO UPDATE SET
                        value = EXCLUDED.value,
                        updated_at = NOW()
                    """,
                    (key, payload),
                )


def load_kv(key: str) -> Any | None:
    if not enabled() or not key:
        return None
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT value FROM studio_kv WHERE key = %s", (key,))
            row = cur.fetchone()
    if not row:
        return None
    val = row[0]
    if isinstance(val, str):
        return json.loads(val)
    return val


def delete_kv(key: str) -> bool:
    if not enabled() or not key:
        return False
    with _lock:
        with connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM studio_kv WHERE key = %s", (key,))
                return cur.rowcount > 0


def list_kv_keys() -> list[str]:
    if not enabled():
        return []
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT key FROM studio_kv ORDER BY key")
            return [str(r[0]) for r in cur.fetchall()]


def _merge_secret_dicts(pg: dict[str, Any] | None, disk: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """PG values win on conflict; disk fills missing / empty keys. Returns (merged, changed)."""
    base = dict(pg) if isinstance(pg, dict) else {}
    changed = False
    for key, val in disk.items():
        if not isinstance(key, str):
            continue
        if val is None:
            continue
        text = str(val).strip() if isinstance(val, str) else val
        if text == "" or text == "********":
            continue
        cur = base.get(key)
        cur_empty = cur is None or (isinstance(cur, str) and not str(cur).strip())
        if cur_empty:
            base[key] = text if isinstance(text, str) else val
            changed = True
    return base, changed or pg is None


def _merge_credits(pg: dict[str, Any] | None, disk: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """Union ledgers / challenges; keep the richer balance and newer updatedAt."""
    if not isinstance(pg, dict) or not pg:
        return dict(disk), True
    out = dict(pg)
    changed = False

    # Ledger by id
    by_id: dict[str, Any] = {}
    for src in (pg.get("ledger") or [], disk.get("ledger") or []):
        if not isinstance(src, list):
            continue
        for entry in src:
            if not isinstance(entry, dict):
                continue
            eid = str(entry.get("id") or "")
            if not eid:
                # Fallback fingerprint
                eid = json.dumps(entry, sort_keys=True, ensure_ascii=False)[:120]
            if eid not in by_id:
                by_id[eid] = entry
                if entry not in (pg.get("ledger") or []):
                    changed = True
    merged_ledger = list(by_id.values())
    merged_ledger.sort(key=lambda e: int(e.get("ts") or 0), reverse=True)
    out["ledger"] = merged_ledger[:500]

    # challengeDone union
    done = dict(pg.get("challengeDone") or {})
    for k, v in dict(disk.get("challengeDone") or {}).items():
        if k not in done:
            done[k] = v
            changed = True
    out["challengeDone"] = done

    # seenRefs union
    seen = set(pg.get("seenRefs") or [])
    before = len(seen)
    seen.update(disk.get("seenRefs") or [])
    if len(seen) != before:
        changed = True
    out["seenRefs"] = sorted(seen)[-200:]

    # Prefer higher counters / newer stamp
    for field in ("balance", "referrals"):
        dv = int(disk.get(field) or 0)
        pv = int(pg.get(field) or 0)
        if dv > pv:
            out[field] = dv
            changed = True
    if not out.get("refCode") and disk.get("refCode"):
        out["refCode"] = disk["refCode"]
        changed = True
    disk_u = int(disk.get("updatedAt") or 0)
    pg_u = int(pg.get("updatedAt") or 0)
    out["updatedAt"] = max(disk_u, pg_u)
    return out, changed


def _event_fp(ev: dict[str, Any]) -> str:
    return "|".join(
        [
            str(ev.get("ts") or ""),
            str(ev.get("provider") or ""),
            str(ev.get("model") or ""),
            str(ev.get("kind") or ""),
            str(ev.get("status") or ""),
            str(ev.get("tokens_in") or ""),
            str(ev.get("tokens_out") or ""),
            str(ev.get("latency_ms") or ""),
            str(ev.get("ok") or ""),
        ]
    )


def _merge_usage(pg: dict[str, Any] | None, disk_events: list[dict[str, Any]]) -> tuple[dict[str, Any], bool]:
    existing = list((pg or {}).get("events") or []) if isinstance(pg, dict) else []
    by_fp: dict[str, dict[str, Any]] = {}
    for ev in existing + disk_events:
        if not isinstance(ev, dict):
            continue
        by_fp[_event_fp(ev)] = ev
    merged = list(by_fp.values())
    merged.sort(key=lambda e: str(e.get("ts") or ""))
    capped = merged[-8000:]
    changed = len(capped) != len(existing) or pg is None
    updated = capped[-1].get("ts") if capped else ""
    return {"events": capped, "updatedAt": updated}, changed


def _merge_items_by_id(pg_items: list[Any], disk_items: list[Any], id_keys: tuple[str, ...] = ("id",)) -> tuple[list[Any], bool]:
    by_id: dict[str, Any] = {}
    order: list[str] = []

    def _id_of(item: dict[str, Any]) -> str:
        for k in id_keys:
            v = item.get(k)
            if v:
                return str(v)
        return json.dumps(item, sort_keys=True, ensure_ascii=False)[:160]

    for src in (pg_items, disk_items):
        for item in src or []:
            if not isinstance(item, dict):
                continue
            eid = _id_of(item)
            if eid not in by_id:
                order.append(eid)
            # Prefer whichever already in map if from PG first pass; disk can fill missing fields
            if eid not in by_id:
                by_id[eid] = dict(item)
            else:
                cur = dict(by_id[eid])
                for k, v in item.items():
                    if k not in cur or cur.get(k) in (None, "", [], {}):
                        cur[k] = v
                by_id[eid] = cur
    merged = [by_id[i] for i in order]
    changed = len(merged) != len(pg_items or [])
    return merged, changed


def migrate_disk_state_to_pg(projects_root) -> dict[str, int]:
    """Merge all known Drama Studio JSON/jsonl state from disk into studio_kv.

    Never skips disk history just because a PG row already exists — missing keys /
    ledger rows / usage events are unioned in. PG non-empty scalar values win on
    conflict for secrets.
    """
    from pathlib import Path

    root = Path(projects_root)
    stats = {
        "secrets": 0,
        "credits": 0,
        "prompts": 0,
        "usage": 0,
        "communitySkills": 0,
        "platformConfig": 0,
        "merged": 0,
        "created": 0,
        "unchanged": 0,
    }
    if not enabled() or not root.is_dir():
        return stats

    def _commit(key: str, value: Any, *, created: bool, bucket: str) -> None:
        upsert_kv(key, value)
        stats[bucket] += 1
        stats["created" if created else "merged"] += 1

    def _migrate_secrets_file(path: Path, key: str) -> None:
        if not path.is_file():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("migrate secrets read failed %s: %s", path, exc)
            return
        if not isinstance(data, dict) or not data:
            return
        existing = load_kv(key)
        merged, changed = _merge_secret_dicts(existing if isinstance(existing, dict) else None, data)
        if not changed:
            stats["unchanged"] += 1
            return
        _commit(key, merged, created=existing is None, bucket="secrets")

    def _migrate_credits_file(path: Path, key: str) -> None:
        if not path.is_file():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("migrate credits read failed %s: %s", path, exc)
            return
        if not isinstance(data, dict) or not data:
            return
        existing = load_kv(key)
        merged, changed = _merge_credits(existing if isinstance(existing, dict) else None, data)
        if not changed:
            stats["unchanged"] += 1
            return
        _commit(key, merged, created=existing is None, bucket="credits")

    # Shared + per-user secrets / credits
    _migrate_secrets_file(root / ".studio_secrets.json", "secrets:.studio_secrets.json")
    _migrate_credits_file(root / ".studio_credits.json", "credits:.studio_credits.json")
    users = root / ".users"
    if users.is_dir():
        for user_dir in users.iterdir():
            if not user_dir.is_dir():
                continue
            _migrate_secrets_file(
                user_dir / "secrets.json",
                f"secrets:.users/{user_dir.name}/secrets.json",
            )
            _migrate_credits_file(user_dir / "credits.json", f"credits:user:{user_dir.name}")

    prompts = root / "_library" / "prompts.json"
    if prompts.is_file():
        try:
            data = json.loads(prompts.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                existing = load_kv("prompts:_library")
                pg_items = []
                if isinstance(existing, dict):
                    pg_items = list(existing.get("items") or [])
                disk_items = list(data.get("items") or [])
                merged_items, changed = _merge_items_by_id(pg_items, disk_items, id_keys=("id", "text"))
                if changed or existing is None:
                    payload = dict(data)
                    payload["items"] = merged_items
                    _commit(
                        "prompts:_library",
                        payload,
                        created=existing is None,
                        bucket="prompts",
                    )
                else:
                    stats["unchanged"] += 1
        except Exception as exc:
            logger.warning("migrate prompts failed: %s", exc)

    usage = root / ".studio_usage.jsonl"
    if usage.is_file() and usage.stat().st_size > 0:
        try:
            events: list[dict[str, Any]] = []
            for line in usage.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                except Exception:
                    continue
                if isinstance(ev, dict):
                    events.append(ev)
            if events:
                existing = load_kv("usage:.studio_usage")
                merged, changed = _merge_usage(
                    existing if isinstance(existing, dict) else None,
                    events,
                )
                if changed:
                    _commit(
                        "usage:.studio_usage",
                        merged,
                        created=existing is None,
                        bucket="usage",
                    )
                else:
                    stats["unchanged"] += 1
        except Exception as exc:
            logger.warning("migrate usage failed: %s", exc)

    community = root / ".community_skills.json"
    if community.is_file():
        try:
            data = json.loads(community.read_text(encoding="utf-8"))
            if isinstance(data, list):
                existing = load_kv("skills:community")
                pg_items = list((existing or {}).get("items") or []) if isinstance(existing, dict) else []
                merged_items, changed = _merge_items_by_id(pg_items, data, id_keys=("id",))
                if changed or existing is None:
                    _commit(
                        "skills:community",
                        {"items": merged_items},
                        created=existing is None,
                        bucket="communitySkills",
                    )
                else:
                    stats["unchanged"] += 1
        except Exception as exc:
            logger.warning("migrate community skills failed: %s", exc)

    # platform.yaml: always refresh from image so deploys win (not historical user data).
    try:
        from platform_config import _resolve_path

        cfg_path = _resolve_path()
        if cfg_path.is_file():
            import yaml

            cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
            if isinstance(cfg, dict):
                upsert_kv(
                    "config:platform",
                    {"source": str(cfg_path), "updatedAt": int(__import__("time").time()), "data": cfg},
                )
                stats["platformConfig"] += 1
    except Exception as exc:
        logger.warning("migrate platform config failed: %s", exc)

    logger.info("migrate_disk_state_to_pg %s", stats)
    return stats


def hydrate_projects_to_disk(projects_root) -> list[str]:
    """Ensure media cache dirs exist for PG projects.

    Does **not** write studio_state.json — project state lives only in Postgres
    when DATABASE_URL is set.
    """
    from pathlib import Path

    root = Path(projects_root)
    root.mkdir(parents=True, exist_ok=True)
    if not enabled():
        return []
    restored: list[str] = []
    try:
        states = list_project_states()
    except Exception as exc:
        logger.error("hydrate list failed: %s", exc)
        return []
    for state in states:
        project = state.get("project") or {}
        pid = str(project.get("id") or "").strip()
        if not pid or "/" in pid or "\\" in pid or pid.startswith("."):
            continue
        dest = root / pid
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "media" / "images").mkdir(parents=True, exist_ok=True)
        (dest / "media" / "videos").mkdir(parents=True, exist_ok=True)
        (dest / "media" / "exports").mkdir(parents=True, exist_ok=True)
        restored.append(pid)
    if restored:
        logger.info("Ensured media dirs for %d PG projects under %s (no studio_state.json)", len(restored), root)
    return restored


def migrate_disk_projects_to_pg(projects_root) -> list[str]:
    """One-way sync: local studio_state.json → PG when row missing or older."""
    from pathlib import Path

    root = Path(projects_root)
    if not enabled() or not root.is_dir():
        return []
    migrated: list[str] = []
    for path in sorted(root.iterdir()):
        if not path.is_dir() or path.name.startswith("."):
            continue
        studio = path / "studio_state.json"
        if not studio.is_file():
            continue
        try:
            state = json.loads(studio.read_text(encoding="utf-8"))
        except Exception:
            continue
        pid = str((state.get("project") or {}).get("id") or path.name)
        try:
            existing = load_project(pid)
            if existing:
                # Prefer disk if it looks newer
                disk_u = str((state.get("project") or {}).get("updatedAt") or "")
                pg_u = str((existing.get("project") or {}).get("updatedAt") or "")
                if pg_u and disk_u and pg_u >= disk_u:
                    continue
            upsert_project(state)
            migrated.append(pid)
        except Exception as exc:
            logger.warning("migrate %s failed: %s", pid, exc)
    if migrated:
        logger.info("Migrated %d projects disk → Postgres", len(migrated))
    return migrated


def upsert_inspire(
    item_id: str,
    *,
    title: str = "",
    prompt: str = "",
    description: str = "",
    category: str = "style",
    media_type: str = "image",
    content_type: str = "image/jpeg",
    origin_hash: str = "",
    data: bytes,
    meta: dict[str, Any] | None = None,
) -> None:
    if not enabled() or not item_id or not data:
        return
    if len(data) > media_max_bytes():
        raise ValueError(f"inspire media too large ({len(data)} > {media_max_bytes()})")
    from psycopg2 import Binary

    object_key = ""
    store_blob = data
    try:
        import object_store as _oss

        if _oss.enabled():
            object_key = _oss.inspire_key(item_id)
            _oss.put_inspire(item_id, data, content_type or "image/jpeg")
            store_blob = None
    except Exception as exc:
        logger.warning("minio inspire put %s failed: %s", item_id, exc)
        object_key = ""
        store_blob = data
    payload = json.dumps(meta or {}, ensure_ascii=False)
    with _lock:
        with connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO studio_inspire (
                        id, title, prompt, description, category, media_type,
                        content_type, origin_hash, byte_size, data, object_key, meta, updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, NOW())
                    ON CONFLICT (id) DO UPDATE SET
                        title = EXCLUDED.title,
                        prompt = EXCLUDED.prompt,
                        description = EXCLUDED.description,
                        category = EXCLUDED.category,
                        media_type = EXCLUDED.media_type,
                        content_type = EXCLUDED.content_type,
                        origin_hash = EXCLUDED.origin_hash,
                        byte_size = EXCLUDED.byte_size,
                        data = EXCLUDED.data,
                        object_key = EXCLUDED.object_key,
                        meta = EXCLUDED.meta,
                        updated_at = NOW()
                    """,
                    (
                        item_id,
                        title or "",
                        prompt or "",
                        description or "",
                        category or "style",
                        media_type or "image",
                        content_type or "image/jpeg",
                        origin_hash or "",
                        len(data),
                        Binary(store_blob) if store_blob is not None else None,
                        object_key,
                        payload,
                    ),
                )


def inspire_exists(item_id: str) -> bool:
    if not enabled() or not item_id:
        return False
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM studio_inspire WHERE id = %s LIMIT 1", (item_id,))
            return cur.fetchone() is not None


def load_inspire_blob(item_id: str) -> tuple[bytes, str] | None:
    if not enabled() or not item_id:
        return None
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT data, content_type, object_key FROM studio_inspire WHERE id = %s",
                (item_id,),
            )
            row = cur.fetchone()
    if not row:
        try:
            import object_store as _oss

            if _oss.enabled():
                return _oss.get_inspire(item_id)
        except Exception:
            return None
        return None
    data, ctype, object_key = row
    if data is not None:
        if isinstance(data, memoryview):
            data = data.tobytes()
        if data:
            return bytes(data), str(ctype or "image/jpeg")
    if object_key:
        try:
            import object_store as _oss

            hit = _oss.get_bytes(str(object_key))
            if hit:
                return hit
        except Exception as exc:
            logger.warning("minio inspire get %s failed: %s", object_key, exc)
    try:
        import object_store as _oss

        if _oss.enabled():
            return _oss.get_inspire(item_id)
    except Exception:
        return None
    return None


def list_inspire_meta(
    *,
    category: str = "all",
    media_type: str = "all",
    q: str = "",
    limit: int = 48,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    """Return (rows without BYTEA, total_count)."""
    if not enabled():
        return [], 0
    clauses: list[str] = []
    args: list[Any] = []
    cat = (category or "all").strip().lower()
    if cat and cat not in ("all", "全部", "*"):
        clauses.append("LOWER(category) = %s")
        args.append(cat)
    media = (media_type or "all").strip().lower()
    if media and media not in ("all", "全部", "*"):
        clauses.append("LOWER(media_type) = %s")
        args.append(media)
    query = (q or "").strip()
    if query:
        like = f"%{query}%"
        clauses.append("(title ILIKE %s OR prompt ILIKE %s OR description ILIKE %s)")
        args.extend([like, like, like])
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    page_size = max(1, min(int(limit or 48), 120))
    start = max(0, int(offset or 0))
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM studio_inspire{where}", args)
            total = int(cur.fetchone()[0])
            cur.execute(
                f"""
                SELECT id, title, prompt, description, category, media_type, content_type, byte_size, meta
                FROM studio_inspire
                {where}
                ORDER BY updated_at DESC
                LIMIT %s OFFSET %s
                """,
                [*args, page_size, start],
            )
            rows = cur.fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        meta = row[8] if len(row) > 8 else {}
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except Exception:
                meta = {}
        out.append(
            {
                "id": str(row[0]),
                "title": str(row[1] or ""),
                "prompt": str(row[2] or ""),
                "description": str(row[3] or ""),
                "category": str(row[4] or "style"),
                "mediaType": str(row[5] or "image"),
                "contentType": str(row[6] or "image/jpeg"),
                "byteSize": int(row[7] or 0),
                "meta": dict(meta or {}),
            }
        )
    return out, total


def inspire_count() -> int:
    if not enabled():
        return 0
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM studio_inspire")
            return int(cur.fetchone()[0])


def offload_blobs_to_minio(*, limit: int = 80) -> dict[str, int]:
    """Move existing BYTEA rows to MinIO and null out Postgres payloads."""
    stats = {"inspire": 0, "media": 0, "errors": 0}
    try:
        import object_store as _oss
    except Exception:
        return stats
    if not enabled() or not _oss.enabled():
        return stats

    def _as_bytes(data: Any) -> bytes:
        if data is None:
            return b""
        if isinstance(data, memoryview):
            data = data.tobytes()
        return bytes(data)

    try:
        with connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, data, content_type FROM studio_inspire
                    WHERE data IS NOT NULL AND octet_length(data) > 0
                    ORDER BY updated_at DESC
                    LIMIT %s
                    """,
                    (limit,),
                )
                rows = cur.fetchall()
        for iid, data, ctype in rows:
            blob = _as_bytes(data)
            if not blob:
                continue
            try:
                key = _oss.inspire_key(str(iid))
                _oss.put_inspire(str(iid), blob, str(ctype or "image/jpeg"))
                with connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            "UPDATE studio_inspire SET data = NULL, object_key = %s, updated_at = NOW() WHERE id = %s",
                            (key, str(iid)),
                        )
                stats["inspire"] += 1
            except Exception as exc:
                stats["errors"] += 1
                logger.warning("offload inspire %s failed: %s", iid, exc)

        with connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT project_id, rel_path, data, content_type FROM studio_media
                    WHERE data IS NOT NULL AND octet_length(data) > 0
                    ORDER BY updated_at DESC
                    LIMIT %s
                    """,
                    (limit,),
                )
                rows = cur.fetchall()
        for pid, rel, data, ctype in rows:
            blob = _as_bytes(data)
            if not blob:
                continue
            try:
                key = _oss.media_key(str(pid), str(rel))
                _oss.put_media(str(pid), str(rel), blob, str(ctype or "application/octet-stream"))
                with connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            UPDATE studio_media SET data = NULL, object_key = %s, updated_at = NOW()
                            WHERE project_id = %s AND rel_path = %s
                            """,
                            (key, str(pid), str(rel)),
                        )
                stats["media"] += 1
            except Exception as exc:
                stats["errors"] += 1
                logger.warning("offload media %s/%s failed: %s", pid, rel, exc)
    except Exception as exc:
        logger.warning("offload_blobs_to_minio failed: %s", exc)
    return stats
