"""Runway Gen-4 video generation via Runway API.

Highest Elo-rated video generation model — professional quality and control.
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


class RunwayVideo(BaseTool):
    name = "runway_video"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "video_generation"
    provider = "runway"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = []
    install_instructions = (
        "Set RUNWAY_API_KEY to your Runway API key.\n"
        "  Get one at https://app.runwayml.com/settings/api-keys"
    )
    agent_skills = ["ai-video-gen"]

    capabilities = ["text_to_video", "image_to_video"]
    supports = {
        "text_to_video": True,
        "image_to_video": True,
        "professional_control": True,
    }
    best_for = [
        "highest overall video quality (#1 Elo rating)",
        "professional video production",
        "precise control over generation",
    ]
    not_good_for = ["budget projects", "offline generation", "very long clips"]
    fallback_tools = ["kling_video", "veo_video", "minimax_video", "wan_video"]

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {"type": "string"},
            "operation": {
                "type": "string",
                "enum": ["text_to_video", "image_to_video"],
                "default": "text_to_video",
            },
            "model": {
                "type": "string",
                "enum": ["gen4_turbo", "gen4"],
                "default": "gen4_turbo",
            },
            "duration": {
                "type": "integer",
                "enum": [5, 10],
                "default": 5,
                "description": "Duration in seconds",
            },
            "ratio": {
                "type": "string",
                "enum": ["16:9", "9:16", "1:1"],
                "default": "16:9",
            },
            "image_url": {"type": "string", "description": "Reference image URL for image_to_video"},
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=512, vram_mb=0, disk_mb=500, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=2, retryable_errors=["rate_limit", "timeout"])
    idempotency_key_fields = ["prompt", "model", "operation", "duration"]
    side_effects = ["writes video file to output_path", "calls Runway API"]
    user_visible_verification = ["Watch generated clip for visual quality and motion coherence"]

    def get_status(self) -> ToolStatus:
        if os.environ.get("RUNWAY_API_KEY"):
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        duration = inputs.get("duration", 5)
        # Runway charges per second of generated video
        return 0.05 * duration  # ~$0.25 for 5s, ~$0.50 for 10s

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        model = inputs.get("model", "gen4_turbo")
        if "turbo" in model:
            return 30.0
        return 60.0

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        api_key = os.environ.get("RUNWAY_API_KEY")
        if not api_key:
            return ToolResult(
                success=False,
                error="RUNWAY_API_KEY not set. " + self.install_instructions,
            )

        import requests

        start = time.time()
        model = inputs.get("model", "gen4_turbo")
        operation = inputs.get("operation", "text_to_video")

        # Runway API v1 — submit task
        task_payload: dict[str, Any] = {
            "model": model,
            "promptText": inputs["prompt"],
            "duration": inputs.get("duration", 5),
            "ratio": inputs.get("ratio", "16:9"),
        }
        if operation == "image_to_video" and inputs.get("image_url"):
            task_payload["promptImage"] = inputs["image_url"]

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "X-Runway-Version": "2024-11-06",
        }

        try:
            # Submit generation task
            submit_response = requests.post(
                "https://api.dev.runwayml.com/v1/image_to_video" if operation == "image_to_video"
                else "https://api.dev.runwayml.com/v1/text_to_video",
                headers=headers,
                json=task_payload,
                timeout=30,
            )
            submit_response.raise_for_status()
            task_id = submit_response.json()["id"]

            # Poll for completion
            video_url = None
            for _ in range(60):  # max 5 minutes
                time.sleep(5)
                poll_response = requests.get(
                    f"https://api.dev.runwayml.com/v1/tasks/{task_id}",
                    headers=headers,
                    timeout=15,
                )
                poll_response.raise_for_status()
                task_data = poll_response.json()

                if task_data["status"] == "SUCCEEDED":
                    video_url = task_data["output"][0]
                    break
                if task_data["status"] == "FAILED":
                    return ToolResult(
                        success=False,
                        error=f"Runway generation failed: {task_data.get('failure', 'unknown error')}",
                    )

            if not video_url:
                return ToolResult(success=False, error="Runway generation timed out.")

            # Download video
            video_response = requests.get(video_url, timeout=120)
            video_response.raise_for_status()

            output_path = Path(inputs.get("output_path", "runway_output.mp4"))
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(video_response.content)

        except Exception as e:
            return ToolResult(success=False, error=f"Runway video generation failed: {e}")

        return ToolResult(
            success=True,
            data={
                "provider": "runway",
                "model": model,
                "prompt": inputs["prompt"],
                "output": str(output_path),
                "task_id": task_id,
            },
            artifacts=[str(output_path)],
            cost_usd=self.estimate_cost(inputs),
            duration_seconds=round(time.time() - start, 2),
            model=model,
        )
