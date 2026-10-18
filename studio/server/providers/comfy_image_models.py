"""ComfyUI still-model strategies.

Add a model by registering another ComfyImageModel. generate_image walks this
registry in priority order and builds the first match. It does not grow a new elif.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from .registry import Registry


@dataclass
class ComfyImageContext:
    prompt: str
    negative: str
    width: int
    height: int
    seed: int
    image_name: str | None
    strength: float
    preferred: str
    ckpts: list[str]
    qwen_local: dict[str, str] | None
    qwen_api_ok: bool


class ComfyImageModel(Protocol):
    id: str

    def match(self, ctx: ComfyImageContext) -> bool: ...

    def build(self, ctx: ComfyImageContext) -> tuple[str, dict[str, Any]]: ...


COMFY_IMAGE_MODELS: Registry[ComfyImageModel] = Registry()


def register_comfy_image_model(model: ComfyImageModel, *, priority: int) -> ComfyImageModel:
    return COMFY_IMAGE_MODELS.register(model.id, model, priority=priority)


def build_comfy_image_workflow(ctx: ComfyImageContext) -> tuple[str, dict[str, Any]]:
    from .comfyui import ComfyUIError

    for model in COMFY_IMAGE_MODELS.all():
        if model.match(ctx):
            return model.build(ctx)
    raise ComfyUIError(
        "ComfyUI 已连通，但未发现可用中文出图模型。"
        "当前镜像多为 MiniMax H3 视频权重 + SD1.5，中文角色定妆会漂。"
        "请安装 SDXL（如 RealVisXL），或配置 COMFY_API_KEY 后选择「Qwen Image 3」。"
    )


def _qwen_api_selected(preferred: str) -> bool:
    from .comfyui import _QWEN_API_MODELS

    return preferred in _QWEN_API_MODELS or preferred.startswith("qwen-image")


class _QwenApiExplicit:
    id = "qwen-image-api"

    def match(self, ctx: ComfyImageContext) -> bool:
        return not ctx.image_name and _qwen_api_selected(ctx.preferred)

    def build(self, ctx: ComfyImageContext) -> tuple[str, dict[str, Any]]:
        from .comfyui import (
            ComfyUIError,
            _QWEN_API_MODELS,
            _comfy_org_api_key,
            _is_weak_latin_only_ckpt,
            _qwen_image_api_workflow,
        )

        if not ctx.qwen_api_ok:
            raise ComfyUIError(
                f"已选择 {ctx.preferred}，但 ComfyUI 未安装 QwenImageTextToImageApi 节点（需 Comfy 登录/Partner Nodes）。"
            )
        if not _comfy_org_api_key():
            strong = next((c for c in ctx.ckpts if not _is_weak_latin_only_ckpt(c)), None)
            raise ComfyUIError(
                "已选择 Qwen Image 中文出图，但未配置 COMFY_API_KEY，且租机 ComfyUI 未登录 Partner Nodes。"
                "请到 https://platform.comfy.org 创建 API Key，在设置里保存为 COMFY_API_KEY；"
                "或在 ComfyUI 网页登录后再试。"
                + (f" 临时可在顶部改选本地模型：{strong}。" if strong else "")
            )
        model_label = ctx.preferred if ctx.preferred in _QWEN_API_MODELS else "qwen-image-3.0-pro"
        workflow = _qwen_image_api_workflow(
            prompt=ctx.prompt,
            negative=ctx.negative,
            width=ctx.width,
            height=ctx.height,
            seed=ctx.seed,
            model=model_label,
        )
        return model_label, workflow


class _LocalCheckpoint:
    id = "checkpoint"

    def match(self, ctx: ComfyImageContext) -> bool:
        return bool(ctx.preferred) and ctx.preferred in ctx.ckpts

    def build(self, ctx: ComfyImageContext) -> tuple[str, dict[str, Any]]:
        from .comfyui import _basic_checkpoint_workflow, _translate_prompt_for_latin_clip, _uses_latin_clip

        model_prompt = (
            _translate_prompt_for_latin_clip(ctx.prompt) if _uses_latin_clip(ctx.preferred) else ctx.prompt
        )
        workflow = _basic_checkpoint_workflow(
            prompt=model_prompt,
            negative=ctx.negative,
            width=ctx.width,
            height=ctx.height,
            ckpt=ctx.preferred,
            seed=ctx.seed,
            image_name=ctx.image_name,
            denoise=ctx.strength,
        )
        return ctx.preferred, workflow


class _QwenUnetExplicit:
    id = "qwen-unet"

    def match(self, ctx: ComfyImageContext) -> bool:
        return bool(ctx.preferred and ctx.qwen_local and ctx.preferred == ctx.qwen_local["unet"])

    def build(self, ctx: ComfyImageContext) -> tuple[str, dict[str, Any]]:
        from .comfyui import _qwen_image_workflow

        assert ctx.qwen_local is not None
        workflow = _qwen_image_workflow(
            prompt=ctx.prompt,
            negative=ctx.negative,
            width=ctx.width,
            height=ctx.height,
            unet=ctx.qwen_local["unet"],
            clip=ctx.qwen_local["clip"],
            vae=ctx.qwen_local["vae"],
            seed=ctx.seed,
            image_name=ctx.image_name,
            denoise=ctx.strength,
        )
        return ctx.preferred, workflow


class _QwenApiWhenNoStrongCkpt:
    id = "qwen-image-api-auto"

    def match(self, ctx: ComfyImageContext) -> bool:
        from .comfyui import _comfy_org_api_key, _is_weak_latin_only_ckpt

        weak_only = not ctx.ckpts or all(_is_weak_latin_only_ckpt(c) for c in ctx.ckpts)
        return bool(not ctx.image_name and ctx.qwen_api_ok and _comfy_org_api_key() and weak_only)

    def build(self, ctx: ComfyImageContext) -> tuple[str, dict[str, Any]]:
        from .comfyui import _qwen_image_api_workflow

        model_label = "qwen-image-3.0-pro"
        workflow = _qwen_image_api_workflow(
            prompt=ctx.prompt,
            negative=ctx.negative,
            width=ctx.width,
            height=ctx.height,
            seed=ctx.seed,
            model=model_label,
        )
        return model_label, workflow


class _QwenUnetWhenNoStrongCkpt:
    id = "qwen-unet-auto"

    def match(self, ctx: ComfyImageContext) -> bool:
        from .comfyui import _is_weak_latin_only_ckpt

        weak_only = not ctx.ckpts or all(_is_weak_latin_only_ckpt(c) for c in ctx.ckpts)
        return bool(ctx.qwen_local and weak_only)

    def build(self, ctx: ComfyImageContext) -> tuple[str, dict[str, Any]]:
        from .comfyui import _qwen_image_workflow

        assert ctx.qwen_local is not None
        workflow = _qwen_image_workflow(
            prompt=ctx.prompt,
            negative=ctx.negative,
            width=ctx.width,
            height=ctx.height,
            unet=ctx.qwen_local["unet"],
            clip=ctx.qwen_local["clip"],
            vae=ctx.qwen_local["vae"],
            seed=ctx.seed,
            image_name=ctx.image_name,
            denoise=ctx.strength,
        )
        return ctx.qwen_local["unet"], workflow


class _AnyCheckpoint:
    id = "checkpoint-auto"

    def match(self, ctx: ComfyImageContext) -> bool:
        return bool(ctx.ckpts)

    def build(self, ctx: ComfyImageContext) -> tuple[str, dict[str, Any]]:
        from .comfyui import (
            _basic_checkpoint_workflow,
            _is_weak_latin_only_ckpt,
            _translate_prompt_for_latin_clip,
            _uses_latin_clip,
        )

        ckpt = next((c for c in ctx.ckpts if not _is_weak_latin_only_ckpt(c)), None) or ctx.ckpts[0]
        model_prompt = _translate_prompt_for_latin_clip(ctx.prompt) if _uses_latin_clip(ckpt) else ctx.prompt
        workflow = _basic_checkpoint_workflow(
            prompt=model_prompt,
            negative=ctx.negative,
            width=ctx.width,
            height=ctx.height,
            ckpt=ckpt,
            seed=ctx.seed,
            image_name=ctx.image_name,
            denoise=ctx.strength,
        )
        return ckpt, workflow


class _QwenUnetFallback:
    id = "qwen-unet-fallback"

    def match(self, ctx: ComfyImageContext) -> bool:
        return ctx.qwen_local is not None

    def build(self, ctx: ComfyImageContext) -> tuple[str, dict[str, Any]]:
        from .comfyui import _qwen_image_workflow

        assert ctx.qwen_local is not None
        workflow = _qwen_image_workflow(
            prompt=ctx.prompt,
            negative=ctx.negative,
            width=ctx.width,
            height=ctx.height,
            unet=ctx.qwen_local["unet"],
            clip=ctx.qwen_local["clip"],
            vae=ctx.qwen_local["vae"],
            seed=ctx.seed,
            image_name=ctx.image_name,
            denoise=ctx.strength,
        )
        return ctx.qwen_local["unet"], workflow


class _QwenApiKeyedFallback:
    id = "qwen-image-api-fallback"

    def match(self, ctx: ComfyImageContext) -> bool:
        from .comfyui import _comfy_org_api_key

        return bool(ctx.qwen_api_ok and _comfy_org_api_key())

    def build(self, ctx: ComfyImageContext) -> tuple[str, dict[str, Any]]:
        from .comfyui import _qwen_image_api_workflow

        model_label = "qwen-image-3.0-pro"
        workflow = _qwen_image_api_workflow(
            prompt=ctx.prompt,
            negative=ctx.negative,
            width=ctx.width,
            height=ctx.height,
            seed=ctx.seed,
            model=model_label,
        )
        return model_label, workflow


register_comfy_image_model(_QwenApiExplicit(), priority=100)
register_comfy_image_model(_LocalCheckpoint(), priority=90)
register_comfy_image_model(_QwenUnetExplicit(), priority=80)
register_comfy_image_model(_QwenApiWhenNoStrongCkpt(), priority=70)
register_comfy_image_model(_QwenUnetWhenNoStrongCkpt(), priority=60)
register_comfy_image_model(_AnyCheckpoint(), priority=50)
register_comfy_image_model(_QwenUnetFallback(), priority=40)
register_comfy_image_model(_QwenApiKeyedFallback(), priority=30)
