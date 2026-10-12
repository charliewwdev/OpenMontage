"""Validate Scheme F subgraph workflow IR files."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from lib.subgraph_validate import validate_subgraph, validate_subgraph_file
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


class SubgraphValidate(BaseTool):
    name = "subgraph_validate"
    version = "0.1.0"
    tier = ToolTier.CORE
    capability = "pipeline"
    provider = "openmontage"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.LOCAL

    dependencies: list[str] = []
    install_instructions = "Bundled with OpenMontage; no extra install."

    capabilities = ["validate_subgraph", "workflow_ir"]
    best_for = [
        "validating Lab-edited subgraph JSON before run",
        "CI checks on workflow_defs/subgraphs",
    ]

    input_schema = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to a .workflow.json file",
            },
            "document": {
                "type": "object",
                "description": "Inline subgraph document (alternative to path)",
            },
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=64, vram_mb=0, disk_mb=0, network_required=False
    )
    side_effects: list[str] = []

    def get_status(self) -> ToolStatus:
        return ToolStatus.AVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        start = time.time()
        path = inputs.get("path")
        document = inputs.get("document")
        if path:
            result = validate_subgraph_file(path)
            ok = result["valid"]
            return ToolResult(
                success=ok,
                data=result,
                error=None if ok else "; ".join(result["errors"]),
                duration_seconds=time.time() - start,
            )
        if document is not None:
            errors = validate_subgraph(document)
            ok = not errors
            return ToolResult(
                success=ok,
                data={"valid": ok, "errors": errors, "id": document.get("id")},
                error=None if ok else "; ".join(errors),
                duration_seconds=time.time() - start,
            )
        return ToolResult(
            success=False,
            error="Provide path or document",
            duration_seconds=time.time() - start,
        )
