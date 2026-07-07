"""Contract tests for the Kling official lip-sync provider."""

from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.avatar.kling_lip_sync import KlingLipSync
from tools.avatar.lip_sync import LipSync
from tools.tool_registry import registry


def test_registry_discovers_kling_lip_sync(monkeypatch):
    monkeypatch.delenv("KLING_API_KEY", raising=False)
    registry.clear()
    registry.discover("tools")
    tool = registry.get("kling_lip_sync")
    assert tool is not None
    assert tool.capability == "avatar"
    assert tool.provider == "kling_official"


def test_lip_sync_schema_and_local_tool_are_distinct():
    tool = KlingLipSync()
    assert "kling-official" in tool.agent_skills
    assert "avatar-video" in tool.agent_skills
    assert tool.runtime.value == "api"
    assert LipSync().provider == "wav2lip"
    assert LipSync().runtime.value == "local_gpu"


def test_identify_face_payload_and_local_video_rejection():
    tool = KlingLipSync()
    request = tool._build_identify_request({"video_url": "https://example.com/source.mp4"})
    assert request["path"] == "/v1/videos/identify-face"
    assert request["payload"] == {"video_url": "https://example.com/source.mp4"}

    try:
        tool._build_identify_request({"video_path": "/tmp/local.mp4"})
    except ValueError as exc:
        assert "local video paths cannot be silently uploaded" in str(exc)
    else:
        raise AssertionError("Local video paths must not be silently uploaded")


def test_advanced_lip_sync_payload_uses_face_and_audio_path(tmp_path):
    audio_path = tmp_path / "voice.mp3"
    audio_path.write_bytes(b"audio")

    request = KlingLipSync()._build_advanced_request(
        {
            "session_id": "session-a",
            "face_id": "face-a",
            "audio_path": str(audio_path),
            "callback_url": "https://example.com/kling/callback",
        }
    )

    assert request["path"] == "/v1/videos/advanced-lip-sync"
    assert request["payload"]["session_id"] == "session-a"
    assert request["payload"]["face_choose"] == [{"face_id": "face-a"}]
    assert request["payload"]["sound_file"] == base64.b64encode(b"audio").decode("ascii")
    assert request["payload"]["callback_url"] == "https://example.com/kling/callback"


def test_identify_face_execute_writes_faces_artifact(monkeypatch, tmp_path):
    class FakeClient:
        def post(self, path, payload):
            assert path == "/v1/videos/identify-face"
            return {
                "code": 0,
                "data": {
                    "session_id": "session-a",
                    "faces": [{"face_id": "face-a", "bbox": [0, 0, 100, 100]}],
                },
            }

    monkeypatch.setenv("KLING_API_KEY", "test-key")
    monkeypatch.setattr("tools.avatar.kling_lip_sync.KlingClient", lambda: FakeClient())

    artifact_path = tmp_path / "faces.json"
    result = KlingLipSync().execute(
        {
            "operation": "identify_face",
            "video_url": "https://example.com/source.mp4",
            "faces_artifact_path": str(artifact_path),
        }
    )

    assert result.success
    assert result.data["session_id"] == "session-a"
    data = json.loads(artifact_path.read_text())
    assert data["provider"] == "kling_official"
    assert data["face_count"] == 1


def test_full_lip_sync_requires_confirmation_for_multiple_faces(monkeypatch, tmp_path):
    class FakeClient:
        def post(self, path, payload):
            return {
                "code": 0,
                "data": {
                    "session_id": "session-a",
                    "faces": [
                        {"face_id": "face-small", "bbox": [0, 0, 50, 50]},
                        {"face_id": "face-large", "bbox": [0, 0, 200, 200]},
                    ],
                },
            }

    monkeypatch.setenv("KLING_API_KEY", "test-key")
    monkeypatch.setattr("tools.avatar.kling_lip_sync.KlingClient", lambda: FakeClient())

    result = KlingLipSync().execute(
        {
            "operation": "full_lip_sync",
            "video_url": "https://example.com/source.mp4",
            "audio_id": "audio-a",
            "faces_artifact_path": str(tmp_path / "faces.json"),
        }
    )

    assert not result.success
    assert result.data["requires_face_selection"] is True
    assert len(result.data["faces"]) == 2
    assert "Multiple faces detected" in result.error
    assert Path(result.artifacts[0]).is_file()


def test_full_lip_sync_auto_selects_largest_face_and_downloads(monkeypatch, tmp_path):
    class FakeClient:
        def post(self, path, payload):
            return {
                "code": 0,
                "data": {
                    "session_id": "session-a",
                    "faces": [
                        {"face_id": "face-small", "bbox": [0, 0, 50, 50]},
                        {"face_id": "face-large", "bbox": [0, 0, 200, 200]},
                    ],
                },
            }

        def create_classic_task(self, path, payload):
            self.path = path
            self.payload = payload
            assert payload["face_choose"] == [{"face_id": "face-large"}]
            return "lip-task-1"

        def poll_classic(self, path, task_id, result_key, timeout_seconds, poll_interval):
            assert result_key == "videos"
            return [{"url": "https://example.com/lip.mp4"}]

        def download(self, url, output_path):
            output_path.write_bytes(b"video")
            return output_path

    monkeypatch.setenv("KLING_API_KEY", "test-key")
    monkeypatch.setattr("tools.avatar.kling_lip_sync.KlingClient", lambda: FakeClient())
    monkeypatch.setattr("tools.avatar.kling_lip_sync.probe_output", lambda path: {"duration_seconds": 4.0})

    result = KlingLipSync().execute(
        {
            "operation": "full_lip_sync",
            "video_url": "https://example.com/source.mp4",
            "audio_id": "audio-a",
            "auto_select_face": True,
            "output_path": str(tmp_path / "lip.mp4"),
        }
    )

    assert result.success
    assert result.data["task_id"] == "lip-task-1"
    assert result.data["face_selection"]["selection_method"] == "auto_selected"
    assert result.data["face_choose"] == [{"face_id": "face-large"}]
    assert Path(result.artifacts[0]).read_bytes() == b"video"
    faces_artifact = next(Path(path) for path in result.artifacts if Path(path).name == "kling_lip_sync_faces.json")
    assert json.loads(faces_artifact.read_text())["selection"]["selection_method"] == "auto_selected"
    assert result.cost_usd > 0


def test_auto_select_face_area_avoids_position_inflation():
    tool = KlingLipSync()
    assert tool._face_area({"bbox": [10, 20, 110, 220]}) == 100 * 200
    assert tool._face_area({"bbox": [10, 20, 100, 200]}) == 90 * 180
    assert tool._face_area({"box": {"width": 80, "height": 90}}) == 80 * 90


def test_advanced_lip_sync_execute_downloads_video(monkeypatch, tmp_path):
    class FakeClient:
        def create_classic_task(self, path, payload):
            assert path == "/v1/videos/advanced-lip-sync"
            assert payload["face_choose"] == [{"face_id": "face-a"}]
            return "lip-task-1"

        def poll_classic(self, path, task_id, result_key, timeout_seconds, poll_interval):
            return [{"video_url": "https://example.com/lip.mp4"}]

        def download(self, url, output_path):
            output_path.write_bytes(b"video")
            return output_path

    monkeypatch.setenv("KLING_API_KEY", "test-key")
    monkeypatch.setattr("tools.avatar.kling_lip_sync.KlingClient", lambda: FakeClient())
    monkeypatch.setattr("tools.avatar.kling_lip_sync.probe_output", lambda path: {"duration_seconds": 4.0})

    result = KlingLipSync().execute(
        {
            "operation": "advanced_lip_sync",
            "session_id": "session-a",
            "face_id": "face-a",
            "audio_id": "audio-a",
            "output_path": str(tmp_path / "lip.mp4"),
        }
    )

    assert result.success
    assert result.data["provider"] == "kling_official"
    assert result.data["task_id"] == "lip-task-1"
    assert result.data["duration_seconds"] == 4.0
    assert result.cost_usd > 0


def test_lip_sync_cost_estimate_is_not_zero():
    tool = KlingLipSync()
    assert tool.estimate_cost({"operation": "identify_face"}) > 0
    assert tool.estimate_cost({"operation": "advanced_lip_sync"}) > tool.estimate_cost({"operation": "identify_face"})
    assert tool.dry_run({"operation": "advanced_lip_sync"})["cost_estimate_confidence"] == "low"
