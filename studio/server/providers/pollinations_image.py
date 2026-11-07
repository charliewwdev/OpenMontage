"""Pollinations text-to-image — anonymous free (no API key required).

Docs: https://pollinations.ai/
GET https://image.pollinations.ai/prompt/{prompt}?width=&height=&model=
"""

from __future__ import annotations

import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

DEFAULT_MODEL = "flux"
API = "https://image.pollinations.ai/prompt"


class PollinationsImageError(RuntimeError):
    pass


def _secret(name: str, default: str = "") -> str:
    try:
        from settings_store import get_secret

        return (get_secret(name, default) or default or "").strip()
    except Exception:
        return (os.environ.get(name) or default or "").strip()


def configured() -> bool:
    flag = (_secret("POLLINATIONS_IMAGE") or "1").lower()
    return flag not in {"0", "false", "off", "no"}


def active_model() -> str:
    return (_secret("POLLINATIONS_IMAGE_MODEL") or DEFAULT_MODEL).strip() or DEFAULT_MODEL


def _size_for_ratio(ratio: str) -> tuple[int, int]:
    # Keep under common free-tier caps; Pollinations accepts arbitrary but prefers multiples of 16.
    mapping = {
        "1:1": (768, 768),
        "9:16": (576, 1024),
        "16:9": (1024, 576),
        "3:4": (768, 1024),
        "4:3": (1024, 768),
    }
    return mapping.get(ratio, (768, 768))


def generate_image(*, prompt: str, ratio: str, out_path: Path) -> Path:
    if not configured():
        raise PollinationsImageError("Pollinations 出图已关闭（POLLINATIONS_IMAGE=0）")
    text = (prompt or "").strip()[:1800]
    if not text:
        raise PollinationsImageError("prompt 为空")
    width, height = _size_for_ratio(ratio)
    model = active_model()
    qs = urllib.parse.urlencode(
        {
            "width": str(width),
            "height": str(height),
            "model": model,
            "nologo": "true",
            "enhance": "false",
        }
    )
    url = f"{API}/{urllib.parse.quote(text, safe='')}?{qs}"
    req = urllib.request.Request(
        url,
        method="GET",
        headers={
            "User-Agent": "OpenMontage-DramaStudio/1.0",
            "Accept": "image/*",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            blob = resp.read()
            ctype = (resp.headers.get("Content-Type") or "").lower()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:400]
        raise PollinationsImageError(f"Pollinations {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise PollinationsImageError(f"Pollinations 连接失败: {exc.reason}") from exc
    if not blob or ("json" in ctype and blob[:1] == b"{"):
        raise PollinationsImageError(
            f"Pollinations 未返回图片: {(blob[:200] or b'').decode('utf-8', errors='replace')}"
        )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(blob)
    return out_path
