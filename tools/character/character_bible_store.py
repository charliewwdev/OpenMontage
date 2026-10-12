"""Persist and load short-drama character bible media + JSON sidecar."""

from __future__ import annotations

import json
import shutil
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


class CharacterBibleStore(BaseTool):
    name = "character_bible_store"
    version = "0.1.0"
    tier = ToolTier.CORE
    capability = "character_animation"
    provider = "openmontage"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.LOCAL

    dependencies: list[str] = []
    install_instructions = "Bundled with OpenMontage."

    capabilities = ["bible_write", "bible_read", "attach_reference"]
    best_for = [
        "persisting short-drama character/location reference packs",
        "binding reference images under projects/<name>/bible/",
    ]

    input_schema = {
        "type": "object",
        "required": ["operation", "project_dir"],
        "properties": {
            "operation": {
                "type": "string",
                "enum": ["write", "read", "attach_reference"],
            },
            "project_dir": {"type": "string"},
            "character_bible": {"type": "object"},
            "character_id": {"type": "string"},
            "location_id": {"type": "string"},
            "source_image": {"type": "string"},
            "label": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=64, vram_mb=0, disk_mb=50, network_required=False
    )
    side_effects = ["writes bible/ directory under project"]

    def get_status(self) -> ToolStatus:
        return ToolStatus.AVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        start = time.time()
        project_dir = Path(inputs["project_dir"])
        bible_dir = project_dir / "bible"
        bible_json = bible_dir / "character_bible.json"
        op = inputs["operation"]
        try:
            if op == "write":
                bible = inputs["character_bible"]
                bible = dict(bible)
                bible["store_path"] = "bible/"
                validate_artifact("character_bible", bible)
                bible_dir.mkdir(parents=True, exist_ok=True)
                bible_json.write_text(json.dumps(bible, indent=2))
                return ToolResult(
                    success=True,
                    data={"character_bible": bible, "path": str(bible_json)},
                    artifacts=[str(bible_json)],
                    duration_seconds=time.time() - start,
                )
            if op == "read":
                if not bible_json.exists():
                    return ToolResult(
                        success=False,
                        error=f"No bible at {bible_json}",
                        duration_seconds=time.time() - start,
                    )
                bible = json.loads(bible_json.read_text())
                validate_artifact("character_bible", bible)
                return ToolResult(
                    success=True,
                    data={"character_bible": bible, "path": str(bible_json)},
                    duration_seconds=time.time() - start,
                )
            if op == "attach_reference":
                source = Path(inputs["source_image"])
                if not source.exists():
                    return ToolResult(
                        success=False,
                        error=f"source_image not found: {source}",
                        duration_seconds=time.time() - start,
                    )
                if not bible_json.exists():
                    return ToolResult(
                        success=False,
                        error="write bible before attach_reference",
                        duration_seconds=time.time() - start,
                    )
                bible = json.loads(bible_json.read_text())
                character_id = inputs.get("character_id")
                location_id = inputs.get("location_id")
                label = inputs.get("label") or source.stem
                dest_dir = bible_dir / "refs"
                dest_dir.mkdir(parents=True, exist_ok=True)
                dest = dest_dir / f"{character_id or location_id or 'ref'}_{label}{source.suffix}"
                shutil.copy2(source, dest)
                rel = str(dest.relative_to(project_dir))
                if character_id:
                    for ch in bible.get("characters", []):
                        if ch["id"] == character_id:
                            refs = list(ch.get("reference_images") or [])
                            refs.append(rel)
                            ch["reference_images"] = refs
                            break
                    else:
                        return ToolResult(
                            success=False,
                            error=f"character_id not found: {character_id}",
                            duration_seconds=time.time() - start,
                        )
                elif location_id:
                    for loc in bible.get("locations", []):
                        if loc["id"] == location_id:
                            refs = list(loc.get("reference_images") or [])
                            refs.append(rel)
                            loc["reference_images"] = refs
                            break
                    else:
                        return ToolResult(
                            success=False,
                            error=f"location_id not found: {location_id}",
                            duration_seconds=time.time() - start,
                        )
                else:
                    return ToolResult(
                        success=False,
                        error="character_id or location_id required",
                        duration_seconds=time.time() - start,
                    )
                validate_artifact("character_bible", bible)
                bible_json.write_text(json.dumps(bible, indent=2))
                return ToolResult(
                    success=True,
                    data={"character_bible": bible, "attached": rel},
                    artifacts=[rel],
                    duration_seconds=time.time() - start,
                )
            return ToolResult(
                success=False,
                error=f"Unknown operation {op}",
                duration_seconds=time.time() - start,
            )
        except Exception as exc:
            return ToolResult(
                success=False,
                error=str(exc),
                duration_seconds=time.time() - start,
            )
