"""LLM chat transports. A new protocol is a register_transport() call."""

from __future__ import annotations

from typing import Any, Protocol

from .registry import Registry


class LlmTransport(Protocol):
    kind: str
    # Cursor returns parsed JSON and skips the shared usage row (historical behavior).
    returns_parsed: bool

    def complete(self, **kwargs: Any) -> Any: ...


LLM_TRANSPORTS: Registry[LlmTransport] = Registry()


class _OpenAiTransport:
    kind = "openai"
    returns_parsed = False

    def complete(self, **kwargs: Any) -> str:
        from .llm import _chat_openai_compat

        return _chat_openai_compat(
            key=kwargs["key"],
            base=kwargs["base"],
            model=kwargs["model"],
            system=kwargs["system"],
            user=kwargs["user"],
            temperature=kwargs["temperature"],
            max_tokens=kwargs["max_tokens"],
        )


class _AnthropicTransport:
    kind = "anthropic"
    returns_parsed = False

    def complete(self, **kwargs: Any) -> str:
        from .llm import _chat_anthropic

        return _chat_anthropic(
            key=kwargs["key"],
            base=kwargs["base"],
            model=kwargs["model"],
            system=kwargs["system"],
            user=kwargs["user"],
            temperature=kwargs["temperature"],
            max_tokens=kwargs["max_tokens"],
        )


class _GeminiTransport:
    kind = "gemini"
    returns_parsed = False

    def complete(self, **kwargs: Any) -> str:
        from .llm import _chat_gemini

        return _chat_gemini(
            key=kwargs["key"],
            base=kwargs["base"],
            model=kwargs["model"],
            system=kwargs["system"],
            user=kwargs["user"],
            temperature=kwargs["temperature"],
            max_tokens=kwargs["max_tokens"],
        )


class _CursorTransport:
    kind = "cursor"
    returns_parsed = True

    def complete(self, **kwargs: Any) -> Any:
        from .cursor_llm import chat_json as cursor_chat_json

        return cursor_chat_json(
            system=kwargs["system"],
            user=kwargs["user"],
            temperature=kwargs["temperature"],
            max_tokens=kwargs["max_tokens"],
            retries=1,
        )


def register_transport(transport: LlmTransport, *, priority: int = 0) -> LlmTransport:
    return LLM_TRANSPORTS.register(transport.kind, transport, priority=priority)


register_transport(_OpenAiTransport(), priority=0)
register_transport(_AnthropicTransport(), priority=0)
register_transport(_GeminiTransport(), priority=0)
register_transport(_CursorTransport(), priority=0)


def transport_for(kind: str) -> LlmTransport:
    found = LLM_TRANSPORTS.get(kind)
    if found is not None:
        return found
    fallback = LLM_TRANSPORTS.get("openai")
    if fallback is None:
        raise RuntimeError(f"未注册的 LLM 协议: {kind}")
    return fallback
