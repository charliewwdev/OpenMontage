"""Media routers: respect Studio image/video backend prefs; ComfyUI preferred in auto when rented."""

from __future__ import annotations

from pathlib import Path


def _secret(name: str, default: str = "") -> str:
    try:
        from settings_store import get_secret

        return (get_secret(name, default) or default or "").strip()
    except Exception:
        return default


def _comfy_image_ok() -> bool:
    try:
        from .comfyui import configured as comfy_ok

        return bool(comfy_ok(capability="image") or comfy_ok())
    except Exception:
        return False


def _comfy_video_ok() -> bool:
    try:
        from .comfyui import configured as comfy_ok

        return bool(comfy_ok(capability="video") or comfy_ok())
    except Exception:
        return False


def _seedream_ok() -> bool:
    try:
        from . import seedream_configured

        return bool(seedream_configured())
    except Exception:
        return False


def _seedance_ok() -> bool:
    try:
        from . import seedance_configured

        return bool(seedance_configured())
    except Exception:
        return False


def image_backend() -> str:
    """Resolve active stills backend.

    Explicit seedream/comfyui is sticky — never silently swap.
    Auto prefers ComfyUI when rented (Chinese Qwen / local), else Seedream.
    """
    preferred = (_secret("STUDIO_IMAGE_BACKEND") or "auto").lower()
    seedream = _seedream_ok()
    comfy = _comfy_image_ok()
    if preferred == "seedream":
        return "seedream" if seedream else "none"
    if preferred == "comfyui":
        return "comfyui" if comfy else "none"
    # auto: rented Comfy first so top-bar Chinese path is not overridden by Seedream/Seedance keys
    if comfy:
        return "comfyui"
    if seedream:
        return "seedream"
    return "none"


def video_backend() -> str:
    """Resolve active video backend.

    Explicit seedance/comfyui is sticky — never silently fall back
    (that caused「选了 ComfyUI 却又跑 Seedance」).
    Auto prefers ComfyUI H3 when rented, else Seedance.
    """
    preferred = (_secret("STUDIO_VIDEO_BACKEND") or "auto").lower()
    seedance = _seedance_ok()
    comfy = _comfy_video_ok()
    if preferred == "seedance":
        return "seedance" if seedance else "none"
    if preferred == "comfyui":
        return "comfyui" if comfy else "none"
    if comfy:
        return "comfyui"
    if seedance:
        return "seedance"
    return "none"


def resolve_video_model(requested: str = "") -> str:
    """Pick the concrete video model id for the active backend."""
    backend = video_backend()
    req = (requested or "").strip()
    if backend == "seedance":
        if req and not req.lower().startswith("comfyui:"):
            return req.split(":", 1)[-1] if req.startswith("seedance:") else req
        return _secret("SEEDANCE_MODEL") or ""
    if backend == "comfyui":
        if req.lower().startswith("comfyui:"):
            return req.split(":", 1)[-1]
        # Ignore Seedance ids when ComfyUI is selected.
        return _secret("COMFYUI_VIDEO_MODEL") or "MiniMax-Hailuo-02 / H3"
    return req


def media_qa_enabled() -> bool:
    raw = (_secret("STUDIO_MEDIA_QA") or "1").strip().lower()
    return raw not in {"0", "false", "off", "no"}


def generate_image(
    *,
    prompt: str,
    ratio: str,
    out_path: Path,
    reference_path: Path | None = None,
    negative_prompt: str | None = None,
    denoise: float | None = None,
) -> Path:
    """Generate stills via the active image backend.

    Explicit ``STUDIO_IMAGE_BACKEND=comfyui|seedream`` is sticky — never silently
    fall back to the other provider (that caused「选了 ComfyUI 却打到 Seedream」).
    """
    import logging

    preferred = (_secret("STUDIO_IMAGE_BACKEND") or "auto").lower()
    backend = image_backend()
    logging.getLogger("studio.media").info(
        "generate_image preferred=%s resolved=%s out=%s",
        preferred,
        backend,
        out_path.name,
    )
    if backend == "none":
        if preferred == "comfyui":
            raise RuntimeError(
                "顶部已选择 ComfyUI 出图，但租机地址不可用。请检查 COMFYUI_SERVER_URL，勿改用其它后端除非你主动切换。"
            )
        if preferred == "seedream":
            raise RuntimeError(
                "顶部已选择 Seedream 出图，但火山 Key 不可用或欠费。请续费/换 Key，或主动切换到 ComfyUI。"
            )
        raise RuntimeError(
            "未配置出图后端：请在顶部选择 Seedream 或 ComfyUI，并配置对应 Key / 租机地址。"
        )
    # Hard sticky: never call Seedream when user locked ComfyUI (and vice versa).
    if preferred == "comfyui" and backend != "comfyui":
        raise RuntimeError(
            f"顶部已锁定 ComfyUI，拒绝改走 {backend or '其它后端'}。请检查租机地址或在顶部手动切换。"
        )
    if preferred == "seedream" and backend != "seedream":
        raise RuntimeError(
            f"顶部已锁定 Seedream，拒绝改走 {backend or '其它后端'}。请检查火山 Key 或在顶部手动切换。"
        )
    if backend == "seedream":
        from .seedream import generate_image as seedream_generate

        return seedream_generate(
            prompt=prompt,
            ratio=ratio,
            out_path=out_path,
            reference_path=reference_path,
        )
    if backend == "comfyui":
        from .comfyui import ComfyUIError, generate_image as comfy_generate

        try:
            return comfy_generate(
                prompt=prompt,
                ratio=ratio,
                out_path=out_path,
                reference_path=reference_path,
                negative_prompt=negative_prompt,
                denoise=denoise,
            )
        except TypeError:
            # Older signature without negative_prompt / denoise
            try:
                return comfy_generate(
                    prompt=prompt,
                    ratio=ratio,
                    out_path=out_path,
                    reference_path=reference_path,
                    negative_prompt=negative_prompt,
                )
            except TypeError:
                try:
                    return comfy_generate(prompt=prompt, ratio=ratio, out_path=out_path)
                except ComfyUIError as exc:
                    raise RuntimeError(f"{exc}。当前严格使用顶部所选 ComfyUI 出图。") from exc
        except ComfyUIError as exc:
            raise RuntimeError(f"{exc}。当前严格使用顶部所选 ComfyUI 出图。") from exc
    raise RuntimeError(
        "未配置出图后端：请配置火山 Seedream Key，或在「智川云 GPU · ComfyUI」填入租机地址。"
    )


def generate_video_file(
    *,
    prompt: str,
    ratio: str,
    duration: float | int,
    out_path: Path,
    reference_path: Path | None = None,
    resolution: str = "720p",
) -> dict:
    """Sync ComfyUI video generation.

    Caller already chose ComfyUI (e.g. start_shot_video thread). Do not re-resolve
    video_backend() here — a flaky Comfy probe can fall back to Seedance mid-job and
    abort with a false「当前出片后端不是 ComfyUI」.
    """
    from .comfyui import generate_video as comfy_generate

    path = comfy_generate(
        prompt=prompt,
        ratio=ratio,
        duration=duration,
        out_path=out_path,
        reference_path=reference_path,
        resolution=resolution,
    )
    return {
        "backend": "comfyui",
        "path": path,
        "providerTaskId": None,
        "model": "minimax-h3",
        "duration": float(duration),
        "resolution": resolution,
    }
