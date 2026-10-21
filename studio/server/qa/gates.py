"""Hard gates as a responsibility chain. Each gate opts in via gate_ids on the strategy."""

from __future__ import annotations

import re
from typing import Any, Protocol

from providers.registry import Registry

from .types import QaContext, gender_hint_from_text

QA_GATES: Registry["QaGate"] = Registry()


def _has_word(text: str, *words: str) -> bool:
    """Whole-word / CJK substring check. Avoids 'male' matching inside 'female'."""
    low = text.lower()
    for w in words:
        if not w:
            continue
        if w.isascii():
            if re.search(rf"(?<![a-z]){re.escape(w.lower())}(?![a-z])", low):
                return True
        elif w in text or w in low:
            return True
    return False


class QaGate(Protocol):
    id: str

    def apply(self, ctx: QaContext, qa: dict[str, Any]) -> dict[str, Any]: ...


def register_qa_gate(gate: QaGate, *, priority: int = 0) -> QaGate:
    return QA_GATES.register(gate.id, gate, priority=priority)


def run_gate_chain(ctx: QaContext, qa: dict[str, Any], gate_ids: list[str]) -> dict[str, Any]:
    out = qa
    for gid in gate_ids:
        gate = QA_GATES.get(gid)
        if gate is None:
            continue
        out = gate.apply(ctx, out)
    return out


class _CharacterEmptyPlateGate:
    id = "character_empty_plate"

    def apply(self, ctx: QaContext, qa: dict[str, Any]) -> dict[str, Any]:
        if qa.get("skipped") or not qa.get("ok", True) or not qa.get("pass"):
            return qa
        reason = str(qa.get("reason") or "")
        low = reason.lower()
        empty_plate = any(
            x in low
            for x in (
                "landscape",
                "cityscape",
                "scenery",
                "mountain",
                "aerial",
                "无人空镜",
                "风景空镜",
                "街景空镜",
                "empty location",
                "empty street",
                "no person visible",
                "no people visible",
                "without any person",
                "without a person",
            )
        )
        has_subject = any(
            x in low
            for x in (
                "portrait",
                "character",
                "male",
                "female",
                "man",
                "woman",
                "person",
                "face",
                "半身",
                "肖像",
                "男性",
                "女性",
            )
        )
        if empty_plate and not has_subject:
            out = dict(qa)
            out["pass"] = False
            out["score"] = min(float(out.get("score") or 0), 0.2)
            out["reason"] = f"character_gate:{reason}"[:400]
            return out
        return qa


class _CharacterGenderGate:
    id = "character_gender"

    def apply(self, ctx: QaContext, qa: dict[str, Any]) -> dict[str, Any]:
        if qa.get("skipped") or not qa.get("ok", True) or not qa.get("pass"):
            return qa
        gender = ctx.gender
        if not gender:
            return qa
        reason = str(qa.get("reason") or "")
        out = dict(qa)
        if gender == "male" and _has_word(reason, "woman", "female", "girl", "女士", "女性", "女主"):
            if not _has_word(reason, "male", "man", "boy", "男性", "男主"):
                out["pass"] = False
                out["score"] = min(float(out.get("score") or 0), 0.15)
                out["reason"] = f"gender_gate_male_expected:{reason}"[:400]
                return out
        if gender == "female" and _has_word(reason, "man", "male", "boy", "男士", "男性", "男主"):
            if not _has_word(reason, "female", "woman", "girl", "女性", "女主"):
                out["pass"] = False
                out["score"] = min(float(out.get("score") or 0), 0.15)
                out["reason"] = f"gender_gate_female_expected:{reason}"[:400]
                return out
        return qa


class _SpiritNoHumanGate:
    id = "spirit_no_human"

    def apply(self, ctx: QaContext, qa: dict[str, Any]) -> dict[str, Any]:
        if qa.get("skipped") or not qa.get("ok", True) or not qa.get("pass"):
            return qa
        reason = str(qa.get("reason") or "")
        low = reason.lower()
        humanish = any(
            x in low
            for x in (
                "person",
                "human",
                "portrait",
                "woman",
                "man",
                "girl",
                "boy",
                "face",
                "人像",
                "半身",
                "角色定妆",
                "physical human",
            )
        ) and not any(
            x in low
            for x in (
                "not a person",
                "no person",
                "no human",
                "spirit",
                "orb",
                "bead",
                "glow",
                "灵光",
                "珠影",
            )
        )
        if humanish:
            out = dict(qa)
            out["pass"] = False
            out["score"] = min(float(out.get("score") or 0), 0.15)
            out["reason"] = f"spirit_gate_no_human:{reason}"[:400]
            return out
        return qa


class _PropNoPersonGate:
    id = "prop_no_person"

    def apply(self, ctx: QaContext, qa: dict[str, Any]) -> dict[str, Any]:
        if qa.get("skipped") or not qa.get("ok", True) or not qa.get("pass"):
            return qa
        reason = str(qa.get("reason") or "")
        low = reason.lower()
        prompt_l = (ctx.prompt or "").lower()
        is_person_shot = any(
            x in low
            for x in (
                "character portrait",
                "full character",
                "half-body portrait",
                "full-body portrait",
                "portrait of a",
                "portrait of the",
                "shows a woman",
                "shows a man",
                "shows a person",
                "image of a woman",
                "image of a man",
                "人像",
                "半身像",
                "角色定妆",
            )
        ) and not any(
            x in low
            for x in (
                "not a person",
                "no person",
                "no people",
                "without person",
                "without people",
                "product",
                "object only",
                "道具",
                "产品",
            )
        )
        if is_person_shot and not any(x in prompt_l for x in ("person", "people", "人物")):
            out = dict(qa)
            out["pass"] = False
            out["score"] = min(float(out.get("score") or 0), 0.2)
            out["reason"] = f"prop_gate_no_person:{reason}"[:400]
            return out
        return qa


class _InjuryNearMissGate:
    id = "injury_near_miss"

    def apply(self, ctx: QaContext, qa: dict[str, Any]) -> dict[str, Any]:
        from .media_checks import injury_near_miss_promote

        return injury_near_miss_promote(qa)


class _SharpnessGate:
    id = "sharpness"

    def apply(self, ctx: QaContext, qa: dict[str, Any]) -> dict[str, Any]:
        if qa.get("skipped"):
            return qa
        from .media_checks import apply_sharpness_gate, sharpness_min_hp_var

        return apply_sharpness_gate(qa, list(ctx.media_paths), min_hp=sharpness_min_hp_var())


class _CastGenderGate:
    id = "cast_gender"

    def apply(self, ctx: QaContext, qa: dict[str, Any]) -> dict[str, Any]:
        if qa.get("skipped") or not qa.get("pass") or not ctx.entities:
            return qa
        reason = str(qa.get("reason") or "")
        low = reason.lower()
        for e in ctx.entities:
            if (e.get("kind") or "") != "character":
                continue
            g = gender_hint_from_text(e.get("description") or "")
            if g == "male" and any(x in low for x in ("wrong gender", "female cast", "woman as", "女性错")):
                out = dict(qa)
                out["pass"] = False
                out["score"] = min(float(out.get("score") or 0), 0.25)
                out["reason"] = f"cast_gender_gate:{reason}"[:400]
                return out
        return qa


class _SkillExpertGate:
    """Skill 专家复审：读对应 Skill Runtime / 默认硬规则，只否决不放水。"""

    id = "skill_expert"

    def apply(self, ctx: QaContext, qa: dict[str, Any]) -> dict[str, Any]:
        from skill_runtime import skill_expert_review

        kind = ctx.strategy_id if ctx.strategy_id == "spirit" else ctx.kind
        skill_id = "drama-entity-still"
        if ctx.kind in {"shot", "segment", "video"}:
            # Portrait-match idlock prompts always include first/last-frame identity lock copy.
            prompt = str(ctx.prompt or "").lower()
            if "first and last frame" in prompt or "identical face" in prompt:
                skill_id = "portrait-idlock"
            else:
                skill_id = "drama-shot-prompt"
        return skill_expert_review(
            qa,
            kind=kind,
            strategy_id=ctx.strategy_id or "",
            skill_id=skill_id,
        )


register_qa_gate(_CharacterEmptyPlateGate())
register_qa_gate(_CharacterGenderGate())
register_qa_gate(_SpiritNoHumanGate())
register_qa_gate(_PropNoPersonGate())
register_qa_gate(_InjuryNearMissGate())
register_qa_gate(_SharpnessGate())
register_qa_gate(_CastGenderGate())
register_qa_gate(_SkillExpertGate())
