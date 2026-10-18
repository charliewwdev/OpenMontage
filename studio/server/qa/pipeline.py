"""QA pipeline: resolve strategy → vision → gate chain. No kind if/else here."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from .gates import run_gate_chain
from .strategies import resolve_qa_strategy
from .types import QaContext, format_entity_context, verdict


def _media_qa_enabled() -> bool:
    try:
        from providers.media import media_qa_enabled

        return bool(media_qa_enabled())
    except Exception:
        return True


def run_image_qa(
    path: Path | str,
    *,
    prompt: str,
    kind: str = "character",
    entity_name: str = "",
    entity_description: str = "",
    vision_call: Callable[..., dict[str, Any]],
    image_data_url: Callable[[Path], str],
) -> dict[str, Any]:
    p = Path(path)
    if not p.is_file():
        return verdict(ok=False, passed=False, score=0, reason="missing_file")
    if not _media_qa_enabled():
        return verdict(ok=True, passed=True, score=1, reason="qa_disabled", skipped=True)

    ctx = QaContext.for_image(
        kind=kind,
        prompt=prompt,
        path=p,
        entity_name=entity_name,
        entity_description=entity_description,
    )
    strategy = resolve_qa_strategy(ctx)
    ctx.strategy_id = strategy.id
    qa = vision_call(
        data_urls=[image_data_url(p)],
        system=strategy.vision_system(ctx),
        user_text=strategy.vision_user(ctx),
    )
    qa = dict(qa)
    qa["strategy"] = strategy.id
    return run_gate_chain(ctx, qa, strategy.gate_ids(ctx))


def run_video_qa(
    path: Path | str,
    *,
    prompt: str,
    kind: str = "shot",
    entity_context: str = "",
    entities: list[dict[str, Any]] | None = None,
    vision_call: Callable[..., dict[str, Any]],
    image_data_url: Callable[[Path], str],
    extract_frame: Callable[..., Path | None],
    video_duration: Callable[[Path], float],
) -> dict[str, Any]:
    src = Path(path)
    if not src.is_file():
        return verdict(ok=False, passed=False, score=0, reason="missing_file")
    if not _media_qa_enabled():
        return verdict(ok=True, passed=True, score=1, reason="qa_disabled", skipped=True)

    dur = video_duration(src)
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
            fr = extract_frame(src, at_sec=t)
            if fr:
                frames.append(fr)
        if not frames:
            return verdict(ok=False, passed=False, score=0, reason="no_frame", skipped=True)

        ctx_text = entity_context or format_entity_context(entities)
        ctx = QaContext.for_video(
            kind=kind,
            prompt=prompt,
            frames=frames,
            entity_context=ctx_text,
            entities=entities,
        )
        strategy = resolve_qa_strategy(ctx)
        ctx.strategy_id = strategy.id
        qa = vision_call(
            data_urls=[image_data_url(f) for f in frames],
            system=strategy.vision_system(ctx),
            user_text=strategy.vision_user(ctx),
        )
        qa = dict(qa)
        qa["strategy"] = strategy.id
        return run_gate_chain(ctx, qa, strategy.gate_ids(ctx))
    finally:
        for fr in frames:
            try:
                fr.unlink(missing_ok=True)
            except Exception:
                pass
