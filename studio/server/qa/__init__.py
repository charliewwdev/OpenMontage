"""Studio QA package: strategies + gate chain. Prefer importing through prompt_qa for callers."""

from .gates import QA_GATES, register_qa_gate
from .pipeline import run_image_qa, run_video_qa
from .strategies import QA_STRATEGIES, register_qa_strategy, resolve_qa_strategy
from .types import QaContext, format_entity_context, gender_hint_from_text, is_spirit_text

__all__ = [
    "QA_GATES",
    "QA_STRATEGIES",
    "QaContext",
    "format_entity_context",
    "gender_hint_from_text",
    "is_spirit_text",
    "register_qa_gate",
    "register_qa_strategy",
    "resolve_qa_strategy",
    "run_image_qa",
    "run_video_qa",
]
