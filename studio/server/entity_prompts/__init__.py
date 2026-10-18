"""Entity still prompt factory. Callers use build() or go through drama_service."""

from .strategies import (
    ENTITY_PROMPT_STRATEGIES,
    register_entity_prompt_strategy,
    resolve_entity_prompt_strategy,
)
from .types import PromptBuildContext, is_injury_variant, is_spirit

__all__ = [
    "ENTITY_PROMPT_STRATEGIES",
    "PromptBuildContext",
    "is_injury_variant",
    "is_spirit",
    "register_entity_prompt_strategy",
    "resolve_entity_prompt_strategy",
]
