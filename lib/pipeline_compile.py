"""Compile / project Lab main-chain edits to pipeline manifest structures.

Scheme F layer B: Lab edits stage order, human gates, tools, subgraph_refs
and writes YAML compatible with pipeline_manifest.schema.json.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

from lib.pipeline_loader import load_pipeline


def project_main_chain_patch(
    base_pipeline: str,
    patch: dict[str, Any],
) -> dict[str, Any]:
    """Apply a restricted Lab patch onto a loaded pipeline manifest.

    Supported patch keys:
    - orchestration (budget / wall time / revisions)
    - subgraph_refs (pipeline-level)
    - stages: list of {name, human_approval_default?, checkpoint_required?,
      tools_available?, subgraph_refs?} — order defines stage order;
      unknown stage names raise ValueError; stages omitted from base are dropped
      only if `allow_drop_stages` is true.
    """
    manifest = deepcopy(load_pipeline(base_pipeline))
    if "orchestration" in patch:
        manifest.setdefault("orchestration", {}).update(patch["orchestration"])
    if "subgraph_refs" in patch:
        manifest["subgraph_refs"] = dict(patch["subgraph_refs"])

    if "stages" in patch:
        allow_drop = bool(patch.get("allow_drop_stages", False))
        base_by_name = {s["name"]: s for s in manifest["stages"]}
        new_stages: list[dict[str, Any]] = []
        for entry in patch["stages"]:
            name = entry["name"]
            if name not in base_by_name:
                raise ValueError(
                    f"Unknown stage {name!r}; main-chain compile cannot invent stages. "
                    "Add stages in pipeline_defs or use subgraphs for branching."
                )
            stage = deepcopy(base_by_name[name])
            for key in (
                "human_approval_default",
                "checkpoint_required",
                "tools_available",
                "subgraph_refs",
                "review_focus",
            ):
                if key in entry:
                    stage[key] = entry[key]
            new_stages.append(stage)
        if not allow_drop:
            missing = [s["name"] for s in manifest["stages"] if s["name"] not in {e["name"] for e in patch["stages"]}]
            if missing:
                raise ValueError(
                    f"Patch omits stages {missing}; set allow_drop_stages=true to confirm"
                )
        manifest["stages"] = new_stages

    return manifest


def write_pipeline_override(
    project_dir: Path,
    manifest: dict[str, Any],
    filename: str = "pipeline.override.yaml",
) -> Path:
    project_dir.mkdir(parents=True, exist_ok=True)
    path = project_dir / filename
    with open(path, "w") as f:
        yaml.safe_dump(manifest, f, sort_keys=False, allow_unicode=True)
    return path
