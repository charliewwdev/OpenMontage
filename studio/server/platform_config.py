"""Load Drama Studio platform config from YAML (single source of truth)."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

CONFIG_CANDIDATES = (
    Path(os.environ.get("STUDIO_PLATFORM_CONFIG", "")),
    Path(__file__).resolve().parents[1] / "config" / "platform.yaml",
    Path("/app/studio/config/platform.yaml"),
)


def _resolve_path() -> Path:
    for path in CONFIG_CANDIDATES:
        if path and str(path) != "." and path.is_file():
            return path
    raise FileNotFoundError(
        "studio/config/platform.yaml not found; set STUDIO_PLATFORM_CONFIG or ship the file with the image"
    )


@lru_cache(maxsize=1)
def load_platform_config() -> dict[str, Any]:
    path = _resolve_path()
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"invalid platform config at {path}")
    return data


def reload_platform_config() -> dict[str, Any]:
    load_platform_config.cache_clear()
    return load_platform_config()


def defaults() -> dict[str, Any]:
    return dict(load_platform_config().get("defaults") or {})


def default_genre() -> str:
    return str(os.environ.get("STUDIO_DEFAULT_GENRE") or defaults().get("genre") or "都市情感")


def default_ratio() -> str:
    return str(os.environ.get("STUDIO_DEFAULT_RATIO") or defaults().get("ratio") or "9:16")


def default_visual_style() -> str:
    return str(os.environ.get("STUDIO_DEFAULT_VISUAL_STYLE") or defaults().get("visualStyle") or "")


def deepseek_base_url() -> str:
    return str(
        os.environ.get("DEEPSEEK_BASE_URL")
        or defaults().get("deepseekBaseUrl")
        or "https://api.deepseek.com"
    )


def deepseek_model() -> str:
    return str(os.environ.get("DEEPSEEK_MODEL") or defaults().get("deepseekModel") or "deepseek-chat")


def seedream_model() -> str:
    return str(os.environ.get("SEEDREAM_MODEL") or defaults().get("seedreamModel") or "")


def seedance_model() -> str:
    return str(os.environ.get("SEEDANCE_MODEL") or defaults().get("seedanceModel") or "")


def seedance_api_url() -> str:
    return str(
        os.environ.get("SEEDANCE_API_URL")
        or defaults().get("seedanceApiUrl")
        or "https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks"
    )


def seedance_models() -> list[dict[str, Any]]:
    models = load_platform_config().get("seedanceModels") or []
    return [m for m in models if isinstance(m, dict) and m.get("id")]


def genres() -> list[str]:
    items = load_platform_config().get("genres") or []
    return [str(x) for x in items if str(x).strip()]


def ratios() -> list[dict[str, Any]]:
    items = load_platform_config().get("ratios") or []
    return [x for x in items if isinstance(x, dict) and x.get("value")]


def six_steps() -> list[dict[str, Any]]:
    items = load_platform_config().get("sixSteps") or []
    return [x for x in items if isinstance(x, dict) and x.get("id")]


def _load_locale_pack(locale: str) -> dict[str, str]:
    root = Path(__file__).resolve().parents[1] / "config" / "locales"
    path = root / f"{locale}.json"
    if not path.is_file():
        return {}
    import json

    data = json.loads(path.read_text(encoding="utf-8"))
    return {str(k): str(v) for k, v in (data or {}).items()} if isinstance(data, dict) else {}


def i18n_payload() -> dict[str, Any]:
    cfg = load_platform_config().get("i18n") or {}
    locales = [str(x) for x in (cfg.get("locales") or ["zh", "en"]) if str(x).strip()]
    if not locales:
        locales = ["zh", "en"]
    default_locale = str(cfg.get("defaultLocale") or locales[0] or "zh")
    messages = {loc: _load_locale_pack(loc) for loc in locales}
    return {
        "defaultLocale": default_locale,
        "locales": locales,
        "messages": messages,
    }


def demo_auth_config() -> dict[str, Any]:
    cfg = (load_platform_config().get("auth") or {}).get("demo") or {}
    env_enabled = os.environ.get("STUDIO_DEMO_ENABLED")
    if env_enabled is not None and str(env_enabled).strip() != "":
        enabled = str(env_enabled).strip().lower() not in ("0", "false", "no", "off")
    else:
        enabled = bool(cfg.get("enabled", True))
    env_auto = os.environ.get("STUDIO_DEMO_AUTO_ENTER")
    if env_auto is not None and str(env_auto).strip() != "":
        auto_enter = str(env_auto).strip().lower() not in ("0", "false", "no", "off")
    else:
        auto_enter = bool(cfg.get("autoEnter", True))
    ttl_days = int(cfg.get("ttlDays") or 7)
    return {
        "enabled": enabled,
        "userId": str(cfg.get("userId") or "demo"),
        "username": str(cfg.get("username") or "demo"),
        "password": str(cfg.get("password") or "demo"),
        "displayName": str(cfg.get("displayName") or cfg.get("username") or "Demo"),
        "ttlDays": ttl_days,
        "seedProjectId": str(cfg.get("seedProjectId") or "welcome-ep01"),
        "autoEnter": auto_enter,
        "prefill": bool(cfg.get("prefill", True)),
    }


def google_auth_config() -> dict[str, Any]:
    cfg = (load_platform_config().get("auth") or {}).get("google") or {}
    env_enabled = os.environ.get("STUDIO_GOOGLE_ENABLED")
    if env_enabled is not None and str(env_enabled).strip() != "":
        enabled = str(env_enabled).strip().lower() not in ("0", "false", "no", "off")
    else:
        enabled = bool(cfg.get("enabled", True))
    client_id = (
        (os.environ.get("STUDIO_GOOGLE_CLIENT_ID") or "").strip()
        or str(cfg.get("clientId") or "").strip()
    )
    return {
        "enabled": enabled and bool(client_id),
        "clientId": client_id,
        "provider": "google",
    }


def auth_payload() -> dict[str, Any]:
    cfg = load_platform_config().get("auth") or {}
    env_required = os.environ.get("STUDIO_AUTH_REQUIRED")
    if env_required is not None and str(env_required).strip() != "":
        required = str(env_required).strip().lower() not in ("0", "false", "no", "off")
    else:
        required = bool(cfg.get("required", True))
    methods = list(cfg.get("methods") or ["password", "register", "phone", "google"])
    return {
        "required": required,
        "client": cfg.get("client") or "WEB",
        "methods": methods,
        "apiBaseUrl": (os.environ.get("API_BASE_URL") or "https://api-app.dtok.io/api/v1").rstrip("/"),
        "demo": demo_auth_config(),
        "google": google_auth_config(),
    }


def pinterest_payload() -> dict[str, Any]:
    cfg = load_platform_config().get("pinterest") or {}
    seed = Path(__file__).resolve().parents[1] / "config" / "pinterest_seed.json"
    return {
        "users": cfg.get("users") or [],
        "boards": cfg.get("boards") or [],
        "categories": cfg.get("categories") or [],
        "seedAvailable": seed.is_file(),
        "enabled": True,
    }


def public_platform_payload() -> dict[str, Any]:
    cfg = load_platform_config()
    product = cfg.get("product") or {}
    return {
        "product": product.get("name") or "OpenMontage Drama Studio",
        "brand": product.get("brand") or "OpenMontage",
        "tagline": product.get("tagline") or "",
        "public_url": os.environ.get(product.get("publicUrlEnv") or "STUDIO_PUBLIC_URL", "")
        or os.environ.get("STUDIO_PUBLIC_URL", ""),
        "defaults": {
            **defaults(),
            "genre": default_genre(),
            "ratio": default_ratio(),
            "visualStyle": default_visual_style(),
            "deepseekBaseUrl": deepseek_base_url(),
            "deepseekModel": deepseek_model(),
            "seedreamModel": seedream_model(),
            "seedanceModel": seedance_model(),
        },
        "genres": genres(),
        "ratios": ratios(),
        "six_steps": six_steps(),
        "pipelineLabels": cfg.get("pipelineLabels") or [],
        "creationSteps": cfg.get("creationSteps") or [],
        "styleCategories": cfg.get("styleCategories") or [],
        "entryCards": cfg.get("entryCards") or [],
        "nav": cfg.get("nav") or [],
        "tools": cfg.get("tools") or [],
        "inspirePrompts": cfg.get("inspirePrompts") or [],
        "challenges": cfg.get("challenges") or [],
        "resources": cfg.get("resources") or [],
        "helpSections": cfg.get("helpSections") or [],
        "splitStages": cfg.get("splitStages") or [],
        "canvasSteps": cfg.get("canvasSteps") or [],
        "pages": cfg.get("pages") or {},
        "seedanceModels": seedance_models(),
        "auth": auth_payload(),
        "i18n": i18n_payload(),
        "pinterest": pinterest_payload(),
    }
