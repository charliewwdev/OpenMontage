"""Request-scoped auth user (contextvars) for per-user secrets / projects."""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any

_current_user: ContextVar[dict[str, Any] | None] = ContextVar("om_current_user", default=None)
# True while serving an HTTP request (set by the auth middleware). Background
# workers / thread-pool jobs run with the default (False).
_in_request: ContextVar[bool] = ContextVar("om_in_request", default=False)


def set_current_user(user: dict[str, Any] | None) -> None:
    _current_user.set(user)


def get_current_user() -> dict[str, Any] | None:
    return _current_user.get()


def current_user_id() -> str:
    user = get_current_user() or {}
    return str(user.get("userId") or user.get("id") or user.get("uid") or "").strip()


def require_user() -> dict[str, Any]:
    user = get_current_user()
    if not user:
        raise PermissionError("login required")
    return user


def set_in_request(value: bool) -> None:
    _in_request.set(bool(value))


def in_request() -> bool:
    return bool(_in_request.get())
