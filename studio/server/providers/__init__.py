"""Model providers for Drama Studio (LLM / Seedream / Seedance)."""

from __future__ import annotations


def _secret(name: str, default: str = "") -> str:
    try:
        from settings_store import get_secret

        return get_secret(name, default)
    except Exception:
        import os

        return (os.environ.get(name) or default or "").strip()


def cursor_configured() -> bool:
    return bool(_secret("CURSOR_API_KEY"))


def deepseek_configured() -> bool:
    """Backward-compat: True when any text LLM is ready (not only DeepSeek)."""
    try:
        from .llm import llm_ready

        return llm_ready()
    except Exception:
        return bool(_secret("DEEPSEEK_API_KEY")) or cursor_configured()


def volc_key() -> str | None:
    return _secret("VOLCENGINE_API_KEY") or _secret("ARK_API_KEY") or None


def comfyui_configured() -> bool:
    try:
        from .comfyui import configured

        return configured()
    except Exception:
        return bool(_secret("COMFYUI_SERVER_URL"))


def seedream_configured() -> bool:
    """Volcengine Seedream specifically (not ComfyUI)."""
    return bool(volc_key())


def image_configured() -> bool:
    """True when an image backend URL/key is configured.

    Prefer ComfyUI when its server URL is set (even if the host is video-only —
    generate_image will then error with a clear “install SDXL/Qwen” message).
    Seedream is only considered when ComfyUI is not configured.
    """
    if comfyui_configured():
        return True
    return seedream_configured()


def _ark_plan_base() -> bool:
    base = (_secret("ARK_API_BASE") or _secret("VOLCENGINE_API_BASE") or "").lower()
    return "/api/plan" in base or (_secret("ARK_PLAN") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
        "agent",
    }


def seedance_configured() -> bool:
    """Seedance video needs a regular Ark key or Agent Plan Large/Max.

    Agent Plan Small/Medium explicitly exclude video generation.
    """
    if not volc_key():
        return False
    if _ark_plan_base():
        tier = (_secret("AGENT_PLAN_TIER") or "small").strip().lower()
        return tier in {"large", "max"}
    return True


def video_configured() -> bool:
    """True when any video backend is ready (ComfyUI GPU or Seedance)."""
    return comfyui_configured() or seedance_configured()


def provider_status() -> dict:
    try:
        from .llm import configured_providers, llm_backend_id, llm_ready

        ready = llm_ready()
        backend = llm_backend_id()
        configured = configured_providers()
    except Exception:
        ready = bool(_secret("DEEPSEEK_API_KEY")) or cursor_configured()
        backend = (
            "deepseek"
            if _secret("DEEPSEEK_API_KEY")
            else ("cursor" if cursor_configured() else "none")
        )
        configured = []
        if _secret("DEEPSEEK_API_KEY"):
            configured.append("deepseek")
        if cursor_configured():
            configured.append("cursor")
    try:
        from .media import image_backend, video_backend

        img_backend = image_backend()
        vid_backend = video_backend()
    except Exception:
        img_backend = "comfyui" if comfyui_configured() else ("seedream" if volc_key() else "none")
        vid_backend = "comfyui" if comfyui_configured() else ("seedance" if seedance_configured() else "none")
    return {
        "deepseek": ready,  # legacy flag: any LLM ready
        "cursor": cursor_configured(),
        "seedream": seedream_configured() or comfyui_configured(),  # legacy: image ready
        "seedance": video_configured(),  # legacy: any video ready (ComfyUI or Seedance)
        "volcengine": bool(volc_key()),
        "comfyui": comfyui_configured(),
        "imageBackend": img_backend,
        "videoBackend": vid_backend,
        "imageReady": image_configured(),
        "videoReady": video_configured(),
        "llmReady": ready,
        "llmBackend": backend,
        "llmProviders": configured,
    }
