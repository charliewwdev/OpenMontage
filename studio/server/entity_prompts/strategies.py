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


_DEFAULT_CUTOUT_BG = (
    "ISOLATED CUTOUT on a seamless PURE WHITE (#FFFFFF) studio plate "
    "(flat even white, no gradient) so the backdrop can be keyed to transparent alpha. "
    "NO room, NO floor, NO wall texture, NO colored backdrop, NO scenery. "
    "透明抠图底板：主体以外必须是纯白无缝底板 #FFFFFF（均匀、无渐变），便于键控成透明 PNG；"
    "禁止场景、地面、墙面、彩色背景与棚拍道具。"
)


def _cutout_clause(ctx: PromptBuildContext) -> str:
    """Prefer drama-entity-still Skill Runtime `cutout_prompt` (Skill 专家可改)."""
    runtime = ctx.runtime or {}
    text = str(runtime.get("cutout_prompt") or "").strip()
    if text:
        return text
    mode = str(runtime.get("cutout_background") or "transparent").strip().lower()
    if mode in {"", "transparent", "alpha", "cutout", "1", "true", "yes"}:
        return _DEFAULT_CUTOUT_BG
    if mode in {"0", "false", "no", "off", "none", "disabled"}:
        return "Plain seamless studio backdrop (no scenery)."
    return _DEFAULT_CUTOUT_BG


def _drawable_look_checklist(look: str) -> str:
    """Front-load model-friendly English visual anchors from a Chinese cast bible.

    Vision models follow early tokens; poetic Chinese alone yields neat black buns /
    clean hanfu and then QA burns retries. Keep the original bible after the checklist.
    """
    raw = str(look or "").strip()
    if not raw:
        return ""
    bits: list[str] = []
    # Age / body
    if any(tok in raw for tok in ("12岁", "十二岁", "少女", "幼女", "女孩")):
        bits.append("slim young East Asian girl (~12 look), not an adult fashion model")
    elif any(tok in raw for tok in ("少年", "男孩", "男童")):
        bits.append("slim young East Asian boy, not an adult")
    # Hair silhouette — the #1 failure mode on 花恋紫
    if any(tok in raw for tok in ("双丫髻", "双髻", "丫髻")):
        bits.append(
            "CRITICAL hair: messy dry straw-yellow double buns (双丫髻) tied with rough hemp/straw rope, "
            "loose wisps on cheeks — NOT neat glossy black buns, NOT a single topknot, NOT platinum blonde"
        )
    elif any(tok in raw for tok in ("丸子头", "单髻", "高髻")):
        bits.append("CRITICAL hair: single messy bun matching the bible — not a sleek salon style")
    elif "枯黄" in raw or "黄发" in raw:
        bits.append("CRITICAL hair: dry straw-yellow unkempt hair (枯黄乱发), not glossy black")
    if "草绳" in raw and not any("hemp/straw rope" in b for b in bits):
        bits.append("hair tied with visible hemp/straw rope")
    # Wardrobe
    if any(tok in raw for tok in ("粗布短褐", "短褐", "粗布")):
        bits.append("washed gray-blue coarse short tunic (青灰粗布短褐), frayed edges")
    if any(tok in raw for tok in ("破麻背心", "麻背心", "破麻")):
        bits.append("torn hemp vest over the tunic")
    if "草绳" in raw and "腰" in raw:
        bits.append("hemp rope belt at the waist")
    if any(tok in raw for tok in ("露趾布鞋", "布鞋")):
        bits.append("open-toe cloth shoes visible at the feet")
    # Bruises are secondary — mention lightly so models don't over-focus
    if any(tok in raw for tok in ("淤痕", "瘀痕", "伤疤")):
        bits.append("faint old bruises on arms optional")
    if not bits:
        return raw
    checklist = "FIRST-PASS visual checklist (must render): " + "; ".join(bits) + "."
    return f"{checklist} Bible: {raw}"


class _SpiritPrompt(_PromptDefaults):
    id = "spirit"

    def match(self, ctx: PromptBuildContext) -> bool:
        return ctx.kind == "character" and is_spirit(name=ctx.name, desc=ctx.desc)

    def build(self, ctx: PromptBuildContext) -> tuple[str, str | None]:
        prompt = (
            f"SPIRIT LIGHT. {_cutout_clause(ctx)} "
            "NOT a human, NOT a portrait, NO face, NO body, NO clothes, NO landscape. "
            f"「{ctx.who}」是淡紫色灵光聚成的半透明珠影，表面有淡淡星纹，悬浮居中。"
            "A small translucent lavender glowing orb with faint star-pattern shimmer."
        )
        if ctx.style:
            prompt += f"光色可参考：{ctx.style}，仍然只是一颗灵光珠影。"
        negative = (
            "person, woman, man, girl, face, body, portrait, clothes, hanfu, hair, "
            "landscape, mountain, moon, forest, text, watermark, "
            "room, floor, wall, scenery, colored backdrop, gradient background"
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
            "FULL BODY standing (not face-only close-up, not chest-up crop). "
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
                f"Cinematic full-body portrait of injured character 「{ctx.who}」. "
                "Surgical white cotton gauze dressing taped/wrapped on left deltoid and clavicle. "
                "Torn dark coat with dried blood. Sweaty pale skin. Head-to-toe standing figure. "
                "左肩锁骨处白色医用纱布包扎清晰，破损外套，全身构图。"
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
        look = _drawable_look_checklist(ctx.look or ctx.desc)
        # Locked framing so every cast still matches the same scale in the asset rail
        # and identity lock stays comparable across characters.
        framing = str((ctx.runtime or {}).get("framing_prompt") or "").strip() or (
            "FULL BODY framing lock: head-to-toe standing figure, slight headroom and footroom, "
            "face and full wardrobe readable, centered. NOT extreme face close-up, NOT chest-up crop only. "
            "统一全身定妆：从头到脚完整入画，站姿，头顶与脚底留一点空间，五官与服装可读；"
            "禁止只有额头眼睛的大特写，禁止半身/胸上裁切。"
        )
        if not framing.endswith((" ", "。", ".", "！", "!")):
            framing = framing + " "
        first_pass = str((ctx.runtime or {}).get("first_pass_prompt") or "").strip()
        prompt = (
            f"CHARACTER SHEET / asset cutout. {_cutout_clause(ctx)} "
            "NO landscape, NO mountains, NO forest, NO moon, NO empty plain. "
            f"{framing}"
        )
        if first_pass:
            prompt += first_pass if first_pass.endswith(" ") else first_pass + " "
        prompt += (
            f"画面中央只有角色「{ctx.who}」，五官与发型清晰，全身服装完整。"
            f"必须严格符合这段外形，不要改性别、年龄或换成泛泛古装："
            f"{look or '短剧主角，五官清晰，服装完整'}。"
        )
        if ctx.atmosphere:
            prompt += (
                f"光线只作肤色与轮廓参考（{ctx.atmosphere}），"
                "背景必须透明或纯白/浅灰抠图底板，禁止画成山景、林间或空镜。"
            )
        prompt += (
            "禁止航拍、街景、市集、山景大远景、岩石植被空镜、第二个人物。"
            "No landscape, no mountain, no cityscape, no empty scenery."
        )
        if ctx.variant and ctx.variant not in {"默认形象", "默认造型", "default"}:
            hint = str((ctx.runtime or {}).get("variant_prompt_hint") or "").strip()
            prompt += (
                f" 本条为变体「{ctx.variant}」，必须让变体差异在画面中清晰可见（妆造/伤势/服装状态），"
                "同时保持与参考定妆图同一张脸与同一全身构图比例。"
            )
            if hint:
                prompt += f" {hint}"
        if ctx.three_view:
            prompt += "同一人物同一服装的三视图设定稿：正面、侧面、背面，透明或纯白抠图背景，各格仍为全身比例。"
        else:
            prompt += (
                "全身定妆（从头到脚，不是半身胸上），清晰五官与发型层次，整套服装与鞋履可见，"
                "电影级柔光与轮廓光，剧照质感，居中构图，边缘干净可抠。"
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
            "architecture only, bird's eye, map, multiple people, text, watermark, "
            "extreme close-up, forehead only, eyes only crop, macro face, "
            "chest-up only, half-body crop, bust portrait, shoulders only, "
            "head-and-shoulders only, cropped at waist, "
            "room interior, wooden floor, concrete wall, colored backdrop, "
            "gradient studio background, scenic background, environment"
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
        framing_fail = any(
            tok in low
            for tok in (
                "close-up",
                "closeup",
                "extreme",
                "forehead",
                "chest-up",
                "half-body",
                "half body",
                "bust",
                "crop",
                "特写",
                "半身",
                "胸上",
                "额头",
            )
        )
        hair_fail = any(
            tok in low
            for tok in (
                "hair",
                "hairstyle",
                "bun",
                "buns",
                "topknot",
                "发型",
                "双丫",
                "丫髻",
                "枯黄",
                "草绳",
            )
        )
        wardrobe_fail = any(
            tok in low
            for tok in (
                "garment",
                "clothing",
                "wardrobe",
                "vest",
                "tunic",
                "coat",
                "服装",
                "短褐",
                "背心",
                "粗布",
            )
        )
        look = _drawable_look_checklist(ctx.look or ctx.desc or ctx.name)
        if framing_fail or attempt == 2:
            return (
                "FULL BODY only. Head-to-toe standing figure, face + wardrobe readable. "
                "No extreme face crop, no chest-up-only crop. "
                f"全身定妆「{ctx.who}」：从头到脚完整入画。"
                f" Keep identity: {look}."
            ), (
                ((base_negative + ", ") if base_negative else "")
                + "extreme close-up, forehead crop, chest-up only, half-body crop, bust portrait"
            )
        if hair_fail:
            return (
                f"Same FULL BODY cast still of 「{ctx.who}」. "
                "FIX HAIR FIRST: messy straw-yellow double buns with hemp rope ties if the bible says so; "
                "reject neat black salon buns. "
                f"{look}"
            ), base_negative
        if wardrobe_fail:
            return (
                f"Same FULL BODY cast still of 「{ctx.who}」. "
                "FIX WARDROBE FIRST: washed gray-blue coarse tunic + torn hemp vest when specified. "
                f"{look}"
            ), base_negative
        return base_prompt, base_negative


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
            f"ISOLATED PRODUCT PHOTO / prop cutout. {_cutout_clause(ctx)} "
            "One object only. No person, no face, no hands, no fingers, no portrait, no character sheet, no fashion. "
            f"关键道具产品特写：{ctx.name}。"
            f"只拍这一件物体的外形与材质：{ctx.desc or ctx.name}。"
            "居中 macro / floating product still，材质反光真实，边缘干净可抠；"
            "禁止任何人物、半身像、城市空镜、桌面杂物；不要试图画清纸上的长段剧情文字。"
        )
        if ctx.three_view:
            prompt += "多角度产品级展示，每格仍为透明或纯白抠图背景。"
        if ctx.style:
            prompt += f"色调气质可参考：{ctx.style}（不可盖过物体主体）。"
        negative = (
            "cityscape, aerial view, full body portrait, half-body portrait, headshot, "
            "crowd, people, person, human, face, woman, man, girl, boy, "
            "fashion model, character sheet, cosplay, selfie, hands holding, fingers, "
            "table clutter, wooden desk, room interior, scenery, colored backdrop, "
            "gradient studio background, environment"
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
                "STRICT PRODUCT MACRO, transparent or pure white seamless cutout, ONE object only. "
                f"Object: {ctx.name or 'prop'}. "
                f"Details: {ctx.desc or ctx.name or ''}. "
                "No humans anywhere in frame. No scenery."
            )
            neg = (
                ((base_negative + ", ") if base_negative else "")
                + "person, people, face, woman, man, portrait, hands, fingers, character sheet, scenery"
            )
            return prompt, neg
        return base_prompt, base_negative


register_entity_prompt_strategy(_SpiritPrompt(), priority=100)
register_entity_prompt_strategy(_InjuryCharacterPrompt(), priority=90)
register_entity_prompt_strategy(_CharacterPrompt(), priority=50)
register_entity_prompt_strategy(_ScenePrompt(), priority=50)
register_entity_prompt_strategy(_PropPrompt(), priority=0)
