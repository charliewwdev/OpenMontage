"""Context for entity still prompt builders."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


SPIRIT_MARKERS = ("无实体", "灵光聚", "珠影", "淡紫色灵光")
INJURY_VARIANT_MARKERS = ("受伤", "绷带", "伤", "bandage", "injury")


def is_spirit(*, name: str, desc: str) -> bool:
    blob = f"{name}{desc}"
    return any(k in blob for k in SPIRIT_MARKERS)


def is_injury_variant(variant: str) -> bool:
    return any(tok in (variant or "") for tok in INJURY_VARIANT_MARKERS)


@dataclass
class PromptBuildContext:
    kind: str
    name: str
    variant: str
    desc: str
    style: str
    three_view: bool = False
    force_illustration: bool = False
    runtime: dict[str, Any] | None = None
    look: str = ""
    atmosphere: str = ""

    @property
    def who(self) -> str:
        return f"{self.name}{(' · ' + self.variant) if self.variant else ''}"
