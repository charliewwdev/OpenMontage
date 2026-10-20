"""NVIDIA NIM hosted open image models (FLUX schnell / klein).

Trial key: https://build.nvidia.com/settings
Docs: https://docs.api.nvidia.com/nim/reference/black-forest-labs-flux_1-schnell-infer
"""

from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

API_ROOT = "https://ai.api.nvidia.com/v1/genai"

# id -> NIM slug. schnell is the speed pick; klein is the newer distilled FLUX.2.
MODELS: dict[str, str] = {
    "flux-3-image-klein": "black-forest-labs/flux-3-image-klein",
    "flux.1-schnell": "black-forest-labs/flux.1-schnell",
    "flux.2-klein-4b": "black-forest-labs/flux.2-klein-4b",
}

# NIM trial accepts a limited size set. Prefer portrait when the API allows it.
SIZES: dict[str, tuple[int, int]] = {
    "9:16": (768, 1344),
    "16:9": (1344, 768),
    "3:4": (896, 1152),
    "4:3": (1152, 896),
    "1:1": (1024, 1024),
}


class NvidiaFluxError(RuntimeError):
    pass


def _secret(name: str, default: str = "") -> str:
    try:
        from settings_store import get_secret

        return (get_secret(name, default) or default or "").strip()
    except Exception:
        return (os.environ.get(name) or default or "").strip()


def api_key() -> str:
    return _secret("NVIDIA_API_KEY") or _secret("NVIDIA_NIM_API_KEY")


def configured() -> bool:
    return bool(api_key())


def active_model() -> str:
    raw = (_secret("NVIDIA_IMAGE_MODEL") or "flux-3-image-klein").strip()
    return raw if raw in MODELS or "/" in raw else "flux-3-image-klein"


def _slug(model: str) -> str:
    if "/" in model:
        return model
    return MODELS.get(model, MODELS["flux.1-schnell"])


def _post(url: str, body: dict, key: str, timeout: int = 180) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        method="POST",
        headers={
            "Authorization": f"Bearer {key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="ignore")[:400]
        raise NvidiaFluxError(f"NVIDIA {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise NvidiaFluxError(f"NVIDIA 连接失败: {exc.reason}") from exc


def _b64_from(payload: dict) -> str:
    artifacts = payload.get("artifacts") or payload.get("data") or []
    if isinstance(artifacts, list):
        for item in artifacts:
            if not isinstance(item, dict):
                continue
            raw = item.get("base64") or item.get("b64_json") or ""
            if raw:
                return str(raw)
    image = payload.get("image")
    if isinstance(image, str) and len(image) > 80:
        return image.split(",", 1)[-1]
    raise NvidiaFluxError("NVIDIA 响应里没有图片")


def generate_image(
    *,
    prompt: str,
    ratio: str,
    out_path: Path,
    reference_path: Path | None = None,
    negative_prompt: str | None = None,
) -> Path:
    del negative_prompt  # FLUX has no negative prompt; callers already phrase positives.
    key = api_key()
    if not key:
        raise NvidiaFluxError("未配置 NVIDIA_API_KEY（build.nvidia.com 试用 Key）")
    model = active_model()
    slug = _slug(model)
    width, height = SIZES.get(ratio) or SIZES["9:16"]
    # FLUX.2 klein trial endpoint is documented at 1024 only.
    if slug.endswith("flux.2-klein-4b"):
        width, height = 1024, 1024
    body: dict = {
        "prompt": (prompt or "").strip()[:4000] or "a character sheet",
        "width": width,
        "height": height,
        "seed": 0,
        "steps": 4,
    }
    if reference_path and reference_path.is_file() and "klein" in slug:
        raw = base64.b64encode(reference_path.read_bytes()).decode()
        body["mode"] = "Image Editing"
        body["image"] = f"data:image/png;base64,{raw}"
    url = f"{API_ROOT}/{slug}"
    try:
        payload = _post(url, body, key)
    except NvidiaFluxError as exc:
        if width == 1024 and height == 1024:
            raise
        # Portrait sizes are rejected by some trial endpoints — retry the documented square.
        if "NVIDIA 4" not in str(exc) and "NVIDIA 422" not in str(exc):
            raise
        body["width"] = 1024
        body["height"] = 1024
        body.pop("mode", None)
        body.pop("image", None)
        payload = _post(url, body, key)
    blob = base64.b64decode(_b64_from(payload))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(blob)
    return out_path
