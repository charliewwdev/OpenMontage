"""Project library covers: first video frame + multi-format crop presets."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from store import ProjectStore, _now, new_id


def cover_formats() -> list[dict[str, Any]]:
    try:
        from platform_config import load_platform_config

        items = (load_platform_config() or {}).get("coverFormats") or []
        if isinstance(items, list) and items:
            return [x for x in items if isinstance(x, dict) and x.get("id")]
    except Exception:
        pass
    return [
        {"id": "portrait_9_16", "label": "竖版封面", "ratio": "9:16", "description": "短剧 / 抖音"},
        {"id": "landscape_16_9", "label": "横版封面", "ratio": "16:9", "description": "横屏预览"},
        {"id": "square_1_1", "label": "方版封面", "ratio": "1:1", "description": "社媒方图"},
        {"id": "social_4_5", "label": "社媒封面", "ratio": "4:5", "description": "信息流"},
    ]


def _ratio_wh(ratio: str) -> tuple[int, int]:
    raw = str(ratio or "9:16").strip()
    if ":" in raw:
        a, b = raw.split(":", 1)
        try:
            return max(1, int(a)), max(1, int(b))
        except Exception:
            pass
    return 9, 16


def _ffmpeg_cover_frame(
    video: Path,
    dest: Path,
    *,
    ratio: str,
    at_sec: float = 0.15,
    width: int = 1080,
) -> bool:
    rw, rh = _ratio_wh(ratio)
    height = max(64, int(round(width * rh / rw)))
    # Scale to cover, then center-crop to target aspect.
    vf = (
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height}"
    )
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-ss",
        str(max(0.0, float(at_sec))),
        "-i",
        str(video),
        "-frames:v",
        "1",
        "-vf",
        vf,
        "-q:v",
        "2",
        str(dest),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=45)
        return dest.is_file() and dest.stat().st_size > 200
    except Exception:
        return False


def resolve_cover_format(format_id: str | None, project_ratio: str | None = None) -> dict[str, Any]:
    formats = cover_formats()
    fid = str(format_id or "").strip()
    if fid:
        hit = next((f for f in formats if f.get("id") == fid), None)
        if hit:
            return hit
    # Default: match project ratio when possible.
    pr = str(project_ratio or "").strip()
    if pr:
        hit = next((f for f in formats if str(f.get("ratio") or "") == pr), None)
        if hit:
            return hit
    return formats[0]


def first_shot_video_rel(store: ProjectStore, project_id: str) -> str | None:
    """Earliest successful shot / edit video path for auto cover."""
    state = store.load(project_id)
    if not state:
        return None
    for edit in state.get("edits") or []:
        out = str(edit.get("outputPath") or "").strip()
        if out and store._media_exists(project_id, out):
            return out
    shots = sorted(
        [s for s in (state.get("shots") or []) if not s.get("deletedAt")],
        key=lambda s: int(s.get("shotOrder") or 0),
    )
    for shot in shots:
        videos = shot.get("videos") or []
        sel = shot.get("selectedVideoId")
        hit = next((v for v in videos if v.get("id") == sel), None)
        if not hit:
            hit = next((v for v in videos if v.get("qaPass") and v.get("path")), None)
        if not hit and videos:
            hit = next((v for v in videos if v.get("path")), None)
        rel = str((hit or {}).get("path") or "").strip()
        if rel and store._media_exists(project_id, rel):
            return rel
    return None


def set_cover_from_video(
    store: ProjectStore,
    project_id: str,
    video_rel: str,
    *,
    format_id: str | None = None,
    at_sec: float = 0.15,
    title: str | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """Extract first usable frame from a project video and set it as still cover."""
    state = store.load(project_id)
    if not state:
        raise FileNotFoundError("project not found")
    proj = state.setdefault("project", {})
    # Keep a manually locked cover unless force.
    if proj.get("coverLocked") and not force:
        return {"skipped": True, "reason": "cover_locked", "coverPath": proj.get("coverPath")}
    rel = str(video_rel or "").strip() or first_shot_video_rel(store, project_id) or ""
    if not rel:
        raise FileNotFoundError("no video for cover")
    src = store.ensure_media(project_id, rel)
    if not src or not Path(src).is_file():
        raise FileNotFoundError("video file missing")
    video_rel = rel
    fmt = resolve_cover_format(format_id or proj.get("coverFormatId"), proj.get("ratio"))
    cover_id = new_id("cover_")
    rel = f"media/covers/{cover_id}.jpg"
    dest = store._dir(project_id) / rel
    ok = _ffmpeg_cover_frame(
        Path(src),
        dest,
        ratio=str(fmt.get("ratio") or "9:16"),
        at_sec=at_sec,
    )
    if not ok:
        raise RuntimeError("封面抽帧失败")
    store.persist_media(project_id, rel)
    proj["coverPath"] = rel
    proj["coverFormatId"] = fmt.get("id")
    proj["coverRatio"] = fmt.get("ratio")
    proj["coverSource"] = "video_first_frame"
    proj["coverSourcePath"] = video_rel
    if title is not None:
        proj["coverTitle"] = str(title).strip()
    elif not proj.get("coverTitle"):
        proj["coverTitle"] = str(proj.get("title") or "").strip()
    proj["updatedAt"] = _now()
    store.save(state)
    return {
        "coverPath": rel,
        "coverFormatId": proj.get("coverFormatId"),
        "coverRatio": proj.get("coverRatio"),
        "coverTitle": proj.get("coverTitle"),
        "url": f"/api/media/{project_id}/{rel}",
    }


def maybe_set_cover_from_shot_video(
    store: ProjectStore,
    project_id: str,
    video_rel: str | None,
) -> None:
    """Best-effort: first successful video becomes library cover (unless locked)."""
    if not video_rel:
        return
    try:
        state = store.load(project_id)
        if not state:
            return
        proj = state.get("project") or {}
        if proj.get("coverLocked"):
            return
        # Prefer first video frame once; later shots do not overwrite unless no cover yet
        # or previous cover was also auto video-frame.
        if proj.get("coverPath") and proj.get("coverSource") not in {None, "", "video_first_frame", "auto"}:
            return
        if proj.get("coverPath") and proj.get("coverSource") == "video_first_frame":
            # Keep the earliest winning frame as the series cover.
            return
        set_cover_from_video(store, project_id, video_rel, force=False)
    except Exception:
        return


def set_cover_from_upload(
    store: ProjectStore,
    project_id: str,
    data: bytes,
    *,
    ext: str = "jpg",
    format_id: str | None = None,
    lock: bool = True,
) -> dict[str, Any]:
    state = store.load(project_id)
    if not state:
        raise FileNotFoundError("project not found")
    proj = state.setdefault("project", {})
    fmt = resolve_cover_format(format_id or proj.get("coverFormatId"), proj.get("ratio"))
    cover_id = new_id("cover_")
    use_ext = (ext or "jpg").lstrip(".").lower()
    if use_ext not in {"jpg", "jpeg", "png", "webp"}:
        use_ext = "jpg"
    rel = f"media/covers/{cover_id}.{use_ext}"
    store.write_media(project_id, rel, data)
    store.persist_media(project_id, rel)
    proj["coverPath"] = rel
    proj["coverFormatId"] = fmt.get("id")
    proj["coverRatio"] = fmt.get("ratio")
    proj["coverSource"] = "upload"
    proj["coverLocked"] = bool(lock)
    proj["updatedAt"] = _now()
    store.save(state)
    return {
        "coverPath": rel,
        "coverFormatId": proj.get("coverFormatId"),
        "coverRatio": proj.get("coverRatio"),
        "url": f"/api/media/{project_id}/{rel}",
        "coverLocked": True,
    }


def patch_cover_settings(
    store: ProjectStore,
    project_id: str,
    fields: dict[str, Any],
) -> dict[str, Any]:
    state = store.load(project_id)
    if not state:
        raise FileNotFoundError("project not found")
    proj = state.setdefault("project", {})
    if "coverTitle" in fields:
        proj["coverTitle"] = str(fields.get("coverTitle") or "").strip()
    if "coverLocked" in fields:
        proj["coverLocked"] = bool(fields.get("coverLocked"))
    if "coverFormatId" in fields:
        fmt = resolve_cover_format(fields.get("coverFormatId"), proj.get("ratio"))
        proj["coverFormatId"] = fmt.get("id")
        proj["coverRatio"] = fmt.get("ratio")
        # Re-crop from last video source when format changes.
        src = str(proj.get("coverSourcePath") or "").strip()
        if src and proj.get("coverSource") in {"video_first_frame", "auto"}:
            set_cover_from_video(
                store,
                project_id,
                src,
                format_id=fmt.get("id"),
                force=True,
            )
            state = store.load(project_id) or state
            return state.get("project") or proj
    if "coverPath" in fields and fields.get("coverPath"):
        proj["coverPath"] = str(fields["coverPath"])
    proj["updatedAt"] = _now()
    store.save(state)
    return proj
