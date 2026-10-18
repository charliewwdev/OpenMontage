"""Prompt-fit QA facade.

Public callers keep importing from this module. Kind-specific rules and hard gates
live under ``qa/`` (strategy + responsibility chain) so new entity types register
instead of growing another if/else here.

Fail-closed: skipped vision (except explicit qa_disabled) must NOT promote assets.
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from qa.media_checks import (
    apply_sharpness_gate as _apply_sharpness_gate,
    frame_sharpness,
    injury_near_miss_promote as _injury_near_miss_promote,
    sharpness_min_hp_var,
)
from qa.types import format_entity_context, gender_hint_from_text


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

    Soft-skipped vision failures must NOT promote assets. Explicit ``qa_disabled``
    remains a soft pass.
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


def judge_image_against_prompt(
    path: Path | str,
    *,
    prompt: str,
    kind: str = "character",
    entity_name: str = "",
    entity_description: str = "",
) -> dict[str, Any]:
    """Return {ok, pass, score, reason, skipped}. Strategy resolved from kind + bible."""
    from qa.pipeline import run_image_qa

    return run_image_qa(
        path,
        prompt=prompt,
        kind=kind,
        entity_name=entity_name,
        entity_description=entity_description,
        vision_call=_call_vision_judge,
        image_data_url=_qa_image_data_url,
    )


def judge_video_against_prompt(
    path: Path | str,
    *,
    prompt: str,
    kind: str = "shot",
    entity_context: str = "",
    entities: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Sample frames and judge cast/scene/prop fit. Shot strategy + cast/sharpness gates."""
    from qa.pipeline import run_video_qa

    return run_video_qa(
        path,
        prompt=prompt,
        kind=kind,
        entity_context=entity_context,
        entities=entities,
        vision_call=_call_vision_judge,
        image_data_url=_qa_image_data_url,
        extract_frame=extract_video_frame,
        video_duration=_video_duration_sec,
    )
