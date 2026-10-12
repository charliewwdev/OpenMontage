"""Model providers for Drama Studio (DeepSeek / Seedream / Seedance)."""

from __future__ import annotations

import os


def deepseek_configured() -> bool:
    return bool(os.environ.get("DEEPSEEK_API_KEY"))


def volc_key() -> str | None:
    return os.environ.get("VOLCENGINE_API_KEY") or os.environ.get("ARK_API_KEY") or None


def seedream_configured() -> bool:
    return bool(volc_key())


def seedance_configured() -> bool:
    return bool(volc_key())


def provider_status() -> dict:
    return {
        "deepseek": deepseek_configured(),
        "seedream": seedream_configured(),
        "seedance": seedance_configured(),
        "volcengine": bool(volc_key()),
    }
