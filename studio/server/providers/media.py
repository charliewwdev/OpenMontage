"""Media routers: ComfyUI (gpuhome GPU) preferred when configured, else Volc Ark."""

from __future__ import annotations

from pathlib import Path


def image_backend() -> str:
    try:
        from .comfyui import configured as comfy_ok

        if comfy_ok(capability="image") or comfy_ok():
            return "comfyui"
    except Exception:
        pass
    try:
        from . import seedream_configured

        if seedream_configured():
            return "seedream"
    except Exception:
        pass
    return "none"


def video_backend() -> str:
    """Prefer ComfyUI when a server URL is configured; else Seedance."""
    try:
        from .comfyui import configured as comfy_ok

        if comfy_ok(capability="video") or comfy_ok():
            return "comfyui"
    except Exception:
        pass
    try:
        from . import seedance_configured

        if seedance_configured():
            return "seedance"
    except Exception:
        pass
    return "none"


def generate_image(
    *,
    prompt: str,
    ratio: str,
    out_path: Path,
    reference_path: Path | None = None,
) -> Path:
    """Generate stills via the active image backend.

    When ComfyUI is configured it is the **only** image path — no Seedream fallback
    (avoids surprise Ark/Seedream billing or overdue errors after switching to GPU).
    """
    backend = image_backend()
    if backend == "comfyui":
        from .comfyui import ComfyUIError, generate_image as comfy_generate

        try:
            # Comfy T2I ignores reference_path today; still generate a fresh lock.
            return comfy_generate(prompt=prompt, ratio=ratio, out_path=out_path)
        except ComfyUIError as exc:
            raise RuntimeError(
                f"{exc}。"
                "当前出图走 ComfyUI（已不再回退 Seedream）。"
                "请在 ComfyUI 安装带 CLIP 的 SDXL / Qwen-Image 等出图模型；"
                "仅 MiniMax H3 的视频镜像无法生成角色/场景静帧。"
            ) from exc
    if backend == "seedream":
        from .seedream import generate_image as seedream_generate

        return seedream_generate(
            prompt=prompt,
            ratio=ratio,
            out_path=out_path,
            reference_path=reference_path,
        )
    raise RuntimeError(
        "未配置出图后端：请在「智川云 GPU · ComfyUI」填入租机地址（需含出图模型），"
        "或配置火山 Seedream Key。"
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
    """Sync ComfyUI video generation. Raises if ComfyUI is not the active backend."""
    if video_backend() != "comfyui":
        raise RuntimeError("当前出片后端不是 ComfyUI")
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
