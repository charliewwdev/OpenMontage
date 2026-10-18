"""QA strategies. Add a kind by registering another QaStrategy — not another if in judge_*."""

from __future__ import annotations

from typing import Protocol

from providers.registry import Registry

from .types import QaContext, is_injury_text, is_spirit_text

QA_STRATEGIES: Registry["QaStrategy"] = Registry()


class QaStrategy(Protocol):
    id: str

    def match(self, ctx: QaContext) -> bool: ...

    def vision_system(self, ctx: QaContext) -> str: ...

    def vision_user(self, ctx: QaContext) -> str: ...

    def gate_ids(self, ctx: QaContext) -> list[str]:
        """Ordered hard-gate ids to run after vision. Empty = none."""
        ...


def register_qa_strategy(strategy: QaStrategy, *, priority: int) -> QaStrategy:
    return QA_STRATEGIES.register(strategy.id, strategy, priority=priority)


def resolve_qa_strategy(ctx: QaContext) -> QaStrategy:
    for strategy in QA_STRATEGIES.all():
        if strategy.match(ctx):
            return strategy
    fallback = QA_STRATEGIES.get("default")
    if fallback is None:
        raise RuntimeError("QA default strategy missing")
    return fallback


def _json_preamble(role: str) -> str:
    return (
        f"You are a {role}. "
        'Reply with JSON only: {"pass": boolean, "score": number 0-1, "reason": string}. '
    )


def _gender_rule(gender: str | None) -> str:
    if gender == "male":
        return (
            " CRITICAL: the bible requires a MALE character. "
            "FAIL immediately if the subject is a woman / girl / feminine presentation."
        )
    if gender == "female":
        return (
            " CRITICAL: the bible requires a FEMALE character. "
            "FAIL immediately if the subject is a man / boy / masculine presentation."
        )
    return ""


class _SpiritStrategy:
    """Non-human spirit light / orb — must NOT be judged as a portrait."""

    id = "spirit"

    def match(self, ctx: QaContext) -> bool:
        if ctx.kind not in {"character", "spirit"}:
            return False
        return is_spirit_text(ctx.entity_name, ctx.entity_description, ctx.prompt)

    def vision_system(self, ctx: QaContext) -> str:
        return _json_preamble("strict media QA judge for short-drama spirit entities") + (
            "PASS only if the image shows a spirit light / translucent orb / luminous bead "
            "(lavender glow, star motifs OK) WITHOUT a human body, face, clothes, or portrait. "
            "FAIL if it is a photographed person, fashion portrait, empty landscape, or prop product shot."
        )

    def vision_user(self, ctx: QaContext) -> str:
        name_line = f"Entity name: {ctx.entity_name}\n" if ctx.entity_name else ""
        desc_line = (
            f"Entity bible (truncated):\n{ctx.entity_description[:600]}\n" if ctx.entity_description else ""
        )
        return (
            f"Asset kind: spirit\n"
            f"{name_line}{desc_line}"
            f"Generation prompt (truncated):\n{ctx.prompt[:1200]}\n\n"
            "Does the attached image show a spirit light / orb (not a human) matching this brief?"
        )

    def gate_ids(self, ctx: QaContext) -> list[str]:
        return ["spirit_no_human", "sharpness", "skill_expert"]


class _InjuryCharacterStrategy:
    id = "injury_character"

    def match(self, ctx: QaContext) -> bool:
        if ctx.kind != "character":
            return False
        if is_spirit_text(ctx.entity_name, ctx.entity_description, ctx.prompt):
            return False
        return is_injury_text(ctx.entity_description, ctx.prompt, ctx.entity_name)

    def vision_system(self, ctx: QaContext) -> str:
        return _json_preamble("practical media QA judge for short-drama injury stills") + (
            "Be lenient on injury wardrobe when white gauze/cotton wrap is visible on the upper body. "
            "PASS only if the image clearly shows a human character portrait / half-body / full-body "
            "matching the description (single person preferred). FAIL for aerial cityscapes, "
            "landscapes, crowded streets, empty rooms, props-only, or animals unless the prompt asks for them."
            + _gender_rule(ctx.gender)
        )

    def vision_user(self, ctx: QaContext) -> str:
        name_line = f"Entity name: {ctx.entity_name}\n" if ctx.entity_name else ""
        desc_line = (
            f"Entity bible (truncated):\n{ctx.entity_description[:600]}\n" if ctx.entity_description else ""
        )
        injury_hint = (
            "Injury still rubric (lenient): PASS if a WHITE cotton/gauze medical wrap is clearly "
            "visible on the upper body — shoulder, clavicle, upper chest, OR upper arm near the shoulder. "
            "A white gauze-like sling/wrap on the injured arm+shoulder counts as PASS. "
            "Do NOT require the bandage to dominate the frame. "
            "Dark torn coat is OPTIONAL — never fail solely because the coat is missing. "
            "FAIL only if: no white wrap at all, wrap is blue plastic/poncho/towel, "
            "OR injury is only facial cuts with bare clean shoulders.\n"
        )
        return (
            f"Asset kind: character\n"
            f"{name_line}{desc_line}{injury_hint}"
            f"Generation prompt (truncated):\n{ctx.prompt[:1200]}\n\n"
            "Does the attached image match this prompt, bible, and kind rules?"
        )

    def gate_ids(self, ctx: QaContext) -> list[str]:
        return ["character_empty_plate", "character_gender", "injury_near_miss", "sharpness", "skill_expert"]


class _CharacterStrategy:
    id = "character"

    def match(self, ctx: QaContext) -> bool:
        return ctx.kind == "character"

    def vision_system(self, ctx: QaContext) -> str:
        return _json_preamble("strict media QA judge for short-drama production") + (
            "PASS only if the image clearly shows a human character portrait / half-body / full-body "
            "matching the description (single person preferred). FAIL for aerial cityscapes, "
            "landscapes, crowded streets, empty rooms, props-only, or animals unless the prompt asks for them."
            + _gender_rule(ctx.gender)
        )

    def vision_user(self, ctx: QaContext) -> str:
        name_line = f"Entity name: {ctx.entity_name}\n" if ctx.entity_name else ""
        desc_line = (
            f"Entity bible (truncated):\n{ctx.entity_description[:600]}\n" if ctx.entity_description else ""
        )
        return (
            f"Asset kind: character\n"
            f"{name_line}{desc_line}"
            f"Generation prompt (truncated):\n{ctx.prompt[:1200]}\n\n"
            "Does the attached image match this prompt, bible, and kind rules?"
        )

    def gate_ids(self, ctx: QaContext) -> list[str]:
        return ["character_empty_plate", "character_gender", "sharpness", "skill_expert"]


class _SceneStrategy:
    id = "scene"

    def match(self, ctx: QaContext) -> bool:
        return ctx.kind == "scene"

    def vision_system(self, ctx: QaContext) -> str:
        return _json_preamble("strict media QA judge for short-drama production") + (
            "PASS only if the image is an environment / location empty plate without a dominant portrait subject. "
            "FAIL if it is mainly a close-up face or product shot."
        )

    def vision_user(self, ctx: QaContext) -> str:
        name_line = f"Entity name: {ctx.entity_name}\n" if ctx.entity_name else ""
        desc_line = (
            f"Entity bible (truncated):\n{ctx.entity_description[:600]}\n" if ctx.entity_description else ""
        )
        return (
            f"Asset kind: scene\n"
            f"{name_line}{desc_line}"
            f"Generation prompt (truncated):\n{ctx.prompt[:1200]}\n\n"
            "Does the attached image match this prompt, bible, and kind rules?"
        )

    def gate_ids(self, ctx: QaContext) -> list[str]:
        return ["sharpness", "skill_expert"]


class _PropStrategy:
    id = "prop"

    def match(self, ctx: QaContext) -> bool:
        return ctx.kind == "prop"

    def vision_system(self, ctx: QaContext) -> str:
        return _json_preamble("strict media QA judge for short-drama production") + (
            "PASS only if the image focuses on an object/prop product shot matching the named prop. "
            "FAIL if it is a cityscape, a full character portrait, a fashion model close-up, "
            "or a person's neck/face/body instead of the object."
        )

    def vision_user(self, ctx: QaContext) -> str:
        name_line = f"Entity name: {ctx.entity_name}\n" if ctx.entity_name else ""
        desc_line = (
            f"Entity bible (truncated):\n{ctx.entity_description[:600]}\n" if ctx.entity_description else ""
        )
        return (
            f"Asset kind: prop\n"
            f"{name_line}{desc_line}"
            f"Generation prompt (truncated):\n{ctx.prompt[:1200]}\n\n"
            "Does the attached image match this prompt, bible, and kind rules?"
        )

    def gate_ids(self, ctx: QaContext) -> list[str]:
        return ["prop_no_person", "sharpness", "skill_expert"]


class _ShotStrategy:
    id = "shot"

    def match(self, ctx: QaContext) -> bool:
        return ctx.kind in {"shot", "segment", "video"}

    def vision_system(self, ctx: QaContext) -> str:
        return _json_preamble("strict short-drama video QA judge") + (
            "PASS only if the frame could plausibly come from the described short-drama shot "
            "(people / setting / props roughly match the brief and cast list). "
            "FAIL for blank/black frames, pure noise, totally unrelated scenery, "
            "wrong gender for named characters, missing required cast, or obvious subject mismatch. "
            "CRITICAL sharpness: FAIL if the main subject face/body is soft, mushy, out of focus, "
            "motion-blurred, or low-detail (cinematic background bokeh is OK; a blurry protagonist is not)."
            " Multiple frames from the SAME clip are attached — judge the clip as a whole. "
            "People on screen MUST match named cast gender/appearance when cast is listed. "
            "Setting must match scene brief; key props should appear when the prompt requires them. "
            "FAIL if the protagonist face/body looks soft, blurry, mushy, or out of focus."
        )

    def vision_user(self, ctx: QaContext) -> str:
        return (
            f"Asset kind: {ctx.kind}\n"
            f"Shot / segment prompt (truncated):\n{ctx.prompt[:1600]}\n\n"
            f"Cast / scene / prop bible for this shot:\n{ctx.entity_context or '(none provided)'}\n\n"
            "Do these frames match the prompt AND the listed cast/scene/props? "
            "Also check whether the main subject is sharp enough for short-drama delivery."
        )

    def gate_ids(self, ctx: QaContext) -> list[str]:
        return ["cast_gender", "sharpness", "skill_expert"]


class _DefaultStrategy:
    id = "default"

    def match(self, ctx: QaContext) -> bool:
        return True

    def vision_system(self, ctx: QaContext) -> str:
        return _json_preamble("strict media QA judge for short-drama production") + (
            "PASS only if the image subject matches the prompt intent."
        )

    def vision_user(self, ctx: QaContext) -> str:
        name_line = f"Entity name: {ctx.entity_name}\n" if ctx.entity_name else ""
        return (
            f"Asset kind: {ctx.kind}\n"
            f"{name_line}"
            f"Generation prompt (truncated):\n{ctx.prompt[:1200]}\n\n"
            "Does the attached image match this prompt and kind rules?"
        )

    def gate_ids(self, ctx: QaContext) -> list[str]:
        return []


# Higher priority wins first match.
register_qa_strategy(_SpiritStrategy(), priority=100)
register_qa_strategy(_InjuryCharacterStrategy(), priority=90)
register_qa_strategy(_CharacterStrategy(), priority=50)
register_qa_strategy(_SceneStrategy(), priority=50)
register_qa_strategy(_PropStrategy(), priority=50)
register_qa_strategy(_ShotStrategy(), priority=50)
register_qa_strategy(_DefaultStrategy(), priority=0)
