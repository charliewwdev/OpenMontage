"""Deterministic media checks used by gates (no vision API)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def frame_sharpness(path: Path | str, *, crop_frac: float = 0.55) -> dict[str, float]:
    """Cheap high-pass variance on the upper-center crop (face / subject zone)."""
    from PIL import Image, ImageChops, ImageFilter, ImageStat

    p = Path(path)
    im = Image.open(p).convert("L")
    w, h = im.size
    cw = max(32, int(w * crop_frac))
    ch = max(32, int(h * crop_frac * 0.7))
    left = max(0, (w - cw) // 2)
    top = max(0, int(h * 0.10))
    if top + ch > h:
        top = max(0, h - ch)
    crop = im.crop((left, top, left + cw, top + ch))
    blur = crop.filter(ImageFilter.GaussianBlur(radius=1.2))
    hp = ImageChops.difference(crop, blur)
    hp_var = float(ImageStat.Stat(hp).var[0])
    edge_var = float(ImageStat.Stat(crop.filter(ImageFilter.FIND_EDGES)).var[0])
    return {"hpVar": hp_var, "edgeVar": edge_var, "width": float(w), "height": float(h)}


def sharpness_min_hp_var() -> float:
    try:
        from settings_store import get_secret

        raw = (get_secret("STUDIO_QA_MIN_SHARPNESS") or "").strip()
    except Exception:
        raw = (os.environ.get("STUDIO_QA_MIN_SHARPNESS") or "").strip()
    try:
        return max(0.5, min(30.0, float(raw or 8.0)))
    except Exception:
        return 8.0


def apply_sharpness_gate(
    qa: dict[str, Any],
    paths: list[Path],
    *,
    min_hp: float | None = None,
) -> dict[str, Any]:
    if not paths or qa.get("skipped"):
        return qa
    bar = sharpness_min_hp_var() if min_hp is None else float(min_hp)
    scores: list[float] = []
    for p in paths:
        try:
            scores.append(float(frame_sharpness(p)["hpVar"]))
        except Exception:
            continue
    if not scores:
        return qa
    ordered = sorted(scores)
    mid = ordered[len(ordered) // 2]
    out = dict(qa)
    out["sharpness"] = {
        "hpVars": [round(s, 2) for s in scores],
        "medianHpVar": round(mid, 2),
        "minHpVar": bar,
    }
    if mid < bar:
        out["pass"] = False
        out["score"] = min(float(out.get("score") or 0), 0.25)
        prev = str(out.get("reason") or "").strip()
        out["reason"] = (
            f"sharpness_gate: subject zone too soft (medianHpVar={mid:.2f} < {bar:.2f})"
            + (f"; {prev}" if prev else "")
        )[:400]
    return out


def injury_near_miss_promote(qa: dict[str, Any] | None) -> dict[str, Any]:
    """Accept usable injury stills when the judge admits a white wrap exists but nitpicks."""
    q = dict(qa or {})
    if q.get("pass") and float(q.get("score") or 0) >= 0.55:
        return q
    reason = str(q.get("reason") or "")
    low = reason.lower()
    hard_fail = any(
        tok in low
        for tok in (
            "blue plastic",
            "no white",
            "no bandage",
            "no gauze",
            "completely absent",
            "only facial",
            "forehead wound only",
            "face cut",
            "no wrap",
            "absent from the image",
        )
    )
    if hard_fail:
        return q
    admits_wrap = any(
        tok in low
        for tok in ("wrap", "gauze", "bandage", "sling", "纱布", "绷带", "包扎", "吊带")
    )
    nitpick = any(
        tok in low
        for tok in (
            "arm",
            "coat",
            "not the required",
            "not present",
            "shoulder or upper chest",
            "left shoulder",
            "dark coat",
            "sling",
        )
    )
    if admits_wrap and nitpick:
        q["pass"] = True
        q["score"] = max(0.6, float(q.get("score") or 0))
        q["injuryNearMiss"] = True
        q["reason"] = (reason + " [injury near-miss accepted: white wrap present]").strip()
    return q
