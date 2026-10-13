"""Fetch public Pinterest pins for inspiration imagery.

Live fetch uses Pinterest public pidgets. When the server network cannot reach
Pinterest, the curated seed catalog (real pinimg URLs) keeps the wall full.
"""

from __future__ import annotations

import json
import os
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
    return {
        "id": str(pin.get("id") or image),
        "title": title[:120],
        "description": title[:400],
        "imageUrl": image,
        "link": str(pin.get("link") or f"https://www.pinterest.com/pin/{pin.get('id')}/"),
        "board": board_name or fallback_board or "pinterest",
        "category": _guess_category(title, board_name),
        "source": "pinterest",
    }


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
            out.append(
                {
                    "id": str(item.get("id") or image),
                    "title": str(item.get("title") or "Pin")[:120],
                    "description": str(item.get("description") or item.get("title") or "")[:400],
                    "imageUrl": _normalize_image(image),
                    "link": str(item.get("link") or "https://www.pinterest.com/"),
                    "board": str(item.get("board") or "seed"),
                    "category": str(item.get("category") or _guess_category(str(item.get("title") or ""), str(item.get("board") or ""))),
                    "source": "pinterest",
                }
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


def fetch_pins(
    limit: int = 48,
    force: bool = False,
    category: str = "all",
    offset: int = 0,
) -> dict[str, Any]:
    now = time.time()
    cached = False
    if not force and _CACHE["items"] and now - float(_CACHE["ts"]) < _CACHE_TTL:
        pool = list(_CACHE["items"])
        source = str(_CACHE["source"] or "pinterest")
        cached = True
    else:
        seed = _load_seed()
        live: list[dict[str, Any]] = []
        errors: list[str] = []
        # Pull more pins from more sources so the wall stays dense after pagination.
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
            pool = _dedupe(live + seed)
            source = "pinterest"
        elif seed:
            pool = _dedupe(seed)
            source = "pinterest-seed"
        else:
            pool = []
            source = "empty"

        _CACHE["ts"] = now
        _CACHE["items"] = pool
        _CACHE["source"] = source
        _CACHE["errors"] = errors[:6]

    cat = (category or "all").strip().lower()
    if cat and cat not in ("all", "全部", "*"):
        filtered = [x for x in pool if str(x.get("category") or "").lower() == cat]
        pool_view = filtered or pool
    else:
        pool_view = pool

    page_size = max(1, min(int(limit or 48), 120))
    start = max(0, int(offset or 0))
    end = start + page_size
    items = pool_view[start:end]
    total = len(pool_view)
    next_offset = end if end < total else None
    return {
        "items": items,
        "source": source,
        "cached": cached,
        "count": len(items),
        "total": total,
        "offset": start,
        "limit": page_size,
        "nextOffset": next_offset,
        "hasMore": next_offset is not None,
        "categories": _categories(),
        "errors": list(_CACHE.get("errors") or [])[:5],
        "boards": [s.get("label") or s.get("user") for s in _sources()],
    }
