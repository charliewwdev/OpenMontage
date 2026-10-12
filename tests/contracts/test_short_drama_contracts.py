"""Contract tests for the short-drama pipeline (Scheme F main chain)."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from lib.checkpoint import ALL_KNOWN_STAGES, CANONICAL_STAGE_ARTIFACTS
from lib.pipeline_loader import get_stage_order, list_pipelines, load_pipeline
from schemas.artifacts import ARTIFACT_NAMES, validate_artifact


def test_short_drama_listed_and_loads():
    assert "short-drama" in list_pipelines()
    manifest = load_pipeline("short-drama")
    assert manifest["name"] == "short-drama"
    assert manifest["stability"] == "beta"
    assert "shot_generation" in manifest.get("subgraph_refs", {})


def test_short_drama_stage_order():
    manifest = load_pipeline("short-drama")
    assert get_stage_order(manifest) == [
        "research",
        "proposal",
        "script",
        "episode_breakdown",
        "character_bible",
        "storyboard",
        "assets",
        "edit",
        "compose",
        "publish",
    ]


def test_short_drama_skills_exist():
    manifest = load_pipeline("short-drama")
    root = PROJECT_ROOT / "skills"
    for stage in manifest["stages"]:
        skill = stage["skill"]
        path = root / f"{skill}.md"
        assert path.is_file(), f"Missing skill: {path}"
    for req in manifest.get("required_skills", []):
        # required_skills may omit .md and use pipelines/... or meta/...
        path = root / f"{req}.md"
        assert path.is_file(), f"Missing required skill: {path}"


def test_short_drama_artifacts_registered():
    needed = {
        "episode_breakdown",
        "character_bible",
        "storyboard",
        "shot_job_ledger",
        "drama_qa_report",
        "production_metrics",
    }
    assert needed.issubset(set(ARTIFACT_NAMES))
    for stage, artifact in {
        "episode_breakdown": "episode_breakdown",
        "character_bible": "character_bible",
        "storyboard": "storyboard",
    }.items():
        assert stage in ALL_KNOWN_STAGES
        assert CANONICAL_STAGE_ARTIFACTS[stage] == artifact


def test_drama_artifact_schemas_validate_minimal():
    validate_artifact(
        "episode_breakdown",
        {
            "version": "1.0",
            "series_title": "Test Series",
            "episodes": [
                {
                    "id": "ep01",
                    "title": "Ep 1",
                    "scenes": [
                        {"id": "ep01_sc01", "title": "Open", "purpose": "hook"},
                    ],
                }
            ],
            "active_episode_id": "ep01",
        },
    )
    validate_artifact(
        "character_bible",
        {
            "version": "1.0",
            "characters": [
                {
                    "id": "hero",
                    "display_name": "Hero",
                    "role": "protagonist",
                    "appearance": "black jacket, short hair",
                }
            ],
            "store_path": "bible/",
        },
    )
    validate_artifact(
        "storyboard",
        {
            "version": "1.0",
            "episode_id": "ep01",
            "shots": [
                {
                    "id": "ep01_sc01_sh01",
                    "scene_id": "ep01_sc01",
                    "index": 1,
                    "description": "Hero looks at phone",
                    "duration_sec": 4,
                    "shot_intent": "dialogue",
                    "character_ids": ["hero"],
                }
            ],
        },
    )
    validate_artifact(
        "shot_job_ledger",
        {
            "version": "1.0",
            "episode_id": "ep01",
            "jobs": [
                {
                    "job_id": "job_1",
                    "shot_id": "ep01_sc01_sh01",
                    "status": "pending",
                }
            ],
        },
    )
    validate_artifact(
        "drama_qa_report",
        {
            "version": "1.0",
            "scope": "shot",
            "findings": [],
            "verdict": "pass",
            "critical_count": 0,
            "warning_count": 0,
        },
    )
    validate_artifact(
        "production_metrics",
        {
            "version": "1.0",
            "scope": "episode",
            "scope_id": "ep01",
            "metrics": {
                "usable_rate": 1.0,
                "cost_per_minute_usd": 0.5,
                "generation_wall_minutes": 10,
                "rework_rate": 0.0,
                "human_intervention_count": 1,
            },
        },
    )


def test_script_dialogue_extensions_validate():
    validate_artifact(
        "script",
        {
            "version": "1.0",
            "title": "Drama",
            "total_duration_seconds": 60,
            "sections": [
                {
                    "id": "s1",
                    "text": "Line",
                    "start_seconds": 0,
                    "end_seconds": 5,
                }
            ],
            "speakers": [
                {"id": "hero", "display_name": "Hero", "character_bible_id": "hero"}
            ],
            "dialogue_beats": [
                {"id": "d1", "speaker_id": "hero", "text": "Wait."}
            ],
        },
    )
