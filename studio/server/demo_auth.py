"""Local demo session — skip DTok so visitors can operate studio data immediately."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Any


TOKEN_PREFIX = "omdemo."
DEFAULT_TTL_SECONDS = 7 * 24 * 3600


def _secret() -> bytes:
    raw = (os.environ.get("STUDIO_DEMO_SECRET") or "openmontage-demo-local").encode("utf-8")
    return hashlib.sha256(raw).digest()


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64url_decode(text: str) -> bytes:
    pad = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + pad)


def _sign(payload_part: str) -> str:
    return hmac.new(_secret(), payload_part.encode("utf-8"), hashlib.sha256).hexdigest()[:40]


def is_demo_token(token: str | None) -> bool:
    return bool(token) and str(token).startswith(TOKEN_PREFIX)


def issue_demo_token(
    *,
    user_id: str = "demo",
    username: str = "Demo",
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> dict[str, Any]:
    now = int(time.time())
    expires_in = max(300, int(ttl_seconds or DEFAULT_TTL_SECONDS))
    payload = {
        "uid": user_id,
        "username": username,
        "iat": now,
        "exp": now + expires_in,
        "kind": "demo",
    }
    payload_part = _b64url(json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
    token = f"{TOKEN_PREFIX}{payload_part}.{_sign(payload_part)}"
    return {
        "token": token,
        "accessToken": token,
        "userId": user_id,
        "username": username,
        "avatar": "",
        "expiresIn": expires_in,
        "demo": True,
    }


def parse_demo_token(token: str) -> dict[str, Any] | None:
    if not is_demo_token(token):
        return None
    body = token[len(TOKEN_PREFIX) :]
    if "." not in body:
        return None
    payload_part, sig = body.rsplit(".", 1)
    if not hmac.compare_digest(_sign(payload_part), sig):
        return None
    try:
        payload = json.loads(_b64url_decode(payload_part).decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    exp = int(payload.get("exp") or 0)
    if exp and exp < int(time.time()):
        return None
    return payload


def demo_me(token: str) -> tuple[int, dict[str, Any]]:
    payload = parse_demo_token(token)
    if not payload:
        return 401, {"ok": False, "error": "invalid or expired demo token"}
    return 200, {
        "ok": True,
        "data": {
            "id": payload.get("uid") or "demo",
            "userId": payload.get("uid") or "demo",
            "username": payload.get("username") or "Demo",
            "nickname": payload.get("username") or "Demo",
            "avatar": "",
            "demo": True,
        },
        "msg": "ok",
    }


def demo_logout(_: str) -> tuple[int, dict[str, Any]]:
    return 200, {"ok": True, "data": None, "msg": "ok"}


def demo_refresh(token: str, *, username: str = "Demo", user_id: str = "demo") -> tuple[int, dict[str, Any]]:
    payload = parse_demo_token(token)
    if not payload:
        return 401, {"ok": False, "error": "invalid or expired demo token"}
    issued = issue_demo_token(
        user_id=str(payload.get("uid") or user_id),
        username=str(payload.get("username") or username),
    )
    return 200, {"ok": True, "data": issued, "msg": "ok"}
