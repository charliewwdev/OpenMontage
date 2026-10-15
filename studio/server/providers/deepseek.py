"""Text LLM JSON chat — thin compatibility wrapper over providers.llm."""

from __future__ import annotations

from typing import Any


class DeepSeekError(RuntimeError):
    pass


def extract_json(text: str) -> Any:
    from .llm import LlmError, extract_json as _extract

    try:
        return _extract(text)
    except LlmError as exc:
        raise DeepSeekError(str(exc)) from exc


def chat_json(
    *,
    system: str,
    user: str,
    temperature: float = 0.7,
    max_tokens: int = 8192,
    retries: int = 2,
) -> Any:
    from .llm import LlmError, chat_json as unified_chat_json

    try:
        return unified_chat_json(
            system=system,
            user=user,
            temperature=temperature,
            max_tokens=max_tokens,
            retries=retries,
        )
    except LlmError as exc:
        raise DeepSeekError(str(exc)) from exc
