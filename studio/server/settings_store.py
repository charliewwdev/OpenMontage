"""Drama Studio secrets store — Postgres is source of truth when DATABASE_URL is set.

Without Postgres (local/dev), falls back to JSON files under PROJECTS_ROOT.
Env vars remain ops bootstrap only (Coolify); UI saves never mutate os.environ.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from providers.llm_catalog import LLM_PROVIDERS, all_secret_envs, provider_by_id

SECRET_KEYS = all_secret_envs()

MASKABLE = frozenset(
    env for item in LLM_PROVIDERS for env in (item.get("keyEnv"),) if env
) | frozenset({"VOLCENGINE_API_KEY", "ARK_API_KEY"})

_projects_root: Path | None = None
_cache: dict[str, str] | None = None
_cache_key: str | None = None


def secrets_path(projects_root: Path | None = None, user_id: str | None = None) -> Path:
    root = projects_root if projects_root is not None else _projects_root
    if root is None:
        raise RuntimeError("secrets store not initialized; call init_secrets() first")
    uid = (user_id or "").strip()
    if not uid:
        try:
            from auth_context import current_user_id

            uid = current_user_id()
        except Exception:
            uid = ""
    if uid and uid not in {".", ".."} and "/" not in uid and "\\" not in uid:
        return Path(root) / ".users" / uid / "secrets.json"
    return Path(root) / ".studio_secrets.json"


def _secrets_rel(path: Path) -> str:
    if _projects_root is None:
        return path.name
    try:
        return str(path.relative_to(_projects_root)).replace("\\", "/")
    except ValueError:
        return path.name


def _kv_key_for_path(path: Path) -> str:
    return f"secrets:{_secrets_rel(path)}"


def _pg_enabled() -> bool:
    try:
        import pg_backend as _pg

        return bool(_pg.enabled())
    except Exception:
        return False


def _invalidate_cache() -> None:
    global _cache, _cache_key
    _cache = None
    _cache_key = None


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


def _normalize_secret_map(data: Any) -> dict[str, str]:
    if not isinstance(data, dict):
        return {}
    out: dict[str, str] = {}
    for key in SECRET_KEYS:
        val = data.get(key)
        if isinstance(val, str) and val.strip():
            out[key] = val.strip()
    return out


def _load_pg_map(path: Path) -> dict[str, str] | None:
    """Load secrets dict from Postgres for *path*; None if missing / PG off."""
    if not _pg_enabled():
        return None
    try:
        import pg_backend as _pg

        hit = _pg.load_kv(_kv_key_for_path(path))
        if isinstance(hit, dict):
            return _normalize_secret_map(hit)
    except Exception:
        return None
    return None


def _write_pg_map(path: Path, data: dict[str, str]) -> None:
    import pg_backend as _pg

    _pg.upsert_kv(_kv_key_for_path(path), data)


def _write_disk_map(path: Path, data: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass


def _read_merged_secrets() -> dict[str, str]:
    """Current-user secrets overlaid on shared instance secrets."""
    global _cache, _cache_key
    if _projects_root is None:
        return {}
    path = secrets_path(_projects_root)
    # Postgres is shared by every uvicorn worker, but this cache is per process.
    # A UI save only clears the worker that handled the request; the other worker
    # kept serving the previous checkpoint to background jobs.
    if _pg_enabled():
        _invalidate_cache()
    cache_key = f"pg:{_pg_enabled()}:{path}"
    if _cache is not None and _cache_key == cache_key:
        return _cache

    loaded: dict[str, str] = {}
    if _pg_enabled():
        shared_path = Path(_projects_root) / ".studio_secrets.json"
        shared = _load_pg_map(shared_path) or {}
        user = _load_pg_map(path) if path != shared_path else {}
        # If user key missing entirely, treat as empty overlay (not disk).
        if user is None:
            user = {}
        loaded = {**shared, **user}
        # One-time migrate: PG empty but disk has data → push disk into PG.
        if not loaded:
            disk_shared = _load_file(shared_path)
            disk_user = _load_file(path) if path != shared_path else {}
            migrated = {**disk_shared, **disk_user}
            if migrated:
                if disk_shared:
                    try:
                        _write_pg_map(shared_path, disk_shared)
                    except Exception:
                        pass
                if disk_user and path != shared_path:
                    try:
                        _write_pg_map(path, disk_user)
                    except Exception:
                        pass
                loaded = migrated
    else:
        loaded = _load_file(path)
        if path.name == "secrets.json":
            shared = Path(_projects_root) / ".studio_secrets.json"
            if shared.is_file() and shared != path:
                merged = dict(_load_file(shared))
                merged.update(loaded)
                loaded = merged

    _cache = loaded
    _cache_key = cache_key
    return loaded


def get_secret(name: str, default: str = "") -> str:
    """Read one secret: Postgres (or file fallback) first, then process env."""
    file_vals = _read_merged_secrets()
    if name in file_vals and file_vals[name]:
        return file_vals[name]
    return (os.environ.get(name) or default or "").strip()


def all_secrets() -> dict[str, str]:
    """Merged view: store values override env for the same key."""
    merged: dict[str, str] = {}
    for key in SECRET_KEYS:
        env_val = (os.environ.get(key) or "").strip()
        if env_val:
            merged[key] = env_val
    merged.update(_read_merged_secrets())
    return merged


def hydrate_secrets_from_pg(projects_root: Path) -> list[str]:
    """No-op when PG is primary — kept for call-site compatibility.

    Historically copied KV → disk; now readers hit Postgres directly.
    Still migrates orphan disk files into PG once if KV is empty.
    """
    restored: list[str] = []
    if not _pg_enabled():
        return restored
    root = Path(projects_root)
    try:
        import pg_backend as _pg

        for key in _pg.list_kv_keys():
            if not str(key).startswith("secrets:"):
                continue
            rel = str(key)[len("secrets:") :]
            if not rel or ".." in Path(rel).parts:
                continue
            data = _pg.load_kv(key)
            if isinstance(data, dict) and data:
                restored.append(rel)
        # Migrate leftover disk secrets into PG when present and KV empty for that path.
        candidates = [root / ".studio_secrets.json"]
        users = root / ".users"
        if users.is_dir():
            for user_dir in users.iterdir():
                if user_dir.is_dir():
                    candidates.append(user_dir / "secrets.json")
        for path in candidates:
            if not path.is_file():
                continue
            disk = _load_file(path)
            if not disk:
                continue
            existing = _load_pg_map(path)
            if existing:
                continue
            try:
                _write_pg_map(path, disk)
                restored.append(str(path.relative_to(root)).replace("\\", "/"))
            except Exception:
                pass
    except Exception:
        pass
    return restored


def init_secrets(projects_root: Path) -> dict[str, str]:
    """Remember projects root. Does not mutate os.environ."""
    global _projects_root
    _projects_root = Path(projects_root)
    hydrate_secrets_from_pg(_projects_root)
    _invalidate_cache()
    return all_secrets()


def load_and_apply(projects_root: Path) -> dict[str, str]:
    return init_secrets(projects_root)


def mask_secret(value: str | None) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:3]}…{value[-4:]}"


def _provider_public(item: dict[str, Any]) -> dict[str, Any]:
    key_env = str(item.get("keyEnv") or "")
    base_env = str(item.get("baseEnv") or "")
    model_env = str(item.get("modelEnv") or "")
    key = get_secret(key_env) if key_env else ""
    base = get_secret(base_env, str(item.get("defaultBase") or ""))
    model = get_secret(model_env, str(item.get("defaultModel") or ""))
    models = item.get("models") or []
    model_ids = [str(m.get("id") or m) for m in models if (m.get("id") if isinstance(m, dict) else m)]
    return {
        "id": item["id"],
        "label": item["label"],
        "kind": item["kind"],
        "configured": bool(key),
        "masked": mask_secret(key) if key else "",
        "baseUrl": base,
        "model": model,
        "models": [
            {"id": str(m["id"]), "label": str(m.get("label") or m["id"])}
            if isinstance(m, dict)
            else {"id": str(m), "label": str(m)}
            for m in models
            if (m.get("id") if isinstance(m, dict) else m)
        ],
        "modelKnown": bool(model) and (not model_ids or model in model_ids),
        "docs": item.get("docs") or "",
        "placeholder": item.get("placeholder") or "sk-...",
        "hint": item.get("hint") or "",
        "keyEnv": key_env,
        "baseEnv": base_env,
        "modelEnv": model_env,
    }


def _comfy_api_key() -> str:
    return (
        get_secret("COMFY_API_KEY")
        or get_secret("COMFYUI_API_KEY")
        or get_secret("COMFY_ORG_API_KEY")
        or ""
    )


def _comfyui_public() -> dict[str, Any]:
    api_key = _comfy_api_key()
    api_meta = {
        "apiKeyConfigured": bool(api_key),
        "apiKeyMasked": mask_secret(api_key) if api_key else "",
    }
    try:
        from providers.comfyui import public_status as comfy_status

        status = comfy_status()
        status.update(api_meta)
        return status
    except Exception:
        return {
            "configured": bool(get_secret("COMFYUI_SERVER_URL")),
            "reachable": False,
            "serverUrl": get_secret("COMFYUI_SERVER_URL") or "",
            "imageUrl": get_secret("COMFYUI_IMAGE_SERVER_URL") or "",
            "videoUrl": get_secret("COMFYUI_VIDEO_SERVER_URL") or "",
            "docs": "https://docs.gpuhome.cc/docs/env/comfyui.html",
            "portsDocs": "https://docs.gpuhome.cc/docs/instance/open-ports.html",
            "market": "https://gpuhome.cc/market",
            "checkpoints": [],
            "checkpoint": get_secret("COMFYUI_CHECKPOINT") or "",
            "videoModels": [],
            "videoModel": get_secret("COMFYUI_VIDEO_MODEL") or "",
            "deviceName": "",
            "error": "",
            "hint": (
                "本机填 http://127.0.0.1:8188；云端可租 gpuhome.cc/market 的 ComfyUI 镜像并开放端口。"
            ),
            **api_meta,
        }


def _image_backend_id(volc_key: str) -> str:
    try:
        from providers.media import image_backend

        return image_backend()
    except Exception:
        pass
    if volc_key:
        return "seedream"
    if get_secret("COMFYUI_SERVER_URL") or get_secret("COMFYUI_IMAGE_SERVER_URL"):
        return "comfyui"
    return "none"


def _video_backend_id(volc_key: str) -> str:
    try:
        from providers.media import video_backend

        return video_backend()
    except Exception:
        pass
    if volc_key:
        return "seedance"
    if get_secret("COMFYUI_SERVER_URL") or get_secret("COMFYUI_VIDEO_SERVER_URL"):
        return "comfyui"
    return "none"


def _studio_image_models(
    volc_key: str,
    active_seedream: str,
    comfy: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Concrete image models from Keys settings (Seedream catalog + Comfy checkpoints)."""
    out: list[dict[str, Any]] = []
    if volc_key:
        try:
            from platform_config import seedream_models

            catalog = seedream_models()
        except Exception:
            catalog = []
        if not catalog and active_seedream:
            catalog = [{"id": active_seedream, "name": active_seedream}]
        seen: set[str] = set()
        for item in catalog:
            mid = str(item.get("id") or "").strip()
            if not mid or mid in seen:
                continue
            seen.add(mid)
            out.append(
                {
                    "id": f"seedream:{mid}",
                    "backend": "seedream",
                    "model": mid,
                    "label": str(item.get("name") or mid),
                    "group": "Seedream",
                }
            )
        if active_seedream and active_seedream not in seen:
            out.append(
                {
                    "id": f"seedream:{active_seedream}",
                    "backend": "seedream",
                    "model": active_seedream,
                    "label": active_seedream,
                    "group": "Seedream",
                }
            )
    comfy = comfy if comfy is not None else _comfyui_public()
    if comfy.get("configured"):
        checkpoints = list(comfy.get("checkpoints") or [])
        preferred = str(comfy.get("checkpoint") or "").strip()
        if preferred and preferred not in checkpoints:
            checkpoints = [preferred, *checkpoints]
        for ckpt in checkpoints:
            name = str(ckpt or "").strip()
            if not name:
                continue
            lower = name.lower()
            if name.startswith("qwen-image"):
                short = f"Qwen Image · {name.replace('qwen-image-', '')}（中文）"
            elif "qwen" in lower:
                short = f"{name.rsplit('/', 1)[-1]}（Qwen）"
            else:
                short = name.rsplit("/", 1)[-1]
            out.append(
                {
                    "id": f"comfyui:{name}",
                    "backend": "comfyui",
                    "model": name,
                    "label": short,
                    "group": "ComfyUI",
                }
            )
    from providers.nvidia_flux import MODELS

    labels = {
        "flux-3-image-klein": "FLUX 3 Image Klein（开源 · 当前可用）",
        "flux.1-schnell": "FLUX.1 schnell（开源）",
        "flux.2-klein-4b": "FLUX.2 klein 4B（开源）",
    }
    for mid in MODELS:
        out.append(
            {
                "id": f"nvidia:{mid}",
                "backend": "nvidia",
                "model": mid,
                "label": labels.get(mid, mid),
                "group": "NVIDIA 开源",
            }
        )
    return out


def _studio_video_models(
    volc_key: str,
    active_seedance: str,
    comfy: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Concrete video models from Keys settings (Seedance catalog + Comfy H3)."""
    out: list[dict[str, Any]] = []
    if volc_key:
        try:
            from platform_config import seedance_models

            catalog = seedance_models()
        except Exception:
            catalog = []
        if not catalog and active_seedance:
            catalog = [{"id": active_seedance, "name": active_seedance}]
        seen: set[str] = set()
        for item in catalog:
            mid = str(item.get("id") or "").strip()
            if not mid or mid in seen:
                continue
            seen.add(mid)
            out.append(
                {
                    "id": f"seedance:{mid}",
                    "backend": "seedance",
                    "model": mid,
                    "label": str(item.get("name") or mid),
                    "group": "Seedance",
                }
            )
        if active_seedance and active_seedance not in seen:
            out.append(
                {
                    "id": f"seedance:{active_seedance}",
                    "backend": "seedance",
                    "model": active_seedance,
                    "label": active_seedance,
                    "group": "Seedance",
                }
            )
    comfy = comfy if comfy is not None else _comfyui_public()
    if comfy.get("configured"):
        video_models = list(comfy.get("videoModels") or [])
        if not video_models and (comfy.get("videoReady") or comfy.get("videoUrl") or comfy.get("serverUrl")):
            video_models = ["MiniMax-Hailuo-02 / H3"]
        for mid in video_models:
            name = str(mid or "").strip()
            if not name:
                continue
            lower = name.lower()
            if "h3" in lower or "hailuo" in lower or "minimax" in lower:
                label = "ComfyUI · MiniMax H3"
            else:
                label = name.rsplit("/", 1)[-1].strip() or name
            out.append(
                {
                    "id": f"comfyui:{name}",
                    "backend": "comfyui",
                    "model": name,
                    "label": label,
                    "group": "ComfyUI",
                }
            )
    return out


def _studio_audio_models() -> list[dict[str, Any]]:
    """Dubbing models for the studio header switcher."""
    out: list[dict[str, Any]] = [
        {
            "id": "edge:multi",
            "backend": "edge",
            "model": "multi",
            "label": "Edge · 按角色分音色",
            "group": "Edge TTS",
        },
        {
            "id": "edge:zh-CN-XiaoxiaoNeural",
            "backend": "edge",
            "model": "zh-CN-XiaoxiaoNeural",
            "label": "Edge · 晓晓",
            "group": "Edge TTS",
        },
        {
            "id": "edge:zh-CN-YunxiNeural",
            "backend": "edge",
            "model": "zh-CN-YunxiNeural",
            "label": "Edge · 云希",
            "group": "Edge TTS",
        },
        {
            "id": "edge:zh-CN-YunjianNeural",
            "backend": "edge",
            "model": "zh-CN-YunjianNeural",
            "label": "Edge · 云健",
            "group": "Edge TTS",
        },
        {
            "id": "edge:zh-CN-XiaoyiNeural",
            "backend": "edge",
            "model": "zh-CN-XiaoyiNeural",
            "label": "Edge · 晓伊",
            "group": "Edge TTS",
        },
    ]
    if get_secret("OPENAI_API_KEY") or get_secret("OPENAI_TTS_API_KEY"):
        active = get_secret("OPENAI_TTS_MODEL") or "gpt-4o-mini-tts"
        seen: set[str] = set()
        for mid, label in (
            (active, f"OpenAI · {active}"),
            ("gpt-4o-mini-tts", "OpenAI · gpt-4o-mini-tts"),
            ("tts-1-hd", "OpenAI · tts-1-hd"),
            ("tts-1", "OpenAI · tts-1"),
        ):
            if not mid or mid in seen:
                continue
            seen.add(mid)
            out.append(
                {
                    "id": f"openai:{mid}",
                    "backend": "openai",
                    "model": mid,
                    "label": label,
                    "group": "OpenAI TTS",
                }
            )
    out.append(
        {
            "id": "indextts:IndexTTS2",
            "backend": "indextts",
            "model": "IndexTTS2",
            "label": "IndexTTS2",
            "group": "IndexTTS",
        }
    )
    return out


def public_status() -> dict[str, Any]:
    providers = [_provider_public(item) for item in LLM_PROVIDERS]
    configured = [p for p in providers if p["configured"]]
    preferred = get_secret("LLM_PROVIDER").lower()
    backend = "none"
    if preferred:
        meta = provider_by_id(preferred)
        if meta and any(p["id"] == preferred and p["configured"] for p in providers):
            backend = preferred
        elif configured:
            backend = configured[0]["id"]
    elif configured:
        try:
            from providers.llm import llm_backend_id

            backend = llm_backend_id()
        except Exception:
            backend = configured[0]["id"]

    deepseek = next((p for p in providers if p["id"] == "deepseek"), None)
    cursor = next((p for p in providers if p["id"] == "cursor"), None)
    volc_key = get_secret("VOLCENGINE_API_KEY") or get_secret("ARK_API_KEY")
    try:
        from platform_config import seedance_model, seedream_model

        seedream = seedream_model()
        seedance = seedance_model()
    except Exception:
        seedream = get_secret("SEEDREAM_MODEL")
        seedance = get_secret("SEEDANCE_MODEL")

    llm_ready = bool(configured)
    comfy = _comfyui_public()
    return {
        "llmProvider": preferred or (backend if backend != "none" else ""),
        "llmProviders": providers,
        "llmReady": llm_ready,
        "llmBackend": backend,
        "deepseek": {
            "configured": bool(deepseek and deepseek["configured"]),
            "masked": (deepseek or {}).get("masked") or "",
            "baseUrl": (deepseek or {}).get("baseUrl") or "",
            "model": (deepseek or {}).get("model") or "",
        },
        "cursor": {
            "configured": bool(cursor and cursor["configured"]),
            "masked": (cursor or {}).get("masked") or "",
            "baseUrl": (cursor or {}).get("baseUrl") or "",
            "model": (cursor or {}).get("model") or "auto",
        },
        "volcengine": {
            "configured": bool(volc_key),
            "masked": mask_secret(volc_key),
            "seedreamModel": seedream,
            "seedanceModel": seedance,
        },
        "nvidia": {
            "configured": bool(get_secret("NVIDIA_API_KEY") or get_secret("NVIDIA_NIM_API_KEY")),
            "masked": mask_secret(get_secret("NVIDIA_API_KEY") or get_secret("NVIDIA_NIM_API_KEY")),
            "model": get_secret("NVIDIA_IMAGE_MODEL") or "flux-3-image-klein",
        },
        "comfyui": comfy,
        "imageBackend": _image_backend_id(volc_key),
        "videoBackend": _video_backend_id(volc_key),
        "imageBackendPref": (get_secret("STUDIO_IMAGE_BACKEND") or "auto").lower() or "auto",
        "videoBackendPref": (get_secret("STUDIO_VIDEO_BACKEND") or "auto").lower() or "auto",
        "ttsBackendPref": (get_secret("STUDIO_TTS_BACKEND") or "auto").lower() or "auto",
        "ttsModel": get_secret("STUDIO_TTS_MODEL") or "",
        "indextts": {
            "configured": bool(get_secret("INDEXTTS_BASE_URL")),
            "baseUrl": get_secret("INDEXTTS_BASE_URL") or "",
        },
        "mediaQa": (get_secret("STUDIO_MEDIA_QA") or "1").strip() not in {"0", "false", "off", "no"},
        "imageBackendsAvailable": [
            *(["seedream"] if volc_key else []),
            *(
                ["nvidia"]
                if (get_secret("NVIDIA_API_KEY") or get_secret("NVIDIA_NIM_API_KEY"))
                else []
            ),
            *(
                ["comfyui"]
                if (get_secret("COMFYUI_SERVER_URL") or get_secret("COMFYUI_IMAGE_SERVER_URL"))
                else []
            ),
        ],
        "videoBackendsAvailable": [
            *(["seedance"] if volc_key else []),
            *(
                ["comfyui"]
                if (get_secret("COMFYUI_SERVER_URL") or get_secret("COMFYUI_VIDEO_SERVER_URL"))
                else []
            ),
        ],
        "seedreamModel": seedream,
        "seedanceModel": seedance,
        "imageModels": _studio_image_models(volc_key, seedream, comfy),
        "videoModels": _studio_video_models(volc_key, seedance, comfy),
        "audioModels": _studio_audio_models(),
        "storage": "postgres" if _pg_enabled() else "disk",
        "ready": llm_ready
        and (
            bool(volc_key)
            or bool(get_secret("COMFYUI_SERVER_URL"))
            or bool(get_secret("COMFYUI_VIDEO_SERVER_URL"))
        ),
    }


def save_secrets(
    projects_root: Path,
    payload: dict[str, Any],
    *,
    user_id: str | None = None,
) -> dict[str, Any]:
    """Persist secrets to Postgres when enabled; otherwise JSON file.

    Pass user_id="" to force the shared instance scope (.studio_secrets.json),
    e.g. Coolify bootstrap restore for all users' env fallback.
    """
    global _projects_root
    _projects_root = Path(projects_root)
    if user_id is not None:
        path = secrets_path(_projects_root, user_id=user_id)
    else:
        path = secrets_path(_projects_root)

    if _pg_enabled():
        current = _load_pg_map(path) or {}
        # Seed from disk once if PG row empty (migration).
        if not current:
            current = _load_file(path)
    else:
        current = _load_file(path)

    for key in SECRET_KEYS:
        if key not in payload:
            continue
        raw = payload.get(key)
        if raw is None:
            continue
        text = str(raw).strip()
        if text == "" or text == "********":
            if text == "":
                current.pop(key, None)
            continue
        if key in MASKABLE and "…" in text and current.get(key):
            continue
        current[key] = text

    if _pg_enabled():
        try:
            _write_pg_map(path, current)
        except Exception as exc:
            # Last-resort disk write if PG fails mid-request.
            _write_disk_map(path, current)
            raise RuntimeError(f"保存密钥到 Postgres 失败: {exc}") from exc
    else:
        _write_disk_map(path, current)

    _invalidate_cache()
    return public_status()
