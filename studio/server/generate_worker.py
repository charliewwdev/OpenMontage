"""Offline / online shot generation worker for Drama Studio.

Offline mode (default): renders SVG keyframe boards from storyboard text so
the product is usable without provider keys. Online mode hooks are reserved
for when FAL_KEY / ARK_API_KEY etc. are present.
"""

from __future__ import annotations

import threading
import time
import xml.sax.saxutils as xml
from pathlib import Path
from typing import Any

_LOCK = threading.Lock()


def _mgr():
    from tools.pipeline.shot_job_manager import ShotJobManager

    return ShotJobManager()
_STATE: dict[str, Any] = {
    "running": False,
    "project": None,
    "processed": 0,
    "failed": 0,
    "last_error": None,
    "updated_at": None,
}


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
    # Prefer text nodes (no foreignObject) for broad SVG preview support
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
  <text x="56" y="{h-60}" fill="rgba(255,255,255,0.55)" font-family="sans-serif" font-size="16">{style_e} · offline board</text>
</svg>
"""


def _write_keyframe(project: Path, shot: dict, bible: dict | None) -> Path:
    out_dir = project / "renders" / "keyframes"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{shot['id']}.svg"
    style = (bible or {}).get("visual_style") or "当代都市夜戏"
    aspect = shot.get("aspect_ratio") or "9:16"
    # storyboard-level aspect may be elsewhere; caller can pass via shot
    path.write_text(_svg_keyframe(shot, style, aspect), encoding="utf-8")
    return path


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
            mark = mgr.execute(
                {
                    "operation": "mark",
                    "ledger_path": str(ledger_path),
                    "job_id": job["job_id"],
                    "status": "needs_review",
                    "provider": "studio-offline",
                    "model": "svg-board",
                    "keyframe_path": str(kf.relative_to(project)),
                    "cost_usd": 0,
                }
            )
            if not mark.success:
                raise RuntimeError(mark.error)
            processed += 1
            results.append({"shot_id": job["shot_id"], "status": "needs_review", "keyframe": str(kf)})
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

    def _run() -> None:
        _set(running=True, project=project.name, processed=0, failed=0, last_error=None)
        try:
            # ensure ledger exists
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
            # drain pending until empty or idle batch
            total_p = total_f = 0
            while True:
                out = _process_batch(project, storyboard, bible, limit)
                total_p += out["processed"]
                total_f += out["failed"]
                _set(processed=total_p, failed=total_f)
                if out["batch_size"] == 0:
                    break
                # small yield so API can poll
                time.sleep(0.05)
        except Exception as exc:
            _set(last_error=str(exc))
        finally:
            _set(running=False)

    t = threading.Thread(target=_run, name=f"gen-{project.name}", daemon=True)
    t.start()
    return {"started": True, "state": get_state()}


def generate_sync(project: Path, storyboard: dict, bible: dict | None, limit: int = 3) -> dict:
    """Synchronous single-batch helper for smoke tests."""
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
