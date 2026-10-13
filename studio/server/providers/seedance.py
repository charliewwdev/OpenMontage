"""Volcengine Ark Seedance video task API."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from . import volc_key


def _models() -> list[dict[str, Any]]:
    try:
        from platform_config import seedance_models

        models = seedance_models()
        if models:
            return models
    except Exception:
        pass
    return []


def _api_url() -> str:
    try:
        from platform_config import seedance_api_url

        return seedance_api_url()
    except Exception:
        return os.environ.get(
            "SEEDANCE_API_URL",
            "https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks",
        )


# Back-compat for imports that expect a module-level list
SEEDANCE_MODELS = _models()


class SeedanceError(RuntimeError):
    pass


def get_model(model_id: str) -> dict:
    models = _models()
    if not models:
        raise SeedanceError("platform.yaml 未配置 seedanceModels")
    return next((m for m in models if m["id"] == model_id), models[0])


def normalize_duration(model_id: str, duration: float | int) -> int:
    m = get_model(model_id)
    return max(m["minDuration"], min(m["maxDuration"], int(round(duration))))


def create_task(
    *,
    model: str,
    content: list[dict[str, Any]],
    ratio: str,
    resolution: str,
    duration: int,
) -> str:
    key = volc_key()
    if not key:
        raise SeedanceError("未配置 VOLCENGINE_API_KEY 或 ARK_API_KEY")
    models = _models()
    m = get_model(model)
    if resolution not in m["resolutions"]:
        raise SeedanceError(f"{m['name']} 不支持 {resolution}")
    default_id = models[0]["id"] if models else m["id"]
    model_id = os.environ.get("SEEDANCE_MODEL") if model == default_id else model
    model_id = model_id or m["id"]
    body = {
        "model": model_id,
        "content": content,
        "ratio": ratio,
        "resolution": resolution,
        "duration": normalize_duration(m["id"], duration),
        "generate_audio": True,
        "watermark": False,
        "return_last_frame": True,
    }
    req = urllib.request.Request(
        _api_url(),
        data=json.dumps(body).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise SeedanceError(f"Seedance 创建失败 HTTP {exc.code}: {detail}") from exc
    task_id = raw.get("id")
    if not task_id:
        raise SeedanceError(f"Seedance 未返回 task id: {raw}")
    return str(task_id)


def query_task(task_id: str) -> dict[str, Any]:
    key = volc_key()
    if not key:
        raise SeedanceError("未配置 VOLCENGINE_API_KEY 或 ARK_API_KEY")
    url = f"{_api_url().rstrip('/')}/{task_id}"
    req = urllib.request.Request(
        url,
        method="GET",
        headers={"Authorization": f"Bearer {key}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise SeedanceError(f"Seedance 查询失败 HTTP {exc.code}: {detail}") from exc
