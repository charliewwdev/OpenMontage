"""Volcengine Ark Seedream image generation."""

from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

from . import volc_key

API_URL = "https://ark.cn-beijing.volces.com/api/v3/images/generations"

SIZES = {
    "16:9": "2848x1600",
    "9:16": "1600x2848",
    "4:3": "2304x1728",
    "3:4": "1728x2304",
    "1:1": "2048x2048",
}


class SeedreamError(RuntimeError):
    pass


def generate_image(
    *,
    prompt: str,
    ratio: str,
    out_path: Path,
    reference_path: Path | None = None,
) -> Path:
    key = volc_key()
    if not key:
        raise SeedreamError("未配置 VOLCENGINE_API_KEY 或 ARK_API_KEY")
    try:
        from platform_config import seedream_model

        model = seedream_model() or os.environ.get("SEEDREAM_MODEL") or ""
    except Exception:
        model = os.environ.get("SEEDREAM_MODEL") or ""
    if not model:
        raise SeedreamError("未配置 SEEDREAM_MODEL（见 studio/config/platform.yaml defaults.seedreamModel）")
    body: dict = {
        "model": model,
        "prompt": prompt,
        "size": SIZES.get(ratio) or SIZES["9:16"],
        "sequential_image_generation": "disabled",
        "response_format": "b64_json",
        "output_format": "png",
        "watermark": False,
        "optimize_prompt_options": {"mode": "standard"},
    }
    if reference_path and reference_path.is_file():
        data = reference_path.read_bytes()
        mime = "image/png" if reference_path.suffix.lower() == ".png" else "image/jpeg"
        body["image"] = f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"

    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise SeedreamError(f"Seedream API 错误 ({exc.code}): {detail}") from exc

    if raw.get("error"):
        raise SeedreamError((raw["error"] or {}).get("message") or "Seedream 生成失败")
    first = next((x for x in (raw.get("data") or []) if x.get("b64_json")), None)
    if not first:
        raise SeedreamError("Seedream 未返回 Base64 图片")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(base64.b64decode(first["b64_json"]))
    return out_path
