"""Soft credits ledger — Postgres is source of truth when DATABASE_URL is set."""

from __future__ import annotations

import json
import threading
import time
import uuid
from pathlib import Path
from typing import Any

_lock = threading.Lock()
_projects_root: Path | None = None


def init_credits(projects_root: Path) -> None:
    global _projects_root
    _projects_root = Path(projects_root)


def _user_scope() -> str:
    try:
        from auth_context import current_user_id

        uid = current_user_id()
    except Exception:
        uid = ""
    if uid and uid not in {".", ".."} and "/" not in uid and "\\" not in uid:
        return uid
    return ""


def credits_path(projects_root: Path | None = None) -> Path:
    root = projects_root or _projects_root
    if root is None:
        raise RuntimeError("credits store not initialized")
    uid = _user_scope()
    if uid:
        return Path(root) / ".users" / uid / "credits.json"
    return Path(root) / ".studio_credits.json"


def _kv_key() -> str:
    uid = _user_scope()
    if uid:
        return f"credits:user:{uid}"
    return "credits:.studio_credits.json"


def _pg_enabled() -> bool:
    try:
        import pg_backend as _pg

        return bool(_pg.enabled())
    except Exception:
        return False


def _empty() -> dict[str, Any]:
    return {
        "balance": 0,
        "referrals": 0,
        "refCode": "",
        "ledger": [],
        "challengeDone": {},
        "updatedAt": int(time.time()),
    }


def _normalize(data: dict[str, Any]) -> dict[str, Any]:
    data.setdefault("balance", 0)
    data.setdefault("referrals", 0)
    data.setdefault("refCode", uuid.uuid4().hex[:8])
    data.setdefault("ledger", [])
    data.setdefault("challengeDone", {})
    if not data.get("refCode"):
        data["refCode"] = uuid.uuid4().hex[:8]
    return data


def load_credits(projects_root: Path | None = None) -> dict[str, Any]:
    path = credits_path(projects_root)
    with _lock:
        data: dict[str, Any] | None = None
        if _pg_enabled():
            try:
                import pg_backend as _pg

                hit = _pg.load_kv(_kv_key())
                if isinstance(hit, dict):
                    data = hit
            except Exception:
                data = None
            # Migrate disk → PG once
            if data is None and path.is_file():
                try:
                    loaded = json.loads(path.read_text(encoding="utf-8"))
                    if isinstance(loaded, dict):
                        data = loaded
                        import pg_backend as _pg

                        _pg.upsert_kv(_kv_key(), data)
                except Exception:
                    data = None
        elif path.is_file():
            try:
                loaded = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    data = loaded
            except Exception:
                data = None

        if data is None:
            data = _empty()
            data["refCode"] = uuid.uuid4().hex[:8]
        data = _normalize(data)
        return data


def _save(data: dict[str, Any], projects_root: Path | None = None) -> dict[str, Any]:
    path = credits_path(projects_root)
    data["updatedAt"] = int(time.time())
    with _lock:
        if _pg_enabled():
            try:
                import pg_backend as _pg

                _pg.upsert_kv(_kv_key(), data)
                return data
            except Exception as exc:
                # Fall through to disk so award isn't lost
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                raise RuntimeError(f"保存积分到 Postgres 失败: {exc}") from exc
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


def award(
    *,
    amount: int,
    reason: str,
    meta: dict[str, Any] | None = None,
    projects_root: Path | None = None,
) -> dict[str, Any]:
    data = load_credits(projects_root)
    pts = int(amount or 0)
    data["balance"] = int(data.get("balance") or 0) + pts
    entry = {
        "id": uuid.uuid4().hex[:12],
        "ts": int(time.time()),
        "amount": pts,
        "reason": reason,
        "meta": meta or {},
        "balance": data["balance"],
    }
    ledger = list(data.get("ledger") or [])
    ledger.insert(0, entry)
    data["ledger"] = ledger[:200]
    return _save(data, projects_root)


def complete_challenge(challenge_id: str, prize_points: int, title: str = "") -> dict[str, Any]:
    data = load_credits()
    done = dict(data.get("challengeDone") or {})
    if challenge_id in done:
        return {"ok": True, "already": True, "credits": data}
    done[challenge_id] = {"at": int(time.time()), "points": int(prize_points or 0), "title": title}
    data["challengeDone"] = done
    _save(data)
    return {
        "ok": True,
        "already": False,
        "credits": award(
            amount=int(prize_points or 0),
            reason=f"挑战完成：{title or challenge_id}",
            meta={"challengeId": challenge_id},
        ),
    }


def record_referral(ref: str = "") -> dict[str, Any]:
    data = load_credits()
    code = (ref or "").strip()[:64]
    if not code:
        return data
    if code and code == str(data.get("refCode") or ""):
        return data
    seen = set(data.get("seenRefs") or [])
    if code in seen:
        return data
    seen.add(code)
    data["seenRefs"] = sorted(seen)[-100:]
    data["referrals"] = int(data.get("referrals") or 0) + 1
    _save(data)
    return award(
        amount=20,
        reason="邀请落地",
        meta={"ref": code},
    )
