"""GitHub OAuth login + per-user daily generation quota for hosted Studio.

Replaces the old "star the repo to generate" gate. Nothing here checks or
rewards stars: the gate only asks for a verified GitHub identity (via OAuth)
and then meters paid generations per GitHub account per UTC day.

Configuration (all optional — self-hosters who set none of these run normally):

    GITHUB_OAUTH_CLIENT_ID        OAuth App client id
    GITHUB_OAUTH_CLIENT_SECRET    OAuth App client secret
    GITHUB_OAUTH_CALLBACK_URL     default: {STUDIO_PUBLIC_URL}/api/auth/github/callback
    STUDIO_REQUIRE_GITHUB_LOGIN   auto (default) | 1 | 0
                                  auto → gate on only when the OAuth app is configured
                                  1    → gate on; generation is refused until OAuth is configured
                                  0    → gate off
    STUDIO_DAILY_GENERATION_QUOTA images + video shots per GitHub user per UTC day (default 20, 0 = unlimited)
    STUDIO_DAILY_VIDEO_QUOTA      video shots per GitHub user per UTC day (default 5, 0 = unlimited)
    STUDIO_SESSION_SECRET         HMAC secret for GitHub session tokens / OAuth state
                                  (falls back to STUDIO_DEMO_SECRET)
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

TOKEN_PREFIX = "omgh."
STATE_COOKIE = "om_gh_oauth"
STATE_TTL_SECONDS = 600
SESSION_TTL_SECONDS = 30 * 24 * 3600
DEFAULT_GENERATION_QUOTA = 20
DEFAULT_VIDEO_QUOTA = 5
# Voice (edge-tts by default) and LLM steps need the GitHub identity but are not metered.
COUNTED_KINDS = {"image", "video"}

_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
_TOKEN_URL = "https://github.com/login/oauth/access_token"
_USER_URL = "https://api.github.com/user"

_quota_lock = threading.Lock()
# GitHub id carried by a queued media job (set while a worker runs that job).
_job_identity: ContextVar[str] = ContextVar("om_github_job_identity", default="")
JOB_IDENTITY_KEY = "_githubId"


class GitHubGateError(RuntimeError):
    """Raised when the hosted gate blocks a call. ``code`` is machine-readable."""

    def __init__(self, message: str, *, code: str = "github_login_required", status: int = 403, extra: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.status = status
        self.extra = dict(extra or {})


# --------------------------------------------------------------------------- config


def _truthy(raw: str) -> bool:
    return raw.strip().lower() not in {"0", "false", "off", "no", ""}


def client_id() -> str:
    return (os.environ.get("GITHUB_OAUTH_CLIENT_ID") or "").strip()


def client_secret() -> str:
    return (os.environ.get("GITHUB_OAUTH_CLIENT_SECRET") or "").strip()


def oauth_configured() -> bool:
    return bool(client_id() and client_secret())


def gate_mode() -> str:
    raw = (os.environ.get("STUDIO_REQUIRE_GITHUB_LOGIN") or "auto").strip().lower()
    if raw in {"", "auto"}:
        return "auto"
    return "on" if _truthy(raw) else "off"


def required() -> bool:
    mode = gate_mode()
    if mode == "off":
        return False
    if mode == "on":
        return True
    return oauth_configured()


def _int_env(name: str, default: int) -> int:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        return max(0, int(raw))
    except ValueError:
        return default


def generation_quota() -> int:
    return _int_env("STUDIO_DAILY_GENERATION_QUOTA", DEFAULT_GENERATION_QUOTA)


def video_quota() -> int:
    return _int_env("STUDIO_DAILY_VIDEO_QUOTA", DEFAULT_VIDEO_QUOTA)


def callback_url(request_base_url: str = "") -> str:
    explicit = (os.environ.get("GITHUB_OAUTH_CALLBACK_URL") or "").strip()
    if explicit:
        return explicit
    base = (os.environ.get("STUDIO_PUBLIC_URL") or "").strip().rstrip("/") or (request_base_url or "").rstrip("/")
    return f"{base}/api/auth/github/callback"


def _secret() -> bytes:
    raw = (
        (os.environ.get("STUDIO_SESSION_SECRET") or "").strip()
        or (os.environ.get("STUDIO_DEMO_SECRET") or "").strip()
        or "openmontage-demo-local"
    )
    return hashlib.sha256(("om-github:" + raw).encode("utf-8")).digest()


# --------------------------------------------------------------------------- signing


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64url_decode(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _sign(part: str) -> str:
    return hmac.new(_secret(), part.encode("utf-8"), hashlib.sha256).hexdigest()[:48]


def _pack(payload: dict[str, Any]) -> str:
    part = _b64url(json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
    return f"{part}.{_sign(part)}"


def _unpack(blob: str) -> dict[str, Any] | None:
    if not blob or "." not in blob:
        return None
    part, sig = blob.rsplit(".", 1)
    if not hmac.compare_digest(_sign(part), sig):
        return None
    try:
        payload = json.loads(_b64url_decode(part).decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    exp = int(payload.get("exp") or 0)
    if exp and exp < int(time.time()):
        return None
    return payload


# --------------------------------------------------------------------------- session tokens


def is_session_token(token: str | None) -> bool:
    return bool(token) and str(token).startswith(TOKEN_PREFIX)


def issue_session_token(gh_user: dict[str, Any], *, ttl_seconds: int = SESSION_TTL_SECONDS) -> dict[str, Any]:
    gh_id = str(gh_user.get("id") or "").strip()
    login = str(gh_user.get("login") or "").strip()
    if not gh_id or not login:
        raise GitHubGateError("GitHub 用户信息不完整", code="github_oauth_failed", status=502)
    now = int(time.time())
    payload = {
        "kind": "github",
        "uid": f"gh-{gh_id}",
        "ghId": gh_id,
        "login": login,
        "avatar": str(gh_user.get("avatar_url") or ""),
        "iat": now,
        "exp": now + max(300, int(ttl_seconds)),
    }
    token = TOKEN_PREFIX + _pack(payload)
    return {
        "token": token,
        "accessToken": token,
        "userId": payload["uid"],
        "username": login,
        "avatar": payload["avatar"],
        "expiresIn": payload["exp"] - now,
        "github": True,
    }


def parse_session_token(token: str) -> dict[str, Any] | None:
    if not is_session_token(token):
        return None
    payload = _unpack(token[len(TOKEN_PREFIX) :])
    if not payload or payload.get("kind") != "github":
        return None
    return payload


def session_user(token: str) -> dict[str, Any] | None:
    payload = parse_session_token(token)
    if not payload:
        return None
    return {
        "id": payload.get("uid"),
        "userId": payload.get("uid"),
        "username": payload.get("login") or "github",
        "nickname": payload.get("login") or "github",
        "avatar": payload.get("avatar") or "",
        "github": {"id": str(payload.get("ghId") or ""), "login": str(payload.get("login") or "")},
    }


def session_me(token: str) -> tuple[int, dict[str, Any]]:
    user = session_user(token)
    if not user:
        return 401, {"ok": False, "error": "invalid or expired GitHub session"}
    return 200, {"ok": True, "data": user, "msg": "ok"}


def session_refresh(token: str) -> tuple[int, dict[str, Any]]:
    payload = parse_session_token(token)
    if not payload:
        return 401, {"ok": False, "error": "invalid or expired GitHub session"}
    issued = issue_session_token(
        {"id": payload.get("ghId"), "login": payload.get("login"), "avatar_url": payload.get("avatar")}
    )
    return 200, {"ok": True, "data": issued, "msg": "ok"}


# --------------------------------------------------------------------------- OAuth flow


def _safe_return_path(path: str) -> str:
    text = (path or "/").strip()
    if not text.startswith("/") or text.startswith("//") or "\\" in text:
        return "/"
    return text[:300]


def _shared_demo_user_id() -> str:
    try:
        from platform_config import demo_auth_config

        return str(demo_auth_config().get("userId") or "demo")
    except Exception:
        return "demo"


def start(*, current_user: dict[str, Any] | None, return_to: str = "/", request_base_url: str = "") -> dict[str, Any]:
    """Build the GitHub authorize URL + a nonce the caller stores in a cookie.

    Logged-in (non-demo) studio users *link* GitHub to their existing account.
    Anonymous visitors and the shared demo account *sign in* with GitHub
    (a separate per-GitHub-user workspace, since the demo account is shared).
    """
    if not oauth_configured():
        raise GitHubGateError("服务器未配置 GitHub OAuth（GITHUB_OAUTH_CLIENT_ID / GITHUB_OAUTH_CLIENT_SECRET）", code="github_oauth_not_configured", status=503)
    nonce = secrets.token_urlsafe(18)
    uid = ""
    if current_user:
        cand = str(current_user.get("userId") or current_user.get("id") or "").strip()
        is_gh_session = cand.startswith("gh-")
        if cand and cand != _shared_demo_user_id() and not current_user.get("demo") and not is_gh_session:
            uid = cand
    state = _pack(
        {
            "n": nonce,
            "uid": uid,
            "ret": _safe_return_path(return_to),
            "exp": int(time.time()) + STATE_TTL_SECONDS,
        }
    )
    query = urllib.parse.urlencode(
        {
            "client_id": client_id(),
            "redirect_uri": callback_url(request_base_url),
            "state": state,
            # No scopes: we only read the public profile (id + login).
            "allow_signup": "true",
        }
    )
    return {"url": f"{_AUTHORIZE_URL}?{query}", "nonce": nonce, "mode": "link" if uid else "login"}


def _http_json(req: urllib.request.Request) -> dict[str, Any]:
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        raise GitHubGateError(f"GitHub 返回 {exc.code}", code="github_oauth_failed", status=502) from exc
    except urllib.error.URLError as exc:
        raise GitHubGateError(f"无法连接 GitHub: {exc.reason}", code="github_unreachable", status=502) from exc
    try:
        data = json.loads(raw) if raw else {}
    except json.JSONDecodeError as exc:
        raise GitHubGateError("GitHub 返回了无法解析的响应", code="github_oauth_failed", status=502) from exc
    return data if isinstance(data, dict) else {}


def exchange_code(code: str, *, request_base_url: str = "") -> dict[str, Any]:
    """Exchange the OAuth code for the GitHub user profile. The access token is discarded."""
    body = urllib.parse.urlencode(
        {
            "client_id": client_id(),
            "client_secret": client_secret(),
            "code": code,
            "redirect_uri": callback_url(request_base_url),
        }
    ).encode("utf-8")
    token_req = urllib.request.Request(
        _TOKEN_URL,
        data=body,
        method="POST",
        headers={"Accept": "application/json", "User-Agent": "OpenMontage-DramaStudio/1.0"},
    )
    token_data = _http_json(token_req)
    access = str(token_data.get("access_token") or "")
    if not access:
        raise GitHubGateError(
            f"GitHub 授权失败：{token_data.get('error_description') or token_data.get('error') or 'no token'}",
            code="github_oauth_failed",
            status=400,
        )
    user_req = urllib.request.Request(
        _USER_URL,
        method="GET",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {access}",
            "User-Agent": "OpenMontage-DramaStudio/1.0",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    profile = _http_json(user_req)
    if not profile.get("id") or not profile.get("login"):
        raise GitHubGateError("GitHub 用户信息不完整", code="github_oauth_failed", status=502)
    return {"id": str(profile["id"]), "login": str(profile["login"]), "avatar_url": str(profile.get("avatar_url") or "")}


def complete(*, code: str, state: str, cookie_nonce: str, request_base_url: str = "", fetch_profile=None) -> dict[str, Any]:
    """Finish the OAuth callback. Returns ``{"redirect": url}`` (plus ``token`` for sign-in)."""
    payload = _unpack(state or "")
    if not payload:
        raise GitHubGateError("GitHub 登录已过期，请重试", code="github_state_invalid", status=400)
    if not cookie_nonce or not hmac.compare_digest(str(payload.get("n") or ""), str(cookie_nonce)):
        raise GitHubGateError("GitHub 登录校验失败，请在同一个浏览器里重试", code="github_state_invalid", status=400)
    if not code:
        raise GitHubGateError("GitHub 未返回授权码", code="github_oauth_failed", status=400)
    profile = (fetch_profile or exchange_code)(code, request_base_url=request_base_url)
    ret = _safe_return_path(str(payload.get("ret") or "/"))
    uid = str(payload.get("uid") or "")
    if uid:
        link_identity(uid, profile)
        return {"redirect": _with_query(ret, {"github": "linked"}), "mode": "link"}
    issued = issue_session_token(profile)
    fragment = urllib.parse.urlencode({"gh_token": issued["token"]})
    return {"redirect": f"{ret.split('#', 1)[0]}#{fragment}", "mode": "login", "token": issued["token"]}


def _with_query(path: str, params: dict[str, str]) -> str:
    base, _, frag = path.partition("#")
    sep = "&" if "?" in base else "?"
    out = f"{base}{sep}{urllib.parse.urlencode(params)}"
    return f"{out}#{frag}" if frag else out


# --------------------------------------------------------------------------- linked identities


def link_identity(user_id: str, profile: dict[str, Any]) -> dict[str, Any]:
    from auth_context import get_current_user, set_current_user
    from credits_store import _save, load_credits

    previous = get_current_user()
    set_current_user({"userId": user_id})
    try:
        data = load_credits()
        data["githubLink"] = {
            "id": str(profile.get("id") or ""),
            "login": str(profile.get("login") or ""),
            "avatar": str(profile.get("avatar_url") or ""),
            "linkedAt": int(time.time()),
        }
        _save(data)
        return data["githubLink"]
    finally:
        set_current_user(previous)


def unlink_current() -> None:
    from credits_store import _save, load_credits

    data = load_credits()
    data.pop("githubLink", None)
    _save(data)


def current_identity() -> dict[str, str] | None:
    """GitHub identity of the current request (session token or linked account)."""
    from auth_context import current_user_id, get_current_user

    user = get_current_user() or {}
    gh = user.get("github") if isinstance(user, dict) else None
    if isinstance(gh, dict) and gh.get("id"):
        return {"id": str(gh["id"]), "login": str(gh.get("login") or ""), "via": "session"}
    uid = current_user_id()
    if not uid or uid == _shared_demo_user_id():
        return None
    if uid.startswith("gh-") and uid[3:].isdigit():
        # GitHub sign-in workspace (e.g. background auto-produce threads that only set userId).
        return {"id": uid[3:], "login": str(user.get("username") or ""), "via": "session"}
    try:
        from credits_store import load_credits

        link = load_credits().get("githubLink")
    except Exception:
        link = None
    if isinstance(link, dict) and link.get("id"):
        return {"id": str(link["id"]), "login": str(link.get("login") or ""), "via": "link"}
    return None


# --------------------------------------------------------------------------- quota store


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _resets_at() -> int:
    now = datetime.now(timezone.utc)
    nxt = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return int(nxt.timestamp())


def _pg_enabled() -> bool:
    try:
        import pg_backend as _pg

        return bool(_pg.enabled())
    except Exception:
        return False


def _projects_root() -> Path | None:
    try:
        import credits_store as cs

        root = getattr(cs, "_projects_root", None)
        return Path(root) if root else None
    except Exception:
        return None


def _quota_path(day: str) -> Path | None:
    root = _projects_root()
    return (root / ".github_quota" / f"{day}.json") if root else None


def _load_day(day: str) -> dict[str, dict[str, int]]:
    data: Any = None
    if _pg_enabled():
        try:
            import pg_backend as _pg

            data = _pg.load_kv(f"github_quota:{day}")
        except Exception:
            data = None
    else:
        path = _quota_path(day)
        if path and path.is_file():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                data = None
    return data if isinstance(data, dict) else {}


def _save_day(day: str, data: dict[str, dict[str, int]]) -> None:
    if _pg_enabled():
        import pg_backend as _pg

        _pg.upsert_kv(f"github_quota:{day}", data)
        return
    path = _quota_path(day)
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def usage_for(gh_id: str) -> dict[str, int]:
    row = _load_day(_today()).get(f"gh:{gh_id}") or {}
    return {"generation": int(row.get("generation") or 0), "video": int(row.get("video") or 0)}


def quota_status(gh_id: str | None) -> dict[str, Any]:
    used = usage_for(gh_id) if gh_id else {"generation": 0, "video": 0}
    gen_limit = generation_quota()
    vid_limit = video_quota()
    return {
        "limit": gen_limit,
        "used": used["generation"],
        "remaining": max(0, gen_limit - used["generation"]) if gen_limit else None,
        "videoLimit": vid_limit,
        "videoUsed": used["video"],
        "videoRemaining": max(0, vid_limit - used["video"]) if vid_limit else None,
        "resetsAt": _resets_at(),
        "period": "utc-day",
    }


def consume(gh_id: str, kind: str) -> dict[str, Any]:
    """Atomically check + count one generation. Raises GitHubGateError when exhausted."""
    if kind not in COUNTED_KINDS:
        return quota_status(gh_id)
    gen_limit = generation_quota()
    vid_limit = video_quota()
    day = _today()
    key = f"gh:{gh_id}"
    with _quota_lock:
        data = _load_day(day)
        row = dict(data.get(key) or {})
        gen_used = int(row.get("generation") or 0)
        vid_used = int(row.get("video") or 0)
        if gen_limit and gen_used >= gen_limit:
            raise _quota_error(gen_used, gen_limit, video=False)
        if kind == "video" and vid_limit and vid_used >= vid_limit:
            raise _quota_error(vid_used, vid_limit, video=True)
        row["generation"] = gen_used + 1
        if kind == "video":
            row["video"] = vid_used + 1
        data[key] = row
        _save_day(day, data)
    return quota_status(gh_id)


def _quota_error(used: int, limit: int, *, video: bool) -> GitHubGateError:
    what = "视频生成" if video else "生成"
    return GitHubGateError(
        f"今天的{what}次数已用完（{used}/{limit}），UTC 0 点（北京时间 8 点）重置。"
        "也可以自部署并使用你自己的模型 Key，不受这个限额影响。",
        code="quota_exceeded",
        status=429,
        extra={"quota": {"used": used, "limit": limit, "video": video, "resetsAt": _resets_at()}},
    )


# --------------------------------------------------------------------------- gate


def assert_generation_allowed(kind: str | None = None) -> None:
    """Raise GitHubGateError when the hosted gate blocks the caller.

    ``kind`` in {"image", "video"} counts against the daily quota;
    ``"llm"`` / ``"audio"`` / ``None`` only require the GitHub identity.

    Inside an HTTP request the caller must be signed in with (or linked to) GitHub.
    Queued media jobs carry the GitHub id of the user who queued them and are
    metered when the worker actually generates. Jobs with no user context at all
    (crash recovery re-queues) are internal and pass.
    """
    job_gh = _job_identity.get()
    if job_gh:
        # Stamped at enqueue time only while the gate was on; meter it even if this
        # worker process does not carry the OAuth env vars (e.g. an edge worker).
        if kind in COUNTED_KINDS:
            consume(job_gh, kind)
        return
    if not required():
        return
    if not oauth_configured():
        raise GitHubGateError(
            "此站点要求 GitHub 登录，但管理员还没有配置 GitHub OAuth。",
            code="github_oauth_not_configured",
            status=503,
        )
    from auth_context import current_user_id, get_current_user, in_request

    if in_request() and not current_user_id():
        raise GitHubGateError("请先登录后再生成", code="login_required", status=401)
    if not in_request() and get_current_user() is None:
        return  # internal background job (no user context)
    ident = current_identity()
    if not ident:
        raise GitHubGateError(
            "请先用 GitHub 登录（或连接 GitHub 账号）后再生成",
            code="github_login_required",
            status=403,
        )
    if kind in COUNTED_KINDS:
        consume(ident["id"], kind)


def precheck_quota(kind: str | None) -> None:
    """Refuse early (without counting) when the caller has nothing left for ``kind``."""
    if not required() or kind not in COUNTED_KINDS:
        return
    ident = current_identity()
    if not ident:
        return
    status = quota_status(ident["id"])
    if status["limit"] and status["used"] >= status["limit"]:
        raise _quota_error(status["used"], status["limit"], video=False)
    if kind == "video" and status["videoLimit"] and status["videoUsed"] >= status["videoLimit"]:
        raise _quota_error(status["videoUsed"], status["videoLimit"], video=True)


def ensure_can_queue(kind: str | None) -> None:
    """Inside a request: refuse before any state is touched when the job would be blocked."""
    if not required():
        return
    from auth_context import in_request

    if not in_request():
        return
    assert_generation_allowed(None)
    precheck_quota(kind)


def tag_job_payload(payload: dict[str, Any], kind: str | None) -> dict[str, Any]:
    """Called by ``job_queue.enqueue``: enforce the gate now and stamp the GitHub id on the job."""
    if not required():
        return payload
    from auth_context import in_request

    if not in_request():
        return payload  # internal re-queue; keep whatever identity the payload already has
    ensure_can_queue(kind)
    ident = current_identity()
    out = dict(payload or {})
    if ident:
        out[JOB_IDENTITY_KEY] = ident["id"]
    return out


@contextmanager
def job_context(payload: dict[str, Any] | None):
    """Run a queued job with the GitHub identity stamped at enqueue time."""
    gh_id = str((payload or {}).get(JOB_IDENTITY_KEY) or "")
    token = _job_identity.set(gh_id)
    try:
        yield
    finally:
        _job_identity.reset(token)


def status_for_current_user() -> dict[str, Any]:
    from auth_context import current_user_id

    ident = current_identity() if current_user_id() else None
    is_required = required()
    return {
        "required": is_required,
        "oauthConfigured": oauth_configured(),
        "verified": bool(ident) if is_required else True,
        "login": (ident or {}).get("login", ""),
        "via": (ident or {}).get("via", ""),
        "loginUrl": "/api/auth/github/start",
        "quota": quota_status((ident or {}).get("id")) if is_required else None,
    }


def attach_gate_status(status: dict[str, Any]) -> dict[str, Any]:
    status = dict(status)
    try:
        status["githubGate"] = status_for_current_user()
    except Exception:
        status["githubGate"] = {"required": False, "verified": True}
    return status
