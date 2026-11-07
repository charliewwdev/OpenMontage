"""Cloudflare Workers AI — FLUX.1 schnell (shared 10k Neurons/day free).

Docs: https://developers.cloudflare.com/workers-ai/models/flux-1-schnell/
Auth: CF_ACCOUNT_ID + CF_API_TOKEN (Workers AI edit permission).
"""

from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_MODEL = "@cf/black-forest-labs/flux-1-schnell"


class CfImageError(RuntimeError):
    pass


def _secret(name: str, default: str = "") -> str:
    try:
        from settings_store import get_secret

        return (get_secret(name, default) or default or "").strip()
    except Exception:
        return (os.environ.get(name) or default or "").strip()


def api_token() -> str:
    return _secret("CF_API_TOKEN") or _secret("CLOUDFLARE_API_TOKEN")


def account_id() -> str:
    return _secret("CF_ACCOUNT_ID") or _secret("CLOUDFLARE_ACCOUNT_ID")


def configured() -> bool:
    return bool(api_token() and account_id())


def active_model() -> str:
    return (_secret("CF_IMAGE_MODEL") or DEFAULT_MODEL).strip() or DEFAULT_MODEL


def generate_image(*, prompt: str, ratio: str, out_path: Path) -> Path:
    token = api_token()
    account = account_id()
    if not token or not account:
        raise CfImageError("未配置 CF_ACCOUNT_ID + CF_API_TOKEN（Cloudflare Workers AI）")
    model = active_model()
    aspect = {
        "9:16": "vertical 9:16 portrait composition",
        "16:9": "widescreen 16:9 landscape composition",
        "1:1": "square 1:1 composition",
        "3:4": "portrait 3:4 composition",
        "4:3": "landscape 4:3 composition",
    }.get(ratio, "")
    full_prompt = f"{(prompt or '').strip()[:1800]} {aspect}".strip()
    url = f"https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/{model}"
    body = json.dumps({"prompt": full_prompt, "steps": 4}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            payload = json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:400]
        raise CfImageError(f"Cloudflare Workers AI {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise CfImageError(f"Cloudflare 连接失败: {exc.reason}") from exc

    result = payload.get("result") if isinstance(payload, dict) else None
    image_b64 = ""
    if isinstance(result, dict):
        image_b64 = str(result.get("image") or "")
    elif isinstance(payload, dict):
        image_b64 = str(payload.get("image") or "")
    if not image_b64:
        raise CfImageError(f"Cloudflare 未返回图片: {str(payload)[:240]}")
    try:
        blob = base64.b64decode(image_b64)
    except Exception as exc:
        raise CfImageError("Cloudflare 图片 base64 解码失败") from exc
    if not blob:
        raise CfImageError("Cloudflare 返回空图片")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(blob)
    return out_path
