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
    """Load product config from shipped YAML (image is source of truth).

    Postgres only mirrors a snapshot for ops/backup — never override a newer
    deploy's platform.yaml with a stale PG row.
    """
    path = _resolve_path()
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"invalid platform config at {path}")
    try:
        import pg_backend as _pg
        import time

        if _pg.enabled():
            _pg.upsert_kv(
                "config:platform",
                {"source": str(path), "updatedAt": int(time.time()), "data": data},
            )
    except Exception:
        pass
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


def _secret(name: str, default: str = "") -> str:
    try:
        from settings_store import get_secret

        return get_secret(name, default)
    except Exception:
        return (os.environ.get(name) or default or "").strip()


def deepseek_base_url() -> str:
    return str(
        _secret("DEEPSEEK_BASE_URL")
        or defaults().get("deepseekBaseUrl")
        or "https://api.deepseek.com"
    )


def deepseek_model() -> str:
    return str(_secret("DEEPSEEK_MODEL") or defaults().get("deepseekModel") or "deepseek-chat")


def seedream_model() -> str:
    return str(_secret("SEEDREAM_MODEL") or defaults().get("seedreamModel") or "")


def seedance_model() -> str:
    return str(_secret("SEEDANCE_MODEL") or defaults().get("seedanceModel") or "")


def seedance_api_url() -> str:
    return str(
        os.environ.get("SEEDANCE_API_URL")
        or defaults().get("seedanceApiUrl")
        or "https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks"
    )


def seedream_models() -> list[dict[str, Any]]:
    models = load_platform_config().get("seedreamModels") or []
    out = [m for m in models if isinstance(m, dict) and m.get("id")]
    if out:
        return out
    # Fallback: single entry from defaults when catalog missing
    mid = seedream_model()
    return [{"id": mid, "name": mid}] if mid else []


def seedance_models() -> list[dict[str, Any]]:
    models = load_platform_config().get("seedanceModels") or []
    return [m for m in models if isinstance(m, dict) and m.get("id")]


def genres() -> list[str]:
    items = load_platform_config().get("genres") or []
    return [str(x) for x in items if str(x).strip()]


def cover_formats() -> list[dict[str, Any]]:
    items = load_platform_config().get("coverFormats") or []
    return [x for x in items if isinstance(x, dict)] if isinstance(items, list) else []


def ratios() -> list[dict[str, Any]]:
    items = load_platform_config().get("ratios") or []
    return [x for x in items if isinstance(x, dict) and x.get("value")]


def six_steps() -> list[dict[str, Any]]:
    items = load_platform_config().get("sixSteps") or []
    return [x for x in items if isinstance(x, dict) and x.get("id")]


def _flatten_locale(data: Any, prefix: str = "", out: dict[str, str] | None = None) -> dict[str, str]:
    """Flatten nested locale trees into module_feature_element keys."""
    result = out if out is not None else {}
    if not isinstance(data, dict):
        return result
    for raw_key, value in data.items():
        part = str(raw_key).replace(".", "_")
        key = f"{prefix}_{part}" if prefix else part
        if isinstance(value, dict):
            _flatten_locale(value, key, result)
        elif value is not None:
            result[key] = str(value)
    return result


def _load_locale_pack(locale: str) -> dict[str, str]:
    root = Path(__file__).resolve().parents[1] / "config" / "locales"
    path = root / f"{locale}.json"
    if not path.is_file():
        return {}
    import json

    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return {}
    # Flat underscore keys, or nested module trees → module_feature_element.
    if any(isinstance(v, dict) for v in data.values()):
        return _flatten_locale(data)
    return {str(k).replace(".", "_"): str(v) for k, v in data.items() if v is not None}


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
    methods = list(cfg.get("methods") or ["password", "google"])
    gate_app = bool(cfg.get("gateApp", False))
    default_nav = str(cfg.get("defaultNav") or "inspire").strip() or "inspire"
    return {
        "required": required,
        "gateApp": gate_app,
        "defaultNav": default_nav,
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


def _llm_providers_public() -> list[dict[str, Any]]:
    try:
        from providers.llm_catalog import LLM_PROVIDERS

        return [
            {
                "id": item["id"],
                "label": item["label"],
                "kind": item["kind"],
                "docs": item.get("docs") or "",
                "placeholder": item.get("placeholder") or "",
                "keyEnv": item.get("keyEnv") or "",
                "baseEnv": item.get("baseEnv") or "",
                "modelEnv": item.get("modelEnv") or "",
                "baseUrl": item.get("defaultBase") or "",
                "model": item.get("defaultModel") or "",
                "configured": False,
            }
            for item in LLM_PROVIDERS
        ]
    except Exception:
        return []


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
        "llmProviders": _llm_providers_public(),

        "genres": genres(),
        "ratios": ratios(),
        "coverFormats": cover_formats(),
        "six_steps": six_steps(),
        "pipelineLabels": cfg.get("pipelineLabels") or [],
        "creationSteps": cfg.get("creationSteps") or [],
        "styleCategories": cfg.get("styleCategories") or [],
        "entryCards": cfg.get("entryCards") or [],
        "nav": cfg.get("nav") or [],
        "tools": cfg.get("tools") or [],
        "inspirePrompts": cfg.get("inspirePrompts") or [],
        "inspirePlatforms": cfg.get("inspirePlatforms") or [],
        "viralScenarios": cfg.get("viralScenarios") or [],
        "challenges": cfg.get("challenges") or [],
        "resources": cfg.get("resources") or [],
        "helpSections": cfg.get("helpSections") or [],
        "splitStages": cfg.get("splitStages") or [],
        "canvasSteps": cfg.get("canvasSteps") or [],
        "pages": cfg.get("pages") or {},
        "skillSources": cfg.get("skillSources") or [],
        "skillCategories": cfg.get("skillCategories") or [],
        "skillTags": cfg.get("skillTags") or [],
        "skillCatalog": cfg.get("skillCatalog") or [],
        "toolHub": cfg.get("toolHub") or {},
        "seedreamModels": seedream_models(),
        "seedanceModels": seedance_models(),
        "auth": auth_payload(),
        "i18n": i18n_payload(),
        "pinterest": pinterest_payload(),
    }
