"""ComfyUI music generation via a local or remote ComfyUI server.

No bundled workflow: ACE-Step's ComfyUI node interface is not standardized
across custom node packs (``AceStepModelLoader`` vs native
``TextEncodeAceStepAudio``, etc.), so a hardcoded template would break for
most installs. This tool always runs a caller-supplied ``workflow_json`` or
``workflow_path`` -- the same override contract ``comfyui_image``/
``comfyui_video`` offer as an alternative to their bundled workflow, just
mandatory here instead of optional. See the ``comfyui`` skill for how to
convert a community ACE-Step workflow into a call.
"""

from __future__ import annotations

import json
import shutil
import subprocess
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
from tools._comfyui.client import ComfyUIClient, ComfyUIError
from tools._comfyui.metadata import COMFYUI_SETUP_OFFER, workflow_hash


class ComfyUIMusic(BaseTool):
    name = "comfyui_music"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "music_generation"
    provider = "comfyui"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.SEEDED
    runtime = ToolRuntime.LOCAL_GPU

    dependencies = []  # checked at runtime via server health
    setup_offer = COMFYUI_SETUP_OFFER
    install_instructions = (
        "Start a ComfyUI server with ACE-Step installed (any node pack) and "
        "set COMFYUI_SERVER_URL (default http://localhost:8188).\n"
        "There is no bundled workflow for this tool -- export your ACE-Step "
        "graph in API format and pass it as workflow_json/workflow_path.\n"
        "Running a separate ComfyUI instance for music? Set "
        "COMFYUI_MUSIC_SERVER_URL instead -- it takes priority over "
        "COMFYUI_SERVER_URL for this tool only."
    )
    agent_skills = ["comfyui"]

    capabilities = ["generate_background_music", "generate_song", "generate_instrumental"]
    supports = {
        "seed": True,
        "custom_workflow": True,
        "custom_output_node": True,
        "offline": True,
    }
    best_for = [
        "local GPU music generation without API costs, using whatever ACE-Step node pack is installed",
        "full control over sampling via custom ComfyUI workflows",
    ]
    not_good_for = [
        "setups without a running ComfyUI server",
        "quick generation without first exporting/adapting an ACE-Step workflow",
        "CPU-only machines",
    ]
    fallback_tools = ["suno_music", "music_gen"]

    input_schema = {
        "type": "object",
        "required": ["prompt", "output_node"],
        "properties": {
            "prompt": {
                "type": "string",
                "description": (
                    "Description of the desired music, for provenance/logging only. "
                    "Not injected into the workflow -- bake the actual tags/lyrics "
                    "into workflow_json/workflow_path before calling."
                ),
            },
            "seed": {"type": "integer", "description": "Random if omitted"},
            "output_path": {"type": "string", "description": "Where to save the audio"},
            "workflow_json": {
                "type": "string",
                "description": "Full ComfyUI ACE-Step workflow JSON (API format). Required if workflow_path is omitted.",
            },
            "workflow_path": {
                "type": "string",
                "description": "Path to a ComfyUI ACE-Step workflow JSON file. Required if workflow_json is omitted.",
            },
            "output_node": {
                "type": "string",
                "description": "ComfyUI output node ID (e.g. the SaveAudio node) to download the artifact from.",
            },
            "workflow_name": {
                "type": "string",
                "description": "Optional human-readable provenance label for the workflow.",
            },
            "workflow_model": {
                "type": "string",
                "description": "Optional model/provenance label (e.g. 'ace-step-v1-3.5b').",
            },
            "workflow_model_stack": {
                "type": "array",
                "description": (
                    "Optional provenance metadata for workflow dependencies. "
                    "Items should include name, role, and node-pack origin when known."
                ),
                "items": {"type": "object"},
            },
            "timeout_seconds": {
                "type": "integer",
                "description": "How long to wait for the ComfyUI job before giving up. Default 1800s (30min).",
            },
            "resume_prompt_id": {
                "type": "string",
                "description": "A prompt_id from a previous timed-out call. Skips resubmission and resumes waiting/downloading.",
            },
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=2, ram_mb=8000, vram_mb=8000, disk_mb=500, network_required=False,
    )
    retry_policy = RetryPolicy(max_retries=1, retryable_errors=["timeout"])
    idempotency_key_fields = ["prompt", "seed", "workflow_json", "workflow_path", "output_node"]
    side_effects = ["writes audio file to output_path"]
    user_visible_verification = ["Listen to generated audio for mood, genre accuracy, and quality"]

    def __init__(self) -> None:
        self._client = ComfyUIClient(capability="music")
        self._last_progress_log = 0.0

    def get_status(self) -> ToolStatus:
        if not self._client.is_available():
            return ToolStatus.UNAVAILABLE
        return ToolStatus.AVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        # Actual runtime depends entirely on the caller's custom workflow
        # (steps, duration, sampler); this is a conservative flat estimate.
        return 180.0

    def get_info(self) -> dict[str, Any]:
        info = super().get_info()
        info["setup_offer"] = self.setup_offer
        info["bundled_workflow"] = None
        info["custom_workflow_required"] = True
        return info

    def _log_progress(self, data: dict) -> None:
        """Throttled progress line (see comfyui_video for rationale)."""
        now = time.monotonic()
        if now - self._last_progress_log < 10:
            return
        self._last_progress_log = now
        value, max_value = data.get("value"), data.get("max")
        if value is not None and max_value:
            print(f"[comfyui_music] step {value}/{max_value}")

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        if not (inputs.get("workflow_json") or inputs.get("workflow_path")):
            return ToolResult(
                success=False,
                error=(
                    "comfyui_music requires workflow_json or workflow_path -- there "
                    "is no bundled default. ACE-Step's ComfyUI node interface isn't "
                    "standardized across custom node packs, so a hardcoded template "
                    "would break for most installs. Export the ACE-Step workflow "
                    "you actually have installed (API format) and pass it in."
                ),
            )

        if not inputs.get("output_node"):
            return ToolResult(
                success=False,
                error="output_node is required so OpenMontage knows which ComfyUI node to download the audio from.",
            )

        if not self._client.is_available():
            return ToolResult(success=False, error=self._client.unavailable_reason())

        start = time.time()
        seed = inputs.get("seed") or ComfyUIClient.random_seed()
        output_path = Path(inputs.get("output_path", f"comfyui_music_{seed}.mp3"))
        output_node = str(inputs["output_node"])

        try:
            workflow = self._load_custom_workflow(inputs)
            provenance = self._workflow_provenance(inputs, output_node, workflow)
            paths = self._client.generate(
                workflow,
                output_node=output_node,
                dest=output_path,
                timeout=inputs.get("timeout_seconds", 1800),
                interval=10,
                resume_prompt_id=inputs.get("resume_prompt_id"),
                on_progress=self._log_progress,
            )

        except ComfyUIError as exc:
            data = {"prompt_id": exc.prompt_id} if exc.prompt_id else {}
            if exc.prompt_id:
                error_msg = (
                    f"{exc}\n\nThis job was NOT cancelled and is very likely still "
                    f"running server-side. To recover it without resubmitting, call "
                    f"execute() again with resume_prompt_id={exc.prompt_id!r} "
                    f"(and a longer timeout_seconds if it needs more time), or poll "
                    f"GET {{COMFYUI_SERVER_URL}}/history/{exc.prompt_id} directly."
                )
            else:
                error_msg = str(exc)
            return ToolResult(success=False, error=error_msg, data=data)
        except Exception as exc:
            return ToolResult(success=False, error=f"ComfyUI music generation failed: {exc}")

        duration = self._probe_duration(paths[0])
        model_name = self._model_name(inputs)
        return ToolResult(
            success=True,
            data={
                "provider": "comfyui",
                "model": model_name,
                "prompt": inputs["prompt"],
                "duration_seconds": duration,
                "output": str(paths[0]),
                "format": paths[0].suffix.lstrip("."),
                "workflow_provenance": provenance,
            },
            artifacts=[str(p) for p in paths],
            cost_usd=0.0,
            duration_seconds=round(time.time() - start, 2),
            seed=seed,
            model=model_name,
        )

    @staticmethod
    def _load_custom_workflow(inputs: dict[str, Any]) -> dict:
        if inputs.get("workflow_json"):
            return json.loads(inputs["workflow_json"])
        return ComfyUIClient.load_workflow(Path(inputs["workflow_path"]))

    @staticmethod
    def _model_name(inputs: dict[str, Any]) -> str:
        return (
            inputs.get("workflow_model")
            or inputs.get("model")
            or inputs.get("workflow_name")
            or "custom-comfyui-workflow"
        )

    @staticmethod
    def _workflow_provenance(
        inputs: dict[str, Any], output_node: str, workflow: dict[str, Any]
    ) -> dict[str, Any]:
        stack = inputs.get("workflow_model_stack")
        return {
            "source": "user_supplied",
            "workflow_name": inputs.get("workflow_name"),
            "workflow_path": inputs.get("workflow_path"),
            "model": inputs.get("workflow_model") or inputs.get("model"),
            "workflow_hash_sha256": workflow_hash(workflow),
            "model_stack": stack if isinstance(stack, list) else [],
            "model_stack_source": "caller_supplied" if stack else "unknown_custom_workflow",
            "output_node": output_node,
        }

    @staticmethod
    def _probe_duration(path: Path) -> float | None:
        """Best-effort track duration via ffprobe; None if unavailable."""
        if shutil.which("ffprobe") is None:
            return None
        try:
            out = subprocess.run(
                [
                    "ffprobe", "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    str(path),
                ],
                capture_output=True, text=True, timeout=15, check=True,
            )
            value = out.stdout.strip()
            return round(float(value), 2) if value else None
        except (subprocess.SubprocessError, ValueError):
            return None
