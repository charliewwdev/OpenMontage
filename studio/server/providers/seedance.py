"""Volcengine Ark Seedance video task API."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from . import volc_key

API_URL = "https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks"

SEEDANCE_MODELS = [
    {
        "id": "doubao-seedance-2-0-260128",
        "name": "Seedance 2.0 Pro",
        "resolutions": ["480p", "720p", "1080p", "4k"],
        "minDuration": 4,
        "maxDuration": 15,
    },
    {
        "id": "doubao-seedance-2-0-fast-260128",
        "name": "Seedance 2.0 Fast",
        "resolutions": ["480p", "720p"],
        "minDuration": 4,
        "maxDuration": 15,
    },
    {
        "id": "doubao-seedance-2-0-mini-260615",
        "name": "Seedance 2.0 Mini",
        "resolutions": ["480p", "720p"],
        "minDuration": 4,
        "maxDuration": 15,
    },
]


class SeedanceError(RuntimeError):
    pass


def get_model(model_id: str) -> dict:
    return next((m for m in SEEDANCE_MODELS if m["id"] == model_id), SEEDANCE_MODELS[0])


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
    m = get_model(model)
    if resolution not in m["resolutions"]:
        raise SeedanceError(f"{m['name']} 不支持 {resolution}")
    model_id = os.environ.get("SEEDANCE_MODEL") if model == SEEDANCE_MODELS[0]["id"] else model
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
        API_URL,
        data=json.dumps(body).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise SeedanceError(f"Seedance API 错误 ({exc.code}): {detail}") from exc
    if raw.get("error"):
        raise SeedanceError((raw["error"] or {}).get("message") or "Seedance 任务创建失败")
    if not raw.get("id"):
        raise SeedanceError("Seedance 未返回任务 ID")
    return raw["id"]


def query_task(task_id: str) -> dict[str, Any]:
    key = volc_key()
    if not key:
        raise SeedanceError("未配置 VOLCENGINE_API_KEY 或 ARK_API_KEY")
    req = urllib.request.Request(
        f"{API_URL}/{task_id}",
        headers={"Authorization": f"Bearer {key}"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise SeedanceError(f"Seedance 查询失败 ({exc.code}): {detail}") from exc
    content = data.get("content") or {}
    return {
        "status": data.get("status"),
        "videoUrl": content.get("video_url"),
        "lastFrameUrl": content.get("last_frame_url"),
        "duration": data.get("duration"),
        "resolution": data.get("resolution"),
        "error": (data.get("error") or {}).get("message"),
    }
