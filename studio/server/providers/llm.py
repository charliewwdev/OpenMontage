"""Unified LLM JSON chat — routes to DeepSeek / OpenAI / Claude / Gemini / Cursor / etc."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any

from .llm_catalog import LLM_PROVIDERS, provider_by_id


class LlmError(RuntimeError):
    pass


def _strip_json_fences(text: str) -> str:
    trimmed = (text or "").strip()
    trimmed = re.sub(r"^```(?:json)?\s*", "", trimmed, flags=re.I)
    trimmed = re.sub(r"\s*```$", "", trimmed)
    return trimmed.strip()


def _repair_json_text(text: str) -> str:
    """Best-effort fixes for common LLM JSON slips (trailing commas, smart quotes)."""
    s = text
    s = s.replace("\u201c", '"').replace("\u201d", '"').replace("\u2018", "'").replace("\u2019", "'")
    # Remove trailing commas before } or ]
    s = re.sub(r",(\s*[}\]])", r"\1", s)
    return s


def _close_truncated_json(text: str) -> str:
    """If the model cut off mid-object, close open braces/brackets when possible."""
    s = text.rstrip()
    if not s or s[-1] in "{}]":
        return s
    # Drop a trailing incomplete string fragment after the last comma/colon.
    cut = max(s.rfind(","), s.rfind(":"), s.rfind("{"), s.rfind("["))
    if cut > 0:
        s = s[: cut + 1].rstrip(",: \n\t")
    opens = s.count("{") - s.count("}")
    opens_b = s.count("[") - s.count("]")
    if opens < 0 or opens_b < 0 or opens + opens_b > 12:
        return text
    return s + ("]" * max(0, opens_b)) + ("}" * max(0, opens))


def extract_json(text: str) -> Any:
    trimmed = _strip_json_fences(text)
    candidates: list[str] = [trimmed]
    start = trimmed.find("{")
    end = trimmed.rfind("}")
    if start >= 0 and end > start:
        candidates.append(trimmed[start : end + 1])
    a0 = trimmed.find("[")
    a1 = trimmed.rfind("]")
    if a0 >= 0 and a1 > a0:
        candidates.append(trimmed[a0 : a1 + 1])
    if start >= 0:
        candidates.append(_close_truncated_json(trimmed[start:]))

    last_err: Exception | None = None
    seen: set[str] = set()
    for raw in candidates:
        for variant in (raw, _repair_json_text(raw), _repair_json_text(_close_truncated_json(raw))):
            if not variant or variant in seen:
                continue
            seen.add(variant)
            try:
                data = json.loads(variant)
            except json.JSONDecodeError as exc:
                last_err = exc
                continue
            if isinstance(data, list):
                return {"shots": data}
            return data
    detail = f"：{last_err}" if last_err else ""
    raise LlmError(f"模型未返回有效 JSON{detail}")


def _secret(name: str, default: str = "") -> str:
    """Dynamically read from secrets store (file), with env fallback."""
    try:
        from settings_store import get_secret

        return get_secret(name, default)
    except Exception:
        return (os.environ.get(name) or default or "").strip()


def provider_configured(meta: dict[str, Any]) -> bool:
    return bool(_secret(str(meta.get("keyEnv") or "")))


def configured_providers() -> list[str]:
    return [p["id"] for p in LLM_PROVIDERS if provider_configured(p)]


def resolve_provider() -> dict[str, Any]:
    preferred = _secret("LLM_PROVIDER").lower()
    if preferred:
        meta = provider_by_id(preferred)
        if meta and provider_configured(meta):
            return meta
        if meta and not provider_configured(meta):
            raise LlmError(f"已选择 {meta['label']}，但未配置 API Key")
    # Prefer explicit order when auto-picking
    for pid in (
        "gpuhome",
        "deepseek",
        "openai",
        "anthropic",
        "gemini",
        "qwen",
        "moonshot",
        "doubao",
        "zhipu",
        "grok",
        "minimax",
        "openrouter",
        "mistral",
        "custom",
        "cursor",
    ):
        meta = provider_by_id(pid)
        if meta and provider_configured(meta):
            return meta
    raise LlmError("未配置任何文本大模型 API Key")


def llm_backend_id() -> str:
    try:
        return resolve_provider()["id"]
    except LlmError:
        return "none"


def llm_ready() -> bool:
    return bool(configured_providers())


def _http_json(method: str, url: str, headers: dict[str, str], body: dict[str, Any] | None, timeout: int = 300) -> Any:
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:800]
        raise LlmError(f"LLM API 错误 ({exc.code}): {detail}") from exc


def _chat_openai_compat(
    *,
    key: str,
    base: str,
    model: str,
    system: str,
    user: str,
    temperature: float,
    max_tokens: int,
) -> str:
    base = base.rstrip("/")
    if base.endswith("/chat/completions"):
        url = base
    else:
        url = f"{base}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {key}",
    }
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    body: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
    }
    try:
        raw = _http_json("POST", url, headers, body)
    except LlmError as exc:
        # Some OpenAI-compatible gateways reject response_format
        if "response_format" in str(exc).lower() or "400" in str(exc):
            body.pop("response_format", None)
            raw = _http_json("POST", url, headers, body)
        else:
            raise
    content = (((raw.get("choices") or [{}])[0].get("message") or {}).get("content")) or ""
    if not str(content).strip():
        raise LlmError("模型返回空 content")
    return str(content)


def _chat_anthropic(
    *,
    key: str,
    base: str,
    model: str,
    system: str,
    user: str,
    temperature: float,
    max_tokens: int,
) -> str:
    base = base.rstrip("/")
    url = f"{base}/v1/messages" if not base.endswith("/messages") else base
    raw = _http_json(
        "POST",
        url,
        {
            "Content-Type": "application/json",
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
        },
        {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "system": system + "\n\n只输出合法 JSON 对象，不要 Markdown。",
            "messages": [{"role": "user", "content": user}],
        },
    )
    parts = raw.get("content") or []
    text = "".join(str(p.get("text") or "") for p in parts if isinstance(p, dict))
    if not text.strip():
        raise LlmError("Claude 返回空 content")
    return text


def _chat_gemini(
    *,
    key: str,
    base: str,
    model: str,
    system: str,
    user: str,
    temperature: float,
    max_tokens: int,
) -> str:
    base = base.rstrip("/")
    url = f"{base}/models/{model}:generateContent?key={key}"
    raw = _http_json(
        "POST",
        url,
        {"Content-Type": "application/json"},
        {
            "systemInstruction": {"parts": [{"text": system + "\n只输出合法 JSON 对象。"}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
                "responseMimeType": "application/json",
            },
        },
    )
    cands = raw.get("candidates") or []
    parts = (((cands[0] if cands else {}).get("content") or {}).get("parts")) or []
    text = "".join(str(p.get("text") or "") for p in parts if isinstance(p, dict))
    if not text.strip():
        raise LlmError("Gemini 返回空 content")
    return text


def _approx_tokens(text: str) -> int:
    # Rough bilingual estimate: ~2 chars / token for CJK-heavy prompts
    return max(1, len(text or "") // 2)


def chat_json(
    *,
    system: str,
    user: str,
    temperature: float = 0.7,
    max_tokens: int = 8192,
    retries: int = 2,
) -> Any:
    import time

    meta = resolve_provider()
    kind = meta["kind"]
    key = _secret(meta["keyEnv"])
    base = _secret(meta["baseEnv"], meta.get("defaultBase") or "")
    model = _secret(meta["modelEnv"], meta.get("defaultModel") or "")
    provider_id = str(meta.get("id") or "unknown")

    last_err: Exception | None = None
    t0 = time.time()

    for attempt in range(max(1, retries)):
        extra = ""
        if attempt > 0:
            extra = "\n\n【JSON 输出重试】只输出一个完整 JSON 对象，不要 Markdown 代码块。"
        sys_prompt = system
        user_prompt = user + extra
        try:
            if kind == "cursor":
                from .cursor_llm import chat_json as cursor_chat_json

                return cursor_chat_json(
                    system=sys_prompt,
                    user=user_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    retries=1,
                )
            if kind == "anthropic":
                text = _chat_anthropic(
                    key=key,
                    base=base,
                    model=model,
                    system=sys_prompt,
                    user=user_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            elif kind == "gemini":
                text = _chat_gemini(
                    key=key,
                    base=base,
                    model=model,
                    system=sys_prompt,
                    user=user_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            else:
                text = _chat_openai_compat(
                    key=key,
                    base=base,
                    model=model,
                    system=sys_prompt,
                    user=user_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            data = extract_json(text)
            try:
                from usage_store import record_usage

                record_usage(
                    provider=provider_id,
                    model=model,
                    kind="text",
                    ok=True,
                    status=200,
                    tokens_in=_approx_tokens(sys_prompt + user_prompt),
                    tokens_out=_approx_tokens(text),
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
            provider=provider_id,
            model=model,
            kind="text",
            ok=False,
            status=500,
            tokens_in=_approx_tokens(system + user),
            latency_ms=int((time.time() - t0) * 1000),
            error=str(last_err or ""),
        )
    except Exception:
        pass
    raise LlmError(str(last_err) if last_err else "LLM 调用失败")
