"""Tests for Scheme F subgraph IR + shot ledger tools."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from lib.pipeline_compile import project_main_chain_patch
from lib.subgraph_validate import validate_subgraph_file
from lib.workflow_expr import bind_params, evaluate, interpolate
from tools.pipeline.shot_job_manager import ShotJobManager
from tools.pipeline.subgraph_validate import SubgraphValidate


def test_all_preset_subgraphs_valid():
    root = PROJECT_ROOT / "workflow_defs" / "subgraphs"
    files = list(root.glob("*.workflow.json"))
    assert len(files) >= 4
    for path in files:
        result = validate_subgraph_file(path)
        assert result["valid"], f"{path.name}: {result['errors']}"


def test_subgraph_validate_tool():
    tool = SubgraphValidate()
    result = tool.execute(
        {"path": str(PROJECT_ROOT / "workflow_defs/subgraphs/keyframe-i2v-qa.workflow.json")}
    )
    assert result.success


def test_workflow_expr():
    ctx = {"shot": {"duration_sec": 4, "shot_intent": "dialogue"}, "critical_count": 2}
    assert interpolate("dur={{shot.duration_sec}}", ctx) == "dur=4"
    assert bind_params({"x": "{{shot.duration_sec}}"}, ctx)["x"] == 4
    assert evaluate("{{critical_count}} > 0", ctx) is True
    assert evaluate("{{critical_count}} > 5", ctx) is False


def test_shot_job_manager_flow(tmp_path):
    ledger_path = tmp_path / "shot_jobs.json"
    storyboard = {
        "version": "1.0",
        "episode_id": "ep01",
        "shots": [
            {
                "id": "ep01_sc01_sh01",
                "scene_id": "ep01_sc01",
                "index": 1,
                "description": "hook",
                "duration_sec": 4,
                "shot_intent": "dialogue",
            }
        ],
    }
    mgr = ShotJobManager()
    created = mgr.execute(
        {
            "operation": "create_from_storyboard",
            "ledger_path": str(ledger_path),
            "storyboard": storyboard,
        }
    )
    assert created.success
    batch = mgr.execute(
        {"operation": "next_batch", "ledger_path": str(ledger_path), "limit": 1}
    )
    assert batch.success
    assert len(batch.data["batch"]) == 1
    job_id = batch.data["batch"][0]["job_id"]
    marked = mgr.execute(
        {
            "operation": "mark",
            "ledger_path": str(ledger_path),
            "job_id": job_id,
            "status": "failed",
            "error": "provider timeout",
        }
    )
    assert marked.success
    resumed = mgr.execute(
        {"operation": "resume_from_failures", "ledger_path": str(ledger_path)}
    )
    assert resumed.success
    assert job_id in resumed.data["resumed"]
    inv = mgr.execute(
        {
            "operation": "invalidate_shot",
            "ledger_path": str(ledger_path),
            "shot_id": "ep01_sc01_sh01",
        }
    )
    assert inv.success


def test_pipeline_compile_reorder_human_gates():
    patched = project_main_chain_patch(
        "short-drama",
        {
            "stages": [
                {"name": "research", "human_approval_default": True},
                {"name": "proposal"},
                {"name": "script"},
                {"name": "episode_breakdown"},
                {"name": "character_bible"},
                {"name": "storyboard"},
                {"name": "assets"},
                {"name": "edit"},
                {"name": "compose"},
                {"name": "publish"},
            ]
        },
    )
    assert patched["stages"][0]["human_approval_default"] is True
