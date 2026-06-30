"""DashScope (Alibaba Cloud Bailian) image generation via Qwen-Image models.

Uses the DashScope-native multimodal-generation endpoint (NOT OpenAI-compatible
mode, which only supports /chat/completions and /embeddings). The response
contains a temporary image URL (valid ~24h) that must be downloaded separately.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    RetryPolicy,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolStatus,
    ToolTier,
)


class DashscopeImage(BaseTool):
    name = "dashscope_image"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "image_generation"
    provider = "dashscope"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = []
    install_instructions = (
        "Set DASHSCOPE_API_KEY to your Alibaba Cloud DashScope API key.\n"
        "  Get one at https://dashscope.aliyun.com/"
    )
    fallback = "grok_image"
    fallback_tools = ["grok_image", "openai_image", "flux_image", "recraft_image"]
    agent_skills = ["dashscope"]

    capabilities = ["generate_image", "text_to_image"]
    supports = {
        "multiple_outputs": True,
        "aspect_ratio": True,
        "resolution": True,
        "negative_prompt": True,
        "seed": True,
    }
    best_for = [
        "high-quality image generation with Qwen-Image models",
        "Chinese-language prompt understanding",
        "cost-effective image generation via Alibaba Cloud",
    ]
    not_good_for = ["offline generation", "image editing (use grok_image edit mode)"]

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {"type": "string"},
            "model": {
                "type": "string",
                "enum": [
                    "qwen-image-2.0-pro",
                    "qwen-image-max",
                    "wan2.7-image",
                    "z-image-turbo",
                ],
                "default": "qwen-image-2.0-pro",
            },
            "size": {
                "type": "string",
                "default": "1024*1024",
                "description": (
                    'Image size as "W*H" (asterisk separator, NOT "x"). '
                    'Examples: "1024*1024", "2048*2048", "2688*1536".'
                ),
            },
            "n": {"type": "integer", "default": 1, "minimum": 1, "maximum": 6},
            "negative_prompt": {
                "type": "string",
                "description": "Negative prompt (max 500 chars). Things to avoid in the image.",
            },
            "prompt_extend": {
                "type": "boolean",
                "default": True,
                "description": "Enable DashScope prompt auto-rewrite for better results.",
            },
            "watermark": {"type": "boolean", "default": False},
            "seed": {"type": "integer", "minimum": 0, "maximum": 2147483647},
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=512, vram_mb=0, disk_mb=100, network_required=True
    )
    retry_policy = RetryPolicy(
        max_retries=2, retryable_errors=["rate_limit", "timeout"]
    )
    idempotency_key_fields = ["prompt", "model", "size", "n"]
    side_effects = [
        "writes image file to output_path",
        "calls DashScope (Alibaba Cloud) image generation API",
    ]
    user_visible_verification = [
        "Inspect generated image for relevance and quality"
    ]

    ENDPOINT = (
        "https://dashscope.aliyuncs.com/api/v1/services/aigc/"
        "multimodal-generation/generation"
    )

    def get_status(self) -> ToolStatus:
        if os.environ.get("DASHSCOPE_API_KEY"):
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        # Conservative per-image estimate; DashScope bills per image.
        # Check the DashScope console for actual pricing.
        n = int(inputs.get("n", 1))
        return n * 0.02

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        api_key = os.environ.get("DASHSCOPE_API_KEY")
        if not api_key:
            return ToolResult(
                success=False,
                error="DASHSCOPE_API_KEY not set. " + self.install_instructions,
            )

        import requests

        start = time.time()
        try:
            payload = self._build_payload(inputs)
            response = requests.post(
                self.ENDPOINT,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=180,
            )
            response.raise_for_status()
            data = response.json()

            choices = data.get("output", {}).get("choices", [])
            if not choices:
                return ToolResult(
                    success=False,
                    error="DashScope returned no image choices",
                )

            content = choices[0].get("message", {}).get("content", [])
            if not content:
                return ToolResult(
                    success=False,
                    error="DashScope returned no image content",
                )

            image_url = content[0].get("image")
            if not image_url:
                return ToolResult(
                    success=False,
                    error="DashScope image output missing URL",
                )

            # Download the image from the temporary URL (valid ~24h).
            download = requests.get(image_url, timeout=120)
            download.raise_for_status()

            output_path = Path(
                inputs.get("output_path", "dashscope_image.png")
            )
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(download.content)

            usage = data.get("usage", {})
            n_generated = int(usage.get("image_count", 1))

        except Exception as e:
            return ToolResult(
                success=False,
                error=f"DashScope image generation failed: {self._safe_error(e)}",
            )

        return ToolResult(
            success=True,
            data={
                "provider": "dashscope",
                "model": payload["model"],
                "prompt": inputs["prompt"],
                "size": payload["parameters"]["size"],
                "output": str(output_path),
                "outputs": [str(output_path)],
                "images_generated": n_generated,
                "usage": usage,
            },
            artifacts=[str(output_path)],
            cost_usd=self.estimate_cost(inputs),
            duration_seconds=round(time.time() - start, 2),
            model=payload["model"],
        )

    def _build_payload(self, inputs: dict[str, Any]) -> dict[str, Any]:
        parameters: dict[str, Any] = {
            "size": inputs.get("size", "1024*1024"),
            "n": int(inputs.get("n", 1)),
            "prompt_extend": bool(inputs.get("prompt_extend", True)),
            "watermark": bool(inputs.get("watermark", False)),
        }
        if inputs.get("negative_prompt"):
            parameters["negative_prompt"] = inputs["negative_prompt"]
        if inputs.get("seed") is not None:
            parameters["seed"] = int(inputs["seed"])

        return {
            "model": inputs.get("model", "qwen-image-2.0-pro"),
            "input": {
                "messages": [
                    {
                        "role": "user",
                        "content": [{"text": inputs["prompt"]}],
                    }
                ]
            },
            "parameters": parameters,
        }

    @staticmethod
    def _safe_error(exc: Exception) -> str:
        return str(exc).replace(
            os.environ.get("DASHSCOPE_API_KEY", ""), "[redacted]"
        )
