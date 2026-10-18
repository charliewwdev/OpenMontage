"""Image backends. Register a new stills provider here; media.py only looks it up."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Protocol

from .registry import Registry

log = logging.getLogger("studio.media")


def _secret(name: str, default: str = "") -> str:
    try:
        from settings_store import get_secret

        return (get_secret(name, default) or default or "").strip()
    except Exception:
        return default


class ImageBackend(Protocol):
    id: str

    def configured(self) -> bool: ...

    def unavailable_message(self) -> str: ...

    def generate(
        self,
        *,
        prompt: str,
        ratio: str,
        out_path: Path,
        reference_path: Path | None = None,
        negative_prompt: str | None = None,
        denoise: float | None = None,
    ) -> Path: ...


IMAGE_BACKENDS: Registry[ImageBackend] = Registry()


class ComfyImageBackend:
    id = "comfyui"

    def configured(self) -> bool:
        try:
            from .comfyui import configured as comfy_ok

            return bool(comfy_ok(capability="image") or comfy_ok())
        except Exception:
            return False

    def unavailable_message(self) -> str:
        return "顶部已选择 ComfyUI 出图，但租机地址不可用。请检查 COMFYUI_SERVER_URL，勿改用其它后端除非你主动切换。"

    def generate(
        self,
        *,
        prompt: str,
        ratio: str,
        out_path: Path,
        reference_path: Path | None = None,
        negative_prompt: str | None = None,
        denoise: float | None = None,
    ) -> Path:
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


class SeedreamImageBackend:
    id = "seedream"

    def configured(self) -> bool:
        try:
            from . import seedream_configured

            return bool(seedream_configured())
        except Exception:
            return False

    def unavailable_message(self) -> str:
        return "顶部已选择 Seedream 出图，但火山 Key 不可用或欠费。请续费/换 Key，或主动切换到 ComfyUI。"

    def generate(
        self,
        *,
        prompt: str,
        ratio: str,
        out_path: Path,
        reference_path: Path | None = None,
        negative_prompt: str | None = None,
        denoise: float | None = None,
    ) -> Path:
        del negative_prompt, denoise
        from .seedream import generate_image as seedream_generate

        return seedream_generate(
            prompt=prompt,
            ratio=ratio,
            out_path=out_path,
            reference_path=reference_path,
        )


IMAGE_BACKENDS.register(ComfyImageBackend.id, ComfyImageBackend(), priority=20)
IMAGE_BACKENDS.register(SeedreamImageBackend.id, SeedreamImageBackend(), priority=10)


def resolve_image_backend() -> tuple[str, ImageBackend | None]:
    """Sticky preferred id never falls through. Unknown ids follow auto order."""
    preferred = (_secret("STUDIO_IMAGE_BACKEND") or "auto").lower()
    pinned = IMAGE_BACKENDS.get(preferred) if preferred not in {"", "auto"} else None
    if preferred not in {"", "auto"} and pinned is not None:
        return preferred, pinned if pinned.configured() else None
    for backend in IMAGE_BACKENDS.all():
        if backend.configured():
            return preferred, backend
    return preferred, None


def image_backend() -> str:
    _preferred, backend = resolve_image_backend()
    return backend.id if backend is not None else "none"


def generate_image(
    *,
    prompt: str,
    ratio: str,
    out_path: Path,
    reference_path: Path | None = None,
    negative_prompt: str | None = None,
    denoise: float | None = None,
) -> Path:
    preferred, backend = resolve_image_backend()
    log.info(
        "generate_image preferred=%s resolved=%s out=%s",
        preferred,
        backend.id if backend else "none",
        out_path.name,
    )
    if backend is None:
        pinned = IMAGE_BACKENDS.get(preferred)
        if pinned is not None:
            raise RuntimeError(pinned.unavailable_message())
        raise RuntimeError("未配置出图后端：请在顶部选择 Seedream 或 ComfyUI，并配置对应 Key / 租机地址。")
    if (
        preferred not in {"", "auto"}
        and IMAGE_BACKENDS.get(preferred) is not None
        and backend.id != preferred
    ):
        raise RuntimeError(f"顶部已锁定 {preferred}，拒绝改走 {backend.id}。请检查配置或在顶部手动切换。")
    return backend.generate(
        prompt=prompt,
        ratio=ratio,
        out_path=out_path,
        reference_path=reference_path,
        negative_prompt=negative_prompt,
        denoise=denoise,
    )
