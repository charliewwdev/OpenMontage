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


class NvidiaFluxImageBackend:
    id = "nvidia"

    def configured(self) -> bool:
        try:
            from .nvidia_flux import configured as nvidia_ok

            return bool(nvidia_ok())
        except Exception:
            return False

    def unavailable_message(self) -> str:
        return "顶部已选择 NVIDIA 开源出图，但没有 NVIDIA_API_KEY。到 build.nvidia.com 领取试用 Key 后填到密钥设置。"

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
        del denoise
        from .nvidia_flux import NvidiaFluxError, generate_image as nvidia_generate

        try:
            return nvidia_generate(
                prompt=prompt,
                ratio=ratio,
                out_path=out_path,
                reference_path=reference_path,
                negative_prompt=negative_prompt,
            )
        except NvidiaFluxError as exc:
            raise RuntimeError(str(exc)) from exc


class HfImageBackend:
    id = "hf"

    def configured(self) -> bool:
        try:
            from .hf_image import configured as hf_ok

            return bool(hf_ok())
        except Exception:
            return False

    def unavailable_message(self) -> str:
        return "顶部已选择 Hugging Face 出图，但没有 HF_TOKEN。到 huggingface.co/settings/tokens 创建 Token（Inference Providers 小额免费额度）。"

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
        del reference_path, negative_prompt, denoise
        from .hf_image import HfImageError, generate_image as hf_generate

        try:
            return hf_generate(prompt=prompt, ratio=ratio, out_path=out_path)
        except HfImageError as exc:
            raise RuntimeError(str(exc)) from exc


class CloudflareImageBackend:
    id = "cloudflare"

    def configured(self) -> bool:
        try:
            from .cf_image import configured as cf_ok

            return bool(cf_ok())
        except Exception:
            return False

    def unavailable_message(self) -> str:
        return "顶部已选择 Cloudflare Workers AI 出图，但缺少 CF_ACCOUNT_ID / CF_API_TOKEN（免费约 10k Neurons/天）。"

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
        del reference_path, negative_prompt, denoise
        from .cf_image import CfImageError, generate_image as cf_generate

        try:
            return cf_generate(prompt=prompt, ratio=ratio, out_path=out_path)
        except CfImageError as exc:
            raise RuntimeError(str(exc)) from exc


class PollinationsImageBackend:
    id = "pollinations"

    def configured(self) -> bool:
        try:
            from .pollinations_image import configured as pollinations_ok

            return bool(pollinations_ok())
        except Exception:
            return False

    def unavailable_message(self) -> str:
        return "顶部已选择 Pollinations 出图，但 POLLINATIONS_IMAGE=0 已关闭。"

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
        del reference_path, negative_prompt, denoise
        from .pollinations_image import PollinationsImageError, generate_image as pollinations_generate

        try:
            return pollinations_generate(prompt=prompt, ratio=ratio, out_path=out_path)
        except PollinationsImageError as exc:
            raise RuntimeError(str(exc)) from exc


def _free_first_enabled() -> bool:
    return (_secret("STUDIO_FREE_FIRST") or "1").lower() not in {"0", "false", "off", "no"}


def _image_usable(backend: ImageBackend) -> bool:
    if not backend.configured():
        return False
    if getattr(backend, "id", "") == "comfyui":
        try:
            from .comfyui import reachable as comfy_reachable

            return bool(comfy_reachable(capability="image"))
        except Exception:
            return False
    return True


# Free stills first when STUDIO_IMAGE_BACKEND=auto; paid/rented backends after.
IMAGE_BACKENDS.register(NvidiaFluxImageBackend.id, NvidiaFluxImageBackend(), priority=40)
IMAGE_BACKENDS.register(CloudflareImageBackend.id, CloudflareImageBackend(), priority=35)
IMAGE_BACKENDS.register(PollinationsImageBackend.id, PollinationsImageBackend(), priority=33)
IMAGE_BACKENDS.register(HfImageBackend.id, HfImageBackend(), priority=30)
IMAGE_BACKENDS.register(SeedreamImageBackend.id, SeedreamImageBackend(), priority=20)
IMAGE_BACKENDS.register(ComfyImageBackend.id, ComfyImageBackend(), priority=10)


def resolve_image_backend() -> tuple[str, ImageBackend | None]:
    """Prefer free backends. Pinned dead Comfy falls through when STUDIO_FREE_FIRST=1 (default)."""
    preferred = (_secret("STUDIO_IMAGE_BACKEND") or "auto").lower() or "auto"
    free_first = _free_first_enabled()
    pinned = IMAGE_BACKENDS.get(preferred) if preferred not in {"", "auto"} else None
    if preferred not in {"", "auto"} and pinned is not None:
        if _image_usable(pinned):
            return preferred, pinned
        if pinned.configured() and not free_first:
            return preferred, None
        # free-first: unreachable/unusable pin → walk free chain
    for backend in IMAGE_BACKENDS.all():
        if _image_usable(backend):
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
    from github_star import assert_github_star_or_raise

    assert_github_star_or_raise()
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
        raise RuntimeError(
            "未配置出图后端：请配置 NVIDIA / Cloudflare / HF（免费）或 Seedream / ComfyUI；默认 auto 优先免费额度。"
        )
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
