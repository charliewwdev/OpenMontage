"""Hugging Face Inference Providers — text-to-image (small free monthly credits).

Docs: https://huggingface.co/docs/inference-providers
Token: https://huggingface.co/settings/tokens
"""

from __future__ import annotations

import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

DEFAULT_MODEL = "black-forest-labs/FLUX.1-schnell"
API = "https://router.huggingface.co/hf-inference/models"


class HfImageError(RuntimeError):
    pass


def _secret(name: str, default: str = "") -> str:
    try:
        from settings_store import get_secret

        return (get_secret(name, default) or default or "").strip()
    except Exception:
        return (os.environ.get(name) or default or "").strip()


def api_key() -> str:
    return _secret("HF_TOKEN") or _secret("HUGGINGFACE_HUB_TOKEN")


def configured() -> bool:
    return bool(api_key())


def active_model() -> str:
    return (_secret("HF_IMAGE_MODEL") or DEFAULT_MODEL).strip() or DEFAULT_MODEL


def generate_image(*, prompt: str, ratio: str, out_path: Path) -> Path:
    key = api_key()
    if not key:
        raise HfImageError("未配置 HF_TOKEN（huggingface.co/settings/tokens）")
    model = active_model()
    # HF inference image API ignores exact pixels; keep prompt aspect hint.
    aspect = {
        "9:16": "vertical 9:16 portrait",
        "16:9": "widescreen 16:9",
        "1:1": "square 1:1",
        "3:4": "portrait 3:4",
        "4:3": "landscape 4:3",
    }.get(ratio, "")
    full_prompt = f"{(prompt or '').strip()[:3500]} {aspect}".strip()
    url = f"{API}/{urllib.parse.quote(model, safe='/')}"
    import json

    req = urllib.request.Request(
        url,
        data=json.dumps({"inputs": full_prompt}).encode(),
        method="POST",
        headers={
            "Authorization": f"Bearer {key}",
            "Accept": "image/png",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            blob = resp.read()
            ctype = (resp.headers.get("Content-Type") or "").lower()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:400]
        raise HfImageError(f"HF {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise HfImageError(f"HF 连接失败: {exc.reason}") from exc
    if not blob or ("json" in ctype and blob[:1] == b"{"):
        raise HfImageError(f"HF 未返回图片: {(blob[:200] or b'').decode('utf-8', errors='replace')}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(blob)
    return out_path
