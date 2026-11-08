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
    if meta.get("keyOptional"):
        return True
    return bool(_secret(str(meta.get("keyEnv") or "")))


def configured_providers() -> list[str]:
    return [p["id"] for p in LLM_PROVIDERS if provider_configured(p)]


# Free / free-tier hosts first — platform default when LLM_PROVIDER is unset.
# Fast / reliable first; NVIDIA last among free (cold start often 1–3 minutes).
_FREE_FIRST_LLM_IDS: tuple[str, ...] = (
    "groq",
    "cloudflare",
    "openrouter",
    "pollinations",
    "gemini",
    "sambanova",
    "cohere",
    "mistral",
    "nvidia",
)

_PAID_FALLBACK_LLM_IDS: tuple[str, ...] = (
    "gpuhome",
    "suanqiao",
    "deepseek",
    "openai",
    "anthropic",
    "qwen",
    "moonshot",
    "doubao",
    "zhipu",
    "grok",
    "minimax",
    "custom",
    "cursor",
)


def _free_first_enabled() -> bool:
    return (_secret("STUDIO_FREE_FIRST") or "1").lower() not in {"0", "false", "off", "no"}


def _llm_provider_pref() -> str:
    """Raw LLM_PROVIDER. Empty / auto / free → free-pool routing."""
    return (_secret("LLM_PROVIDER") or "").strip().lower()


def llm_free_pool_active() -> bool:
    """True when platform/user wants all free LLMs available (not a single pin)."""
    pref = _llm_provider_pref()
    return _free_first_enabled() and pref in {"", "auto", "free"}


def _provider_order() -> tuple[str, ...]:
    if _free_first_enabled():
        return _FREE_FIRST_LLM_IDS + _PAID_FALLBACK_LLM_IDS
    return _PAID_FALLBACK_LLM_IDS + _FREE_FIRST_LLM_IDS


def resolve_provider() -> dict[str, Any]:
    preferred = _llm_provider_pref()
    if preferred and preferred not in {"auto", "free"}:
        meta = provider_by_id(preferred)
        if meta and provider_configured(meta):
            # Explicit user/platform pick always wins (BYOK / paid pin).
            return meta
        if meta and not provider_configured(meta):
            raise LlmError(f"已选择 {meta['label']}，但未配置 API Key")
    # Free pool / unset: walk free hosts first, then paid fallbacks
    for pid in _provider_order():
        meta = provider_by_id(pid)
        if meta and provider_configured(meta):
            return meta
    raise LlmError("未配置任何文本大模型 API Key")


def provider_candidates() -> list[dict[str, Any]]:
    """Providers to try for chat. Free-pool: full cascade; pinned: single provider."""
    preferred = _llm_provider_pref()
    if preferred and preferred not in {"auto", "free"}:
        meta = provider_by_id(preferred)
        if meta and provider_configured(meta):
            return [meta]
        if meta and not provider_configured(meta):
            raise LlmError(f"已选择 {meta['label']}，但未配置 API Key")
        raise LlmError(f"未知 LLM 供应商: {preferred}")
    out: list[dict[str, Any]] = []
    for pid in _provider_order():
        meta = provider_by_id(pid)
        if meta and provider_configured(meta):
            out.append(meta)
    if not out:
        raise LlmError("未配置任何文本大模型 API Key")
    return out


def llm_backend_id() -> str:
    try:
        return resolve_provider()["id"]
    except LlmError:
        return "none"


def llm_ready() -> bool:
    return bool(configured_providers())


def _http_json(method: str, url: str, headers: dict[str, str], body: dict[str, Any] | None, timeout: int = 120) -> Any:
    data = None if body is None else json.dumps(body).encode("utf-8")
    # Groq / some edges return Cloudflare 1010 without a browser-like UA.
    merged = {
        "User-Agent": "Mozilla/5.0 (compatible; OpenMontageStudio/1.0)",
        **(headers or {}),
    }
    req = urllib.request.Request(url, data=data, method=method, headers=merged)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:800]
        raise LlmError(f"LLM API 错误 ({exc.code}): {detail}") from exc
    except urllib.error.URLError as exc:
        raise LlmError(f"LLM 网络错误: {exc.reason}") from exc
    except TimeoutError as exc:
        raise LlmError("LLM 请求超时") from exc


def _chat_openai_compat(
    *,
    key: str,
    base: str,
    model: str,
    system: str,
    user: str,
    temperature: float,
    max_tokens: int,
    timeout: int = 120,
) -> str:
    base = base.rstrip("/")
    if base.endswith("/chat/completions"):
        url = base
    else:
        url = f"{base}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "OpenMontage-DramaStudio/1.0",
    }
    if key:
        headers["Authorization"] = f"Bearer {key}"

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
        raw = _http_json("POST", url, headers, body, timeout=timeout)
    except LlmError as exc:
        # Some OpenAI-compatible gateways reject response_format
        if "response_format" in str(exc).lower() or "400" in str(exc):
            body.pop("response_format", None)
            raw = _http_json("POST", url, headers, body, timeout=timeout)
        else:
            raise
    message = ((raw.get("choices") or [{}])[0].get("message") or {})
    content = message.get("content") or ""
    # Free / OSS gateways (Groq gpt-oss, some OpenRouter :free) often put the
    # final answer in reasoning* while leaving content empty. Only adopt that
    # text when it already looks like JSON — raw chain-of-thought is not usable.
    if not str(content).strip():
        for key in ("reasoning", "reasoning_content", "reasoning_text"):
            alt = message.get(key)
            if not isinstance(alt, str) or not alt.strip():
                continue
            stripped = alt.strip()
            if stripped.startswith("{") or stripped.startswith("["):
                content = stripped
                break
            # Prefer a JSON object embedded in the reasoning trailer.
            brace = stripped.rfind("{")
            if brace >= 0 and "}" in stripped[brace:]:
                content = stripped[brace:]
                break
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
    timeout: int = 120,
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
        timeout=timeout,
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
    timeout: int = 120,
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
        timeout=timeout,
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


def _prepare_provider_endpoint(meta: dict[str, Any]) -> tuple[str, str, str, str]:
    """Return provider_id, key, base, model for a catalog entry."""
    provider_id = str(meta.get("id") or "unknown")
    key = _secret(str(meta.get("keyEnv") or ""))
    base = _secret(str(meta.get("baseEnv") or ""), str(meta.get("defaultBase") or ""))
    model = _secret(str(meta.get("modelEnv") or ""), str(meta.get("defaultModel") or ""))
    if provider_id == "cloudflare" and not base:
        account = _secret("CF_ACCOUNT_ID")
        if not account:
            raise LlmError("Cloudflare Workers AI 需要 CF_ACCOUNT_ID，或填写 CLOUDFLARE_AI_BASE_URL")
        base = f"https://api.cloudflare.com/client/v4/accounts/{account}/ai/v1"
    if provider_id == "nvidia" and not base:
        base = "https://integrate.api.nvidia.com/v1"
    return provider_id, key, base, model


def chat_json(
    *,
    system: str,
    user: str,
    temperature: float = 0.7,
    max_tokens: int = 8192,
    retries: int = 2,
) -> Any:
    import time

    from github_star import assert_github_star_or_raise

    assert_github_star_or_raise()

    candidates = provider_candidates()
    # Free-pool: short per-provider timeout so a cold NVIDIA does not block the product.
    pool = llm_free_pool_active()
    per_timeout = 45 if pool else 120
    last_err: Exception | None = None
    t0 = time.time()
    tried: list[str] = []

    for meta in candidates:
        provider_id, key, base, model = _prepare_provider_endpoint(meta)
        kind = str(meta.get("kind") or "openai")
        tried.append(provider_id)
        for attempt in range(max(1, retries if not pool else 1)):
            extra = ""
            if attempt > 0:
                extra = "\n\n【JSON 输出重试】只输出一个完整 JSON 对象，不要 Markdown 代码块。"
            sys_prompt = system
            user_prompt = user + extra
            try:
                from .llm_transports import transport_for

                transport = transport_for(kind)
                payload = transport.complete(
                    key=key,
                    base=base,
                    model=model,
                    system=sys_prompt,
                    user=user_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout=per_timeout,
                )
                if transport.returns_parsed:
                    return payload
                text = payload
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
        # Free pool: try next provider. Pinned: stop after retries on that one.
        if not pool:
            break

    try:
        from usage_store import record_usage

        record_usage(
            provider=tried[-1] if tried else "unknown",
            model="",
            kind="text",
            ok=False,
            status=500,
            tokens_in=_approx_tokens(system + user),
            latency_ms=int((time.time() - t0) * 1000),
            error=str(last_err or ""),
        )
    except Exception:
        pass
    detail = str(last_err) if last_err else "LLM 调用失败"
    if pool and len(tried) > 1:
        detail = f"{detail}（已尝试: {', '.join(tried)}）"
    raise LlmError(detail)
