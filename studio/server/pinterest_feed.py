"""Fetch public Pinterest pins for inspiration imagery.

Live fetch uses Pinterest public pidgets. When the server network cannot reach
Pinterest, the curated seed catalog (real pinimg URLs) keeps the wall full.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import socket
import ssl
import subprocess
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from platform_config import load_platform_config

socket.setdefaulttimeout(8)

_CACHE: dict[str, Any] = {"ts": 0.0, "items": [], "source": ""}
_CACHE_TTL = 1800.0

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)

_STREAM_TAIL = re.compile(
    r"(?is)\s*(?:stream|catch up|now streaming|watch now|see which|available on|"
    r"on hbo|on max|on netflix|utm_source=).*$"
)

_CATEGORY_PROMPT_HINTS = {
    "character": "电影级角色肖像，浅景深，自然皮肤纹理，电影灯光，情绪明确",
    "scene": "电影场景空镜，广角构图，氛围光，空间关系清晰，画面中不出现主体角色",
    "prop": "电影道具特写，材质细节清晰，柔光产品摄影，干净背景",
    "style": "强视觉风格定调，统一色板与光影语言，电影调色，专业摄影构图",
    "storyboard": "影视分镜感画面，叙事构图，镜头语言明确，电影质感",
}

_SEED_CANDIDATES = (
    Path(os.environ.get("STUDIO_PINTEREST_SEED", "")),
    Path(__file__).resolve().parents[1] / "config" / "pinterest_seed.json",
    Path("/app/studio/config/pinterest_seed.json"),
)


def _ssl_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _sources() -> list[dict[str, str]]:
    cfg = load_platform_config().get("pinterest") or {}
    out: list[dict[str, str]] = []
    for item in cfg.get("users") or []:
        if isinstance(item, str) and item.strip():
            out.append({"kind": "user", "user": item.strip(), "label": item.strip()})
        elif isinstance(item, dict) and item.get("user"):
            out.append(
                {
                    "kind": "user",
                    "user": str(item["user"]).strip(),
                    "label": str(item.get("label") or item["user"]),
                }
            )
    for item in cfg.get("boards") or []:
        if not isinstance(item, dict):
            continue
        user = str(item.get("user") or "").strip()
        board = str(item.get("board") or "").strip()
        if user and board:
            out.append(
                {
                    "kind": "board",
                    "user": user,
                    "board": board,
                    "label": str(item.get("label") or board),
                }
            )
    if not out:
        out = [
            {"kind": "user", "user": "pinterest", "label": "Pinterest"},
            {"kind": "user", "user": "netflix", "label": "Netflix"},
            {"kind": "user", "user": "voguemagazine", "label": "Vogue"},
        ]
    return out


def _categories() -> list[dict[str, str]]:
    cfg = load_platform_config().get("pinterest") or {}
    cats = cfg.get("categories") or []
    out = []
    for item in cats:
        if isinstance(item, dict) and item.get("id"):
            out.append({"id": str(item["id"]), "label": str(item.get("label") or item["id"])})
    return out or [
        {"id": "all", "label": "全部"},
        {"id": "character", "label": "角色"},
        {"id": "scene", "label": "场景"},
        {"id": "prop", "label": "道具"},
        {"id": "style", "label": "风格"},
        {"id": "storyboard", "label": "分镜"},
    ]


def _normalize_image(url: str) -> str:
    return (
        url.replace("/236x/", "/736x/")
        .replace("/237x/", "/736x/")
        .replace("/474x/", "/736x/")
        .replace("/564x/", "/736x/")
    )


def _pin_from_raw(pin: dict[str, Any], *, fallback_board: str = "") -> dict[str, Any] | None:
    images = pin.get("images") or {}
    image = ""
    for key in ("orig", "736x", "564x", "474x", "237x", "236x"):
        node = images.get(key) if isinstance(images, dict) else None
        if isinstance(node, dict) and node.get("url"):
            image = _normalize_image(str(node["url"]))
            break
    if not image:
        return None
    board_name = ""
    board = pin.get("board")
    if isinstance(board, dict):
        board_name = str(board.get("name") or board.get("url") or "")
    title = str(pin.get("description") or pin.get("grid_title") or board_name or "Pin").strip() or "Pin"
    category = _guess_category(title, board_name)
    return _with_prompt(
        {
            "id": str(pin.get("id") or image),
            "title": title[:120],
            "description": title[:400],
            "imageUrl": image,
            "link": str(pin.get("link") or f"https://www.pinterest.com/pin/{pin.get('id')}/"),
            "board": board_name or fallback_board or "pinterest",
            "category": category,
            "mediaType": "image",
            "source": "pinterest",
        }
    )


def _guess_category(text: str, board: str = "") -> str:
    blob = f"{text} {board}".lower()
    rules = (
        ("character", ("portrait", "face", "actor", "actress", "beauty", "model", "people", "woman", "man", "人物", "角色")),
        ("scene", ("interior", "exterior", "city", "street", "room", "landscape", "architecture", "set", "scene", "场景", "夜景")),
        ("prop", ("product", "object", "bag", "shoe", "jewelry", "watch", "prop", "道具", "产品")),
        ("storyboard", ("film", "movie", "cinema", "poster", "frame", "drama", "trailer", "电影", "海报", "分镜")),
        ("style", ("fashion", "style", "editorial", "aesthetic", "look", "mood", "风格", "时尚")),
    )
    for cat, kws in rules:
        if any(k in blob for k in kws):
            return cat
    return "style"


def _clean_prompt_text(text: str) -> str:
    cleaned = _STREAM_TAIL.sub("", (text or "").strip())
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -–—|")
    return cleaned


def _build_prompt(*, title: str, description: str, category: str, explicit: str = "") -> str:
    if explicit.strip():
        return explicit.strip()[:1200]
    raw = _clean_prompt_text(description or title)
    if len(raw) >= 60:
        return raw[:1200]
    subject = _clean_prompt_text(title or description) or "影视画面"
    hint = _CATEGORY_PROMPT_HINTS.get(category, "电影级画面，专业摄影构图，清晰细节")
    return (
        f"{subject[:220]}。"
        f"{hint}。"
        "画面干净，清晰度高，细节清晰，专业摄影构图，无文字、无水印、无 LOGO。"
    )[:1200]


def _with_prompt(item: dict[str, Any]) -> dict[str, Any]:
    category = str(item.get("category") or "style")
    prompt = _build_prompt(
        title=str(item.get("title") or ""),
        description=str(item.get("description") or ""),
        category=category,
        explicit=str(item.get("prompt") or ""),
    )
    out = dict(item)
    out["prompt"] = prompt
    out["hasPrompt"] = bool(prompt.strip())
    out["mediaType"] = str(item.get("mediaType") or "image")
    return out


def _load_seed() -> list[dict[str, Any]]:
    for path in _SEED_CANDIDATES:
        if not path or str(path) == "." or not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        items = data.get("items") if isinstance(data, dict) else data
        out: list[dict[str, Any]] = []
        for item in items or []:
            if not isinstance(item, dict):
                continue
            image = str(item.get("imageUrl") or item.get("image") or "").strip()
            if not image:
                continue
            title = str(item.get("title") or "Pin")[:120]
            description = str(item.get("description") or item.get("title") or "")[:800]
            category = str(
                item.get("category")
                or _guess_category(title, str(item.get("board") or ""))
            )
            out.append(
                _with_prompt(
                    {
                        "id": str(item.get("id") or image),
                        "title": title,
                        "description": description[:400],
                        "imageUrl": _normalize_image(image),
                        "link": str(item.get("link") or "https://www.pinterest.com/"),
                        "board": str(item.get("board") or "seed"),
                        "category": category,
                        "prompt": str(item.get("prompt") or ""),
                        "mediaType": "image",
                        "source": "pinterest",
                    }
                )
            )
        if out:
            return out
    return []


def _http_get(url: str, timeout: float = 8.0) -> str:
    # Prefer curl when available — more reliable TLS to Pinterest from some hosts.
    curl = shutil.which("curl")
    if curl:
        try:
            proc = subprocess.run(
                [
                    curl,
                    "-fsSL",
                    "--connect-timeout",
                    str(max(1, int(timeout // 2))),
                    "--max-time",
                    str(int(timeout)),
                    "-A",
                    _UA,
                    "-H",
                    "Accept: application/json",
                    url,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            if proc.returncode == 0 and proc.stdout:
                return proc.stdout
        except Exception:  # noqa: BLE001
            pass
    req = urllib.request.Request(url, headers={"Accept": "application/json,text/html,*/*", "User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=timeout, context=_ssl_context()) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _from_user_pidgets(user: str, limit: int) -> list[dict[str, Any]]:
    url = f"https://widgets.pinterest.com/v3/pidgets/users/{urllib.parse.quote(user)}/pins/?page_size={max(limit, 25)}"
    raw = _http_get(url, timeout=10.0)
    data = json.loads(raw)
    pins = (((data or {}).get("data") or {}).get("pins")) or []
    items: list[dict[str, Any]] = []
    for pin in pins:
        if not isinstance(pin, dict):
            continue
        item = _pin_from_raw(pin, fallback_board=user)
        if item:
            items.append(item)
        if len(items) >= limit:
            break
    return items


def _from_board_pidgets(user: str, board: str, limit: int) -> list[dict[str, Any]]:
    path = f"{urllib.parse.quote(user)}/{urllib.parse.quote(board)}"
    url = f"https://widgets.pinterest.com/v3/pidgets/boards/{path}/pins/?page_size={max(limit, 25)}"
    raw = _http_get(url, timeout=10.0)
    data = json.loads(raw)
    pins = (((data or {}).get("data") or {}).get("pins")) or []
    items: list[dict[str, Any]] = []
    for pin in pins:
        if not isinstance(pin, dict):
            continue
        item = _pin_from_raw(pin, fallback_board=f"{user}/{board}")
        if item:
            items.append(item)
        if len(items) >= limit:
            break
    return items


def _dedupe(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    uniq: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items:
        img = item.get("imageUrl") or ""
        if not img or img in seen:
            continue
        seen.add(img)
        uniq.append(item)
    return uniq


def proxied_image_url(url: str) -> str:
    """Legacy helper — prefer inspire_store.public_media_url after ingest."""
    raw = (url or "").strip()
    if not raw:
        return ""
    if raw.startswith("/api/inspire/media/") or raw.startswith("/api/inspire/img"):
        return raw
    return raw


def _public_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Strip remote URLs / external links — clients only see local media paths."""
    out: list[dict[str, Any]] = []
    for item in items:
        row = dict(item)
        iid = str(row.get("id") or "").strip()
        image = str(row.get("imageUrl") or "").strip()
        if image.startswith("/api/inspire/media/"):
            pass
        elif iid:
            row["imageUrl"] = f"/api/inspire/media/{iid}"
        else:
            continue
        row.pop("link", None)
        row.pop("originUrl", None)
        row.pop("boardUrl", None)
        out.append(row)
    return out


def fetch_remote_image(url: str) -> tuple[bytes, str]:
    """Fetch a remote inspiration image (used by /api/inspire/img)."""
    raw = (url or "").strip()
    if not raw.startswith("https://"):
        raise ValueError("invalid image url")
    host = (urllib.parse.urlparse(raw).hostname or "").lower()
    if not (host.endswith("pinimg.com") or host.endswith("pinterest.com") or host.endswith("pinimg.com.")):
        raise ValueError("host not allowed")
    data = b""
    curl = shutil.which("curl")
    if curl:
        proc = subprocess.run(
            [
                curl,
                "-fsSL",
                "--connect-timeout",
                "8",
                "--max-time",
                "25",
                "-A",
                _UA,
                "-H",
                "Accept: image/avif,image/webp,image/*,*/*",
                raw,
            ],
            capture_output=True,
            check=False,
        )
        if proc.returncode == 0 and proc.stdout:
            data = proc.stdout
    if not data:
        req = urllib.request.Request(
            raw,
            headers={"Accept": "image/avif,image/webp,image/*,*/*", "User-Agent": _UA},
        )
        with urllib.request.urlopen(req, timeout=20, context=_ssl_context()) as resp:
            data = resp.read()
    if not data:
        raise RuntimeError("empty image body")
    ctype = "image/jpeg"
    lower = raw.lower()
    if lower.endswith(".png"):
        ctype = "image/png"
    elif lower.endswith(".webp"):
        ctype = "image/webp"
    elif lower.endswith(".gif"):
        ctype = "image/gif"
    return data, ctype


def fetch_pins(
    limit: int = 48,
    force: bool = False,
    category: str = "all",
    offset: int = 0,
    q: str = "",
    media_type: str = "all",
) -> dict[str, Any]:
    """Serve inspiration from local PG/disk store; optionally refresh remote → ingest."""
    import inspire_store

    page_size = max(1, min(int(limit or 48), 120))
    start = max(0, int(offset or 0))
    errors: list[str] = []

    local_count = inspire_store.count_local()
    # Prefer already-localized library; only pull remote when empty or force refresh.
    if force or local_count < 12:
        now = time.time()
        if force or not _CACHE["items"] or now - float(_CACHE["ts"]) >= _CACHE_TTL:
            seed = _load_seed()
            live: list[dict[str, Any]] = []
            for src in _sources()[:12]:
                try:
                    if src.get("kind") == "board":
                        batch = _from_board_pidgets(src["user"], src.get("board") or "", 50)
                    else:
                        batch = _from_user_pidgets(src["user"], 50)
                    live.extend(batch)
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"{src.get('label') or src.get('user')}: {exc}")
                if len(live) >= 240:
                    break
            if live:
                pool = [_with_prompt(x) for x in _dedupe(live + seed)]
                source_tag = "pinterest"
            elif seed:
                pool = [_with_prompt(x) for x in _dedupe(seed)]
                source_tag = "pinterest-seed"
            else:
                pool = []
                source_tag = "empty"
            for row in pool:
                src = str(row.get("imageUrl") or "").strip()
                if src.startswith("https://"):
                    row["originUrl"] = src
            _CACHE["ts"] = now
            _CACHE["items"] = pool
            _CACHE["source"] = source_tag
            _CACHE["errors"] = errors[:6]
        # Localize into PG/disk so clients never hit pinimg.
        candidates = list(_CACHE.get("items") or [])
        try:
            # Sync: enough for the current page so the response is useful.
            inspire_store.ingest_many(
                candidates[start : start + page_size + 8],
                fetch_remote_image,
                max_items=page_size + 8,
            )
        except Exception as exc:  # noqa: BLE001
            errors.append(f"ingest: {exc}")

        # Async: fill the rest of the library without blocking this request.
        def _bg_ingest() -> None:
            try:
                inspire_store.ingest_many(candidates, fetch_remote_image, max_items=120)
            except Exception as exc:  # noqa: BLE001
                _CACHE.setdefault("errors", []).append(f"bg-ingest: {exc}")

        try:
            import threading

            threading.Thread(target=_bg_ingest, name="inspire-ingest", daemon=True).start()
        except Exception:
            pass

    items, total = inspire_store.list_local(
        category=category,
        media_type=media_type,
        q=q,
        limit=page_size,
        offset=start,
    )
    items = _public_items(items)
    # Attach prompts if metadata was thin
    items = [_with_prompt(x) for x in items]
    items = _public_items(items)
    end = start + len(items)
    next_offset = start + page_size if (start + page_size) < total else None
    source = "local" if inspire_store.count_local() else str(_CACHE.get("source") or "empty")
    return {
        "items": items,
        "source": source,
        "cached": not force and local_count >= 12,
        "count": len(items),
        "total": total,
        "offset": start,
        "limit": page_size,
        "nextOffset": next_offset,
        "hasMore": next_offset is not None,
        "categories": _categories(),
        "errors": (errors or list(_CACHE.get("errors") or []))[:5],
        "boards": [],
    }
