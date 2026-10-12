"""Structured short-drama visual QA via frame sampling + checklist artifact."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from schemas.artifacts import validate_artifact
from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolStatus,
    ToolTier,
)


class DramaVisualQa(BaseTool):
    name = "drama_visual_qa"
    version = "0.1.0"
    tier = ToolTier.ANALYZE
    capability = "analysis"
    provider = "openmontage"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.LOCAL

    dependencies = ["binary:ffmpeg"]
    install_instructions = "Install ffmpeg (provides frame extraction)."

    capabilities = ["drama_qa", "shot_qa", "episode_qa"]
    best_for = [
        "structured short-drama QA checklists",
        "flagging identity/continuity risks for agent review",
    ]
    not_good_for = [
        "fully automatic multimodal scoring without an agent looking at frames",
    ]
    fallback_tools = ["visual_qa", "frame_sampler"]

    input_schema = {
        "type": "object",
        "required": ["scope"],
        "properties": {
            "scope": {
                "type": "string",
                "enum": ["shot", "scene", "episode", "compose"],
            },
            "video_path": {"type": "string"},
            "image_path": {"type": "string"},
            "episode_id": {"type": "string"},
            "shot_id": {"type": "string"},
            "scene_id": {"type": "string"},
            "character_ids": {
                "type": "array",
                "items": {"type": "string"},
            },
            "output_dir": {"type": "string"},
            "agent_findings": {
                "type": "array",
                "description": "Optional findings supplied by the reviewing agent after inspecting frames",
                "items": {"type": "object"},
            },
            "force_verdict": {
                "type": "string",
                "enum": ["pass", "needs_review", "fail"],
            },
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=256, vram_mb=0, disk_mb=50, network_required=False
    )
    side_effects = ["may write sampled frames under output_dir"]

    def get_status(self) -> ToolStatus:
        try:
            self.check_dependencies()
            return ToolStatus.AVAILABLE
        except Exception:
            return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        start = time.time()
        scope = inputs["scope"]
        sampled: list[str] = []
        findings: list[dict[str, Any]] = []

        video_path = inputs.get("video_path")
        image_path = inputs.get("image_path")
        output_dir = Path(inputs["output_dir"]) if inputs.get("output_dir") else None

        # Heuristic pre-checks (file existence). Rich visual judgment is agent-side.
        media = video_path or image_path
        if media and not Path(media).exists():
            findings.append(
                {
                    "id": "missing_media",
                    "category": "artifact",
                    "severity": "critical",
                    "message": f"Media path missing: {media}",
                    "suggested_action": "regenerate",
                }
            )
        elif media and output_dir and video_path:
            try:
                from tools.analysis.frame_sampler import FrameSampler

                output_dir.mkdir(parents=True, exist_ok=True)
                sample = FrameSampler().execute(
                    {
                        "input_path": video_path,
                        "output_dir": str(output_dir),
                        "strategy": "count",
                        "count": 3,
                    }
                )
                if sample.success:
                    frames = sample.data.get("frames") or sample.data.get("paths") or []
                    if isinstance(frames, list):
                        sampled = [str(f) for f in frames]
                    findings.append(
                        {
                            "id": "frames_ready",
                            "category": "other",
                            "severity": "info",
                            "message": f"Sampled {len(sampled)} frames for agent inspection",
                            "suggested_action": "accept",
                        }
                    )
                else:
                    findings.append(
                        {
                            "id": "sample_failed",
                            "category": "artifact",
                            "severity": "warning",
                            "message": sample.error or "frame sampling failed",
                            "suggested_action": "human_review",
                        }
                    )
            except Exception as exc:
                findings.append(
                    {
                        "id": "sample_error",
                        "category": "artifact",
                        "severity": "warning",
                        "message": str(exc),
                        "suggested_action": "human_review",
                    }
                )

        if inputs.get("character_ids") and not findings:
            findings.append(
                {
                    "id": "identity_check_pending",
                    "category": "identity_drift",
                    "severity": "info",
                    "message": "Agent should compare faces/wardrobe to bible refs on sampled frames",
                    "suggested_action": "human_review",
                }
            )

        for raw in inputs.get("agent_findings") or []:
            findings.append(raw)

        critical = sum(1 for f in findings if f.get("severity") == "critical")
        warning = sum(1 for f in findings if f.get("severity") == "warning")
        if inputs.get("force_verdict"):
            verdict = inputs["force_verdict"]
        elif critical:
            verdict = "fail"
        elif warning:
            verdict = "needs_review"
        else:
            verdict = "pass"

        report = {
            "version": "1.0",
            "scope": scope,
            "episode_id": inputs.get("episode_id"),
            "shot_id": inputs.get("shot_id"),
            "scene_id": inputs.get("scene_id"),
            "findings": findings,
            "verdict": verdict,
            "critical_count": critical,
            "warning_count": warning,
            "sampled_frames": sampled,
        }
        # Drop nulls for schema (optional fields)
        report = {k: v for k, v in report.items() if v is not None}
        try:
            validate_artifact("drama_qa_report", report)
        except Exception as exc:
            return ToolResult(
                success=False,
                error=f"drama_qa_report invalid: {exc}",
                duration_seconds=time.time() - start,
            )

        return ToolResult(
            success=True,
            data={"drama_qa_report": report},
            artifacts=sampled,
            duration_seconds=time.time() - start,
        )
