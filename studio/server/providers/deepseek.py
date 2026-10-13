"""DeepSeek OpenAI-compatible chat for script / storyboard JSON."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any


class DeepSeekError(RuntimeError):
    pass


def _cfg() -> tuple[str, str, str]:
    key = os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        raise DeepSeekError("未配置 DEEPSEEK_API_KEY")
    try:
        from platform_config import deepseek_base_url, deepseek_model

        base = deepseek_base_url().rstrip("/")
        model = deepseek_model()
    except Exception:
        base = (os.environ.get("DEEPSEEK_BASE_URL") or "https://api.deepseek.com").rstrip("/")
        model = os.environ.get("DEEPSEEK_MODEL") or "deepseek-chat"
    return key, base, model


def extract_json(text: str) -> Any:
    trimmed = text.strip()
    trimmed = re.sub(r"^```(?:json)?\s*", "", trimmed, flags=re.I)
    trimmed = re.sub(r"\s*```$", "", trimmed)
    try:
        return json.loads(trimmed)
    except json.JSONDecodeError:
        start = trimmed.find("{")
        end = trimmed.rfind("}")
        if start >= 0 and end > start:
            return json.loads(trimmed[start : end + 1])
        raise DeepSeekError("DeepSeek 未返回有效 JSON")


def chat_json(
    *,
    system: str,
    user: str,
    temperature: float = 0.7,
    max_tokens: int = 8192,
    retries: int = 2,
) -> Any:
    key, base, model = _cfg()
    last_err: Exception | None = None
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    for attempt in range(retries):
        if attempt > 0:
            messages = [
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": user
                    + "\n\n【JSON 输出重试】只输出一个完整 JSON 对象，不要 Markdown 代码块。",
                },
            ]
        body = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
        }
        req = urllib.request.Request(
            f"{base}/chat/completions",
            data=json.dumps(body).encode("utf-8"),
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {key}",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                raw = json.loads(resp.read().decode("utf-8"))
            content = (((raw.get("choices") or [{}])[0].get("message") or {}).get("content")) or ""
            if not content.strip():
                raise DeepSeekError("DeepSeek 返回空 content")
            return extract_json(content)
        except (urllib.error.HTTPError, DeepSeekError, json.JSONDecodeError) as exc:
            last_err = exc
            if isinstance(exc, urllib.error.HTTPError):
                detail = exc.read().decode("utf-8", errors="replace")[:500]
                last_err = DeepSeekError(f"DeepSeek API 错误 ({exc.code}): {detail}")
            continue
    raise DeepSeekError(str(last_err) if last_err else "DeepSeek 调用失败")
