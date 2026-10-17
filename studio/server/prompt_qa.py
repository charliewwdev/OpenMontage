"""Prompt-fit QA for generated stills (and optional video frames).

Uses multimodal OpenAI-compatible chat when available; otherwise returns skipped.
Does not claim aesthetic scoring — only subject/kind match against the brief.

Fail-closed: skipped vision (except explicit qa_disabled) must NOT promote assets.
"""

from __future__ import annotations

import base64
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any


def qa_min_score() -> float:
    """Pass bar for prompt-fit QA (default 0.7)."""
    try:
        from settings_store import get_secret

        raw = (get_secret("STUDIO_QA_MIN_SCORE") or "").strip()
    except Exception:
        raw = (os.environ.get("STUDIO_QA_MIN_SCORE") or "").strip()
    if not raw:
        try:
            from platform_config import load_platform_config

            cfg = (load_platform_config() or {}).get("defaults") or {}
            raw = str(cfg.get("qaMinScore") or "").strip()
        except Exception:
            raw = ""
    try:
        return max(0.0, min(1.0, float(raw or 0.7)))
    except Exception:
        return 0.7


def entity_qa_max_attempts() -> int:
    try:
        from settings_store import get_secret

        raw = (get_secret("STUDIO_ENTITY_QA_MAX_ATTEMPTS") or "").strip()
    except Exception:
        raw = (os.environ.get("STUDIO_ENTITY_QA_MAX_ATTEMPTS") or "").strip()
    if not raw:
        try:
            from platform_config import load_platform_config

            cfg = (load_platform_config() or {}).get("defaults") or {}
            raw = str(cfg.get("entityQaMaxAttempts") or "").strip()
        except Exception:
            raw = ""
    try:
        return max(1, min(10, int(raw or 5)))
    except Exception:
        return 5


def video_qa_max_attempts() -> int:
    try:
        from settings_store import get_secret

        raw = (get_secret("STUDIO_VIDEO_QA_MAX_ATTEMPTS") or "").strip()
    except Exception:
        raw = (os.environ.get("STUDIO_VIDEO_QA_MAX_ATTEMPTS") or "").strip()
    if not raw:
        try:
            from platform_config import load_platform_config

            cfg = (load_platform_config() or {}).get("defaults") or {}
            raw = str(cfg.get("videoQaMaxAttempts") or "").strip()
        except Exception:
            raw = ""
    try:
        return max(1, min(10, int(raw or 5)))
    except Exception:
        return 5


def qa_meets_bar(qa: dict[str, Any] | None, *, min_score: float | None = None) -> bool:
    """True when vision QA scored at/above the bar.

    Soft-skipped vision failures must NOT promote assets (Latin-CLIP landscapes were
    being selected as character stills). Explicit ``qa_disabled`` remains a soft pass.
    """
    q = qa or {}
    if q.get("skipped"):
        return str(q.get("reason") or "") == "qa_disabled"
    bar = qa_min_score() if min_score is None else float(min_score)
    try:
        score = float(q.get("score") or 0)
    except Exception:
        score = 0.0
    return bool(q.get("pass")) and score >= bar


def is_soft_pass_qa(qa: dict[str, Any] | None) -> bool:
    """Detect legacy / broken QA that pretended to pass without a real vision verdict."""
    q = qa or {}
    reason = str(q.get("reason") or q.get("error") or "")
    if q.get("skipped") and reason != "qa_disabled":
        return True
    low = reason.lower()
    markers = (
        "qa_error",
        "qa_exception",
        "模型未返回有效 json",
        "vision_blind",
        "vision_no_endpoint",
        "vision_all_endpoints",
        "no image",
        "no_frame",
        "missing_file",
    )
    if any(m in low for m in markers) and (q.get("pass") or float(q.get("score") or 0) >= 0.99):
        return True
    return False


def _injury_near_miss_promote(qa: dict[str, Any] | None) -> dict[str, Any]:
    """Accept usable injury stills when the judge admits a white wrap exists but nitpicks.

    RealVis often renders shoulder gauze as an arm sling / torso wrap. Strict judges then
    fail forever on「not left shoulder」or「missing dark coat」— that is a near miss, not a miss.
    """
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
        for tok in (
            "wrap",
            "gauze",
            "bandage",
            "sling",
            "纱布",
            "绷带",
            "包扎",
            "吊带",
        )
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


def frame_sharpness(path: Path | str, *, crop_frac: float = 0.55) -> dict[str, float]:
    """Cheap high-pass variance on the upper-center crop (face / subject zone).

    Ignores the bottom subtitle band. Higher ``hpVar`` = sharper. Empirically:
    soft/mushy AI frames ≈ 2–3; usable portraits ≈ 5–15+.
    """
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
    """Fail frames below this high-pass variance (default 8.0).

    Soft/mushy or heavily compressed short-drama frames often land around 3–7;
    usable clips are typically ≥8–10. Override with STUDIO_QA_MIN_SHARPNESS.
    """
    try:
        from settings_store import get_secret

        raw = (get_secret("STUDIO_QA_MIN_SHARPNESS") or "").strip()
    except Exception:
        raw = (os.environ.get("STUDIO_QA_MIN_SHARPNESS") or "").strip()
    try:
        return max(0.5, min(30.0, float(raw or 8.0)))
    except Exception:
        return 8.0


def _apply_sharpness_gate(
    qa: dict[str, Any],
    paths: list[Path],
    *,
    min_hp: float | None = None,
) -> dict[str, Any]:
    """Fail closed when subject-zone frames are soft/mushy."""
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
    # Use median so one sharp subtitle-heavy frame cannot mask a soft face.
    ordered = sorted(scores)
    mid = ordered[len(ordered) // 2]
    qa = dict(qa)
    qa["sharpness"] = {"hpVars": [round(s, 2) for s in scores], "medianHpVar": round(mid, 2), "minHpVar": bar}
    if mid < bar:
        qa["pass"] = False
        qa["score"] = min(float(qa.get("score") or 0), 0.25)
        prev = str(qa.get("reason") or "").strip()
        qa["reason"] = (
            f"sharpness_gate: subject zone too soft (medianHpVar={mid:.2f} < {bar:.2f})"
            + (f"; {prev}" if prev else "")
        )[:400]
    return qa


def _mime_for(path: Path) -> str:
    suf = path.suffix.lower()
    if suf in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suf == ".webp":
        return "image/webp"
    return "image/png"


def _data_url(path: Path) -> str:
    raw = path.read_bytes()
    b64 = base64.b64encode(raw).decode("ascii")
    return f"data:{_mime_for(path)};base64,{b64}"


def _qa_image_data_url(path: Path) -> str:
    """Downscale to JPEG so vision gateways accept the payload (PNG base64 often dropped)."""
    try:
        from PIL import Image
        import io

        with Image.open(path) as im:
            im = im.convert("RGB")
            w, h = im.size
            max_edge = 768
            if max(w, h) > max_edge:
                scale = max_edge / float(max(w, h))
                im = im.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.Resampling.LANCZOS)
            buf = io.BytesIO()
            im.save(buf, format="JPEG", quality=85, optimize=True)
            b64 = base64.b64encode(buf.getvalue()).decode("ascii")
            return f"data:image/jpeg;base64,{b64}"
    except Exception:
        return _data_url(path)


def gender_hint_from_text(text: str) -> str | None:
    """Return 'male' / 'female' / None from Chinese/English character bible text."""
    t = str(text or "")
    male_hits = ("男性", "男人", "男主", "男演员", "东亚男性", "male", "man ", " young man")
    female_hits = ("女性", "女人", "女主", "女演员", "东亚女性", "female", "woman", " young woman")
    # Prefer explicit age+gender patterns first.
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


def _kind_rules(kind: str, *, gender: str | None = None) -> str:
    if kind == "character":
        gender_rule = ""
        if gender == "male":
            gender_rule = (
                " CRITICAL: the bible requires a MALE character. "
                "FAIL immediately if the subject is a woman / girl / feminine presentation."
            )
        elif gender == "female":
            gender_rule = (
                " CRITICAL: the bible requires a FEMALE character. "
                "FAIL immediately if the subject is a man / boy / masculine presentation."
            )
        return (
            "PASS only if the image clearly shows a human character portrait / half-body / full-body "
            "matching the description (single person preferred). FAIL for aerial cityscapes, "
            "landscapes, crowded streets, empty rooms, props-only, or animals unless the prompt asks for them."
            + gender_rule
        )
    if kind == "scene":
        return (
            "PASS only if the image is an environment / location empty plate without a dominant portrait subject. "
            "FAIL if it is mainly a close-up face or product shot."
        )
    if kind == "prop":
        return (
            "PASS only if the image focuses on an object/prop product shot matching the named prop. "
            "FAIL if it is a cityscape, a full character portrait, a fashion model close-up, "
            "or a person's neck/face/body instead of the object."
        )
    if kind in {"shot", "segment", "video"}:
        return (
            "PASS only if the frame could plausibly come from the described short-drama shot "
            "(people / setting / props roughly match the brief and cast list). "
            "FAIL for blank/black frames, pure noise, totally unrelated scenery, "
            "wrong gender for named characters, missing required cast, or obvious subject mismatch. "
            "CRITICAL sharpness: FAIL if the main subject face/body is soft, mushy, out of focus, "
            "motion-blurred, or low-detail (cinematic background bokeh is OK; a blurry protagonist is not)."
        )
    return "PASS only if the image subject matches the prompt intent."


def _vision_endpoints() -> list[tuple[str, str, str]]:
    try:
        from providers.llm import resolve_provider, _secret
    except Exception:
        return []

    endpoints: list[tuple[str, str, str]] = []
    qa_vision = (_secret("STUDIO_QA_VISION_MODEL") or "").strip()
    for key_env, base_env, model_env, default_base, default_model in (
        (
            "OPENAI_API_KEY",
            "OPENAI_BASE_URL",
            "OPENAI_MODEL",
            "https://api.openai.com/v1",
            qa_vision or "gpt-4o-mini",
        ),
        (
            "ARK_API_KEY",
            "ARK_API_BASE",
            "ARK_MODEL",
            "https://ark.cn-beijing.volces.com/api/v3",
            qa_vision or "",
        ),
        (
            "VOLCENGINE_API_KEY",
            "ARK_API_BASE",
            "OPENAI_MODEL",
            "https://ark.cn-beijing.volces.com/api/v3",
            qa_vision or "",
        ),
    ):
        key = _secret(key_env)
        base = _secret(base_env, default_base)
        model = (_secret(model_env) or default_model or "").strip()
        if key and base and model and (key, base, model) not in endpoints:
            endpoints.append((key, base, model))
    if qa_vision:
        for key_env, base_env, default_base in (
            ("OPENAI_API_KEY", "OPENAI_BASE_URL", "https://api.openai.com/v1"),
            ("ARK_API_KEY", "ARK_API_BASE", "https://ark.cn-beijing.volces.com/api/v3"),
        ):
            key = _secret(key_env)
            base = _secret(base_env, default_base)
            if key and base and (key, base, qa_vision) not in endpoints:
                endpoints.insert(0, (key, base, qa_vision))
    try:
        meta = resolve_provider()
    except Exception:
        meta = {}
    if meta and meta.get("kind") not in {"anthropic", "gemini", "cursor"}:
        key = _secret(meta["keyEnv"])
        base = _secret(meta["baseEnv"], meta.get("defaultBase") or "")
        model = _secret(meta["modelEnv"], meta.get("defaultModel") or "")
        if key and base and model and (key, base, model) not in endpoints:
            endpoints.append((key, base, model))
    return endpoints


def _call_vision_judge(
    *,
    data_urls: list[str],
    system: str,
    user_text: str,
) -> dict[str, Any]:
    """Run multimodal JSON judge across configured endpoints. Fail-closed on skip."""
    try:
        from providers.llm import LlmError, extract_json
    except Exception as exc:
        return {"ok": False, "pass": False, "score": 0, "reason": f"qa_unavailable:{exc}", "skipped": True}

    endpoints = _vision_endpoints()
    if not endpoints:
        return {"ok": False, "pass": False, "score": 0, "reason": "vision_no_endpoint", "skipped": True}

    import urllib.error
    import urllib.request

    last_err = ""
    content_parts: list[dict[str, Any]] = [{"type": "text", "text": user_text}]
    for url in data_urls[:4]:
        content_parts.append({"type": "image_url", "image_url": {"url": url}})

    for key, base, model in endpoints:
        try:
            api_url = base.rstrip("/")
            if not api_url.endswith("/chat/completions"):
                api_url = f"{api_url}/chat/completions"
            body = {
                "model": model,
                "temperature": 0.1,
                "max_tokens": 500,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": content_parts},
                ],
                "response_format": {"type": "json_object"},
            }
            req = urllib.request.Request(
                api_url,
                data=json.dumps(body).encode("utf-8"),
                method="POST",
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
            )
            try:
                with urllib.request.urlopen(req, timeout=90) as resp:
                    raw = json.loads(resp.read().decode("utf-8") or "{}")
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")[:400]
                last_err = f"vision_unsupported:{exc.code}:{detail[:120]}"
                if exc.code in {400, 401, 402, 404, 422} or "image" in detail.lower() or "vision" in detail.lower():
                    continue
                raise LlmError(f"QA API error ({exc.code}): {detail}") from exc
            content = (((raw.get("choices") or [{}])[0].get("message") or {}).get("content")) or ""
            data = extract_json(str(content))
            passed = bool(data.get("pass"))
            score = float(data.get("score") or (1.0 if passed else 0.0))
            reason = str(data.get("reason") or ("ok" if passed else "mismatch"))
            if any(
                x in reason.lower()
                for x in ("no image", "not provided", "no image attached", "cannot verify", "未提供", "没有图")
            ):
                last_err = f"vision_blind:{model}:{reason[:120]}"
                continue
            return {
                "ok": True,
                "pass": passed,
                "score": score,
                "reason": reason[:400],
                "skipped": False,
                "model": model,
            }
        except Exception as exc:  # noqa: BLE001
            last_err = str(exc)[:200]
            continue

    return {
        "ok": False,
        "pass": False,
        "score": 0,
        "reason": last_err or "vision_all_endpoints_failed",
        "skipped": True,
    }


def _apply_hard_gates(kind_id: str, qa: dict[str, Any], *, gender: str | None, prompt: str) -> dict[str, Any]:
    if qa.get("skipped") or not qa.get("ok", True):
        return qa
    passed = bool(qa.get("pass"))
    score = float(qa.get("score") or 0)
    reason = str(qa.get("reason") or "")
    low = reason.lower()
    prompt_l = (prompt or "").lower()

    if kind_id == "character" and passed:
        # Only kill true empty plates. Do NOT trip on "no other people in background".
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
            passed = False
            score = min(score, 0.2)
            reason = f"character_gate:{reason}"
        if gender == "male" and any(
            x in low for x in ("woman", "female", "girl", "女士", "女性", "女主")
        ):
            if "male" not in low and "男性" not in reason:
                passed = False
                score = min(score, 0.15)
                reason = f"gender_gate_male_expected:{reason}"
        if gender == "female" and any(
            x in low for x in ("man", "male", "boy", "男士", "男性", "男主")
        ):
            if "female" not in low and "女性" not in reason:
                passed = False
                score = min(score, 0.15)
                reason = f"gender_gate_female_expected:{reason}"

    if kind_id == "prop" and passed:
        # Trip only on "this IS a person/portrait". Negations like "no person" must pass.
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
            passed = False
            score = min(score, 0.2)
            reason = f"prop_gate_no_person:{reason}"

    qa["pass"] = passed
    qa["score"] = score
    qa["reason"] = reason[:400]
    return qa


def judge_image_against_prompt(
    path: Path | str,
    *,
    prompt: str,
    kind: str = "character",
    entity_name: str = "",
    entity_description: str = "",
) -> dict[str, Any]:
    """Return {ok, pass, score, reason, skipped}."""
    p = Path(path)
    if not p.is_file():
        return {"ok": False, "pass": False, "score": 0, "reason": "missing_file", "skipped": False}

    try:
        from providers.media import media_qa_enabled

        if not media_qa_enabled():
            return {"ok": True, "pass": True, "score": 1, "reason": "qa_disabled", "skipped": True}
    except Exception:
        pass

    kind_id = str(kind or "other")
    gender = gender_hint_from_text(f"{entity_description}\n{prompt}")
    system = (
        "You are a strict media QA judge for short-drama production. "
        'Reply with JSON only: {"pass": boolean, "score": number 0-1, "reason": string}. '
        + _kind_rules(kind_id, gender=gender)
    )
    name_line = f"Entity name: {entity_name}\n" if entity_name else ""
    desc_line = f"Entity bible (truncated):\n{(entity_description or '')[:600]}\n" if entity_description else ""
    injury_mode = False
    injury_hint = ""
    blob = f"{entity_description}\n{prompt}\n{entity_name}".lower()
    if any(tok in blob for tok in ("bandage", "gauze", "绷带", "纱布", "受伤", "injury")):
        injury_mode = True
        injury_hint = (
            "Injury still rubric (lenient): PASS if a WHITE cotton/gauze medical wrap is clearly "
            "visible on the upper body — shoulder, clavicle, upper chest, OR upper arm near the shoulder. "
            "A white gauze-like sling/wrap on the injured arm+shoulder counts as PASS. "
            "Do NOT require the bandage to dominate the frame. "
            "Dark torn coat is OPTIONAL — never fail solely because the coat is missing. "
            "FAIL only if: no white wrap at all, wrap is blue plastic/poncho/towel, "
            "OR injury is only facial cuts with bare clean shoulders.\n"
        )
        # Injury judges must not use the default "strict" bar — it rejects usable wardrobe edits.
        system = (
            "You are a practical media QA judge for short-drama injury stills. "
            'Reply with JSON only: {"pass": boolean, "score": number 0-1, "reason": string}. '
            "Be lenient on injury wardrobe when white gauze/cotton wrap is visible on the upper body. "
            + _kind_rules(kind_id, gender=gender)
        )
    user_text = (
        f"Asset kind: {kind_id}\n"
        f"{name_line}{desc_line}{injury_hint}"
        f"Generation prompt (truncated):\n{(prompt or '')[:1200]}\n\n"
        "Does the attached image match this prompt, bible, and kind rules?"
    )
    qa = _call_vision_judge(
        data_urls=[_qa_image_data_url(p)],
        system=system,
        user_text=user_text,
    )
    qa = _apply_hard_gates(kind_id, qa, gender=gender, prompt=prompt)
    if injury_mode:
        qa = _injury_near_miss_promote(qa)
    # Character / scene / prop stills: catch mushy soft gens vision often forgives.
    if kind_id in {"character", "scene", "prop"} and not qa.get("skipped"):
        qa = _apply_sharpness_gate(qa, [p], min_hp=sharpness_min_hp_var())
    return qa


def extract_video_frame(video_path: Path | str, *, at_sec: float = 1.0) -> Path | None:
    """Grab one JPEG frame with ffmpeg; return temp path or None."""
    src = Path(video_path)
    if not src.is_file():
        return None
    try:
        tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        tmp.close()
        out = Path(tmp.name)
        cmd = [
            "ffmpeg",
            "-y",
            "-ss",
            str(max(0.0, float(at_sec))),
            "-i",
            str(src),
            "-frames:v",
            "1",
            "-q:v",
            "2",
            str(out),
        ]
        subprocess.run(cmd, check=True, capture_output=True, timeout=30)
        if out.is_file() and out.stat().st_size > 100:
            return out
    except Exception:
        return None
    return None


def _video_duration_sec(path: Path) -> float:
    try:
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ]
        out = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=15)
        return max(0.1, float((out.stdout or "0").strip() or 0))
    except Exception:
        return 5.0


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


def judge_video_against_prompt(
    path: Path | str,
    *,
    prompt: str,
    kind: str = "shot",
    entity_context: str = "",
    entities: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Sample multiple frames and judge cast/scene/prop fit against the shot brief."""
    src = Path(path)
    if not src.is_file():
        return {"ok": False, "pass": False, "score": 0, "reason": "missing_file", "skipped": False}

    try:
        from providers.media import media_qa_enabled

        if not media_qa_enabled():
            return {"ok": True, "pass": True, "score": 1, "reason": "qa_disabled", "skipped": True}
    except Exception:
        pass

    dur = _video_duration_sec(src)
    sample_at = sorted(
        {
            min(1.0, max(0.2, dur * 0.15)),
            max(0.5, min(dur - 0.3, dur * 0.5)),
            max(0.8, min(dur - 0.2, dur * 0.85)),
        }
    )
    frames: list[Path] = []
    try:
        for t in sample_at:
            fr = extract_video_frame(src, at_sec=t)
            if fr:
                frames.append(fr)
        if not frames:
            # Fail closed — previously soft-passed and let bad clips through.
            return {"ok": False, "pass": False, "score": 0, "reason": "no_frame", "skipped": True}

        ctx = entity_context or format_entity_context(entities)
        kind_id = str(kind or "shot")
        system = (
            "You are a strict short-drama video QA judge. "
            'Reply with JSON only: {"pass": boolean, "score": number 0-1, "reason": string}. '
            + _kind_rules(kind_id)
            + " Multiple frames from the SAME clip are attached — judge the clip as a whole. "
            "People on screen MUST match named cast gender/appearance when cast is listed. "
            "Setting must match scene brief; key props should appear when the prompt requires them. "
            "FAIL if the protagonist face/body looks soft, blurry, mushy, or out of focus."
        )
        user_text = (
            f"Asset kind: {kind_id}\n"
            f"Shot / segment prompt (truncated):\n{(prompt or '')[:1600]}\n\n"
            f"Cast / scene / prop bible for this shot:\n{ctx or '(none provided)'}\n\n"
            "Do these frames match the prompt AND the listed cast/scene/props? "
            "Also check whether the main subject is sharp enough for short-drama delivery."
        )
        qa = _call_vision_judge(
            data_urls=[_qa_image_data_url(f) for f in frames],
            system=system,
            user_text=user_text,
        )
        # Gender hard gate from cast bible when characters are listed.
        if not qa.get("skipped") and qa.get("pass") and entities:
            reason = str(qa.get("reason") or "")
            low = reason.lower()
            for e in entities:
                if (e.get("kind") or "") != "character":
                    continue
                g = gender_hint_from_text(e.get("description") or "")
                if g == "male" and any(x in low for x in ("wrong gender", "female cast", "woman as", "女性错")):
                    qa["pass"] = False
                    qa["score"] = min(float(qa.get("score") or 0), 0.25)
                    qa["reason"] = f"cast_gender_gate:{reason}"[:400]
                    break
        # Deterministic sharpness gate — vision often ignores soft AI faces when cast matches.
        if not qa.get("skipped"):
            qa = _apply_sharpness_gate(qa, frames)
        return qa
    finally:
        for fr in frames:
            try:
                fr.unlink(missing_ok=True)
            except Exception:
                pass
