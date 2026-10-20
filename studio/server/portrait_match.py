"""抖音写真对标（首尾帧 MiniMax H3 idlock）— Studio UI workflow helpers."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from drama_service import _now, new_id

_ASSETS = Path(__file__).resolve().parents[1] / "assets" / "portrait-match"

MOTION = {
    "ref1": "Night riverside idol look-back / spin / heart / wink energy between frames; soft wet-city bokeh.",
    "ref2": "Pink lolita sakura dance beat between frames; sheer sleeves and frills move gracefully.",
    "ref3": "High-key indoor sweet dance between frames; center girl focus, soft friends behind.",
}

IDENTITY = (
    "Keep the EXACT same person as shown in the first and last frames: identical face, "
    "eyes, nose, mouth, skin, makeup, hair, outfit. Do not beautify into a different face. "
    "Expression must transition naturally from the first-frame expression to the last-frame "
    "expression. Photoreal skin pores and catchlights. "
    "Stable anatomy: two arms two legs, five fingers, no melted limbs, no face warp."
)

TEMPLATES = [
    {
        "id": "ref1",
        "title": "甜屿 · 夜景回眸",
        "desc": "雨夜河边暖光 bokeh，偶像感回眸 / 转体 / 比心",
        "ratio": "9:16",
        "sample": "samples/match_ref1_v3.mp4",
    },
    {
        "id": "ref2",
        "title": "甜屿 · 粉色洛丽塔",
        "desc": "樱花舞拍，薄纱袖与荷叶边",
        "ratio": "9:16",
        "sample": "samples/match_ref2_v3.mp4",
    },
    {
        "id": "ref3",
        "title": "甜屿 · 室内甜舞",
        "desc": "高调室内甜舞，中心女主 + 柔焦同伴",
        "ratio": "9:16",
        "sample": "samples/match_ref3_v3.mp4",
    },
]


def assets_root() -> Path:
    return _ASSETS


def list_templates() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    pairs = _load_pairs()
    for t in TEMPLATES:
        frames = _ASSETS / t["id"] / "frames"
        n = len(list(frames.glob("*_s.jpg"))) if frames.is_dir() else 0
        sample = _ASSETS / t["sample"] if t.get("sample") else None
        out.append(
            {
                **t,
                "shotCount": n or len(pairs.get(t["id"]) or []),
                "ready": n > 0,
                "sampleUrl": f"/api/portrait-match/assets/{t['sample']}" if sample and sample.is_file() else None,
            }
        )
    return out


def _load_pairs() -> dict[str, Any]:
    path = _ASSETS / "pairs.json"
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _idlock_prompt(template_id: str) -> str:
    motion = MOTION.get(template_id) or MOTION["ref1"]
    return (
        f"{IDENTITY} Motion between first and last frame: {motion} "
        "Camera: locked or micro follow only, no whip pan, no heavy motion blur, sharp face always. "
        "Preserve exact identity and the expression change shown by the two frames."
    )


def create_from_template(
    store: Any,
    *,
    template_id: str,
    title: str | None = None,
    owner_id: str | None = None,
    include_sample: bool = True,
) -> dict[str, Any]:
    """Create a portrait-match project with one shot per frame pair."""
    tid = (template_id or "").strip()
    meta = next((t for t in TEMPLATES if t["id"] == tid), None)
    if not meta:
        raise ValueError(f"未知模板: {template_id}")
    frames_src = _ASSETS / tid / "frames"
    if not frames_src.is_dir():
        raise FileNotFoundError(f"模板帧目录缺失: {frames_src}")
    pairs = _load_pairs().get(tid) or []
    if not pairs:
        # Fall back to glob order from *_s.jpg
        for s in sorted(frames_src.glob("*_s.jpg")):
            pairs.append({"id": s.stem.replace("_s", "")})

    label = (title or meta["title"]).strip() or meta["title"]
    state = store.create_project(
        title=label,
        brief=f"写真对标 · {meta['desc']}",
        genre="氛围写真",
        visual_style="抖音 AI 氛围感写真卡点，首尾帧身份锁",
        ratio=meta.get("ratio") or "9:16",
        name=f"portrait-{tid}",
        owner_id=owner_id,
    )
    pid = state["project"]["id"]
    state["project"]["workflow"] = "portrait-match"
    state["project"]["portraitTemplate"] = tid
    state["project"]["updatedAt"] = _now()

    ep_id = new_id("ep_")
    state["episodes"] = [
        {
            "id": ep_id,
            "episodeNumber": 1,
            "order": 1,
            "title": meta["title"],
            "synopsis": meta["desc"],
            "content": meta["desc"],
            "status": "draft",
            "createdAt": _now(),
            "updatedAt": _now(),
        }
    ]

    dest_frames = store._dir(pid) / "media" / "id_frames"
    dest_frames.mkdir(parents=True, exist_ok=True)
    prompt = _idlock_prompt(tid)
    shots: list[dict[str, Any]] = []
    for i, pair in enumerate(pairs):
        sid_label = str(pair.get("id") or f"s{i+1:02d}")
        src_s = frames_src / f"{sid_label}_s.jpg"
        src_e = frames_src / f"{sid_label}_e.jpg"
        if not src_s.is_file() or not src_e.is_file():
            continue
        rel_s = f"media/id_frames/{sid_label}_s.jpg"
        rel_e = f"media/id_frames/{sid_label}_e.jpg"
        shutil.copy2(src_s, store._dir(pid) / rel_s)
        shutil.copy2(src_e, store._dir(pid) / rel_e)
        try:
            store.persist_media(pid, rel_s)
            store.persist_media(pid, rel_e)
        except Exception:
            pass
        # Match offline idlock_v3: fixed 3.5s H3 clips (not gap+2.5).
        duration = 3.5
        shot_id = new_id("sh_")
        shots.append(
            {
                "id": shot_id,
                "projectId": pid,
                "episodeId": ep_id,
                "shotOrder": i + 1,
                "order": i + 1,
                "segmentOrder": i + 1,
                "beatIndex": 1,
                "isSegmentLead": True,
                "title": sid_label,
                "prompt": prompt,
                "dialogue": "",
                "action": sid_label,
                "duration": duration,
                "referenceEntityIds": [],
                "startFramePath": rel_s,
                "endFramePath": rel_e,
                "idlock": True,
                "skipVideoQa": True,
                "status": "pending",
                "providerTaskId": None,
                "error": None,
                "videos": [],
                "selectedVideoId": None,
                "createdAt": _now(),
                "updatedAt": _now(),
            }
        )
    if not shots:
        raise RuntimeError("模板没有可用的首尾帧对")
    state["shots"] = shots

    if include_sample:
        sample_src = _ASSETS / (meta.get("sample") or "")
        if sample_src.is_file():
            rel = "media/videos/sample_match_v3.mp4"
            dest = store._dir(pid) / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(sample_src, dest)
            try:
                store.persist_media(pid, rel)
            except Exception:
                pass
            state.setdefault("edits", []).append(
                {
                    "id": new_id("ed_"),
                    "kind": "portrait-sample",
                    "title": f"{meta['title']} · 样片成片",
                    "outputPath": rel,
                    "createdAt": _now(),
                }
            )

    store.save(state)
    return store.bundle(pid) or state


def start_all_idlock(
    store: Any,
    project_id: str,
    *,
    model: str = "",
    resolution: str = "720p",
    only_missing: bool = True,
) -> dict[str, Any]:
    """Enqueue H3 idlock for every portrait shot (skip ones that already have video)."""
    from drama_service import start_shot_video
    from providers.media import resolve_video_model

    state = store.load(project_id)
    if not state:
        raise FileNotFoundError("project not found")
    if (state.get("project") or {}).get("workflow") != "portrait-match":
        raise RuntimeError("不是写真对标项目")
    vid_model = resolve_video_model(model or "")
    started: list[dict[str, Any]] = []
    for sh in state.get("shots") or []:
        if sh.get("deletedAt"):
            continue
        if only_missing and sh.get("selectedVideoId") and sh.get("status") == "success":
            continue
        if sh.get("status") == "generating":
            started.append({"shotId": sh["id"], "skipped": "generating"})
            continue
        try:
            out = start_shot_video(
                store,
                project_id,
                sh["id"],
                model=vid_model,
                resolution=resolution or "720p",
                skip_refs=True,
            )
            started.append({"shotId": sh["id"], "status": out.get("status")})
        except Exception as exc:
            started.append({"shotId": sh["id"], "error": str(exc)})
    return {"started": started, "bundle": store.bundle(project_id)}


def assemble_portrait(store: Any, project_id: str) -> dict[str, Any]:
    """Concat successful idlock clips into one 9:16 match video (front of each clip)."""
    state = store.load(project_id)
    if not state:
        raise FileNotFoundError("project not found")
    shots = sorted(
        [s for s in (state.get("shots") or []) if not s.get("deletedAt")],
        key=lambda s: int(s.get("order") or 0),
    )
    clips: list[Path] = []
    for sh in shots:
        sel = sh.get("selectedVideoId")
        vid = next((v for v in (sh.get("videos") or []) if v.get("id") == sel), None)
        if not vid or not vid.get("path"):
            continue
        p = store._dir(project_id) / vid["path"]
        if p.is_file() and p.stat().st_size > 10000:
            clips.append(p)
    if len(clips) < 2:
        raise RuntimeError(f"至少需要 2 个成功镜头才能合片（当前 {len(clips)}）")

    work = store._dir(project_id) / "media" / "assemble_portrait"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True, exist_ok=True)
    parts: list[Path] = []
    for i, src in enumerate(clips):
        dest = work / f"{i:03d}.mp4"
        # Front of each H3 clip — closest to first-frame identity lock.
        subprocess.check_call(
            [
                "ffmpeg",
                "-y",
                "-ss",
                "0.05",
                "-t",
                "0.95",
                "-i",
                str(src),
                "-an",
                "-vf",
                "setpts=PTS/1.12,fps=30,format=yuv420p",
                "-c:v",
                "libx264",
                "-preset",
                "fast",
                "-crf",
                "16",
                str(dest),
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        parts.append(dest)

    lst = work / "list.txt"
    lst.write_text("".join(f"file '{p.resolve()}'\n" for p in parts), encoding="utf-8")
    visual = work / "visual.mp4"
    subprocess.check_call(
        [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(lst),
            "-vf",
            "eq=saturation=1.05:contrast=1.03,fps=30,format=yuv420p",
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "16",
            "-an",
            str(visual),
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    rel = "media/videos/portrait_match_assembled.mp4"
    out = store._dir(project_id) / rel
    out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(visual, out)
    try:
        store.persist_media(project_id, rel)
    except Exception:
        pass
    edit = {
        "id": new_id("ed_"),
        "kind": "portrait-assemble",
        "title": "写真对标合片",
        "outputPath": rel,
        "clipCount": len(clips),
        "createdAt": _now(),
    }
    state.setdefault("edits", []).append(edit)
    state["project"]["updatedAt"] = _now()
    store.save(state)
    bundle = store.bundle(project_id) or state
    return {"edit": {**edit, "outputUrl": f"/api/media/{project_id}/{rel}"}, "bundle": bundle}
