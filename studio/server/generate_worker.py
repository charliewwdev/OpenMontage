"""Shot generation worker for Drama Studio.

Produces:
1. SVG keyframe boards (browser preview, always)
2. Short MP4 clips via FFmpeg (when available) so Edit can export a real episode
"""

from __future__ import annotations

import threading
import time
import xml.sax.saxutils as xml
from pathlib import Path
from typing import Any

_LOCK = threading.Lock()

_STATE: dict[str, Any] = {
    "running": False,
    "project": None,
    "processed": 0,
    "failed": 0,
    "last_error": None,
    "updated_at": None,
    "mode": "offline",
}


def _mgr():
    from tools.pipeline.shot_job_manager import ShotJobManager

    return ShotJobManager()


def get_state() -> dict[str, Any]:
    with _LOCK:
        return dict(_STATE)


def _set(**kwargs: Any) -> None:
    with _LOCK:
        _STATE.update(kwargs)
        _STATE["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _svg_keyframe(shot: dict, style: str, aspect: str) -> str:
    desc_raw = (shot.get("description") or "镜头")[:180]
    dialogue = xml.escape((shot.get("dialogue") or "")[:120])
    intent = xml.escape(str(shot.get("shot_intent") or "shot"))
    sid = xml.escape(str(shot.get("id") or ""))
    style_e = xml.escape((style or "电影感")[:80])
    if aspect == "16:9":
        w, h = 1280, 720
    elif aspect == "1:1":
        w, h = 1080, 1080
    else:
        w, h = 720, 1280
    lines = []
    buf = desc_raw
    while buf and len(lines) < 6:
        lines.append(xml.escape(buf[:28]))
        buf = buf[28:]
    text_block = "\n".join(
        f'<text x="56" y="{h // 3 + i * 36}" fill="#f7f3ea" font-family="Georgia, serif" font-size="28">{line}</text>'
        for i, line in enumerate(lines)
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">
  <defs>
    <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#0b1c24"/>
      <stop offset="55%" stop-color="#12383f"/>
      <stop offset="100%" stop-color="#c45c26"/>
    </linearGradient>
  </defs>
  <rect width="100%" height="100%" fill="url(#g)"/>
  <rect x="36" y="36" width="{w-72}" height="{h-72}" rx="18" fill="none" stroke="rgba(255,255,255,0.28)" stroke-width="2"/>
  <text x="56" y="90" fill="#8fd6cb" font-family="Georgia, serif" font-size="28">{sid}</text>
  <text x="56" y="130" fill="#f4efe6" font-family="Georgia, serif" font-size="22">{intent}</text>
  {text_block}
  <text x="56" y="{h-120}" fill="#f0c9a8" font-family="Georgia, serif" font-size="24">「{dialogue}」</text>
  <text x="56" y="{h-60}" fill="rgba(255,255,255,0.55)" font-family="sans-serif" font-size="16">{style_e} · board</text>
</svg>
"""


def _write_keyframe(project: Path, shot: dict, bible: dict | None) -> Path:
    out_dir = project / "renders" / "keyframes"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{shot['id']}.svg"
    style = (bible or {}).get("visual_style") or "当代都市夜戏"
    aspect = shot.get("aspect_ratio") or "9:16"
    path.write_text(_svg_keyframe(shot, style, aspect), encoding="utf-8")
    return path


def _write_clip(project: Path, shot: dict, aspect: str) -> Path | None:
    try:
        from export_mp4 import ffmpeg_available, render_clip_from_board
    except ImportError:
        from studio.server.export_mp4 import ffmpeg_available, render_clip_from_board  # type: ignore

    if not ffmpeg_available():
        return None
    return render_clip_from_board(project, shot, aspect=aspect)


def _process_batch(project: Path, storyboard: dict, bible: dict | None, limit: int) -> dict:
    ledger_path = project / "shot_jobs.json"
    mgr = _mgr()
    batch_res = mgr.execute(
        {"operation": "next_batch", "ledger_path": str(ledger_path), "limit": limit}
    )
    if not batch_res.success:
        raise RuntimeError(batch_res.error or "next_batch failed")
    batch = (batch_res.data or {}).get("batch") or []
    shots = {s["id"]: s for s in (storyboard.get("shots") or [])}
    aspect = storyboard.get("aspect_ratio") or "9:16"
    processed = 0
    failed = 0
    results = []
    for job in batch:
        shot = dict(shots.get(job["shot_id"]) or {"id": job["shot_id"]})
        shot.setdefault("aspect_ratio", aspect)
        try:
            kf = _write_keyframe(project, shot, bible)
            clip = _write_clip(project, shot, aspect)
            mark_payload = {
                "operation": "mark",
                "ledger_path": str(ledger_path),
                "job_id": job["job_id"],
                "status": "needs_review" if clip else "needs_review",
                "provider": "studio-offline",
                "model": "ffmpeg-board" if clip else "svg-board",
                "keyframe_path": str(kf.relative_to(project)),
                "cost_usd": 0,
            }
            if clip:
                mark_payload["clip_path"] = str(clip.relative_to(project))
            mark = mgr.execute(mark_payload)
            if not mark.success:
                raise RuntimeError(mark.error)
            processed += 1
            results.append(
                {
                    "shot_id": job["shot_id"],
                    "status": "needs_review",
                    "keyframe": str(kf),
                    "clip": str(clip) if clip else None,
                }
            )
        except Exception as exc:
            failed += 1
            mgr.execute(
                {
                    "operation": "mark",
                    "ledger_path": str(ledger_path),
                    "job_id": job["job_id"],
                    "status": "failed",
                    "error": str(exc),
                }
            )
            results.append({"shot_id": job["shot_id"], "status": "failed", "error": str(exc)})
    return {"processed": processed, "failed": failed, "results": results, "batch_size": len(batch)}


def start_generate(project: Path, storyboard: dict, bible: dict | None, limit: int = 3) -> dict:
    st = get_state()
    if st.get("running"):
        return {"started": False, "error": "generator already running", "state": st}

    try:
        from export_mp4 import ffmpeg_available
    except ImportError:
        from studio.server.export_mp4 import ffmpeg_available  # type: ignore

    mode = "offline+ffmpeg" if ffmpeg_available() else "offline-svg"

    def _run() -> None:
        _set(running=True, project=project.name, processed=0, failed=0, last_error=None, mode=mode)
        try:
            ledger_path = project / "shot_jobs.json"
            if not ledger_path.exists():
                _mgr().execute(
                    {
                        "operation": "create_from_storyboard",
                        "ledger_path": str(ledger_path),
                        "storyboard": storyboard,
                        "episode_id": storyboard.get("episode_id") or "ep01",
                        "concurrency": 2,
                        "max_retries": 2,
                        "default_subgraph_id": "keyframe-i2v-qa",
                    }
                )
            total_p = total_f = 0
            while True:
                out = _process_batch(project, storyboard, bible, limit)
                total_p += out["processed"]
                total_f += out["failed"]
                _set(processed=total_p, failed=total_f)
                if out["batch_size"] == 0:
                    break
                time.sleep(0.05)
        except Exception as exc:
            _set(last_error=str(exc))
        finally:
            _set(running=False)

    t = threading.Thread(target=_run, name=f"gen-{project.name}", daemon=True)
    t.start()
    return {"started": True, "state": get_state()}


def generate_sync(project: Path, storyboard: dict, bible: dict | None, limit: int = 3) -> dict:
    ledger_path = project / "shot_jobs.json"
    if not ledger_path.exists():
        _mgr().execute(
            {
                "operation": "create_from_storyboard",
                "ledger_path": str(ledger_path),
                "storyboard": storyboard,
                "episode_id": storyboard.get("episode_id") or "ep01",
            }
        )
    return _process_batch(project, storyboard, bible, limit)


def write_entity_board(project: Path, entity: str, item: dict, visual_style: str = "") -> Path:
    """Write a reference SVG board for character / location / prop."""
    out_dir = project / "renders" / "entities" / entity
    out_dir.mkdir(parents=True, exist_ok=True)
    eid = item.get("id") or "entity"
    name = xml.escape(str(item.get("name") or item.get("display_name") or eid)[:40])
    blurb = xml.escape(
        str(item.get("appearance") or item.get("description") or item.get("look") or "")[:200]
    )
    style = xml.escape((visual_style or "短剧定妆")[:60])
    kind_label = {"character": "角色定妆", "location": "场景空镜", "prop": "关键道具"}.get(entity, entity)
    path = out_dir / f"{eid}.svg"
    path.write_text(
        f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="720" height="960" viewBox="0 0 720 960">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#101827"/>
      <stop offset="100%" stop-color="#1f3a44"/>
    </linearGradient>
  </defs>
  <rect width="100%" height="100%" fill="url(#bg)"/>
  <rect x="32" y="32" width="656" height="896" rx="20" fill="none" stroke="#56c7c1" stroke-opacity="0.45"/>
  <text x="56" y="90" fill="#f2b84b" font-family="sans-serif" font-size="18">{kind_label}</text>
  <text x="56" y="150" fill="#ffffff" font-family="Georgia, serif" font-size="40">{name}</text>
  <foreignObject x="56" y="200" width="608" height="560">
    <div xmlns="http://www.w3.org/1999/xhtml" style="color:#e8eef2;font:22px/1.6 Georgia,serif;white-space:pre-wrap">{blurb}</div>
  </foreignObject>
  <text x="56" y="900" fill="rgba(255,255,255,0.45)" font-family="sans-serif" font-size="16">{style}</text>
</svg>
""",
        encoding="utf-8",
    )
    return path
