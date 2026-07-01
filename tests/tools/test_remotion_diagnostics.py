"""Tests for Remotion render debuggability in video_compose (issue #217).

Two creator-facing gaps:
  1. A failed `npx remotion render` surfaced only "returned non-zero exit
     status 1"; the useful Remotion diagnostics in stderr were dropped.
  2. There was no pass-through for Remotion's `--timeout`, so a slow headless
     browser setup failed opaquely with no way to raise the limit.
"""

import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.video.video_compose import VideoCompose  # noqa: E402


@pytest.fixture
def tool(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/npx")
    return VideoCompose()


def test_render_failure_surfaces_remotion_stderr_tail(tool, tmp_path, monkeypatch):
    stderr = "some npm noise\nError: Delayed render timed out\nRemotion actual cause here"

    def fake_run_command(cmd, *a, **k):
        raise subprocess.CalledProcessError(returncode=1, cmd=cmd, output="", stderr=stderr)

    monkeypatch.setattr(tool, "run_command", fake_run_command)
    result = tool._remotion_render(
        {"composition_data": {"cuts": []}, "output_path": str(tmp_path / "out.mp4")}
    )

    assert result.success is False
    assert "exit 1" in result.error
    assert "Remotion actual cause here" in result.error


def test_timeout_expired_gives_actionable_message(tool, tmp_path, monkeypatch):
    def fake_run_command(cmd, *a, **k):
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=600)

    monkeypatch.setattr(tool, "run_command", fake_run_command)
    result = tool._remotion_render(
        {"composition_data": {"cuts": []}, "output_path": str(tmp_path / "out.mp4")}
    )

    assert result.success is False
    assert "timed out" in result.error.lower()
    assert "remotion_timeout_ms" in result.error


def test_remotion_timeout_ms_is_passed_through(tool, tmp_path, monkeypatch):
    seen = {}

    def fake_run_command(cmd, *a, **k):
        seen["cmd"] = cmd
        seen["timeout"] = k.get("timeout")
        return None  # output file intentionally absent

    monkeypatch.setattr(tool, "run_command", fake_run_command)
    tool._remotion_render(
        {
            "composition_data": {"cuts": []},
            "output_path": str(tmp_path / "out.mp4"),
            "remotion_timeout_ms": 120000,
        }
    )

    assert "--timeout=120000" in seen["cmd"]
    # subprocess timeout widened past the 120s render budget so run_command
    # does not kill Remotion before its own timeout fires.
    assert seen["timeout"] >= 180


def test_no_timeout_flag_when_not_requested(tool, tmp_path, monkeypatch):
    seen = {}

    def fake_run_command(cmd, *a, **k):
        seen["cmd"] = cmd
        seen["timeout"] = k.get("timeout")
        return None

    monkeypatch.setattr(tool, "run_command", fake_run_command)
    tool._remotion_render(
        {"composition_data": {"cuts": []}, "output_path": str(tmp_path / "out.mp4")}
    )

    assert not any(str(c).startswith("--timeout") for c in seen["cmd"])
    assert seen["timeout"] == 600
