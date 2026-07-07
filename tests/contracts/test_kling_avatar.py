"""Contract tests for the Kling official avatar provider."""

from __future__ import annotations

import base64
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.avatar.kling_avatar import KlingAvatar
from tools.avatar.talking_head import TalkingHead
from tools.tool_registry import registry


def test_registry_discovers_kling_avatar(monkeypatch):
    monkeypatch.delenv("KLING_API_KEY", raising=False)
    registry.clear()
    registry.discover("tools")
    tool = registry.get("kling_avatar")
    assert tool is not None
    assert tool.capability == "avatar"
    assert tool.provider == "kling_official"


def test_avatar_schema_and_local_tool_are_distinct():
    tool = KlingAvatar()
    assert "anyOf" in tool.input_schema
    assert "allOf" in tool.input_schema
    assert "kling-official" in tool.agent_skills
    assert "avatar-video" in tool.agent_skills
    assert tool.runtime.value == "api"
    assert TalkingHead().provider == "sadtalker"
    assert TalkingHead().runtime.value == "local_gpu"


def test_avatar_payload_uses_image_and_audio_paths(tmp_path):
    image_path = tmp_path / "avatar.png"
    audio_path = tmp_path / "voice.mp3"
    image_path.write_bytes(b"image")
    audio_path.write_bytes(b"audio")

    request = KlingAvatar()._build_request(
        {
            "image_path": str(image_path),
            "audio_path": str(audio_path),
            "prompt": "warm presenter, subtle head motion",
            "mode": "pro",
            "callback_url": "https://example.com/kling/callback",
        }
    )

    assert request["path"] == "/v1/videos/avatar/image2video"
    assert request["payload"]["image"] == base64.b64encode(b"image").decode("ascii")
    assert request["payload"]["sound_file"] == base64.b64encode(b"audio").decode("ascii")
    assert request["payload"]["mode"] == "pro"
    assert request["payload"]["callback_url"] == "https://example.com/kling/callback"
    assert request["audio_source"]["type"] == "sound_file"


def test_avatar_requires_image_and_audio():
    tool = KlingAvatar()
    try:
        tool._build_request({"audio_id": "audio-a"})
    except ValueError as exc:
        assert "image_url or image_path" in str(exc)
    else:
        raise AssertionError("Kling avatar must require an image")

    try:
        tool._build_request({"image_url": "https://example.com/avatar.png"})
    except ValueError as exc:
        assert "requires audio_id" in str(exc)
    else:
        raise AssertionError("Kling avatar must require audio input")


def test_execute_downloads_avatar_video(monkeypatch, tmp_path):
    class FakeClient:
        def create_classic_task(self, path, payload):
            self.path = path
            self.payload = payload
            return "avatar-task-1"

        def poll_classic(self, path, task_id, result_key, timeout_seconds, poll_interval):
            assert result_key == "videos"
            return [{"url": "https://example.com/avatar.mp4"}]

        def download(self, url, output_path):
            output_path.write_bytes(b"video")
            return output_path

    monkeypatch.setenv("KLING_API_KEY", "test-key")
    monkeypatch.setattr("tools.avatar.kling_avatar.KlingClient", lambda: FakeClient())
    monkeypatch.setattr("tools.avatar.kling_avatar.probe_output", lambda path: {"duration_seconds": 5.0})

    result = KlingAvatar().execute(
        {
            "image_url": "https://example.com/avatar.png",
            "audio_id": "audio-a",
            "output_path": str(tmp_path / "avatar.mp4"),
        }
    )

    assert result.success
    assert result.data["provider"] == "kling_official"
    assert result.data["task_id"] == "avatar-task-1"
    assert result.data["duration_seconds"] == 5.0
    assert Path(result.artifacts[0]).read_bytes() == b"video"
    assert result.cost_usd > 0


def test_avatar_cost_estimate_is_not_zero():
    tool = KlingAvatar()
    base = tool.estimate_cost({"image_url": "x", "audio_id": "a"})
    pro = tool.estimate_cost({"image_url": "x", "audio_id": "a", "mode": "pro"})
    assert base > 0
    assert pro > base
    assert tool.dry_run({"image_url": "x", "audio_id": "a"})["cost_estimate_confidence"] == "low"
