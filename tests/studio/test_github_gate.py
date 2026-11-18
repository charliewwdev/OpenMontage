"""GitHub OAuth login + daily quota gate (studio/server/github_gate.py). No network."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
STUDIO_SERVER = ROOT / "studio" / "server"
if str(STUDIO_SERVER) not in sys.path:
    sys.path.insert(0, str(STUDIO_SERVER))

import auth_context  # noqa: E402
import credits_store  # noqa: E402
import github_gate as gg  # noqa: E402

GATE_ENV = (
    "GITHUB_OAUTH_CLIENT_ID",
    "GITHUB_OAUTH_CLIENT_SECRET",
    "GITHUB_OAUTH_CALLBACK_URL",
    "STUDIO_REQUIRE_GITHUB_LOGIN",
    "STUDIO_DAILY_GENERATION_QUOTA",
    "STUDIO_DAILY_VIDEO_QUOTA",
    "STUDIO_PUBLIC_URL",
    "DATABASE_URL",
    "STUDIO_DATABASE_URL",
)


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    for name in GATE_ENV:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(gg, "_pg_enabled", lambda: False)
    monkeypatch.setattr(credits_store, "_pg_enabled", lambda: False)
    credits_store.init_credits(tmp_path)
    auth_context.set_current_user(None)
    auth_context.set_in_request(False)
    yield
    auth_context.set_current_user(None)
    auth_context.set_in_request(False)


def _configure(monkeypatch, **extra):
    monkeypatch.setenv("GITHUB_OAUTH_CLIENT_ID", "cid")
    monkeypatch.setenv("GITHUB_OAUTH_CLIENT_SECRET", "secret")
    monkeypatch.setenv("STUDIO_PUBLIC_URL", "https://studio.example")
    for k, v in extra.items():
        monkeypatch.setenv(k, str(v))


def _as_request(user):
    auth_context.set_in_request(True)
    auth_context.set_current_user(user)


# ---------------------------------------------------------------- mode / self-host


def test_self_host_without_oauth_is_ungated():
    assert gg.gate_mode() == "auto"
    assert gg.required() is False
    _as_request(None)
    gg.assert_generation_allowed("video")  # no exception
    assert gg.status_for_current_user()["verified"] is True


def test_auto_mode_turns_on_when_oauth_configured(monkeypatch):
    _configure(monkeypatch)
    assert gg.required() is True


def test_explicit_off_wins(monkeypatch):
    _configure(monkeypatch, STUDIO_REQUIRE_GITHUB_LOGIN="0")
    assert gg.required() is False


def test_explicit_on_without_oauth_fails_closed(monkeypatch):
    monkeypatch.setenv("STUDIO_REQUIRE_GITHUB_LOGIN", "1")
    _as_request({"userId": "u1"})
    with pytest.raises(gg.GitHubGateError) as exc:
        gg.assert_generation_allowed("image")
    assert exc.value.code == "github_oauth_not_configured"


# ---------------------------------------------------------------- identity


def test_requires_github_identity(monkeypatch):
    _configure(monkeypatch)
    _as_request(None)
    with pytest.raises(gg.GitHubGateError) as exc:
        gg.assert_generation_allowed("llm")
    assert exc.value.code == "login_required"

    _as_request({"userId": "dtok-42", "username": "alice"})
    with pytest.raises(gg.GitHubGateError) as exc:
        gg.assert_generation_allowed("llm")
    assert exc.value.code == "github_login_required"


def test_session_token_roundtrip_and_tamper(monkeypatch):
    _configure(monkeypatch)
    issued = gg.issue_session_token({"id": 123, "login": "octocat", "avatar_url": "https://a"})
    token = issued["token"]
    assert gg.is_session_token(token)
    user = gg.session_user(token)
    assert user["userId"] == "gh-123"
    assert user["github"] == {"id": "123", "login": "octocat"}
    assert gg.session_user(token[:-2] + "00") is None
    _as_request(user)
    gg.assert_generation_allowed("llm")


def test_linked_identity_for_existing_account(monkeypatch):
    _configure(monkeypatch)
    gg.link_identity("dtok-42", {"id": "777", "login": "alice"})
    _as_request({"userId": "dtok-42"})
    assert gg.current_identity() == {"id": "777", "login": "alice", "via": "link"}
    gg.assert_generation_allowed("llm")
    gg.unlink_current()
    assert gg.current_identity() is None


def test_shared_demo_account_cannot_hold_identity(monkeypatch):
    _configure(monkeypatch)
    started = gg.start(current_user={"userId": "demo", "demo": True}, return_to="/")
    assert started["mode"] == "login"
    started = gg.start(current_user={"userId": "dtok-42"}, return_to="/")
    assert started["mode"] == "link"
    assert "client_id=cid" in started["url"]
    assert "redirect_uri=https%3A%2F%2Fstudio.example%2Fapi%2Fauth%2Fgithub%2Fcallback" in started["url"]


# ---------------------------------------------------------------- OAuth callback


def _fake_profile(code, request_base_url=""):
    assert code == "the-code"
    return {"id": "555", "login": "bob", "avatar_url": ""}


def test_callback_login_issues_token(monkeypatch):
    _configure(monkeypatch)
    started = gg.start(current_user=None, return_to="/workshop")
    state = started["url"].split("state=", 1)[1].split("&", 1)[0]
    from urllib.parse import unquote

    done = gg.complete(code="the-code", state=unquote(state), cookie_nonce=started["nonce"], fetch_profile=_fake_profile)
    assert done["mode"] == "login"
    assert done["redirect"].startswith("/workshop#gh_token=omgh.")
    assert gg.session_user(done["token"])["userId"] == "gh-555"


def test_callback_link_mode_and_csrf(monkeypatch):
    _configure(monkeypatch)
    started = gg.start(current_user={"userId": "dtok-9"}, return_to="//evil.example")
    from urllib.parse import unquote

    state = unquote(started["url"].split("state=", 1)[1].split("&", 1)[0])
    with pytest.raises(gg.GitHubGateError) as exc:
        gg.complete(code="the-code", state=state, cookie_nonce="wrong", fetch_profile=_fake_profile)
    assert exc.value.code == "github_state_invalid"
    done = gg.complete(code="the-code", state=state, cookie_nonce=started["nonce"], fetch_profile=_fake_profile)
    assert done == {"redirect": "/?github=linked", "mode": "link"}  # open redirect stripped
    auth_context.set_current_user({"userId": "dtok-9"})
    assert gg.current_identity()["id"] == "555"


# ---------------------------------------------------------------- quota


def test_daily_quota_counts_images_and_videos(monkeypatch):
    _configure(monkeypatch, STUDIO_DAILY_GENERATION_QUOTA=3, STUDIO_DAILY_VIDEO_QUOTA=1)
    _as_request({"userId": "gh-1", "github": {"id": "1", "login": "a"}})
    gg.assert_generation_allowed("llm")  # not metered
    gg.assert_generation_allowed("audio")  # not metered
    gg.assert_generation_allowed("image")
    gg.assert_generation_allowed("video")
    with pytest.raises(gg.GitHubGateError) as exc:
        gg.assert_generation_allowed("video")
    assert exc.value.code == "quota_exceeded" and exc.value.status == 429
    gg.assert_generation_allowed("image")
    with pytest.raises(gg.GitHubGateError) as exc:
        gg.assert_generation_allowed("image")
    assert exc.value.code == "quota_exceeded"
    status = gg.status_for_current_user()["quota"]
    assert status["used"] == 3 and status["remaining"] == 0
    assert status["videoUsed"] == 1 and status["videoRemaining"] == 0


def test_quota_is_per_github_user(monkeypatch):
    _configure(monkeypatch, STUDIO_DAILY_GENERATION_QUOTA=1)
    _as_request({"userId": "gh-1", "github": {"id": "1", "login": "a"}})
    gg.assert_generation_allowed("image")
    _as_request({"userId": "gh-2", "github": {"id": "2", "login": "b"}})
    gg.assert_generation_allowed("image")


def test_zero_means_unlimited(monkeypatch):
    _configure(monkeypatch, STUDIO_DAILY_GENERATION_QUOTA=0, STUDIO_DAILY_VIDEO_QUOTA=0)
    _as_request({"userId": "gh-1", "github": {"id": "1", "login": "a"}})
    for _ in range(30):
        gg.assert_generation_allowed("video")


def test_queued_jobs_carry_identity_and_are_metered_in_worker(monkeypatch):
    _configure(monkeypatch, STUDIO_DAILY_GENERATION_QUOTA=1)
    _as_request({"userId": "gh-8", "github": {"id": "8", "login": "w"}})
    payload = gg.tag_job_payload({"projectId": "p"}, "image")
    assert payload[gg.JOB_IDENTITY_KEY] == "8"
    # Worker thread: no request, no user — identity comes from the job payload.
    auth_context.set_in_request(False)
    auth_context.set_current_user(None)
    with gg.job_context(payload):
        gg.assert_generation_allowed("image")
        with pytest.raises(gg.GitHubGateError):
            gg.assert_generation_allowed("image")
    # Enqueue precheck now refuses without counting.
    _as_request({"userId": "gh-8", "github": {"id": "8", "login": "w"}})
    with pytest.raises(gg.GitHubGateError) as exc:
        gg.tag_job_payload({"projectId": "p"}, "image")
    assert exc.value.code == "quota_exceeded"


def test_internal_job_without_user_context_passes(monkeypatch):
    _configure(monkeypatch)
    auth_context.set_in_request(False)
    auth_context.set_current_user(None)
    gg.assert_generation_allowed("image")


def test_job_identity_is_metered_even_without_oauth_env_in_worker(monkeypatch):
    _configure(monkeypatch, STUDIO_DAILY_GENERATION_QUOTA=1)
    _as_request({"userId": "gh-3", "github": {"id": "3", "login": "e"}})
    payload = gg.tag_job_payload({}, "video")
    # Edge worker: no OAuth env vars, no request, no user.
    monkeypatch.delenv("GITHUB_OAUTH_CLIENT_ID")
    monkeypatch.delenv("GITHUB_OAUTH_CLIENT_SECRET")
    auth_context.set_in_request(False)
    auth_context.set_current_user(None)
    with gg.job_context(payload):
        gg.assert_generation_allowed("video")
        with pytest.raises(gg.GitHubGateError):
            gg.assert_generation_allowed("image")
