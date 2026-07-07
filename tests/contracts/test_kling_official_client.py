"""Contract tests for the Kling official shared client and schema snapshot."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools._kling.client import KlingClient
from tools._kling.errors import KlingAPIError, is_retryable_kling_error
from tools._kling.schemas import DEFAULT_API_BASE_URL


class FakeResponse:
    def __init__(self, data=None, status_code=200, content=b"data", text=""):
        self._data = data if data is not None else {"code": 0}
        self.status_code = status_code
        self.content = content
        self.text = text

    def json(self):
        if isinstance(self._data, Exception):
            raise self._data
        return self._data


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append(("post", url, kwargs))
        return self.responses.pop(0)

    def get(self, url, **kwargs):
        self.calls.append(("get", url, kwargs))
        return self.responses.pop(0)


def test_missing_api_key_header_error(monkeypatch):
    monkeypatch.delenv("KLING_API_KEY", raising=False)
    client = KlingClient(session=FakeSession([]))
    with pytest.raises(KlingAPIError) as exc:
        _ = client.headers
    assert "KLING_API_KEY" in str(exc.value)


def test_headers_use_bearer_api_key(monkeypatch):
    monkeypatch.setenv("KLING_API_KEY", "test-key")
    session = FakeSession([FakeResponse({"code": 0, "data": {"ok": True}})])
    client = KlingClient(session=session)
    client.post("/v1/test", {"prompt": "x"})
    headers = session.calls[0][2]["headers"]
    assert headers["Authorization"] == "Bearer test-key"
    assert headers["Content-Type"] == "application/json"


def test_default_and_env_base_url(monkeypatch):
    monkeypatch.setenv("KLING_API_KEY", "test-key")
    monkeypatch.delenv("KLING_API_BASE_URL", raising=False)
    assert KlingClient().base_url == DEFAULT_API_BASE_URL
    monkeypatch.setenv("KLING_API_BASE_URL", "https://api-beijing.klingai.com")
    assert KlingClient().base_url == "https://api-beijing.klingai.com"


def test_business_error_preserves_code_message_request_id(monkeypatch):
    monkeypatch.setenv("KLING_API_KEY", "test-key")
    session = FakeSession([FakeResponse({"code": 1200, "message": "bad parameter", "request_id": "req-1"})])
    client = KlingClient(session=session, max_retries=0)
    with pytest.raises(KlingAPIError) as exc:
        client.post("/v1/videos/text2video", {})
    assert exc.value.code == 1200
    assert exc.value.message == "bad parameter"
    assert exc.value.request_id == "req-1"


def test_1303_retryable_message_mentions_concurrency(monkeypatch):
    monkeypatch.setenv("KLING_API_KEY", "test-key")
    session = FakeSession([FakeResponse({"code": 1303, "message": "parallel task over resource pack limit"})])
    client = KlingClient(session=session, max_retries=0)
    with pytest.raises(KlingAPIError) as exc:
        client.post("/v1/videos/text2video", {})
    assert is_retryable_kling_error(exc.value)
    assert "并发/资源包限制" in exc.value.message


def test_classic_create_and_poll_parse_result_paths(monkeypatch):
    monkeypatch.setenv("KLING_API_KEY", "test-key")
    session = FakeSession(
        [
            FakeResponse({"code": 0, "data": {"task_id": "task-1"}}),
            FakeResponse(
                {
                    "code": 0,
                    "data": {
                        "task_status": "succeed",
                        "task_result": {"videos": [{"url": "https://example.com/out.mp4"}]},
                    },
                }
            ),
        ]
    )
    client = KlingClient(session=session)
    task_id = client.create_classic_task("/v1/videos/text2video", {"prompt": "x"})
    outputs = client.poll_classic("/v1/videos/text2video", task_id, "videos")
    assert task_id == "task-1"
    assert outputs == [{"url": "https://example.com/out.mp4"}]


def test_turbo_create_and_poll_parse_result_paths(monkeypatch):
    monkeypatch.setenv("KLING_API_KEY", "test-key")
    session = FakeSession(
        [
            FakeResponse({"code": 0, "data": {"id": "turbo-1"}}),
            FakeResponse(
                {
                    "code": 0,
                    "data": [
                        {
                            "id": "turbo-1",
                            "status": "succeeded",
                            "outputs": [{"url": "https://example.com/out.mp4"}],
                        }
                    ],
                }
            ),
        ]
    )
    client = KlingClient(session=session)
    task_id = client.create_turbo("/text-to-video/kling-3.0-turbo", {"prompt": "x"})
    outputs = client.poll_turbo(task_id)
    assert task_id == "turbo-1"
    assert outputs == [{"url": "https://example.com/out.mp4"}]


def test_schema_snapshot_contains_phase1_contract_fields():
    fixture = PROJECT_ROOT / "tests/fixtures/kling_official/schema_snapshot.json"
    data = json.loads(fixture.read_text())
    assert data["build_id"] == "97344324"
    assert "index-B9E4in0e.js" in data["chunk_names"]
    assert "document-navigation-nxVgwiS5.js" in data["chunk_names"]
    assert data["api_base"]["auth_env"] == "KLING_API_KEY"
    assert data["task_statuses"]["classic"] == ["submitted", "processing", "succeed", "failed"]
    assert data["task_statuses"]["turbo"] == ["submitted", "processing", "succeeded", "failed"]
    assert data["result_paths"]["classic_created_id"] == "data.task_id"
    assert data["result_paths"]["turbo_created_id"] == "data.id"
    assert "kling-v3" in data["models"]["video"]
    assert "kling-v3" in data["models"]["image"]
    assert data["endpoints"]["tts"]["path"] == "/v1/audio/tts"
    assert data["endpoints"]["avatar_image_to_video"]["path"] == "/v1/videos/avatar/image2video"
    assert data["endpoints"]["identify_face"]["path"] == "/v1/videos/identify-face"
    assert data["endpoints"]["advanced_lip_sync"]["path"] == "/v1/videos/advanced-lip-sync"
    assert data["endpoints"]["video_effects"]["path"] == "/v1/videos/effects"
    assert data["result_paths"]["classic_audio_results"] == "data.task_result.audios[]"
    assert data["result_paths"]["identify_face_session"] == "data.session_id"
    assert data["core_field_enums"]["tts_voice_language"] == ["zh", "en"]
    assert data["core_field_enums"]["avatar_mode"] == ["std", "pro"]


def test_optional_live_doc_snapshot_check():
    if os.environ.get("RUN_KLING_DOC_LIVE_CHECK") != "1":
        pytest.skip("Set RUN_KLING_DOC_LIVE_CHECK=1 to compare fixture against current Kling docs HTML.")
    import re
    import urllib.request

    fixture = PROJECT_ROOT / "tests/fixtures/kling_official/schema_snapshot.json"
    expected = json.loads(fixture.read_text())
    with urllib.request.urlopen("https://kling.ai/document-api/api/video/3-0-turbo/text-to-video", timeout=20) as response:
        html = response.read().decode("utf-8", errors="ignore")
    match = re.search(r'<meta name="buildId" content="([^"]+)"', html)
    assert match, "Kling official docs HTML no longer exposes buildId; refresh schema fixture."
    assert match.group(1) == expected["build_id"], "Kling official docs buildId changed; refresh schema fixture before implementation."
