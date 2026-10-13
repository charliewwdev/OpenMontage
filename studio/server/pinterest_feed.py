"""Fetch public Pinterest board pins for product / inspiration imagery."""

from __future__ import annotations

import json
import re
import socket
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from platform_config import load_platform_config

socket.setdefaulttimeout(8)

_CACHE: dict[str, Any] = {"ts": 0.0, "items": [], "source": ""}
_CACHE_TTL = 3600.0

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)


def _ssl_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    # Some environments (corporate / CI) fail Pinterest cert chain; keep feed usable.
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _boards() -> list[dict[str, str]]:
    cfg = load_platform_config().get("pinterest") or {}
    boards = cfg.get("boards") or []
    out: list[dict[str, str]] = []
    for item in boards:
        if not isinstance(item, dict):
            continue
        user = str(item.get("user") or "").strip()
        board = str(item.get("board") or "").strip()
        if user and board:
            out.append(
                {
                    "user": user,
                    "board": board,
                    "label": str(item.get("label") or board),
                }
            )
    return out


def _fallback_items() -> list[dict[str, Any]]:
    cfg = load_platform_config().get("pinterest") or {}
    items = cfg.get("fallbackPins") or []
    out: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        image = str(item.get("image") or item.get("imageUrl") or "").strip()
        if not image:
            continue
        out.append(
            {
                "id": str(item.get("id") or image),
                "title": str(item.get("title") or item.get("description") or "Pinterest"),
                "description": str(item.get("description") or ""),
                "imageUrl": image,
                "link": str(item.get("link") or item.get("url") or ""),
                "board": str(item.get("board") or "fallback"),
                "source": "fallback",
            }
        )
    return out


def _http_get(url: str, timeout: float = 8.0) -> str:
    req = urllib.request.Request(url, headers={"Accept": "application/json,text/html,*/*", "User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=timeout, context=_ssl_context()) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _from_pidgets(user: str, board: str, limit: int) -> list[dict[str, Any]]:
    path = f"{urllib.parse.quote(user)}/{urllib.parse.quote(board)}"
    url = f"https://widgets.pinterest.com/v3/pidgets/boards/{path}/pins/?page_size={max(limit, 25)}"
    raw = _http_get(url, timeout=6.0)
    data = json.loads(raw)
    pins = (((data or {}).get("data") or {}).get("pins")) or []
    items: list[dict[str, Any]] = []
    for pin in pins:
        if not isinstance(pin, dict):
            continue
        images = pin.get("images") or {}
        image = ""
        for key in ("orig", "736x", "564x", "474x", "237x"):
            node = images.get(key) if isinstance(images, dict) else None
            if isinstance(node, dict) and node.get("url"):
                image = str(node["url"])
                break
        if not image:
            continue
        items.append(
            {
                "id": str(pin.get("id") or image),
                "title": str(pin.get("description") or pin.get("grid_title") or "Pin")[:160],
                "description": str(pin.get("description") or "")[:400],
                "imageUrl": image,
                "link": str(pin.get("link") or f"https://www.pinterest.com/pin/{pin.get('id')}/"),
                "board": f"{user}/{board}",
                "source": "pinterest",
            }
        )
        if len(items) >= limit:
            break
    return items


def _from_board_html(user: str, board: str, limit: int) -> list[dict[str, Any]]:
    url = f"https://www.pinterest.com/{urllib.parse.quote(user)}/{urllib.parse.quote(board)}/"
    html = _http_get(url, timeout=8.0)
    urls = re.findall(r"https://i\.pinimg\.com/[^\"'\\s]+", html)
    seen: set[str] = set()
    items: list[dict[str, Any]] = []
    for u in urls:
        # Prefer larger variants
        cleaned = u.replace("/236x/", "/736x/").replace("/474x/", "/736x/")
        if cleaned in seen:
            continue
        if any(x in cleaned for x in ("/avatars/", "/user/", ".svg")):
            continue
        seen.add(cleaned)
        items.append(
            {
                "id": cleaned,
                "title": f"{user}/{board}",
                "description": "",
                "imageUrl": cleaned,
                "link": url,
                "board": f"{user}/{board}",
                "source": "pinterest-html",
            }
        )
        if len(items) >= limit:
            break
    return items


def fetch_pins(limit: int = 24, force: bool = False) -> dict[str, Any]:
    now = time.time()
    if not force and _CACHE["items"] and now - float(_CACHE["ts"]) < _CACHE_TTL:
        items = _CACHE["items"][:limit]
        return {"items": items, "source": _CACHE["source"], "cached": True, "count": len(items)}

    boards = _boards()
    collected: list[dict[str, Any]] = []
    errors: list[str] = []
    source = "empty"

    per_board = max(8, min(limit, 16))
    # Prefer live Pinterest; bail early to configured fallbacks if network is blocked.
    for board in boards[:2]:
        try:
            batch = _from_pidgets(board["user"], board["board"], per_board)
            if not batch:
                batch = _from_board_html(board["user"], board["board"], per_board)
            if batch:
                collected.extend(batch)
                source = "pinterest"
                if len(collected) >= limit:
                    break
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{board['user']}/{board['board']}: {exc}")
            continue

    if not collected:
        collected = _fallback_items()
        source = "fallback" if collected else "empty"

    # de-dupe by image url
    uniq: list[dict[str, Any]] = []
    seen_img: set[str] = set()
    for item in collected:
        img = item.get("imageUrl") or ""
        if not img or img in seen_img:
            continue
        seen_img.add(img)
        uniq.append(item)

    _CACHE["ts"] = now
    _CACHE["items"] = uniq
    _CACHE["source"] = source
    items = uniq[:limit]
    return {
        "items": items,
        "source": source,
        "cached": False,
        "count": len(items),
        "errors": errors[:5],
        "boards": [f"{b['user']}/{b['board']}" for b in boards],
    }
