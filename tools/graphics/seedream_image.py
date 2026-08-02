"""Seedream  V5 image generation via fal.ai API.
deep-thinking prompt understanding, native text in 14 languages, and precise control over dense layouts and structured designs.
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
class SeedreamImage(BaseTool):
    name = "seedream_image"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "image_generation"
    provider = "seedream"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = []
    install_instructions = (
        "Set FAL_KEY to your fal.ai API key.\n"
        "  Get one at https://fal.ai/dashboard/keys"
    )
    agent_skills = []

    capabilities = [
        "generate_image",
        "generate_logo",
        "generate_vector",
        "text_to_image",
        "structured_designs",
        "dense_layouts",
        "multi_language_text",
    ]
    supports = {
        "svg_output": True,
        "text_rendering": True,
        "color_palette": True,
        "custom_size": True,
        "structured_designs": True,
        "dense_layouts": True,
        "multi_language_text": True,
    }
    best_for = [
        "logos and brand assets",
        "SVG vector output",
        "images with accurate text rendering",
        "structured designs and dense layouts",
        "multi-language text rendering (14 languages)",
    ]
    
    input_schema = {
            "type": "object",
            "required": ["prompt"],
            "properties": {
                "prompt": {"type": "string"},
                "image_size": {
                    "type": "string",
                    "enum": [
                        "square", "square_hd",
                        "landscape_4_3", "landscape_16_9",
                        "portrait_4_3", "portrait_16_9",
                        "auto_1K","auto_2K"
                    ],
                    "default": "auto_2K",
                },
                "num_images": {
                    "type": "number",
                    "default": 1,
                },
                "output_format": {
                    "type": "string",
                    "enum": ["jpeg", "png"],
                    "description": "Output image format. Use 'jpeg' for smaller file size with lossy compression (suitable for web/preview), or 'png' for lossless quality with transparency support (suitable for design assets and further editing).",
                },
                "enable_safety_checker": {
                    "type": "boolean",
                    "default": True,
                    "description": "If set to true, the safety checker will be enabled.",
                 },
                "enable_safety_checker": {
                    "type": "boolean",
                    "description": "IIf True, the media will be returned as a data URI and the output data won't be available in the request history.",
                 }
            },
        }
    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=512, vram_mb=0, disk_mb=100, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=2, retryable_errors=["rate_limit", "timeout"])
    idempotency_key_fields = ["prompt", "model", "style", "image_size"]
    side_effects = ["writes image file to output_path", "calls fal.ai API"]
    user_visible_verification = ["Inspect generated image for brand accuracy and text readability"]
