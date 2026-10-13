"""Persist Drama Studio API keys to a local secrets file and inject into process env."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

SECRET_KEYS = (
    "DEEPSEEK_API_KEY",
    "DEEPSEEK_BASE_URL",
    "DEEPSEEK_MODEL",
    "VOLCENGINE_API_KEY",
    "ARK_API_KEY",
    "SEEDREAM_MODEL",
    "SEEDANCE_MODEL",
)

MASKABLE = frozenset({"DEEPSEEK_API_KEY", "VOLCENGINE_API_KEY", "ARK_API_KEY"})


def secrets_path(projects_root: Path) -> Path:
    return Path(projects_root) / ".studio_secrets.json"


def _load_file(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    out: dict[str, str] = {}
    for key in SECRET_KEYS:
        val = data.get(key)
        if isinstance(val, str) and val.strip():
            out[key] = val.strip()
    return out


def apply_to_environ(values: dict[str, str]) -> None:
    for key, value in values.items():
        if value:
            os.environ[key] = value


def load_and_apply(projects_root: Path) -> dict[str, str]:
    values = _load_file(secrets_path(projects_root))
    apply_to_environ(values)
    return values


def mask_secret(value: str | None) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:3]}…{value[-4:]}"


def public_status() -> dict[str, Any]:
    deepseek = bool(os.environ.get("DEEPSEEK_API_KEY"))
    volc = bool(os.environ.get("VOLCENGINE_API_KEY") or os.environ.get("ARK_API_KEY"))
    return {
        "deepseek": {
            "configured": deepseek,
            "masked": mask_secret(os.environ.get("DEEPSEEK_API_KEY")),
            "baseUrl": os.environ.get("DEEPSEEK_BASE_URL") or "https://api.deepseek.com",
            "model": os.environ.get("DEEPSEEK_MODEL") or "deepseek-chat",
        },
        "volcengine": {
            "configured": volc,
            "masked": mask_secret(os.environ.get("VOLCENGINE_API_KEY") or os.environ.get("ARK_API_KEY")),
            "seedreamModel": os.environ.get("SEEDREAM_MODEL") or "doubao-seedream-5-0-260128",
            "seedanceModel": os.environ.get("SEEDANCE_MODEL") or "",
        },
        "ready": deepseek and volc,
    }


def save_secrets(projects_root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    path = secrets_path(projects_root)
    current = _load_file(path)
    for key in SECRET_KEYS:
        if key not in payload:
            continue
        raw = payload.get(key)
        if raw is None:
            continue
        text = str(raw).strip()
        if text == "" or text == "********":
            # empty means clear; mask placeholder means keep
            if text == "":
                current.pop(key, None)
                os.environ.pop(key, None)
            continue
        if key in MASKABLE and "…" in text and current.get(key):
            # ignore accidental masked resubmit
            continue
        current[key] = text
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(current, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass
    apply_to_environ(current)
    return public_status()
