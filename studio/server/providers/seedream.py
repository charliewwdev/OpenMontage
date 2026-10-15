"""Volcengine Ark Seedream image generation (standard /api/v3 or Agent Plan /api/plan/v3)."""

from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

from . import volc_key

DEFAULT_API_URL = "https://ark.cn-beijing.volces.com/api/v3/images/generations"
PLAN_API_URL = "https://ark.cn-beijing.volces.com/api/plan/v3/images/generations"

SIZES = {
    "16:9": "2848x1600",
    "9:16": "1600x2848",
    "4:3": "2304x1728",
    "3:4": "1728x2304",
    "1:1": "2048x2048",
}


class SeedreamError(RuntimeError):
    pass


def _secret(name: str, default: str = "") -> str:
    try:
        from settings_store import get_secret

        return get_secret(name, default)
    except Exception:
        return (os.environ.get(name) or default or "").strip()


def images_api_url() -> str:
    base = (_secret("ARK_API_BASE") or _secret("VOLCENGINE_API_BASE") or "").rstrip("/")
    if base:
        if base.endswith("/images/generations"):
            return base
        return f"{base}/images/generations"
    # Agent Plan exclusive keys must use /api/plan/v3
    if (_secret("ARK_PLAN") or "").strip().lower() in {"1", "true", "yes", "on", "agent"}:
        return PLAN_API_URL
    return DEFAULT_API_URL


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

        model = seedream_model() or ""
    except Exception:
        model = _secret("SEEDREAM_MODEL")

    if not model:
        raise SeedreamError("未配置 SEEDREAM_MODEL（见 studio/config/platform.yaml defaults.seedreamModel）")

    api_url = images_api_url()
    prefer_url = "/api/plan/" in api_url
    # Ark Seedream 5.x rejects several 4.x-only fields on /api/v3; keep the body minimal.
    body: dict = {
        "model": model,
        "prompt": prompt,
        "size": SIZES.get(ratio) or SIZES["9:16"],
        "response_format": "url" if prefer_url else "b64_json",
        "watermark": False,
    }
    if reference_path and reference_path.is_file():
        data = reference_path.read_bytes()
        mime = "image/png" if reference_path.suffix.lower() == ".png" else "image/jpeg"
        body["image"] = f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"

    req = urllib.request.Request(
        api_url,
        data=json.dumps(body).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
    )
    import time

    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        try:
            from usage_store import record_usage

            record_usage(
                provider="volcengine",
                model=model,
                kind="image",
                ok=False,
                status=int(exc.code),
                latency_ms=int((time.time() - t0) * 1000),
                error=detail,
            )
        except Exception:
            pass
        raise SeedreamError(f"Seedream API 错误 ({exc.code}): {detail}") from exc

    if raw.get("error"):
        raise SeedreamError((raw["error"] or {}).get("message") or "Seedream 生成失败")

    items = raw.get("data") or []
    first = next((x for x in items if x.get("b64_json") or x.get("url")), None)
    if not first:
        raise SeedreamError("Seedream 未返回图片")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    from media_qa import MediaQAError, assert_media_ok

    try:
        if first.get("b64_json"):
            out_path.write_bytes(base64.b64decode(first["b64_json"]))
        else:
            img_url = str(first.get("url") or "")
            with urllib.request.urlopen(img_url, timeout=120) as img_resp:
                out_path.write_bytes(img_resp.read())
        assert_media_ok(out_path, kind="image", unlink_on_fail=True)
    except MediaQAError as exc:
        try:
            from usage_store import record_usage

            record_usage(
                provider="volcengine",
                model=model,
                kind="image",
                ok=False,
                latency_ms=int((time.time() - t0) * 1000),
                error=str(exc),
            )
        except Exception:
            pass
        raise SeedreamError(f"Seedream 返回无效图片：{exc}") from exc
    except Exception:
        if out_path.is_file() and out_path.stat().st_size <= 0:
            try:
                out_path.unlink()
            except OSError:
                pass
        raise

    try:
        from usage_store import record_usage

        record_usage(
            provider="volcengine",
            model=model,
            kind="image",
            ok=True,
            latency_ms=int((time.time() - t0) * 1000),
        )
    except Exception:
        pass
    return out_path
