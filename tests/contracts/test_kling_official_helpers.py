"""Contract tests for Kling official Phase 2 helpers."""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools._kling.account import get_account_costs, reset_account_usage_cache
from tools._kling.client import KlingClient
from tools._kling.elements import (
    get_custom_element,
    list_custom_elements,
    list_preset_elements,
    normalize_element_list,
    write_elements_artifact,
)
from tools.tool_registry import registry


class FakeClient:
    def __init__(self, api_key="fake-key", base_url="https://api.example.test"):
        self.api_key = api_key
        self.base_url = base_url
        self.calls = []

    def get(self, path, params=None):
        self.calls.append((path, params or {}))
        if path.startswith("/v1/general/advanced-custom-elements/"):
            return {"code": 0, "data": {"element_id": 123}}
        if path == "/v1/general/advanced-custom-elements":
            return {"code": 0, "data": [{"element_id": 456}]}
        if path == "/v1/general/advanced-presets-elements":
            return {"code": 0, "data": [{"element_id": 1}]}
        return {"code": 0, "data": {"resource_pack_subscribe_infos": [{"name": "pack-a"}]}}


class FakeResponse:
    status_code = 200

    def json(self):
        return {"code": 0, "data": {"resource_pack_subscribe_infos": [{"name": "pack-a"}]}}


class FakeSession:
    def __init__(self):
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append(("get", url, kwargs))
        return FakeResponse()


def test_elements_helper_normalizes_and_records_metadata(tmp_path):
    assert normalize_element_list([123, {"element_id": "456"}]) == [
        {"element_id": 123},
        {"element_id": 456},
    ]
    artifact = write_elements_artifact(
        tmp_path / "kling_elements.json",
        [{"element_id": 123, "kind": "character", "name": "main-presenter"}],
    )
    data = json.loads(artifact.read_text())
    assert data["provider"] == "kling_official"
    assert data["elements"][0]["element_id"] == 123

    try:
        normalize_element_list([{"name": "missing-id"}])
    except ValueError as exc:
        assert "element_id" in str(exc)
    else:
        raise AssertionError("element_list items without element_id must be rejected")


def test_elements_helper_read_only_endpoints_do_not_enter_registry():
    fake = FakeClient()
    assert get_custom_element(123, client=fake)["data"]["element_id"] == 123
    assert list_custom_elements(client=fake)["data"][0]["element_id"] == 456
    assert list_preset_elements(client=fake)["data"][0]["element_id"] == 1
    assert fake.calls == [
        ("/v1/general/advanced-custom-elements/123", {}),
        ("/v1/general/advanced-custom-elements", {}),
        ("/v1/general/advanced-presets-elements", {}),
    ]
    import tools._kling.elements as elements_module

    assert not hasattr(elements_module, "create_element")
    assert not hasattr(elements_module, "delete_element")

    registry.clear()
    registry.discover("tools")
    assert registry.get("kling_elements") is None
    assert registry.get("kling_account_usage") is None


def test_account_usage_helper_uses_endpoint_cache_and_throttle():
    reset_account_usage_cache()
    fake = FakeClient()
    first = get_account_costs(
        start_time="2026-07-01",
        end_time="2026-07-03",
        client=fake,
        now=100.0,
    )
    second = get_account_costs(
        start_time="2026-07-01",
        end_time="2026-07-03",
        client=fake,
        now=101.0,
    )
    throttled = get_account_costs(
        resource_pack_name="different",
        client=fake,
        now=102.0,
    )

    assert fake.calls == [
        ("/account/costs", {"start_time": "2026-07-01", "end_time": "2026-07-03"})
    ]
    assert first["throttle_status"] == "fresh"
    assert second["cached"] is True
    assert second["throttle_status"] == "cache_hit"
    assert throttled["throttle_status"] == "throttled_no_cache"


def test_account_usage_cache_is_scoped_by_api_identity():
    reset_account_usage_cache()
    first_client = FakeClient(api_key="account-a")
    second_client = FakeClient(api_key="account-b")

    get_account_costs(client=first_client, now=100.0)
    get_account_costs(client=second_client, now=111.0)
    cached = get_account_costs(client=second_client, now=112.0)

    assert first_client.calls == [("/account/costs", {})]
    assert second_client.calls == [("/account/costs", {})]
    assert cached["cached"] is True


def test_account_usage_helper_uses_kling_auth_header(monkeypatch):
    reset_account_usage_cache()
    monkeypatch.setenv("KLING_API_KEY", "test-key")
    session = FakeSession()
    client = KlingClient(session=session, max_retries=0)

    result = get_account_costs(
        start_time="2026-07-01",
        end_time="2026-07-03",
        resource_pack_name="starter",
        client=client,
        now=200.0,
    )

    assert result["resource_pack_subscribe_infos"][0]["name"] == "pack-a"
    method, url, kwargs = session.calls[0]
    assert method == "get"
    assert url.endswith("/account/costs")
    assert kwargs["headers"]["Authorization"] == "Bearer test-key"
    assert kwargs["params"] == {
        "start_time": "2026-07-01",
        "end_time": "2026-07-03",
        "resource_pack_name": "starter",
    }
