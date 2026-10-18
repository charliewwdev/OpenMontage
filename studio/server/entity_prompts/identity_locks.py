"""English CLIP identity locks shared by entity prompts and Comfy RealVis translation."""

from __future__ import annotations

import re

from .types import SPIRIT_MARKERS, is_spirit


def clip_identity_prefix(raw: str) -> str:
    """English locks RealVis/SDXL must see first. Chinese CLIP drops gender, age, and spirit form."""
    text = raw or ""
    if is_spirit(name="", desc=text) or any(k in text for k in SPIRIT_MARKERS):
        return (
            "NOT a human, NOT a portrait, NOT a woman, NO face, NO body, NO clothes. "
            "A small translucent lavender glowing orb with faint star-pattern shimmer, "
            "spirit light floating on a plain dark studio backdrop."
        )
    bits: list[str] = []
    age_m = re.search(r"(\d{1,2})\s*岁", text)
    age = age_m.group(1) if age_m else ""
    if "男孩" in text:
        bits.append(
            f"ONE East Asian BOY age {age or '8'}, male child, not an adult, not a woman, not a girl."
        )
    elif any(k in text for k in ("男性", "农夫", "男人")):
        bits.append(
            f"ONE East Asian MAN age {age or 'adult'}, male, masculine face, not a woman, not a girl."
        )
    elif any(k in text for k in ("少女", "村妇", "女子")):
        bits.append(f"ONE East Asian FEMALE age {age or 'adult'}, not a man.")
    if any(k in text for k in ("灰袍", "灰衣", "兜帽")):
        bits.append(
            "Gray hooded robe, hood shadowing the face, pale jaw only, "
            "not a white collared shirt, not modern fashion."
        )
    if any(k in text for k in ("双丫髻", "枯黄乱发", "粗布短褐")):
        bits.append(
            "Withered yellow messy hair in two side buns tied with straw rope, "
            "coarse blue-gray short jacket, torn linen vest, straw-rope belt, open-toe cloth shoes. "
            "Not a silk robe."
        )
    if "围裙" in text or "村妇" in text:
        bits.append(
            "Stout village woman, high cheekbones, hair bun with a wooden pin, "
            "gray-blue coarse cross-collar shirt, stained apron. Not a young model."
        )
    if "农夫" in text or ("草鞋" in text and "微驼" in text):
        bits.append(
            "Slightly hunched farmer, deep eye wrinkles, dark brown coarse short jacket, "
            "rolled trouser cuffs, straw sandals. Male."
        )
    if "雀斑" in text or "靛蓝布" in text:
        bits.append(
            "Freckles on the nose, indigo cloth jacket with short sleeves, old cloth shoes, child proportions."
        )
    low = text.lower()
    if "white collared" in low or "white shirt" in low:
        bits.append("No white collared shirt.")
    if "physical human" in low:
        bits.append("No solid living human body.")
    if "young woman" in low or "young east asian female" in low:
        bits.append("Do not draw a young woman.")
    seen: set[str] = set()
    out: list[str] = []
    for bit in bits:
        if bit not in seen:
            seen.add(bit)
            out.append(bit)
    return " ".join(out)
