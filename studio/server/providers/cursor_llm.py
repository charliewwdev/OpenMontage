"""Cursor Cloud Agents API as OpenAI-JSON stand-in (model Auto / default).

Cursor API keys (crsr_*) are NOT chat-completions keys. They drive Cloud Agents.
We launch a no-repo agent, poll the run, and parse JSON from the result text.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any

from .deepseek import DeepSeekError, extract_json


def _secret(name: str, default: str = "") -> str:
    try:
        from settings_store import get_secret

        return get_secret(name, default)
    except Exception:
        import os

        return (os.environ.get(name) or default or "").strip()


def cursor_configured() -> bool:
    return bool(_secret("CURSOR_API_KEY"))


def _api_base() -> str:
    return _secret("CURSOR_API_BASE", "https://api.cursor.com").rstrip("/")


def _api_key() -> str:
    key = _secret("CURSOR_API_KEY")
    if not key:
        raise DeepSeekError("未配置 CURSOR_API_KEY")
    return key


def _model_id() -> str:
    # GET /v1/models → id "default" aliases ["auto"]
    raw = _secret("CURSOR_MODEL", "auto").lower()
    if raw in {"auto", "default", ""}:
        return "default"
    return raw


def _request(method: str, path: str, body: dict[str, Any] | None = None, timeout: int = 60) -> Any:
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        f"{_api_base()}{path}",
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {_api_key()}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8") or "{}"
            return json.loads(raw)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:800]
        raise DeepSeekError(f"Cursor API 错误 ({exc.code}): {detail}") from exc


def chat_json(
    *,
    system: str,
    user: str,
    temperature: float = 0.7,
    max_tokens: int = 8192,
    retries: int = 2,
) -> Any:
    """Ask Cursor Auto (Cloud Agent, no-repo) for a JSON object."""
    del temperature, max_tokens  # agent API has no direct equivalents
    last_err: Exception | None = None
    t0 = time.time()
    model = _model_id()
    for attempt in range(max(1, retries)):
        extra = ""
        if attempt > 0:
            extra = "\n\n【重试】只输出一个完整 JSON 对象，不要 Markdown 代码块，不要解释。"
        prompt_text = (
            f"{system.strip()}\n\n"
            f"{user.strip()}\n\n"
            "重要：你的最终回复必须是且仅是一个合法 JSON 对象。"
            f"{extra}"
        )
        try:
            created = _request(
                "POST",
                "/v1/agents",
                {
                    "prompt": {"text": prompt_text},
                    "model": {"id": model},
                    "name": f"om-json-{int(time.time()) % 100000}",
                },
                timeout=90,
            )
            agent = created.get("agent") or {}
            run = created.get("run") or {}
            agent_id = agent.get("id")
            run_id = run.get("id") or agent.get("latestRunId")
            if not agent_id or not run_id:
                raise DeepSeekError(f"Cursor 未返回 agent/run: {created}")

            deadline = time.time() + 180
            result_text = ""
            while time.time() < deadline:
                info = _request("GET", f"/v1/agents/{agent_id}/runs/{run_id}", timeout=60)
                run_info = info.get("run") or info
                status = str(run_info.get("status") or "")
                if status in {"FINISHED", "COMPLETED"}:
                    result_text = str(run_info.get("result") or "")
                    break
                if status in {"FAILED", "CANCELLED", "ERROR", "EXPIRED"}:
                    raise DeepSeekError(f"Cursor run {status}: {run_info}")
                time.sleep(3)
            else:
                raise DeepSeekError("Cursor run 超时")

            if not result_text.strip():
                raise DeepSeekError("Cursor 返回空 result")
            data = extract_json(result_text)
            try:
                from usage_store import record_usage

                record_usage(
                    provider="cursor",
                    model=_secret("CURSOR_MODEL", "auto") or "auto",
                    kind="text",
                    ok=True,
                    tokens_in=max(1, len(prompt_text) // 2),
                    tokens_out=max(1, len(result_text) // 2),
                    latency_ms=int((time.time() - t0) * 1000),
                )
            except Exception:
                pass
            return data
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            continue
    try:
        from usage_store import record_usage

        record_usage(
            provider="cursor",
            model=_secret("CURSOR_MODEL", "auto") or "auto",
            kind="text",
            ok=False,
            status=500,
            latency_ms=int((time.time() - t0) * 1000),
            error=str(last_err or ""),
        )
    except Exception:
        pass
    raise DeepSeekError(str(last_err) if last_err else "Cursor 调用失败")
