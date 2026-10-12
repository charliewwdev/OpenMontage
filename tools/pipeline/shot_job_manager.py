"""Shot job ledger queue for short-drama Map runtime (Scheme F light-C)."""

from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from schemas.artifacts import validate_artifact
from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    ResumeSupport,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolStatus,
    ToolTier,
)

_TERMINAL = {"succeeded"}
_ACTIVE = {"pending", "running", "rewriting", "needs_review", "failed"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _recompute_stats(ledger: dict[str, Any]) -> None:
    stats = {
        "pending": 0,
        "running": 0,
        "succeeded": 0,
        "failed": 0,
        "needs_review": 0,
        "rewriting": 0,
        "total_cost_usd": 0.0,
    }
    for job in ledger.get("jobs", []):
        st = job.get("status")
        if st in stats:
            stats[st] += 1
        stats["total_cost_usd"] += float(job.get("cost_usd") or 0)
    ledger["stats"] = stats


def _save(path: Path, ledger: dict[str, Any]) -> None:
    _recompute_stats(ledger)
    validate_artifact("shot_job_ledger", ledger)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(ledger, indent=2))


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


class ShotJobManager(BaseTool):
    name = "shot_job_manager"
    version = "0.1.0"
    tier = ToolTier.CORE
    capability = "pipeline"
    provider = "openmontage"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.LOCAL
    resume_support = ResumeSupport.FROM_CHECKPOINT

    dependencies: list[str] = []
    install_instructions = "Bundled with OpenMontage."

    capabilities = [
        "create_ledger",
        "next_batch",
        "mark_status",
        "invalidate",
        "resume_failures",
        "cost_summary",
        "pause_resume",
    ]
    best_for = [
        "fan-out short-drama shot generation",
        "retry/resume failed I2V jobs",
        "cost tracking per shot",
    ]
    not_good_for = ["replacing Temporal for multi-tenant cloud at scale (v1 is file-ledger)"]

    input_schema = {
        "type": "object",
        "required": ["operation"],
        "properties": {
            "operation": {
                "type": "string",
                "enum": [
                    "create_from_storyboard",
                    "load",
                    "next_batch",
                    "mark",
                    "invalidate_shot",
                    "resume_from_failures",
                    "set_paused",
                    "cost_summary",
                ],
            },
            "ledger_path": {"type": "string"},
            "storyboard": {"type": "object"},
            "episode_id": {"type": "string"},
            "concurrency": {"type": "integer", "default": 3},
            "max_retries": {"type": "integer", "default": 2},
            "default_subgraph_id": {"type": "string", "default": "keyframe-i2v-qa"},
            "provider_fallback_chain": {
                "type": "array",
                "items": {"type": "string"},
            },
            "limit": {"type": "integer", "default": 3},
            "job_id": {"type": "string"},
            "shot_id": {"type": "string"},
            "status": {"type": "string"},
            "provider": {"type": "string"},
            "model": {"type": "string"},
            "cost_usd": {"type": "number"},
            "keyframe_path": {"type": "string"},
            "clip_path": {"type": "string"},
            "error": {"type": "string"},
            "paused": {"type": "boolean"},
            "params": {"type": "object"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=64, vram_mb=0, disk_mb=1, network_required=False
    )
    side_effects = ["writes shot_jobs.json ledger"]

    def get_status(self) -> ToolStatus:
        return ToolStatus.AVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        start = time.time()
        op = inputs["operation"]
        try:
            data = self._dispatch(op, inputs)
            return ToolResult(
                success=True,
                data=data,
                artifacts=[inputs["ledger_path"]] if inputs.get("ledger_path") else [],
                duration_seconds=time.time() - start,
            )
        except Exception as exc:
            return ToolResult(
                success=False,
                error=str(exc),
                duration_seconds=time.time() - start,
            )

    def _dispatch(self, op: str, inputs: dict[str, Any]) -> dict[str, Any]:
        if op == "create_from_storyboard":
            return self._create_from_storyboard(inputs)
        path = Path(inputs["ledger_path"])
        if op == "load":
            ledger = _load(path)
            validate_artifact("shot_job_ledger", ledger)
            return {"ledger": ledger}
        ledger = _load(path)
        if op == "next_batch":
            return self._next_batch(path, ledger, inputs)
        if op == "mark":
            return self._mark(path, ledger, inputs)
        if op == "invalidate_shot":
            return self._invalidate(path, ledger, inputs)
        if op == "resume_from_failures":
            return self._resume_failures(path, ledger)
        if op == "set_paused":
            ledger["paused"] = bool(inputs.get("paused", True))
            _save(path, ledger)
            return {"ledger": ledger}
        if op == "cost_summary":
            _recompute_stats(ledger)
            return {"stats": ledger.get("stats", {}), "jobs": ledger.get("jobs", [])}
        raise ValueError(f"Unknown operation: {op}")

    def _create_from_storyboard(self, inputs: dict[str, Any]) -> dict[str, Any]:
        storyboard = inputs.get("storyboard") or {}
        episode_id = inputs.get("episode_id") or storyboard.get("episode_id")
        if not episode_id:
            raise ValueError("episode_id required")
        path = Path(inputs["ledger_path"])
        jobs = []
        for shot in storyboard.get("shots", []):
            jobs.append(
                {
                    "job_id": f"job_{uuid.uuid4().hex[:10]}",
                    "shot_id": shot["id"],
                    "scene_id": shot.get("scene_id"),
                    "status": "pending",
                    "subgraph_id": shot.get("subgraph_id")
                    or inputs.get("default_subgraph_id", "keyframe-i2v-qa"),
                    "attempt": 0,
                    "cost_usd": 0,
                    "updated_at": _now(),
                    "params": {
                        "duration_sec": shot.get("duration_sec"),
                        "shot_intent": shot.get("shot_intent"),
                        "preferred_provider": shot.get("preferred_provider"),
                    },
                }
            )
        ledger = {
            "version": "1.0",
            "episode_id": episode_id,
            "concurrency": int(inputs.get("concurrency", 3)),
            "max_retries": int(inputs.get("max_retries", 2)),
            "paused": False,
            "default_subgraph_id": inputs.get("default_subgraph_id", "keyframe-i2v-qa"),
            "provider_fallback_chain": inputs.get("provider_fallback_chain")
            or ["seedance", "kling", "minimax"],
            "jobs": jobs,
        }
        _save(path, ledger)
        return {"ledger": ledger, "created": len(jobs)}

    def _next_batch(
        self, path: Path, ledger: dict[str, Any], inputs: dict[str, Any]
    ) -> dict[str, Any]:
        if ledger.get("paused"):
            return {"batch": [], "paused": True, "ledger": ledger}
        limit = int(inputs.get("limit") or ledger.get("concurrency") or 3)
        running = sum(1 for j in ledger["jobs"] if j["status"] == "running")
        slots = max(0, int(ledger.get("concurrency", 3)) - running)
        take = min(limit, slots)
        batch = []
        for job in ledger["jobs"]:
            if take <= 0:
                break
            if job["status"] in ("pending", "rewriting"):
                job["status"] = "running"
                job["updated_at"] = _now()
                batch.append(job)
                take -= 1
        _save(path, ledger)
        return {"batch": batch, "ledger": ledger}

    def _mark(
        self, path: Path, ledger: dict[str, Any], inputs: dict[str, Any]
    ) -> dict[str, Any]:
        job_id = inputs.get("job_id")
        shot_id = inputs.get("shot_id")
        target = None
        for job in ledger["jobs"]:
            if job_id and job["job_id"] == job_id:
                target = job
                break
            if shot_id and job["shot_id"] == shot_id and job["status"] == "running":
                target = job
                break
            if shot_id and job["shot_id"] == shot_id:
                target = job
        if target is None:
            raise ValueError("job not found")
        if "status" in inputs:
            target["status"] = inputs["status"]
        for key in ("provider", "model", "keyframe_path", "clip_path", "error"):
            if key in inputs and inputs[key] is not None:
                target[key] = inputs[key]
        if "cost_usd" in inputs and inputs["cost_usd"] is not None:
            target["cost_usd"] = float(inputs["cost_usd"])
        if "params" in inputs and inputs["params"]:
            target["params"] = {**(target.get("params") or {}), **inputs["params"]}
        if target["status"] == "failed":
            target["attempt"] = int(target.get("attempt") or 0) + 1
            max_retries = int(ledger.get("max_retries", 2))
            if target["attempt"] <= max_retries:
                # stay failed until resume_from_failures or explicit rewriting
                pass
        target["updated_at"] = _now()
        _save(path, ledger)
        return {"job": target, "ledger": ledger}

    def _invalidate(
        self, path: Path, ledger: dict[str, Any], inputs: dict[str, Any]
    ) -> dict[str, Any]:
        shot_id = inputs["shot_id"]
        updated = []
        for job in ledger["jobs"]:
            if job["shot_id"] == shot_id:
                job["status"] = "rewriting"
                job.pop("error", None)
                job["updated_at"] = _now()
                updated.append(job["job_id"])
        if not updated:
            raise ValueError(f"No jobs for shot_id={shot_id}")
        _save(path, ledger)
        return {"invalidated": updated, "ledger": ledger}

    def _resume_failures(self, path: Path, ledger: dict[str, Any]) -> dict[str, Any]:
        max_retries = int(ledger.get("max_retries", 2))
        resumed = []
        for job in ledger["jobs"]:
            if job["status"] == "failed" and int(job.get("attempt") or 0) <= max_retries:
                # rotate provider hint from fallback chain
                chain = ledger.get("provider_fallback_chain") or []
                attempt = int(job.get("attempt") or 0)
                if chain:
                    job.setdefault("params", {})["preferred_provider"] = chain[
                        min(attempt, len(chain) - 1)
                    ]
                job["status"] = "rewriting"
                job["updated_at"] = _now()
                resumed.append(job["job_id"])
        ledger["paused"] = False
        _save(path, ledger)
        return {"resumed": resumed, "ledger": ledger}
