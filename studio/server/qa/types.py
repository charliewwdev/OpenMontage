"""Shared QA context. Strategies and gates both read this; neither needs the other."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


SPIRIT_MARKERS = ("无实体", "灵光聚", "珠影", "淡紫色灵光")
# Bible / variant markers only. Never match the English word "injury" inside
# identity-lock phrases like "wardrobe or injury state" — that false-positive
# forced default cast stills into the gauze QA ladder.
INJURY_MARKERS = ("bandage", "gauze", "绷带", "纱布", "受伤", "负伤", "外伤")
INJURY_VARIANT_MARKERS = (
    "受伤",
    "绷带",
    "负伤",
    "外伤",
    "伤势",
    "bandage",
    "injury",
    "wounded",
)


def gender_hint_from_text(text: str) -> str | None:
    """Return 'male' / 'female' / None from Chinese/English character bible text."""
    t = str(text or "")
    male_hits = ("男性", "男人", "男主", "男演员", "东亚男性", "male", "man ", " young man")
    female_hits = ("女性", "女人", "女主", "女演员", "东亚女性", "female", "woman", " young woman")
    if re.search(r"\d+\s*岁?\s*东亚?男", t) or "东亚男性" in t or "岁东亚男性" in t:
        return "male"
    if re.search(r"\d+\s*岁?\s*东亚?女", t) or "东亚女性" in t or "岁东亚女性" in t:
        return "female"
    tl = t.lower()
    m = any((x in tl) if x.isascii() else (x in t) for x in male_hits)
    f = any((x in tl) if x.isascii() else (x in t) for x in female_hits)
    if m and not f:
        return "male"
    if f and not m:
        return "female"
    return None


def is_spirit_text(*parts: str) -> bool:
    blob = "".join(parts)
    return any(k in blob for k in SPIRIT_MARKERS)


def is_injury_variant_name(variant: str) -> bool:
    """True when the entity variant itself is an injury look."""
    v = str(variant or "").strip().lower()
    if not v:
        return False
    if any(tok in v for tok in INJURY_VARIANT_MARKERS):
        return True
    return v.endswith("伤") or "伤后" in v or "伤态" in v


def is_injury_text(*parts: str) -> bool:
    """Detect injury intent from bible/variant text — not from generation prompts."""
    blob = "\n".join(parts).lower()
    return any(tok in blob for tok in INJURY_MARKERS)


@dataclass
class QaContext:
    """Everything a strategy or gate needs. Built once at the facade."""

    kind: str
    prompt: str
    entity_name: str = ""
    entity_description: str = ""
    entity_variant: str = ""
    entity_context: str = ""
    entities: list[dict[str, Any]] = field(default_factory=list)
    media_paths: list[Path] = field(default_factory=list)
    gender: str | None = None
    strategy_id: str = ""

    @property
    def bible_blob(self) -> str:
        return f"{self.entity_description}\n{self.prompt}\n{self.entity_name}"

    @classmethod
    def for_image(
        cls,
        *,
        kind: str,
        prompt: str,
        path: Path,
        entity_name: str = "",
        entity_description: str = "",
        entity_variant: str = "",
    ) -> QaContext:
        gender = gender_hint_from_text(f"{entity_description}\n{prompt}")
        return cls(
            kind=str(kind or "other"),
            prompt=prompt or "",
            entity_name=entity_name or "",
            entity_description=entity_description or "",
            entity_variant=entity_variant or "",
            media_paths=[path],
            gender=gender,
        )

    @classmethod
    def for_video(
        cls,
        *,
        kind: str,
        prompt: str,
        frames: list[Path],
        entity_context: str = "",
        entities: list[dict[str, Any]] | None = None,
    ) -> QaContext:
        return cls(
            kind=str(kind or "shot"),
            prompt=prompt or "",
            entity_context=entity_context or "",
            entities=list(entities or []),
            media_paths=list(frames),
        )


def format_entity_context(entities: list[dict[str, Any]] | None) -> str:
    """Compact cast/scene/prop brief for video QA."""
    lines: list[str] = []
    for e in entities or []:
        kind = e.get("kind") or "entity"
        name = e.get("name") or ""
        variant = e.get("variant") or ""
        desc = (e.get("description") or "")[:220]
        label = f"{name}{(' · ' + variant) if variant else ''}"
        gender = gender_hint_from_text(desc) or ""
        gbit = f" gender={gender}" if gender else ""
        lines.append(f"- [{kind}] {label}{gbit}: {desc}")
    return "\n".join(lines[:12])


def verdict(
    *,
    ok: bool = True,
    passed: bool = False,
    score: float = 0,
    reason: str = "",
    skipped: bool = False,
    **extra: Any,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "ok": ok,
        "pass": passed,
        "score": score,
        "reason": (reason or "")[:400],
        "skipped": skipped,
    }
    out.update(extra)
    return out
