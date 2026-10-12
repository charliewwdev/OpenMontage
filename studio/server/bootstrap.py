"""Bootstrap a short-drama project from novel / script text (offline heuristics)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def slugify(name: str) -> str:
    s = re.sub(r"[^\w\u4e00-\u9fff\-]+", "-", name.strip(), flags=re.UNICODE)
    s = re.sub(r"-+", "-", s).strip("-").lower()
    return s[:64] or "drama-project"


def _split_scenes(text: str) -> list[dict[str, str]]:
    text = text.replace("\r\n", "\n").strip()
    if not text:
        return []
    # Prefer explicit scene headings
    parts = re.split(r"\n(?=(?:第[一二三四五六七八九十百\d]+[场幕章集]|Scene\s*\d+|【.+?】))", text)
    blocks = [p.strip() for p in parts if p.strip()]
    if len(blocks) <= 1:
        blocks = [b.strip() for b in re.split(r"\n{2,}", text) if b.strip()]
    if not blocks:
        blocks = [text]
    scenes = []
    for i, block in enumerate(blocks, 1):
        lines = [ln.strip() for ln in block.split("\n") if ln.strip()]
        title = lines[0][:40] if lines else f"场次{i}"
        body = "\n".join(lines[1:] if len(lines) > 1 else lines)
        scenes.append({"title": title, "body": body or block})
    return scenes[:24]


_DIALOGUE_RE = re.compile(
    r"^(?P<speaker>[\u4e00-\u9fffA-Za-z0-9_·]{1,12})[：:]\s*(?P<line>.+)$"
)
_QUOTE_RE = re.compile(r"[「\"](.+?)[」\"]")


def _extract_dialogue(body: str) -> list[dict[str, str]]:
    out = []
    for ln in body.split("\n"):
        ln = ln.strip()
        if not ln:
            continue
        m = _DIALOGUE_RE.match(ln)
        if m:
            out.append({"speaker": m.group("speaker"), "text": m.group("line").strip()})
            continue
        quotes = _QUOTE_RE.findall(ln)
        for q in quotes:
            out.append({"speaker": "旁白", "text": q.strip()})
    return out


def _speaker_id(name: str) -> str:
    return "spk_" + re.sub(r"[^\w\u4e00-\u9fff]", "", name)[:24] or "spk_unknown"


def _char_id(name: str) -> str:
    return "char_" + re.sub(r"[^\w\u4e00-\u9fff]", "", name)[:24] or "char_unknown"


def _extract_props(text: str) -> list[dict[str, str]]:
    keywords = ["手机", "钥匙", "照片", "信件", "戒指", "刀", "枪", "手表", "项链", "合同", "U盘", "信封"]
    found = []
    for kw in keywords:
        if kw in text and len(found) < 8:
            found.append(
                {
                    "id": f"prop_{len(found)+1:02d}",
                    "name": kw,
                    "description": f"剧情关键道具：{kw}，保持造型一致",
                }
            )
    return found


def materialize_project(
    project: Path,
    *,
    title: str,
    source_text: str,
    aspect_ratio: str = "9:16",
    visual_style: str = "当代都市夜戏，电影感冷暖对比",
    genre: str = "都市逆袭",
) -> dict[str, Any]:
    """Write novel + all six-step artifacts into an existing project directory."""
    project.mkdir(parents=True, exist_ok=True)
    (project / "source").mkdir(exist_ok=True)
    (project / "source" / "NOVEL.md").write_text(source_text.strip() + "\n", encoding="utf-8")
    (project / "README.md").write_text(f"# {title}\n\nBootstrapped by Drama Studio.\n", encoding="utf-8")

    scenes_raw = _split_scenes(source_text)
    speakers: dict[str, str] = {}
    dialogue_all: list[dict[str, Any]] = []
    scene_docs = []
    for i, sc in enumerate(scenes_raw, 1):
        sid = f"ep01_sc{i:02d}"
        dialogues = _extract_dialogue(sc["body"])
        if not dialogues:
            # fall back: first 2 sentences as VO
            chunks = re.split(r"[。！？\n]", sc["body"])
            chunks = [c.strip() for c in chunks if c.strip()]
            for c in chunks[:3]:
                dialogues.append({"speaker": "旁白", "text": c})
        for d in dialogues:
            speakers.setdefault(d["speaker"], _speaker_id(d["speaker"]))
            dialogue_all.append(
                {
                    "id": f"d{len(dialogue_all)+1}",
                    "speaker_id": speakers[d["speaker"]],
                    "section_id": f"s{i}",
                    "text": d["text"],
                    "scene_id": sid,
                }
            )
        scene_docs.append(
            {
                "id": sid,
                "index": i,
                "title": sc["title"],
                "location_id": f"loc_sc{i:02d}",
                "purpose": sc["title"],
                "characters": [],
                "estimated_duration_seconds": max(12, min(45, 8 + 4 * len(dialogues))),
                "body": sc["body"][:2000],
            }
        )

    # Character bible from speakers (skip 旁白/短信-like)
    characters = []
    for display, spk in speakers.items():
        if display in {"旁白", "画外音", "字幕"}:
            continue
        cid = _char_id(display)
        characters.append(
            {
                "id": cid,
                "display_name": display,
                "role": "supporting" if len(characters) else "protagonist",
                "appearance": f"{display}，短剧角色，外貌待定稿",
                "wardrobe_variants": [{"id": "w_default", "label": "默认", "description": "日常装"}],
            }
        )
        for sc in scene_docs:
            # attach later via dialogue
            pass

    # Link characters into scenes via dialogue
    spk_to_char = {
        speakers[c["display_name"]]: c["id"]
        for c in characters
        if c["display_name"] in speakers
    }
    for sc in scene_docs:
        ids = []
        for d in dialogue_all:
            if d["scene_id"] == sc["id"] and d["speaker_id"] in spk_to_char:
                cid = spk_to_char[d["speaker_id"]]
                if cid not in ids:
                    ids.append(cid)
        sc["characters"] = ids

    locations = [
        {
            "id": sc["location_id"],
            "name": sc["title"][:20],
            "description": (sc.get("body") or "")[:80] or sc["title"],
        }
        for sc in scene_docs
    ]

    bible = {
        "version": "1.0",
        "visual_style": visual_style,
        "palette": ["#0B1C24", "#E8F2F5", "#C45C26", "#5B8C9A"],
        "characters": characters
        or [
            {
                "id": "char_lead",
                "display_name": "主角",
                "role": "protagonist",
                "appearance": "待定",
                "wardrobe_variants": [{"id": "w_default", "label": "默认", "description": "日常装"}],
            }
        ],
        "locations": locations,
        "props": _extract_props(source_text),
    }

    logline = (scenes_raw[0]["body"] if scenes_raw else title)[:120]
    script = {
        "version": "1.0",
        "title": title,
        "synopsis": logline,
        "brief": source_text.strip()[:4000],
        "genre": genre,
        "visual_style": visual_style,
        "aspect_ratio": aspect_ratio,
        "total_duration_seconds": sum(sc["estimated_duration_seconds"] for sc in scene_docs) or 90,
        "speakers": [
            {
                "id": spk,
                "display_name": name,
                "character_bible_id": spk_to_char.get(spk),
            }
            for name, spk in speakers.items()
        ],
        "sections": [
            {
                "id": f"s{i}",
                "label": sc["title"],
                "text": (sc.get("body") or "")[:240],
                "start_seconds": 0,
                "end_seconds": sc["estimated_duration_seconds"],
            }
            for i, sc in enumerate(scene_docs, 1)
        ],
        "episodes": [
            {
                "id": "ep01",
                "episodeNumber": 1,
                "title": title,
                "status": "draft",
                "content": "\n\n".join(
                    f"【{sc['title']}】\n{sc.get('body') or ''}" for sc in scene_docs
                ),
                "summary": logline,
            }
        ],
        "dialogue_beats": [
            {k: v for k, v in d.items() if k != "scene_id"} for d in dialogue_all
        ],
    }

    breakdown = {
        "version": "1.0",
        "series_title": title,
        "aspect_ratio": aspect_ratio,
        "target_episode_duration_seconds": script["total_duration_seconds"],
        "active_episode_id": "ep01",
        "episodes": [
            {
                "id": "ep01",
                "index": 1,
                "title": title,
                "logline": (scenes_raw[0]["body"] if scenes_raw else title)[:120],
                "hook": (dialogue_all[0]["text"] if dialogue_all else title),
                "cliffhanger": (dialogue_all[-1]["text"] if dialogue_all else ""),
                "target_duration_seconds": script["total_duration_seconds"],
                "scenes": [
                    {k: v for k, v in sc.items() if k != "body"} for sc in scene_docs
                ],
            }
        ],
    }

    shots = []
    idx = 1
    for sc in scene_docs:
        # establishing
        shots.append(
            {
                "id": f"{sc['id']}_sh00",
                "scene_id": sc["id"],
                "index": idx,
                "description": f"建立镜头：{sc['title']}",
                "duration_sec": 3,
                "shot_intent": "establishing",
                "character_ids": sc.get("characters") or [],
                "location_id": sc["location_id"],
                "keyframe_prompt": f"{visual_style}, establishing shot, {sc['title']}, {aspect_ratio}",
                "video_prompt": "slow push in establishing",
            }
        )
        idx += 1
        scene_lines = [d for d in dialogue_all if d["scene_id"] == sc["id"]]
        for di, d in enumerate(scene_lines, 1):
            intent = "dialogue" if d["speaker_id"] != speakers.get("旁白") else "insert"
            cid = spk_to_char.get(d["speaker_id"])
            shots.append(
                {
                    "id": f"{sc['id']}_sh{di:02d}",
                    "scene_id": sc["id"],
                    "index": idx,
                    "description": d["text"][:80],
                    "duration_sec": 4 if intent == "dialogue" else 3,
                    "shot_intent": intent,
                    "dialogue": d["text"],
                    "speaker_ids": [d["speaker_id"]],
                    "character_ids": [cid] if cid else [],
                    "location_id": sc["location_id"],
                    "keyframe_prompt": f"{visual_style}, {intent}, {d['text'][:60]}, {aspect_ratio}",
                    "video_prompt": "subtle performance, cinematic",
                    "needs_lip_sync": intent == "dialogue",
                }
            )
            idx += 1

    storyboard = {
        "version": "1.0",
        "episode_id": "ep01",
        "aspect_ratio": aspect_ratio,
        "subgraph_refs": {
            "shot_generation": "workflow_defs/subgraphs/keyframe-i2v-qa.workflow.json",
            "model_routing": "workflow_defs/subgraphs/video-router.workflow.json",
        },
        "shots": shots,
    }

    research = {
        "version": "1.0",
        "genre": genre,
        "platform_format": "竖屏短剧" if aspect_ratio == "9:16" else "横屏",
        "aspect_ratio": aspect_ratio,
        "visual_style": visual_style,
        "references": [],
        "notes": "Studio bootstrap from novel / source text",
    }

    proposal = {
        "version": "1.0",
        "title": title,
        "logline": breakdown["episodes"][0]["logline"],
        "episode_count": 1,
        "budget_usd": 25,
    }

    def dump(path: Path, data: dict) -> None:
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    dump(project / "research_brief.json", research)
    dump(project / "proposal_packet.json", proposal)
    dump(project / "script.json", script)
    dump(project / "episode_breakdown.json", breakdown)
    dump(project / "character_bible.json", bible)
    dump(project / "storyboard.json", storyboard)

    # ledger via ShotJobManager if available
    ledger_path = project / "shot_jobs.json"
    try:
        from tools.pipeline.shot_job_manager import ShotJobManager

        result = ShotJobManager().execute(
            {
                "operation": "create_from_storyboard",
                "ledger_path": str(ledger_path),
                "storyboard": storyboard,
                "episode_id": "ep01",
                "concurrency": 2,
                "max_retries": 2,
                "default_subgraph_id": "keyframe-i2v-qa",
            }
        )
        if not result.success:
            raise RuntimeError(result.error or "ledger create failed")
    except Exception:
        dump(
            ledger_path,
            {
                "version": "1.0",
                "episode_id": "ep01",
                "concurrency": 2,
                "max_retries": 2,
                "paused": False,
                "default_subgraph_id": "keyframe-i2v-qa",
                "jobs": [
                    {
                        "job_id": f"job_{i:04d}",
                        "shot_id": sh["id"],
                        "scene_id": sh["scene_id"],
                        "status": "pending",
                        "subgraph_id": "keyframe-i2v-qa",
                        "attempt": 0,
                        "cost_usd": 0,
                        "params": {
                            "duration_sec": sh["duration_sec"],
                            "shot_intent": sh["shot_intent"],
                        },
                    }
                    for i, sh in enumerate(shots, 1)
                ],
                "stats": {"pending": len(shots), "running": 0, "succeeded": 0, "failed": 0},
            },
        )

    return {
        "name": project.name,
        "path": str(project),
        "title": title,
        "scenes": len(scene_docs),
        "shots": len(shots),
        "characters": len(bible["characters"]),
        "props": len(bible.get("props") or []),
    }


def bootstrap_project(
    projects_root: Path,
    *,
    name: str,
    title: str,
    source_text: str,
    aspect_ratio: str = "9:16",
    visual_style: str = "当代都市夜戏，电影感冷暖对比",
    genre: str = "都市逆袭",
) -> dict[str, Any]:
    slug = slugify(name or title)
    project = projects_root / slug
    if project.exists():
        raise FileExistsError(f"project already exists: {slug}")
    return materialize_project(
        project,
        title=title,
        source_text=source_text,
        aspect_ratio=aspect_ratio,
        visual_style=visual_style,
        genre=genre,
    )


def rebuild_project(
    project: Path,
    *,
    title: str | None = None,
    source_text: str,
    aspect_ratio: str | None = None,
    visual_style: str | None = None,
    genre: str | None = None,
) -> dict[str, Any]:
    """Re-split an existing project from novel text (keeps project folder name)."""
    script = {}
    script_path = project / "script.json"
    if script_path.exists():
        try:
            script = json.loads(script_path.read_text(encoding="utf-8"))
        except Exception:
            script = {}
    # Clear previous renders/exports so UI doesn't show stale media
    for rel in ("renders", "exports"):
        target = project / rel
        if target.is_dir():
            import shutil

            shutil.rmtree(target, ignore_errors=True)
    return materialize_project(
        project,
        title=title or script.get("title") or project.name,
        source_text=source_text,
        aspect_ratio=aspect_ratio or script.get("aspect_ratio") or "9:16",
        visual_style=visual_style
        or script.get("visual_style")
        or "当代都市夜戏，电影感冷暖对比",
        genre=genre or script.get("genre") or "都市逆袭",
    )
