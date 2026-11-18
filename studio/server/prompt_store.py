"""Per-user saved prompts (我的提示词).

Every saved prompt belongs to exactly one owner:

* a logged-in account → its user id (DTok id, ``gh-<id>`` GitHub session, …)
* ``_local`` → the anonymous single user of an instance running with
  ``STUDIO_AUTH_REQUIRED=false``

Nobody else can list, read, update or delete it: every query is scoped by
owner, ids are random (uuid4) and an id from another owner simply does not
exist for you (404).

Who may write:

* anonymous visitors on a login-required instance: read-only empty list
  (``readOnlyReason = "login"``), writes → 401
* the shared demo account (``demo: true`` on the session; every demo visitor
  has the same user id) is read-only by default (``readOnlyReason =
  "shared_demo"``), writes → 403. Set ``STUDIO_DEMO_SAVE_PROMPTS=1`` on a
  private single-user install where the demo login is just "me".

Storage backends (chosen like the rest of the studio):

* Postgres (``DATABASE_URL`` / ``STUDIO_DATABASE_URL``): table
  ``studio_prompts``; schema created/migrated idempotently on first use.
* Disk: ``PROJECTS_ROOT/.users/<owner>/prompts.json`` written atomically
  (temp file + ``os.replace``) under a per-file lock (thread lock + ``flock``).

Legacy: before per-user storage there was one shared list (studio_kv
``prompts:_library`` or ``PROJECTS_ROOT/_library/prompts.json``). It is never
modified or deleted. In Postgres it is imported once as owner-less rows
(``owner_id IS NULL``) that no user can see. ``studio/scripts/prompts_admin.py``
lists them and copies them to an account; ``STUDIO_LEGACY_PROMPTS_OWNER`` does
the same automatically for one account on first use (and ``_local`` adopts
them automatically when login is disabled, so single-user installs keep their
prompts).

Logging never includes prompt titles or bodies; owners are logged as a short
hash.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import threading
import time
import uuid
from collections import deque
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

try:  # POSIX advisory locks; Windows falls back to the in-process lock only.
    import fcntl  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover
    fcntl = None  # type: ignore[assignment]

logger = logging.getLogger("studio.prompts")

LOCAL_OWNER = "_local"
LEGACY_KV_KEY = "prompts:_library"
LEGACY_OWNER_ENV = "STUDIO_LEGACY_PROMPTS_OWNER"
CATEGORIES = (
    "general",
    "style",
    "composition",
    "lighting",
    "character",
    "scene",
    "camera",
    "quality",
    "audio",
    "text",
    "template",
)
ORIGIN_KEYS = ("source", "sourceUrl", "license", "licenseUrl", "attribution")
_OWNER_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9._:@-]{0,127}$")
_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
# Hard backstops; the configurable limits below are clamped to these.
DB_TEXT_MAX = 20000
DB_TITLE_MAX = 300
MAX_BODY_BYTES = 64 * 1024
LIST_DEFAULT_LIMIT = 60
LIST_MAX_LIMIT = 200


def _env_int(name: str, default: int, lo: int, hi: int) -> int:
    try:
        val = int(str(os.environ.get(name, "")).strip() or default)
    except ValueError:
        val = default
    return max(lo, min(hi, val))


def _env_flag(name: str, default: bool = False) -> bool:
    raw = str(os.environ.get(name, "")).strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "on")


def limits() -> dict[str, int]:
    return {
        "titleMax": _env_int("STUDIO_PROMPT_TITLE_MAX", 120, 10, DB_TITLE_MAX),
        "textMax": _env_int("STUDIO_PROMPT_TEXT_MAX", 8000, 100, DB_TEXT_MAX),
        "maxPerUser": _env_int("STUDIO_PROMPTS_MAX_PER_USER", 500, 1, 100000),
    }


def _rate_config() -> tuple[int, float]:
    raw = str(os.environ.get("STUDIO_PROMPTS_RATE_LIMIT", "") or "30/60").strip()
    try:
        count, window = raw.split("/", 1)
        return max(1, int(count)), max(1.0, float(window))
    except ValueError:
        return 30, 60.0


# --------------------------------------------------------------------- errors


class PromptError(Exception):
    """User-facing error. ``key`` is a ui_messages key (zh/en)."""

    def __init__(self, status: int, code: str, key: str | None = None, **params: Any):
        super().__init__(code)
        self.status = status
        self.code = code
        self.key = key or code
        self.params = params

    def message(self) -> str:
        try:
            from ui_messages import ui_msg

            return ui_msg(self.key, **self.params)
        except Exception:  # noqa: BLE001
            return self.code

    def payload(self) -> dict[str, Any]:
        out: dict[str, Any] = {"error": self.message(), "code": self.code}
        out.update({k: v for k, v in self.params.items() if isinstance(v, (int, str))})
        return out


def http_exception(exc: PromptError):
    """FastAPI HTTPException for a PromptError (JSON body + Retry-After on 429)."""
    from fastapi import HTTPException

    retry = exc.params.get("retryAfter")
    headers = {"Retry-After": str(retry)} if retry is not None else None
    return HTTPException(status_code=exc.status, detail=exc.payload(), headers=headers)


def _owner_tag(owner: str | None) -> str:
    if not owner:
        return "-"
    return hashlib.sha256(owner.encode("utf-8")).hexdigest()[:10]


# -------------------------------------------------------------------- identity


@dataclass(frozen=True)
class Access:
    owner: str | None  # None → nothing to read or write
    reason: str | None = None  # "login" | "shared_demo" when read-only


def auth_required() -> bool:
    return os.environ.get("STUDIO_AUTH_REQUIRED", "true").strip().lower() not in ("0", "false", "no", "off")


def safe_owner(uid: str | None) -> str:
    uid = (uid or "").strip()
    if not uid or uid in (".", "..") or not _OWNER_RE.match(uid):
        return ""
    return uid


def current_access() -> Access:
    import auth_context

    uid = safe_owner(auth_context.current_user_id())
    user = auth_context.get_current_user() or {}
    if uid:
        if user.get("demo") and not _env_flag("STUDIO_DEMO_SAVE_PROMPTS"):
            return Access(None, "shared_demo")
        return Access(uid)
    if user:
        # Logged in but the id is unusable as a storage key: treat as anonymous.
        return Access(None, "login")
    if not auth_required():
        return Access(LOCAL_OWNER)
    return Access(None, "login")


def _require_owner(access: Access) -> str:
    if access.owner:
        return access.owner
    if access.reason == "shared_demo":
        raise PromptError(403, "prompts_shared_demo")
    raise PromptError(401, "prompts_login_required")


# ---------------------------------------------------------------- rate limits


class _RateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def check(self, key: str) -> None:
        count, window = _rate_config()
        now = time.monotonic()
        with self._lock:
            q = self._hits.setdefault(key, deque())
            while q and now - q[0] > window:
                q.popleft()
            if len(q) >= count:
                retry = max(1, int(window - (now - q[0])) + 1)
                raise PromptError(429, "prompts_rate_limited", retryAfter=retry)
            q.append(now)
            if len(self._hits) > 10000:  # bound memory under abuse
                for k in [k for k, v in self._hits.items() if not v or now - v[-1] > window][:5000]:
                    self._hits.pop(k, None)

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


rate_limiter = _RateLimiter()


# ------------------------------------------------------------------ validation


def sanitize_origin(raw: Any) -> dict[str, str] | None:
    if not isinstance(raw, dict):
        return None
    library_id = str(raw.get("libraryId") or "").strip()[:120]
    if not library_id:
        return None
    out = {"libraryId": library_id}
    for key in ORIGIN_KEYS:
        val = str(raw.get(key) or "").strip()
        if val:
            out[key] = val[:500]
    return out


def validate_input(body: Any) -> dict[str, Any]:
    if not isinstance(body, dict):
        raise PromptError(400, "prompts_bad_request")
    lim = limits()
    text = body.get("text")
    if not isinstance(text, str) or not text.strip():
        raise PromptError(400, "prompts_text_required")
    text = text.strip()
    if len(text) > lim["textMax"]:
        raise PromptError(400, "prompts_text_too_long", max=lim["textMax"])
    title = body.get("title") or ""
    if not isinstance(title, str):
        raise PromptError(400, "prompts_bad_request")
    title = " ".join(title.split())
    if len(title) > lim["titleMax"]:
        raise PromptError(400, "prompts_title_too_long", max=lim["titleMax"])
    category = str(body.get("category") or "general").strip() or "general"
    if category not in CATEGORIES:
        raise PromptError(400, "prompts_bad_category")
    prompt_id = body.get("id")
    if prompt_id not in (None, ""):
        if not isinstance(prompt_id, str) or not _ID_RE.match(prompt_id):
            raise PromptError(404, "prompts_not_found")
    else:
        prompt_id = None
    return {
        "id": prompt_id,
        "title": title or text[:40],
        "text": text,
        "category": category,
        "origin": sanitize_origin(body.get("origin")),
    }


def _clean_stored(item: Any) -> dict[str, Any] | None:
    """Normalise an item read from storage or handed over by legacy callers."""
    if not isinstance(item, dict):
        return None
    text = str(item.get("text") or "").strip()
    if not text:
        return None
    now = time.time()
    pid = str(item.get("id") or "").strip()
    out: dict[str, Any] = {
        "id": pid if _ID_RE.match(pid) else uuid.uuid4().hex,
        "title": str(item.get("title") or text[:40])[:DB_TITLE_MAX],
        "text": text[:DB_TEXT_MAX],
        "category": str(item.get("category") or "general") if item.get("category") in CATEGORIES else "general",
        "createdAt": float(item.get("createdAt") or item.get("updatedAt") or now),
        "updatedAt": float(item.get("updatedAt") or item.get("createdAt") or now),
    }
    origin = sanitize_origin(item.get("origin"))
    if origin:
        out["origin"] = origin
    if item.get("legacyId"):
        out["legacyId"] = str(item["legacyId"])[:64]
    return out


def _public(item: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in item.items() if k != "legacyId"}


# ---------------------------------------------------------------- disk backend


_file_locks: dict[str, threading.Lock] = {}
_file_locks_guard = threading.Lock()


def _thread_lock(path: Path) -> threading.Lock:
    key = str(path)
    with _file_locks_guard:
        lock = _file_locks.get(key)
        if lock is None:
            lock = _file_locks[key] = threading.Lock()
        return lock


@contextmanager
def _file_locked(path: Path) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    with _thread_lock(path):
        with open(path.with_name(path.name + ".lock"), "a+") as lockf:
            if fcntl is not None:
                fcntl.flock(lockf.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                if fcntl is not None:
                    fcntl.flock(lockf.fileno(), fcntl.LOCK_UN)


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as exc:
        logger.error("prompt store unreadable path=%s err=%s", path.name, type(exc).__name__)
        raise PromptError(503, "prompts_storage_error") from exc


def _write_json_atomic(path: Path, payload: Any) -> None:
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex[:8]}.tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


class FileBackend:
    name = "disk"

    def __init__(self, projects_root: Path):
        self.root = Path(projects_root)

    def _path(self, owner: str) -> Path:
        return self.root / ".users" / owner / "prompts.json"

    def _marker(self, owner: str) -> Path:
        return self.root / ".users" / owner / ".legacy_prompts_adopted"

    def _load(self, owner: str) -> list[dict[str, Any]]:
        data = _read_json(self._path(owner))
        items = data.get("items") if isinstance(data, dict) else data
        return [x for x in (_clean_stored(i) for i in (items or [])) if x]

    def _save(self, owner: str, items: list[dict[str, Any]]) -> None:
        _write_json_atomic(self._path(owner), {"version": 1, "items": items})

    # -- reads
    def all(self, owner: str) -> list[dict[str, Any]]:
        return self._load(owner)

    def count(self, owner: str) -> int:
        return len(self._load(owner))

    # -- writes (each one read-modify-write under the file lock)
    def create(self, owner: str, item: dict[str, Any], max_items: int) -> tuple[dict[str, Any], bool]:
        with _file_locked(self._path(owner)):
            items = self._load(owner)
            lib_id = (item.get("origin") or {}).get("libraryId")
            if lib_id:
                for cur in items:
                    if (cur.get("origin") or {}).get("libraryId") == lib_id:
                        cur.update(title=item["title"], text=item["text"], category=item["category"],
                                   origin=item["origin"], updatedAt=item["updatedAt"])
                        self._save(owner, items)
                        return cur, False
            if len(items) >= max_items:
                raise PromptError(409, "prompts_limit_reached", max=max_items)
            items.insert(0, item)
            self._save(owner, items)
            return item, True

    def update(self, owner: str, prompt_id: str, fields: dict[str, Any]) -> dict[str, Any] | None:
        with _file_locked(self._path(owner)):
            items = self._load(owner)
            for cur in items:
                if cur["id"] == prompt_id:
                    cur.update(fields)
                    if fields.get("origin") is None:
                        cur.pop("origin", None)
                    self._save(owner, items)
                    return cur
            return None

    def delete(self, owner: str, prompt_id: str) -> bool:
        with _file_locked(self._path(owner)):
            items = self._load(owner)
            rest = [x for x in items if x["id"] != prompt_id]
            if len(rest) == len(items):
                return False
            self._save(owner, rest)
            return True

    def replace_all(self, owner: str, items: list[dict[str, Any]]) -> None:
        with _file_locked(self._path(owner)):
            self._save(owner, items)

    # -- legacy
    def legacy(self) -> list[dict[str, Any]]:
        data = _read_json(self.root / "_library" / "prompts.json")
        items = data.get("items") if isinstance(data, dict) else data
        out = []
        for raw in items or []:
            item = _clean_stored(raw)
            if item:
                item["legacyId"] = str((raw or {}).get("id") or item["id"])[:64]
                out.append(item)
        return out

    def assign_legacy(self, owner: str, legacy_ids: set[str] | None, max_items: int | None) -> int:
        legacy = [x for x in self.legacy() if legacy_ids is None or x["legacyId"] in legacy_ids]
        with _file_locked(self._path(owner)):
            items = self._load(owner)
            have = {x.get("legacyId") for x in items if x.get("legacyId")}
            added = 0
            for src in legacy:
                if src["legacyId"] in have:
                    continue
                if max_items is not None and len(items) >= max_items:
                    break
                copy = dict(src)
                copy["id"] = uuid.uuid4().hex
                items.append(copy)
                have.add(src["legacyId"])
                added += 1
            if added:
                self._save(owner, items)
        return added

    def adopted(self, owner: str) -> bool:
        return self._marker(owner).exists()

    def mark_adopted(self, owner: str) -> None:
        marker = self._marker(owner)
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(str(time.time()), encoding="utf-8")

    def owners(self) -> dict[str, int]:
        base = self.root / ".users"
        out: dict[str, int] = {}
        if base.is_dir():
            for d in sorted(base.iterdir()):
                if (d / "prompts.json").is_file():
                    out[d.name] = self.count(d.name)
        return out


# ------------------------------------------------------------ Postgres backend


MIGRATIONS: list[tuple[str, str]] = [
    (
        "0001_studio_prompts",
        """
        CREATE TABLE IF NOT EXISTS studio_prompts (
            id          TEXT PRIMARY KEY,
            owner_id    TEXT,
            title       TEXT NOT NULL DEFAULT '',
            body        TEXT NOT NULL,
            category    TEXT NOT NULL DEFAULT 'general',
            origin      JSONB,
            legacy_id   TEXT,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT studio_prompts_body_len CHECK (char_length(body) BETWEEN 1 AND 20000),
            CONSTRAINT studio_prompts_title_len CHECK (char_length(title) <= 300),
            CONSTRAINT studio_prompts_owner_len CHECK (owner_id IS NULL OR char_length(owner_id) BETWEEN 1 AND 128)
        );
        COMMENT ON COLUMN studio_prompts.owner_id IS
            'Account that owns the prompt; NULL = legacy shared prompt imported from studio_kv prompts:_library (never listed to users)';
        CREATE INDEX IF NOT EXISTS idx_studio_prompts_owner_updated
            ON studio_prompts (owner_id, updated_at DESC);
        CREATE UNIQUE INDEX IF NOT EXISTS uq_studio_prompts_owner_library
            ON studio_prompts (owner_id, (origin->>'libraryId'))
            WHERE owner_id IS NOT NULL AND origin ? 'libraryId';
        CREATE UNIQUE INDEX IF NOT EXISTS uq_studio_prompts_owner_legacy
            ON studio_prompts (owner_id, legacy_id)
            WHERE owner_id IS NOT NULL AND legacy_id IS NOT NULL;
        CREATE INDEX IF NOT EXISTS idx_studio_prompts_legacy
            ON studio_prompts (updated_at DESC) WHERE owner_id IS NULL;
        """,
    ),
]
_MIGRATION_LOCK = 0x6F6D707274  # "omprt": serialises migrations across workers


def _legacy_row_id(legacy_id: str, text: str) -> str:
    return "lg" + hashlib.sha1(f"{legacy_id}\x00{text}".encode("utf-8")).hexdigest()[:30]


class PgBackend:
    name = "postgres"
    _ready = False
    _ready_lock = threading.Lock()

    def __init__(self, projects_root: Path):
        self.root = Path(projects_root)

    # -- plumbing
    @contextmanager
    def _cursor(self) -> Iterator[Any]:
        import pg_backend

        self.ensure_schema()
        try:
            with pg_backend.connection() as conn:
                with conn.cursor() as cur:
                    yield cur
        except PromptError:
            raise
        except Exception as exc:  # noqa: BLE001
            if exc.__class__.__name__ in ("UniqueViolation", "IntegrityError"):
                raise PromptError(409, "prompts_conflict") from exc
            logger.error("prompt store postgres error: %s", type(exc).__name__)
            raise PromptError(503, "prompts_storage_error") from exc

    @classmethod
    def reset_schema_cache(cls) -> None:
        cls._ready = False

    def ensure_schema(self) -> None:
        if PgBackend._ready:
            return
        with PgBackend._ready_lock:
            if PgBackend._ready:
                return
            migrate(self.root)
            PgBackend._ready = True

    @staticmethod
    def _row(r: Any) -> dict[str, Any]:
        out: dict[str, Any] = {
            "id": r[0],
            "title": r[1],
            "text": r[2],
            "category": r[3],
            "createdAt": float(r[5]),
            "updatedAt": float(r[6]),
        }
        if r[4]:
            out["origin"] = r[4] if isinstance(r[4], dict) else json.loads(r[4])
        return out

    _COLS = "id, title, body, category, origin, EXTRACT(EPOCH FROM created_at), EXTRACT(EPOCH FROM updated_at)"

    @staticmethod
    def _lock_owner(cur: Any, owner: str) -> None:
        cur.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 7))", (f"prompts:{owner}",))

    # -- reads
    def query(self, owner: str, *, category: str, q: str, sort: str, offset: int, limit: int) -> tuple[list[dict], int]:
        where = ["owner_id = %s"]
        args: list[Any] = [owner]
        if category:
            where.append("category = %s")
            args.append(category)
        if q:
            pat = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
            where.append("(title ILIKE %s ESCAPE '\\' OR body ILIKE %s ESCAPE '\\' OR category ILIKE %s ESCAPE '\\')")
            args += [pat, pat, pat]
        order = {
            "oldest": "updated_at ASC, id ASC",
            "name": "lower(title) ASC, id ASC",
        }.get(sort, "updated_at DESC, id DESC")
        sql_where = " AND ".join(where)
        with self._cursor() as cur:
            cur.execute(f"SELECT count(*) FROM studio_prompts WHERE {sql_where}", args)
            total = int(cur.fetchone()[0])
            cur.execute(
                f"SELECT {self._COLS} FROM studio_prompts WHERE {sql_where} ORDER BY {order} LIMIT %s OFFSET %s",
                [*args, limit, offset],
            )
            rows = [self._row(r) for r in cur.fetchall()]
        return rows, total

    def all(self, owner: str) -> list[dict[str, Any]]:
        with self._cursor() as cur:
            cur.execute(
                f"SELECT {self._COLS} FROM studio_prompts WHERE owner_id = %s ORDER BY updated_at DESC, id DESC",
                (owner,),
            )
            return [self._row(r) for r in cur.fetchall()]

    def count(self, owner: str) -> int:
        with self._cursor() as cur:
            cur.execute("SELECT count(*) FROM studio_prompts WHERE owner_id = %s", (owner,))
            return int(cur.fetchone()[0])

    # -- writes (one transaction each; per-owner advisory lock serialises the limit check)
    def create(self, owner: str, item: dict[str, Any], max_items: int) -> tuple[dict[str, Any], bool]:
        origin = item.get("origin")
        with self._cursor() as cur:
            self._lock_owner(cur, owner)
            if origin:
                cur.execute(
                    f"""UPDATE studio_prompts SET title = %s, body = %s, category = %s, origin = %s::jsonb,
                               updated_at = NOW()
                         WHERE owner_id = %s AND origin->>'libraryId' = %s
                     RETURNING {self._COLS}""",
                    (item["title"], item["text"], item["category"], json.dumps(origin, ensure_ascii=False),
                     owner, origin["libraryId"]),
                )
                row = cur.fetchone()
                if row:
                    return self._row(row), False
            cur.execute("SELECT count(*) FROM studio_prompts WHERE owner_id = %s", (owner,))
            if int(cur.fetchone()[0]) >= max_items:
                raise PromptError(409, "prompts_limit_reached", max=max_items)
            cur.execute(
                f"""INSERT INTO studio_prompts (id, owner_id, title, body, category, origin)
                    VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                 RETURNING {self._COLS}""",
                (item["id"], owner, item["title"], item["text"], item["category"],
                 json.dumps(origin, ensure_ascii=False) if origin else None),
            )
            return self._row(cur.fetchone()), True

    def update(self, owner: str, prompt_id: str, fields: dict[str, Any]) -> dict[str, Any] | None:
        origin = fields.get("origin")
        with self._cursor() as cur:
            cur.execute(
                f"""UPDATE studio_prompts
                       SET title = %s, body = %s, category = %s, origin = %s::jsonb, updated_at = NOW()
                     WHERE owner_id = %s AND id = %s
                 RETURNING {self._COLS}""",
                (fields["title"], fields["text"], fields["category"],
                 json.dumps(origin, ensure_ascii=False) if origin else None, owner, prompt_id),
            )
            row = cur.fetchone()
            return self._row(row) if row else None

    def delete(self, owner: str, prompt_id: str) -> bool:
        with self._cursor() as cur:
            cur.execute("DELETE FROM studio_prompts WHERE owner_id = %s AND id = %s", (owner, prompt_id))
            return cur.rowcount > 0

    def replace_all(self, owner: str, items: list[dict[str, Any]]) -> None:
        with self._cursor() as cur:
            self._lock_owner(cur, owner)
            cur.execute("DELETE FROM studio_prompts WHERE owner_id = %s", (owner,))
            for it in items:
                cur.execute(
                    """INSERT INTO studio_prompts (id, owner_id, title, body, category, origin, legacy_id,
                                                   created_at, updated_at)
                       VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, to_timestamp(%s), to_timestamp(%s))
                       ON CONFLICT DO NOTHING""",
                    (it["id"], owner, it["title"], it["text"], it["category"],
                     json.dumps(it["origin"], ensure_ascii=False) if it.get("origin") else None,
                     it.get("legacyId"), it["createdAt"], it["updatedAt"]),
                )

    # -- legacy
    def legacy(self) -> list[dict[str, Any]]:
        with self._cursor() as cur:
            cur.execute(
                f"SELECT {self._COLS}, legacy_id FROM studio_prompts WHERE owner_id IS NULL ORDER BY updated_at DESC"
            )
            out = []
            for r in cur.fetchall():
                item = self._row(r)
                item["legacyId"] = r[7] or r[0]
                out.append(item)
            return out

    def assign_legacy(self, owner: str, legacy_ids: set[str] | None, max_items: int | None) -> int:
        added = 0
        with self._cursor() as cur:
            self._lock_owner(cur, owner)
            cur.execute(
                "SELECT legacy_id, title, body, category, origin, created_at, updated_at FROM studio_prompts "
                "WHERE owner_id IS NULL ORDER BY updated_at DESC"
            )
            rows = [r for r in cur.fetchall() if legacy_ids is None or r[0] in legacy_ids]
            cur.execute("SELECT count(*) FROM studio_prompts WHERE owner_id = %s", (owner,))
            have = int(cur.fetchone()[0])
            for r in rows:
                if max_items is not None and have >= max_items:
                    break
                cur.execute(
                    """INSERT INTO studio_prompts (id, owner_id, title, body, category, origin, legacy_id,
                                                   created_at, updated_at)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                       ON CONFLICT (owner_id, legacy_id) WHERE owner_id IS NOT NULL AND legacy_id IS NOT NULL
                       DO NOTHING""",
                    (uuid.uuid4().hex, owner, r[1], r[2], r[3],
                     json.dumps(r[4]) if isinstance(r[4], dict) else r[4], r[0], r[5], r[6]),
                )
                if cur.rowcount:
                    added += 1
                    have += 1
        return added

    def adopted(self, owner: str) -> bool:
        import pg_backend

        return pg_backend.load_kv(f"prompts:legacy_adopted:{owner}") is not None

    def mark_adopted(self, owner: str) -> None:
        import pg_backend

        pg_backend.upsert_kv(f"prompts:legacy_adopted:{owner}", {"at": time.time()})

    def owners(self) -> dict[str, int]:
        with self._cursor() as cur:
            cur.execute(
                "SELECT owner_id, count(*) FROM studio_prompts WHERE owner_id IS NOT NULL GROUP BY owner_id ORDER BY 1"
            )
            return {str(r[0]): int(r[1]) for r in cur.fetchall()}


def _legacy_source_items(projects_root: Path) -> list[dict[str, Any]]:
    """Legacy shared list: studio_kv first, then the old disk file."""
    import pg_backend

    data = None
    try:
        data = pg_backend.load_kv(LEGACY_KV_KEY)
    except Exception:  # noqa: BLE001
        data = None
    if data is None:
        path = Path(projects_root) / "_library" / "prompts.json"
        if path.is_file():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                data = None
    items = data.get("items") if isinstance(data, dict) else data
    return [x for x in (items or []) if isinstance(x, dict) and str(x.get("text") or "").strip()]


def migrate(projects_root: Path) -> dict[str, int]:
    """Create/upgrade the studio_prompts schema and import legacy rows. Idempotent.

    Safe on an existing database: only CREATE … IF NOT EXISTS, a migrations
    ledger, and INSERT … ON CONFLICT DO NOTHING for the owner-less legacy copy.
    The legacy studio_kv row and disk file are read, never changed.
    """
    import pg_backend

    stats = {"applied": 0, "legacyImported": 0}
    legacy_items = _legacy_source_items(projects_root)  # read before taking a connection
    with pg_backend.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT pg_advisory_xact_lock(%s)", (_MIGRATION_LOCK,))
            cur.execute(
                """CREATE TABLE IF NOT EXISTS studio_schema_migrations (
                       name        TEXT PRIMARY KEY,
                       applied_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
                   )"""
            )
            cur.execute("SELECT name FROM studio_schema_migrations")
            done = {r[0] for r in cur.fetchall()}
            for name, sql in MIGRATIONS:
                if name in done:
                    continue
                cur.execute(sql)
                cur.execute("INSERT INTO studio_schema_migrations (name) VALUES (%s) ON CONFLICT DO NOTHING", (name,))
                stats["applied"] += 1
            for raw in legacy_items:
                item = _clean_stored(raw)
                if not item:
                    continue
                legacy_id = str(raw.get("id") or item["id"])[:64]
                cur.execute(
                    """INSERT INTO studio_prompts (id, owner_id, title, body, category, origin, legacy_id,
                                                   created_at, updated_at)
                       VALUES (%s, NULL, %s, %s, %s, %s::jsonb, %s, to_timestamp(%s), to_timestamp(%s))
                       ON CONFLICT DO NOTHING""",
                    (_legacy_row_id(legacy_id, item["text"]), item["title"], item["text"], item["category"],
                     json.dumps(item["origin"], ensure_ascii=False) if item.get("origin") else None,
                     legacy_id, item["createdAt"], item["updatedAt"]),
                )
                stats["legacyImported"] += cur.rowcount
    if stats["applied"] or stats["legacyImported"]:
        logger.info("prompt store migrated applied=%s legacy_imported=%s", stats["applied"], stats["legacyImported"])
    return stats


def import_user_files(projects_root: Path) -> int:
    """Copy per-user disk prompt files (.users/<uid>/prompts.json) into Postgres.

    Used by the disk -> Postgres state migration. Idempotent (ON CONFLICT DO
    NOTHING); never overwrites a row that already exists, never touches the files.
    """
    files = FileBackend(projects_root)
    store = PgBackend(projects_root)
    added = 0
    for owner in files.owners():
        if not safe_owner(owner):
            continue
        items = files.all(owner)
        if not items:
            continue
        with store._cursor() as cur:
            store._lock_owner(cur, owner)
            for it in items:
                cur.execute(
                    """INSERT INTO studio_prompts (id, owner_id, title, body, category, origin, legacy_id,
                                                   created_at, updated_at)
                       VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, to_timestamp(%s), to_timestamp(%s))
                       ON CONFLICT DO NOTHING""",
                    (it["id"], owner, it["title"], it["text"], it["category"],
                     json.dumps(it["origin"], ensure_ascii=False) if it.get("origin") else None,
                     it.get("legacyId"), it["createdAt"], it["updatedAt"]),
                )
                added += cur.rowcount
    if added:
        logger.info("prompt store imported %s per-user disk prompt(s)", added)
    return added


def backend(projects_root: Path) -> FileBackend | PgBackend:
    import pg_backend

    return PgBackend(projects_root) if pg_backend.enabled() else FileBackend(projects_root)


# ------------------------------------------------------------------ public API


def _maybe_adopt_legacy(store: FileBackend | PgBackend, owner: str) -> None:
    target = LOCAL_OWNER if owner == LOCAL_OWNER else safe_owner(os.environ.get(LEGACY_OWNER_ENV, ""))
    if not target or target != owner or store.adopted(owner):
        return
    added = store.assign_legacy(owner, None, None)
    store.mark_adopted(owner)
    logger.info("legacy prompts adopted owner=%s added=%s", _owner_tag(owner), added)


def list_view(
    projects_root: Path,
    *,
    category: str = "all",
    q: str = "",
    sort: str = "latest",
    offset: int = 0,
    limit: int = LIST_DEFAULT_LIMIT,
) -> dict[str, Any]:
    access = current_access()
    lim = limits()
    offset = max(0, int(offset or 0))
    limit = max(1, min(int(limit or LIST_DEFAULT_LIMIT), LIST_MAX_LIMIT))
    base = {"requiresLogin": access.reason == "login", "readOnlyReason": access.reason, "limits": lim}
    if not access.owner:
        return {**base, "prompts": [], "total": 0, "offset": offset, "limit": limit, "hasMore": False, "nextOffset": None}
    store = backend(projects_root)
    _maybe_adopt_legacy(store, access.owner)
    cat = (category or "all").strip()
    cat = "" if cat.lower() in ("all", "*", "") else cat
    query = (q or "").strip()[:200]
    sort_key = (sort or "latest").strip().lower()
    if isinstance(store, PgBackend):
        page, total = store.query(access.owner, category=cat, q=query, sort=sort_key, offset=offset, limit=limit)
    else:
        items = store.all(access.owner)
        if cat:
            items = [x for x in items if x["category"] == cat]
        if query:
            ql = query.lower()
            items = [x for x in items if ql in x["title"].lower() or ql in x["text"].lower() or ql in x["category"]]
        if sort_key == "oldest":
            items.sort(key=lambda x: (x["updatedAt"], x["id"]))
        elif sort_key == "name":
            items.sort(key=lambda x: (x["title"].lower(), x["id"]))
        else:
            items.sort(key=lambda x: (x["updatedAt"], x["id"]), reverse=True)
        total = len(items)
        page = items[offset : offset + limit]
    nxt = offset + len(page)
    return {
        **base,
        "prompts": [_public(x) for x in page],
        "total": total,
        "offset": offset,
        "limit": limit,
        "hasMore": nxt < total,
        "nextOffset": nxt if nxt < total else None,
    }


def save_prompt(projects_root: Path, body: Any) -> tuple[dict[str, Any], bool]:
    """Create (no id) or update (own id) a prompt. Returns (item, created)."""
    owner = _require_owner(current_access())
    data = validate_input(body)
    rate_limiter.check(owner)
    store = backend(projects_root)
    now = time.time()
    if data["id"]:
        fields = {
            "title": data["title"],
            "text": data["text"],
            "category": data["category"],
            "origin": data["origin"],
            "updatedAt": now,
        }
        item = store.update(owner, data["id"], fields)
        if item is None:
            raise PromptError(404, "prompts_not_found")
        logger.info("prompt updated owner=%s id=%s", _owner_tag(owner), data["id"])
        return _public(item), False
    new = {
        "id": uuid.uuid4().hex,
        "title": data["title"],
        "text": data["text"],
        "category": data["category"],
        "createdAt": now,
        "updatedAt": now,
    }
    if data["origin"]:
        new["origin"] = data["origin"]
    item, created = store.create(owner, new, limits()["maxPerUser"])
    logger.info("prompt %s owner=%s id=%s", "created" if created else "deduped", _owner_tag(owner), item["id"])
    return _public(item), created


def delete_prompt(projects_root: Path, prompt_id: str) -> None:
    owner = _require_owner(current_access())
    pid = str(prompt_id or "")
    if not _ID_RE.match(pid):
        raise PromptError(404, "prompts_not_found")
    rate_limiter.check(owner)
    if not backend(projects_root).delete(owner, pid):
        raise PromptError(404, "prompts_not_found")
    logger.info("prompt deleted owner=%s id=%s", _owner_tag(owner), pid)


# -------- compatibility for callers that read/write the whole list at once


def load_all(projects_root: Path, owner: str | None) -> list[dict[str, Any]]:
    if not owner:
        return []
    store = backend(projects_root)
    _maybe_adopt_legacy(store, owner)
    return [_public(x) for x in store.all(owner)]


def replace_all(projects_root: Path, owner: str | None, items: list[dict[str, Any]]) -> None:
    if not owner:
        raise PromptError(401, "prompts_login_required")
    clean = [x for x in (_clean_stored(i) for i in items) if x]
    max_items = limits()["maxPerUser"]
    if len(clean) > max_items:
        raise PromptError(409, "prompts_limit_reached", max=max_items)
    backend(projects_root).replace_all(owner, clean)


# ---------------------------------------------------------------- admin helpers


def legacy_prompts(projects_root: Path) -> list[dict[str, Any]]:
    return backend(projects_root).legacy()


def assign_legacy(projects_root: Path, owner: str, legacy_ids: list[str] | None = None, *, force: bool = False) -> int:
    owner = safe_owner(owner)
    if not owner:
        raise ValueError("invalid owner id")
    store = backend(projects_root)
    added = store.assign_legacy(owner, set(legacy_ids) if legacy_ids else None, None if force else limits()["maxPerUser"])
    logger.info("legacy prompts assigned owner=%s added=%s", _owner_tag(owner), added)
    return added


def owner_counts(projects_root: Path) -> dict[str, int]:
    return backend(projects_root).owners()
