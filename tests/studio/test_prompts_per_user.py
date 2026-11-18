"""我的提示词 is per user: isolation, anonymous behaviour, legacy rows, both storage backends."""

from __future__ import annotations

import contextvars
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
STUDIO_SERVER = ROOT / "studio" / "server"
if str(STUDIO_SERVER) not in sys.path:
    sys.path.insert(0, str(STUDIO_SERVER))

import asset_library as lib  # noqa: E402
import pg_backend  # noqa: E402
from auth_context import set_current_user  # noqa: E402


def as_user(uid: str | None, fn, *args, **kwargs):
    """Run fn in a fresh context with the given request user (None = anonymous)."""

    def run():
        set_current_user({"userId": uid, "username": uid} if uid else None)
        return fn(*args, **kwargs)

    return contextvars.copy_context().run(run)


class FakeKV:
    def __init__(self):
        self.data: dict[str, object] = {}

    def load_kv(self, key):
        return json.loads(json.dumps(self.data[key])) if key in self.data else None

    def upsert_kv(self, key, value):
        self.data[key] = json.loads(json.dumps(value))


@pytest.fixture(params=["disk", "postgres"])
def backend(request, monkeypatch):
    monkeypatch.setenv("STUDIO_AUTH_REQUIRED", "true")
    monkeypatch.delenv(lib.LEGACY_OWNER_ENV, raising=False)
    if request.param == "disk":
        monkeypatch.setattr(pg_backend, "enabled", lambda: False)
        return None
    kv = FakeKV()
    monkeypatch.setattr(pg_backend, "enabled", lambda: True)
    monkeypatch.setattr(pg_backend, "load_kv", kv.load_kv)
    monkeypatch.setattr(pg_backend, "upsert_kv", kv.upsert_kv)
    return kv


def _seed_legacy(root: Path, kv: FakeKV | None, items: list[dict]) -> None:
    payload = {"items": items}
    if kv is not None:
        kv.upsert_kv(lib.LEGACY_PROMPTS_KEY, payload)
    else:
        path = root / "_library" / "prompts.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")


LEGACY = [{"id": "old-1", "title": "shared", "text": "old shared prompt", "category": "general", "updatedAt": 1}]


def test_users_cannot_see_edit_or_delete_each_others_prompts(tmp_path, backend):
    a = as_user("alice", lib.upsert_prompt, tmp_path, {"title": "A", "text": "alice prompt"})
    assert [x["id"] for x in as_user("alice", lib.list_prompts, tmp_path)] == [a["id"]]
    assert as_user("bob", lib.list_prompts, tmp_path) == []

    # Bob "editing" Alice's id only writes into Bob's own store; Alice's stays as it was.
    b = as_user("bob", lib.upsert_prompt, tmp_path, {"id": a["id"], "text": "hijack"})
    assert as_user("alice", lib.list_prompts, tmp_path)[0]["text"] == "alice prompt"
    assert [x["text"] for x in as_user("bob", lib.list_prompts, tmp_path)] == ["hijack"]

    # Deleting that id as Bob removes only Bob's copy.
    assert as_user("bob", lib.delete_prompt, tmp_path, b["id"]) is True
    assert as_user("bob", lib.delete_prompt, tmp_path, a["id"]) is False
    assert len(as_user("alice", lib.list_prompts, tmp_path)) == 1
    b = as_user("bob", lib.upsert_prompt, tmp_path, {"text": "bob prompt"})

    # Each user edits and deletes their own.
    as_user("alice", lib.upsert_prompt, tmp_path, {"id": a["id"], "text": "alice v2"})
    assert as_user("alice", lib.list_prompts, tmp_path)[0]["text"] == "alice v2"
    assert as_user("bob", lib.delete_prompt, tmp_path, b["id"]) is True
    assert as_user("bob", lib.list_prompts, tmp_path) == []


def test_storage_locations_are_per_user(tmp_path, backend):
    as_user("gh-12345", lib.upsert_prompt, tmp_path, {"text": "github user prompt"})
    if backend is None:
        stored = json.loads((tmp_path / ".users" / "gh-12345" / "prompts.json").read_text(encoding="utf-8"))
    else:
        stored = backend.data["prompts:user:gh-12345"]
        assert lib.LEGACY_PROMPTS_KEY not in backend.data
    assert stored["items"][0]["text"] == "github user prompt"


def test_anonymous_gets_empty_read_only_view_when_login_required(tmp_path, backend):
    _seed_legacy(tmp_path, backend, LEGACY)
    as_user("alice", lib.upsert_prompt, tmp_path, {"text": "alice prompt"})
    assert as_user(None, lib.prompt_scope) is None
    assert as_user(None, lib.list_prompts, tmp_path) == []
    with pytest.raises(lib.PromptAccessError):
        as_user(None, lib.upsert_prompt, tmp_path, {"text": "anon"})
    assert as_user(None, lib.delete_prompt, tmp_path, "old-1") is False
    assert lib.load_legacy_prompts(tmp_path)[0]["id"] == "old-1"


def test_unsafe_user_ids_are_treated_as_anonymous(tmp_path, backend):
    for bad in ("../alice", "a/b", "..", "x\\y"):
        assert as_user(bad, lib.prompt_scope) is None


def test_legacy_shared_prompts_are_kept_but_hidden(tmp_path, backend):
    _seed_legacy(tmp_path, backend, LEGACY)
    assert as_user("alice", lib.list_prompts, tmp_path) == []
    as_user("alice", lib.upsert_prompt, tmp_path, {"text": "new"})
    assert as_user("alice", lib.delete_prompt, tmp_path, "old-1") is False
    # Legacy rows are untouched.
    assert [x["id"] for x in lib.load_legacy_prompts(tmp_path)] == ["old-1"]


def test_legacy_owner_env_copies_legacy_prompts_once(tmp_path, backend, monkeypatch):
    _seed_legacy(tmp_path, backend, LEGACY)
    monkeypatch.setenv(lib.LEGACY_OWNER_ENV, "alice")
    assert [x["id"] for x in as_user("alice", lib.list_prompts, tmp_path)] == ["old-1"]
    assert as_user("bob", lib.list_prompts, tmp_path) == []
    as_user("alice", lib.delete_prompt, tmp_path, "old-1")
    # Deleting from Alice's copy does not re-adopt or touch the legacy store.
    assert as_user("alice", lib.list_prompts, tmp_path) == []
    assert [x["id"] for x in lib.load_legacy_prompts(tmp_path)] == ["old-1"]


def test_single_user_self_host_without_auth_keeps_shared_store(tmp_path, backend, monkeypatch):
    monkeypatch.setenv("STUDIO_AUTH_REQUIRED", "false")
    _seed_legacy(tmp_path, backend, LEGACY)
    assert as_user(None, lib.prompt_scope) == ""
    assert [x["id"] for x in as_user(None, lib.list_prompts, tmp_path)] == ["old-1"]
    as_user(None, lib.upsert_prompt, tmp_path, {"text": "local"})
    assert len(lib.load_legacy_prompts(tmp_path)) == 2


# ------------------------------------------------------------------ HTTP


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("PROJECTS_ROOT", str(tmp_path))
    monkeypatch.setenv("STUDIO_AUTH_REQUIRED", "true")
    monkeypatch.delenv(lib.LEGACY_OWNER_ENV, raising=False)
    monkeypatch.setattr(pg_backend, "enabled", lambda: False)
    import app as studio_app
    from fastapi.testclient import TestClient

    monkeypatch.setattr(studio_app, "PROJECTS_ROOT", tmp_path)
    monkeypatch.setattr(studio_app, "_resolve_user", lambda token: {"userId": token, "username": token})
    _seed_legacy(tmp_path, None, LEGACY)
    return TestClient(studio_app.app)


def _h(uid: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {uid}"}


def test_api_isolation_and_anonymous(client):
    r = client.post("/api/platform/prompts", json={"text": "alice prompt"}, headers=_h("alice"))
    assert r.status_code == 200
    pid = r.json()["prompt"]["id"]

    alice = client.get("/api/platform/prompts", headers=_h("alice")).json()
    assert [x["id"] for x in alice["prompts"]] == [pid] and alice["requiresLogin"] is False

    bob = client.get("/api/platform/prompts", headers=_h("bob")).json()
    assert bob["prompts"] == [] and bob["requiresLogin"] is False
    assert client.delete(f"/api/platform/prompts/{pid}", headers=_h("bob")).status_code == 404

    anon = client.get("/api/platform/prompts").json()
    assert anon["prompts"] == [] and anon["requiresLogin"] is True
    assert client.post("/api/platform/prompts", json={"text": "x"}).status_code == 401
    assert client.delete(f"/api/platform/prompts/{pid}").status_code == 401

    assert client.delete(f"/api/platform/prompts/{pid}", headers=_h("alice")).status_code == 200
