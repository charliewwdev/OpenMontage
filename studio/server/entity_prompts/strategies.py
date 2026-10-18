"""Entity still prompt strategies. Register a new kind — do not grow build_entity_image_prompt ifs."""

from __future__ import annotations

from typing import Protocol

from providers.registry import Registry

from .types import PromptBuildContext, is_injury_variant, is_spirit

ENTITY_PROMPT_STRATEGIES: Registry["EntityPromptStrategy"] = Registry()


class EntityPromptStrategy(Protocol):
    id: str

    def match(self, ctx: PromptBuildContext) -> bool: ...

    def build(self, ctx: PromptBuildContext) -> tuple[str, str | None]: ...

    def retry_clause(self, ctx: PromptBuildContext, *, attempt: int, max_attempts: int) -> str:
        """Kind-specific QA retry suffix. Scenes stay empty plates."""
        ...

    def paraphrase_attempt(
        self,
        ctx: PromptBuildContext,
        *,
        attempt: int,
        base_prompt: str,
        base_negative: str | None,
        last_reason: str = "",
    ) -> tuple[str, str | None]:
        """Optional attempt rewrite (injury / prop leak ladder). Default: keep base."""
        ...


def register_entity_prompt_strategy(strategy: EntityPromptStrategy, *, priority: int) -> EntityPromptStrategy:
    return ENTITY_PROMPT_STRATEGIES.register(strategy.id, strategy, priority=priority)


def resolve_entity_prompt_strategy(ctx: PromptBuildContext) -> EntityPromptStrategy:
    for strategy in ENTITY_PROMPT_STRATEGIES.all():
        if strategy.match(ctx):
            return strategy
    fallback = ENTITY_PROMPT_STRATEGIES.get("prop")
    if fallback is None:
        raise RuntimeError("entity prompt strategies not registered")
    return fallback


class _PromptDefaults:
    def retry_clause(self, ctx: PromptBuildContext, *, attempt: int, max_attempts: int) -> str:
        tag = f" 【质检重试 {attempt}/{max_attempts}】"
        if ctx.kind == "scene":
            return (
                tag
                + "EMPTY LOCATION PLATE only. No people, no faces, no portraits. "
                "必须是上述地点的无人空镜。"
            )
        if ctx.kind == "prop":
            return (
                tag
                + "PRODUCT PHOTO of the single named object. "
                "No people, no faces, no hands, no portrait, no scenery. "
                "画面主体只有这一件道具。"
            )
        if self.id == "spirit":  # type: ignore[attr-defined]
            return tag + "SPIRIT LIGHT orb only. Not a human portrait."
        return tag + "ONE character portrait of the named person. 禁止航拍、城市空镜、风景、人群和第二个人物。"

    def paraphrase_attempt(
        self,
        ctx: PromptBuildContext,
        *,
        attempt: int,
        base_prompt: str,
        base_negative: str | None,
        last_reason: str = "",
    ) -> tuple[str, str | None]:
        del last_reason
        return base_prompt, base_negative


class _SpiritPrompt(_PromptDefaults):
    id = "spirit"

    def match(self, ctx: PromptBuildContext) -> bool:
        return ctx.kind == "character" and is_spirit(name=ctx.name, desc=ctx.desc)

    def build(self, ctx: PromptBuildContext) -> tuple[str, str | None]:
        prompt = (
            "SPIRIT LIGHT on a plain seamless dark studio backdrop. "
            "NOT a human, NOT a portrait, NO face, NO body, NO clothes, NO landscape. "
            f"「{ctx.who}」是淡紫色灵光聚成的半透明珠影，表面有淡淡星纹，悬浮居中。"
            "A small translucent lavender glowing orb with faint star-pattern shimmer."
        )
        if ctx.style:
            prompt += f"光色可参考：{ctx.style}，仍然只是一颗灵光珠影。"
        negative = (
            "person, woman, man, girl, face, body, portrait, clothes, hanfu, hair, "
            "landscape, mountain, moon, forest, text, watermark"
        )
        return prompt, negative


class _InjuryCharacterPrompt(_PromptDefaults):
    id = "injury_character"

    def match(self, ctx: PromptBuildContext) -> bool:
        if ctx.kind != "character" or is_spirit(name=ctx.name, desc=ctx.desc):
            return False
        return is_injury_variant(ctx.variant)

    def build(self, ctx: PromptBuildContext) -> tuple[str, str | None]:
        base_prompt, base_neg = _CharacterPrompt().build(ctx)
        prompt = (
            "MEDIUM SHOT chest-up (not face-only close-up). "
            "LEFT shoulder and upper chest have a thick WHITE medical gauze wrap "
            "(rolled surgical gauze, cotton dressing — not plastic sheet, not towel). "
            "Dark coat torn or blood-stained. Pale sweaty face. "
            + base_prompt
        )
        negative = (
            ((base_neg + ", ") if base_neg else "")
            + (
                "clean uninjured clothes, pristine high collar, forehead wound only, "
                "cheek cut only, facial laceration as sole injury, blue plastic sheet, "
                "rain poncho, towel around neck, head-and-shoulders crop hiding shoulders, "
                "fashion portrait, unbroken skin"
            )
        )
        return prompt, negative

    def paraphrase_attempt(
        self,
        ctx: PromptBuildContext,
        *,
        attempt: int,
        base_prompt: str,
        base_negative: str | None,
        last_reason: str = "",
    ) -> tuple[str, str | None]:
        del last_reason
        if attempt <= 1:
            return base_prompt, base_negative
        if attempt == 2:
            # Synonyms help CLIP more than repeating「绷带」.
            return (
                f"Cinematic half-body portrait of injured character 「{ctx.who}」. "
                "Surgical white cotton gauze dressing taped/wrapped on left deltoid and clavicle. "
                "Torn dark coat with dried blood. Sweaty pale skin. Medium shot shows both shoulders. "
                "左肩锁骨处白色医用纱布包扎清晰，破损外套，半身构图。"
                f" Keep identity: {ctx.look or ctx.desc or ctx.name}."
            ), base_negative
        return (
            base_prompt
            + " Keep a similar face identity; rebuild wardrobe and shoulder gauze."
        ), base_negative


class _CharacterPrompt(_PromptDefaults):
    id = "character"

    def match(self, ctx: PromptBuildContext) -> bool:
        return ctx.kind == "character"

    def build(self, ctx: PromptBuildContext) -> tuple[str, str | None]:
        look = ctx.look or ctx.desc
        prompt = (
            "CHARACTER SHEET on a plain seamless dark studio backdrop. "
            "NO landscape, NO mountains, NO forest, NO moon, NO empty plain. "
            f"画面中央只有角色「{ctx.who}」，半身，居中，五官清晰。"
            f"必须严格符合这段外形，不要改性别、年龄或换成泛泛古装："
            f"{look or '短剧主角，五官清晰，服装完整'}。"
        )
        if ctx.atmosphere:
            prompt += (
                f"光线只作肤色与轮廓参考（{ctx.atmosphere}），"
                "背景必须是纯色棚拍，禁止画成山景、林间或空镜。"
            )
        prompt += (
            "禁止航拍、街景、市集、山景大远景、岩石植被空镜、第二个人物。"
            "No landscape, no mountain, no cityscape, no empty scenery."
        )
        if ctx.variant and ctx.variant not in {"默认形象", "默认造型", "default"}:
            hint = str((ctx.runtime or {}).get("variant_prompt_hint") or "").strip()
            prompt += (
                f" 本条为变体「{ctx.variant}」，必须让变体差异在画面中清晰可见（妆造/伤势/服装状态），"
                "同时保持与参考定妆图同一张脸。"
            )
            if hint:
                prompt += f" {hint}"
        if ctx.three_view:
            prompt += "同一人物同一服装的三视图设定稿：正面、侧面、背面，纯色背景。"
        else:
            prompt += (
                "半身或全身定妆，清晰五官与发型层次，服装面料与配饰细节完整，"
                "电影级柔光与轮廓光，浅景深，剧照质感，居中构图。"
            )
        if ctx.force_illustration:
            prompt += "虚构角色插画，避免真人照片质感。"
        else:
            prompt += "虚构短剧角色，影视剧照质感与妆造完成度，不是简笔卡通、不是证件照、不是AI塑料脸。"
        if ctx.style:
            prompt += f"色调气质可参考：{ctx.style}（不可盖过人物主体）。"
        negative = (
            "aerial view, drone shot, cityscape, skyline, landscape, mountain, hillside, "
            "rocks, forest, nature scenery, empty street, crowded market, crowd, "
            "architecture only, bird's eye, map, multiple people, text, watermark"
        )
        return prompt, negative


class _ScenePrompt(_PromptDefaults):
    id = "scene"

    def match(self, ctx: PromptBuildContext) -> bool:
        return ctx.kind == "scene"

    def build(self, ctx: PromptBuildContext) -> tuple[str, str | None]:
        prompt = (
            "EMPTY location plate, no people, no faces, no portraits, no fashion models. "
            f"短剧场景空镜：{ctx.name}。"
            f"{ctx.desc or '可拍的竖屏短剧空间'}。"
            "制作设计完整：空间层次、道具陈设、材质与光影氛围，电影级构图，画面中不要出现人物。"
        )
        if ctx.style:
            prompt += f"色调气质可参考：{ctx.style}。"
        negative = (
            "close-up portrait, face closeup, character sheet, person, people, woman, man, "
            "fashion model, full body, crowd"
        )
        return prompt, negative


class _PropPrompt(_PromptDefaults):
    id = "prop"

    _PORTRAIT_LEAK = (
        "portrait",
        "person",
        "woman",
        "man",
        "character",
        "face",
        "人物",
        "肖像",
        "半身",
    )

    def match(self, ctx: PromptBuildContext) -> bool:
        return True

    def build(self, ctx: PromptBuildContext) -> tuple[str, str | None]:
        prompt = (
            "ISOLATED PRODUCT PHOTO on a plain seamless studio backdrop, one object only. "
            "No person, no face, no hands, no fingers, no portrait, no character sheet, no fashion. "
            f"关键道具产品特写：{ctx.name}。"
            f"只拍这一件物体的外形与材质：{ctx.desc or ctx.name}。"
            "居中 macro / tabletop 静物，浅景深，材质反光真实；"
            "禁止任何人物、半身像、城市空镜；不要试图画清纸上的长段剧情文字。"
        )
        if ctx.three_view:
            prompt += "多角度产品级展示。"
        if ctx.style:
            prompt += f"色调气质可参考：{ctx.style}（不可盖过物体主体）。"
        negative = (
            "cityscape, aerial view, full body portrait, half-body portrait, headshot, "
            "crowd, people, person, human, face, woman, man, girl, boy, "
            "fashion model, character sheet, cosplay, selfie, hands holding, fingers"
        )
        return prompt, negative

    def paraphrase_attempt(
        self,
        ctx: PromptBuildContext,
        *,
        attempt: int,
        base_prompt: str,
        base_negative: str | None,
        last_reason: str = "",
    ) -> tuple[str, str | None]:
        if attempt <= 1:
            return base_prompt, base_negative
        low = (last_reason or "").lower()
        if any(tok in low for tok in self._PORTRAIT_LEAK):
            prompt = (
                "STRICT PRODUCT MACRO, plain white/gray seamless backdrop, ONE object only. "
                f"Object: {ctx.name or 'prop'}. "
                f"Details: {ctx.desc or ctx.name or ''}. "
                "No humans anywhere in frame."
            )
            neg = (
                ((base_negative + ", ") if base_negative else "")
                + "person, people, face, woman, man, portrait, hands, fingers, character sheet"
            )
            return prompt, neg
        return base_prompt, base_negative


register_entity_prompt_strategy(_SpiritPrompt(), priority=100)
register_entity_prompt_strategy(_InjuryCharacterPrompt(), priority=90)
register_entity_prompt_strategy(_CharacterPrompt(), priority=50)
register_entity_prompt_strategy(_ScenePrompt(), priority=50)
register_entity_prompt_strategy(_PropPrompt(), priority=0)
