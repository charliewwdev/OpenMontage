"""Contract tests for the Kling official E2E smoke script."""

from __future__ import annotations

import importlib.util
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "kling_official_animated_explainer_e2e.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("kling_official_animated_explainer_e2e", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_env_status_redacts_secret_values():
    script = _load_script()

    status = script._env_status(
        {
            "KLING_API_KEY": "secret-token",
            "KLING_API_BASE_URL": "https://api-beijing.klingai.com",
            "FAL_KEY": "",
        }
    )

    assert status["KLING_API_KEY"]["present"] is True
    assert status["KLING_API_KEY"]["display"] == "<set:12 chars>"
    assert "secret-token" not in repr(status)
    assert status["KLING_API_BASE_URL"]["display"] == "https://api-beijing.klingai.com"
    assert status["FAL_KEY"]["present"] is False


def test_cli_modes_are_explicit_and_non_paid_by_default():
    script = _load_script()

    assert script._execution_mode(script._parse_args([])) == "dry_run"
    assert script._execution_mode(script._parse_args(["--live-tts"])) == "live_tts"
    assert script._execution_mode(script._parse_args(["--live-full"])) == "live_full"
    assert script._execution_mode(script._parse_args(["--live"])) == "live_full"


def test_video_duration_aligns_to_narration_within_kling_limits():
    script = _load_script()

    assert script._aligned_video_duration("3", 6.05) == "7"
    assert script._aligned_video_duration("10", 6.05) == "10"
    assert script._aligned_video_duration("3", None) == "3"
    assert script._aligned_video_duration("3", 30.0) == "15"
