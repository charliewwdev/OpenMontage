"""HTTP flow for GitHub OAuth sign-in (no network: the GitHub exchange is stubbed)."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

ROOT = Path(__file__).resolve().parents[2]
STUDIO_SERVER = ROOT / "studio" / "server"
for p in (str(STUDIO_SERVER), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

os.environ.setdefault("PROJECTS_ROOT", tempfile.mkdtemp(prefix="om-gate-api-"))
os.environ.setdefault("STUDIO_DIST", tempfile.mkdtemp(prefix="om-gate-dist-"))

fastapi_testclient = pytest.importorskip("fastapi.testclient")
app_module = pytest.importorskip("app")
import github_gate as gg  # noqa: E402


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("GITHUB_OAUTH_CLIENT_ID", "cid")
    monkeypatch.setenv("GITHUB_OAUTH_CLIENT_SECRET", "secret")
    monkeypatch.setenv("STUDIO_PUBLIC_URL", "http://testserver")
    monkeypatch.delenv("STUDIO_REQUIRE_GITHUB_LOGIN", raising=False)
    monkeypatch.setattr(gg, "_pg_enabled", lambda: False)
    monkeypatch.setattr(
        gg, "exchange_code", lambda code, request_base_url="": {"id": "4242", "login": "octo", "avatar_url": ""}
    )
    return fastapi_testclient.TestClient(app_module.app)


def test_status_endpoint_is_public(client):
    data = client.get("/api/settings/github-gate").json()["githubGate"]
    assert data["required"] is True
    assert data["verified"] is False
    assert data["quota"]["limit"] == gg.DEFAULT_GENERATION_QUOTA


def test_signin_flow_issues_session(client):
    started = client.post("/api/auth/github/start", json={"returnTo": "/"})
    assert started.status_code == 200
    url = started.json()["url"]
    assert url.startswith("https://github.com/login/oauth/authorize?")
    state = parse_qs(urlparse(url).query)["state"][0]
    cb = client.get(
        "/api/auth/github/callback",
        params={"code": "abc", "state": state},
        follow_redirects=False,
    )
    assert cb.status_code == 302
    location = cb.headers["location"]
    assert "#gh_token=" in location
    token = parse_qs(location.split("#", 1)[1])["gh_token"][0]
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).json()
    assert me["data"]["userId"] == "gh-4242"
    gate = client.get("/api/settings/github-gate", headers={"Authorization": f"Bearer {token}"}).json()["githubGate"]
    assert gate["verified"] is True and gate["login"] == "octo"


def test_callback_without_cookie_is_rejected(client):
    url = client.post("/api/auth/github/start", json={}).json()["url"]
    state = parse_qs(urlparse(url).query)["state"][0]
    client.cookies.clear()
    cb = client.get("/api/auth/github/callback", params={"code": "abc", "state": state}, follow_redirects=False)
    assert cb.status_code == 302
    assert cb.headers["location"] == "/?github_error=github_state_invalid"
