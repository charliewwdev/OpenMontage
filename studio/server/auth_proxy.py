"""Proxy Drama Studio auth to dtok public API (API_BASE_URL)."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any


def api_base_url() -> str:
    return (os.environ.get("API_BASE_URL") or "https://api-app.dtok.io/api/v1").rstrip("/")


def _request(
    method: str,
    path: str,
    *,
    body: dict[str, Any] | None = None,
    token: str | None = None,
    timeout: float = 30.0,
) -> tuple[int, dict[str, Any]]:
    url = f"{api_base_url()}{path if path.startswith('/') else '/' + path}"
    data = None
    headers = {
        "Accept": "application/json",
        "User-Agent": "OpenMontage-DramaStudio/0.2",
    }
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(url, data=data, headers=headers, method=method.upper())
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            payload = json.loads(raw) if raw else {}
            return int(resp.status), payload if isinstance(payload, dict) else {"data": payload}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            payload = {"msg": raw or str(exc.reason), "success": False}
        if not isinstance(payload, dict):
            payload = {"msg": str(payload), "success": False}
        return int(exc.code), payload
    except Exception as exc:  # noqa: BLE001
        return 502, {"success": False, "msg": f"upstream auth unreachable: {exc}", "code": 502}


def unwrap_result(status: int, payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """Normalize dtok Result envelope into {ok, data, error, ...}."""
    if not isinstance(payload, dict):
        return status, {"ok": False, "error": "invalid upstream response"}

    success = payload.get("success")
    code = payload.get("code")
    msg = payload.get("msg") or payload.get("message") or payload.get("error") or ""
    data = payload.get("data")

    if success is True or code in (200, "200", "success"):
        return 200, {"ok": True, "data": data, "msg": msg or "ok", "raw": payload}

    http_status = status if status >= 400 else 400
    if code in (401, "401", 2001, "2001"):
        http_status = 401
    elif code in (403, "403"):
        http_status = 403
    elif code in (404, "404"):
        http_status = 404
    elif code in (429, "429"):
        http_status = 429

    return http_status, {
        "ok": False,
        "error": msg or "auth failed",
        "code": code,
        "errorCode": payload.get("errorCode"),
        "data": data,
        "raw": payload,
    }


def proxy(method: str, path: str, body: dict[str, Any] | None = None, token: str | None = None):
    status, payload = _request(method, path, body=body, token=token)
    return unwrap_result(status, payload)


def get_captcha():
    return proxy("GET", "/auth/captcha")


def login(body: dict[str, Any]):
    payload = dict(body or {})
    payload.setdefault("client", "WEB")
    return proxy("POST", "/auth/login", body=payload)


def register(body: dict[str, Any]):
    payload = dict(body or {})
    return proxy("POST", "/auth/register", body=payload)


def phone_login(body: dict[str, Any]):
    return proxy("POST", "/auth/phone-login", body=body or {})


def send_code(body: dict[str, Any]):
    return proxy("POST", "/auth/send-code", body=body or {})


def social_providers():
    return proxy("GET", "/auth/social-providers")


def me(token: str):
    return proxy("GET", "/auth/me", token=token)


def logout(token: str):
    return proxy("POST", "/auth/logout", body={}, token=token)


def refresh_token(token: str):
    return proxy("POST", "/auth/refresh-token", body={}, token=token)


def auth_public_config() -> dict[str, Any]:
    required = (os.environ.get("STUDIO_AUTH_REQUIRED") or "true").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )
    return {
        "required": required,
        "apiBaseUrl": api_base_url(),
        "methods": ["password", "register", "phone"],
        "client": "WEB",
    }
