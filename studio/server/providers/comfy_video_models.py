"""ComfyUI video-model strategies.

Add a clip model by registering another ComfyVideoModel. generate_video walks
this registry in priority order and builds the first match — no new elif.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from .registry import Registry


@dataclass
class ComfyVideoContext:
    prompt: str
    width: int
    height: int
    length: int
    seed: int
    image_name: str | None
    root: str
    preferred: str
    end_image_name: str | None = None
    use_turbo: bool = True


class ComfyVideoModel(Protocol):
    id: str

    def match(self, ctx: ComfyVideoContext) -> bool: ...

    def build(self, ctx: ComfyVideoContext) -> tuple[str, dict[str, Any], str]:
        """Return (model_label, workflow, save_node_id)."""
        ...


COMFY_VIDEO_MODELS: Registry[ComfyVideoModel] = Registry()


def register_comfy_video_model(model: ComfyVideoModel, *, priority: int) -> ComfyVideoModel:
    return COMFY_VIDEO_MODELS.register(model.id, model, priority=priority)


def build_comfy_video_workflow(ctx: ComfyVideoContext) -> tuple[str, dict[str, Any], str]:
    from .comfyui import ComfyUIError

    for model in COMFY_VIDEO_MODELS.all():
        if model.match(ctx):
            return model.build(ctx)
    raise ComfyUIError(
        "ComfyUI 已连通，但未发现可用出片模型（需 fl2va UNET + Qwen3-VL + video/audio VAE）。"
        "请使用 MiniMax-H3 / 含 H3 权重的 ComfyUI 镜像。"
    )


def list_ready_video_models(root: str) -> list[str]:
    """Probe which registered video strategies are available on this ComfyUI."""
    ready: list[str] = []
    for model in COMFY_VIDEO_MODELS.all():
        probe = ComfyVideoContext(
            prompt="",
            width=768,
            height=1344,
            length=124,
            seed=0,
            image_name=None,
            root=root,
            preferred="",
        )
        try:
            if model.match(probe):
                ready.append(model.id)
        except Exception:
            continue
    return ready


class _MiniMaxH3:
    id = "minimax-h3"

    def match(self, ctx: ComfyVideoContext) -> bool:
        from .comfyui import _pick_minimax_h3_stack

        preferred = (ctx.preferred or "").lower()
        if preferred and preferred not in {"", "minimax-h3", "h3", "minimax", "minimax-hailuo-02 / h3"}:
            if "h3" not in preferred and "minimax" not in preferred and "fl2va" not in preferred:
                return False
        return _pick_minimax_h3_stack(ctx.root) is not None

    def build(self, ctx: ComfyVideoContext) -> tuple[str, dict[str, Any], str]:
        from .comfyui import (
            ComfyUIError,
            _minimax_h3_workflow,
            _node_exists,
            _pick_minimax_h3_stack,
        )

        stack = _pick_minimax_h3_stack(ctx.root)
        if not stack:
            raise ComfyUIError(
                "ComfyUI 已连通，但未发现 MiniMax H3 出片模型（需 fl2va UNET + Qwen3-VL + video/audio VAE）。"
                "请使用 MiniMax-H3 / 含 H3 权重的 ComfyUI 镜像。"
            )
        use_low_vram = _node_exists(ctx.root, "MiniMaxLowVRAMAttention") and _node_exists(
            ctx.root, "MiniMaxChunkFeedForward"
        )
        if stack.get("turbo") and (
            not ctx.use_turbo or not _node_exists(ctx.root, "MiniMaxH3TurboLoRA")
        ):
            stack = {k: v for k, v in stack.items() if k != "turbo"}
        if not _node_exists(ctx.root, "MiniMaxH3SigmaShift"):
            raise ComfyUIError("ComfyUI 缺少 MiniMaxH3SigmaShift 节点，请升级含 MiniMax H3 的镜像。")

        workflow, save_node = _minimax_h3_workflow(
            prompt=ctx.prompt,
            width=ctx.width,
            height=ctx.height,
            length=ctx.length,
            seed=ctx.seed,
            stack=stack,
            image_name=ctx.image_name,
            end_image_name=ctx.end_image_name,
            use_low_vram=use_low_vram,
        )
        label = stack.get("unet") or self.id
        return label, workflow, save_node


register_comfy_video_model(_MiniMaxH3(), priority=100)
