"""GitHub Star gate — require starring the repo before using hosted Studio generation."""

from __future__ import annotations

import json
import os
import re
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

_lock = threading.Lock()
_LOGIN_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$")


class GitHubStarError(RuntimeError):
    def __init__(self, message: str, *, code: str = "star_required"):
        super().__init__(message)
        self.code = code


def required() -> bool:
    raw = (os.environ.get("STUDIO_REQUIRE_GITHUB_STAR") or "0").strip().lower()
    return raw not in {"0", "false", "off", "no", ""}


def star_repo() -> str:
    return (os.environ.get("GITHUB_STAR_REPO") or "charliewwdev/OpenMontage").strip().strip("/")


def star_url() -> str:
    return f"https://github.com/{star_repo()}"


def _projects_root() -> Path | None:
    try:
        import credits_store as cs

        root = getattr(cs, "_projects_root", None)
        return Path(root) if root else None
    except Exception:
        return None


def _pg_enabled() -> bool:
    try:
        import pg_backend as _pg

        return bool(_pg.enabled())
    except Exception:
        return False


def _normalize_login(login: str) -> str:
    text = (login or "").strip().lstrip("@")
    if not text or not _LOGIN_RE.match(text):
        raise GitHubStarError("GitHub 用户名无效", code="invalid_login")
    return text


def _binds_path(root: Path) -> Path:
    return Path(root) / ".github_star_binds.json"


def _load_binds(root: Path) -> dict[str, str]:
    if _pg_enabled():
        try:
            import pg_backend as _pg

            hit = _pg.load_kv("github_star_binds")
            if isinstance(hit, dict):
                return {
                    str(k).lower(): str(v)
                    for k, v in hit.items()
                    if isinstance(k, str) and isinstance(v, str) and k and v
                }
        except Exception:
            pass
    path = _binds_path(root)
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    return {
        str(k).lower(): str(v)
        for k, v in data.items()
        if isinstance(k, str) and isinstance(v, str) and k and v
    }


def _save_binds(root: Path, binds: dict[str, str]) -> None:
    if _pg_enabled():
        import pg_backend as _pg

        _pg.upsert_kv("github_star_binds", binds)
        return
    path = _binds_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(binds, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _user_star_record() -> dict[str, Any]:
    try:
        from credits_store import load_credits

        data = load_credits()
        raw = data.get("githubStar")
        return raw if isinstance(raw, dict) else {}
    except Exception:
        return {}


def _save_user_star(record: dict[str, Any]) -> dict[str, Any]:
    from credits_store import _save, load_credits

    data = load_credits()
    data["githubStar"] = record
    return _save(data)


def _check_starred(login: str) -> bool:
    owner_repo = star_repo()
    if "/" not in owner_repo:
        raise GitHubStarError("GITHUB_STAR_REPO 配置无效", code="misconfigured")
    owner, repo = owner_repo.split("/", 1)
    url = f"https://api.github.com/users/{login}/starred/{owner}/{repo}"
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "OpenMontage-DramaStudio/1.0",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = (os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, method="GET", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return int(resp.status) == 204 or 200 <= int(resp.status) < 300
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return False
        if exc.code == 403:
            raise GitHubStarError("GitHub API 限额，请稍后重试或配置 GITHUB_TOKEN", code="github_rate_limit") from exc
        detail = exc.read().decode("utf-8", errors="replace")[:200]
        raise GitHubStarError(f"GitHub API {exc.code}: {detail}", code="github_api_error") from exc
    except urllib.error.URLError as exc:
        raise GitHubStarError(f"无法连接 GitHub: {exc.reason}", code="github_unreachable") from exc


def status_for_current_user() -> dict[str, Any]:
    from auth_context import current_user_id

    uid = current_user_id()
    record = _user_star_record() if uid else {}
    login = str(record.get("login") or "").strip()
    repo = str(record.get("repo") or star_repo())
    verified = bool(login) and repo == star_repo() and bool(record.get("verifiedAt"))
    return {
        "required": required(),
        "verified": verified if required() else True,
        "login": login if verified else "",
        "repo": star_repo(),
        "starUrl": star_url(),
        "verifiedAt": int(record.get("verifiedAt") or 0) if verified else 0,
        "userId": uid or "",
    }


def is_verified() -> bool:
    if not required():
        return True
    return bool(status_for_current_user().get("verified"))


def verify_and_bind(login: str) -> dict[str, Any]:
    from auth_context import current_user_id

    uid = current_user_id()
    if not uid:
        raise GitHubStarError("请先登录后再验证 Star", code="login_required")
    norm = _normalize_login(login)
    root = _projects_root()
    if root is None:
        raise GitHubStarError("密钥存储未初始化", code="misconfigured")

    if not _check_starred(norm):
        raise GitHubStarError(
            f"未检测到 @{norm} 对 {star_repo()} 的 Star。请先打开仓库点 Star，再重试验证。",
            code="not_starred",
        )

    with _lock:
        binds = _load_binds(root)
        key = norm.lower()
        owner = binds.get(key) or ""
        if owner and owner != uid:
            raise GitHubStarError(
                f"GitHub 用户 @{norm} 已绑定其他账号，请使用你自己的 GitHub 用户名。",
                code="login_taken",
            )
        # Drop previous bind for this studio user if they re-verify under a new login
        for existing_login, existing_uid in list(binds.items()):
            if existing_uid == uid and existing_login != key:
                binds.pop(existing_login, None)
        binds[key] = uid
        _save_binds(root, binds)

    record = {
        "login": norm,
        "repo": star_repo(),
        "verifiedAt": int(time.time()),
    }
    _save_user_star(record)
    return status_for_current_user()


def assert_github_star_or_raise() -> None:
    """Raise GitHubStarError when the hosted star gate blocks the caller."""
    if not required():
        return
    from auth_context import current_user_id

    if not current_user_id():
        raise GitHubStarError("请先登录，并 Star GitHub 仓库后再使用", code="login_required")
    if not is_verified():
        raise GitHubStarError(
            "请先在 GitHub 为 OpenMontage 点 Star，并在模型配置页完成验证后，才能查看与使用模型。",
            code="star_required",
        )


def redact_keys_status(status: dict[str, Any]) -> dict[str, Any]:
    """Strip secrets / readiness when star gate is on and user is not verified."""
    gate = status_for_current_user()
    status = dict(status)
    status["githubStar"] = gate
    if not gate.get("required") or gate.get("verified"):
        return status

    redacted_providers = []
    for item in status.get("llmProviders") or []:
        if not isinstance(item, dict):
            continue
        redacted_providers.append(
            {
                "id": item.get("id"),
                "label": item.get("label"),
                "kind": item.get("kind"),
                "freeTier": bool(item.get("freeTier")),
                "configured": False,
                "masked": "",
                "baseUrl": "",
                "model": "",
                "models": [],
                "modelKnown": False,
                "docs": item.get("docs") or "",
                "placeholder": "",
                "hint": "",
                "keyOptional": False,
                "keyEnv": "",
                "baseEnv": "",
                "modelEnv": "",
            }
        )
    status["llmProviders"] = redacted_providers
    status["llmReady"] = False
    status["llmBackend"] = "none"
    status["llmProvider"] = ""
    status["ready"] = False
    status["imageBackendsAvailable"] = []
    status["videoBackendsAvailable"] = []
    status["imageModels"] = []
    status["videoModels"] = []
    status["audioModels"] = []
    for key in ("deepseek", "cursor", "volcengine", "nvidia", "hf", "cloudflareImage", "pollinationsImage"):
        block = status.get(key)
        if isinstance(block, dict):
            status[key] = {
                **{k: "" for k in block.keys()},
                "configured": False,
                "masked": "",
            }
    comfy = status.get("comfyui")
    if isinstance(comfy, dict):
        status["comfyui"] = {
            **comfy,
            "configured": False,
            "serverUrl": "",
            "imageUrl": "",
            "videoUrl": "",
            "masked": "",
            "reachable": False,
        }
    status["indextts"] = {"configured": False, "baseUrl": ""}
    return status
