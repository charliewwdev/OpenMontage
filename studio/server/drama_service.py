"""Business logic for Xuefeng-parity Drama Studio flows."""

from __future__ import annotations

import json
import re
import threading
import urllib.request
from pathlib import Path
from typing import Any

from store import ProjectStore, _now, new_id

SKILLS_ROOT = Path(__file__).resolve().parents[1] / "skills"
STYLES_PATH = Path(__file__).resolve().parent / "video_styles.json"


def load_skill(name: str) -> str:
    path = SKILLS_ROOT / name / "SKILL.md"
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8")
    # strip frontmatter
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            return parts[2].strip()
    return text.strip()


def load_styles() -> list[dict]:
    if STYLES_PATH.exists():
        return json.loads(STYLES_PATH.read_text(encoding="utf-8"))
    return []


def resolve_style_prompt(visual_style: str) -> str:
    for s in load_styles():
        if s["promptValue"] == visual_style or s["id"] == visual_style or s["label"] == visual_style:
            return s["generationPrompt"]
    return visual_style or "电影级写实光影"


def optimize_brief(store: ProjectStore, payload: dict) -> dict:
    from providers.deepseek import chat_json

    skill = load_skill("script-brief")
    user = json.dumps(
        {
            "title": payload.get("title") or "",
            "brief": payload.get("brief") or "",
            "genre": payload.get("genre") or "",
            "visualStyle": payload.get("visualStyle") or "",
            "ratio": payload.get("ratio") or "9:16",
        },
        ensure_ascii=False,
    )
    data = chat_json(
        system=skill + "\n\n只输出 JSON：brief, genreDetected, tips。",
        user=user,
        temperature=0.6,
    )
    brief = (data.get("brief") or "").strip()
    if not brief:
        raise RuntimeError("AI 未返回有效的创作需求")
    return {
        "brief": brief[:100_000],
        "genreDetected": data.get("genreDetected") or "",
        "tips": (data.get("tips") or [])[:5],
    }


def _apply_generated_script(state: dict, generated: dict, *, replace_episodes: bool = True, start_number: int = 1) -> dict:
    ts = _now()
    pid = state["project"]["id"]
    summary = generated.get("summary") or {}
    if summary.get("title"):
        state["project"]["title"] = summary["title"]
    if summary.get("synopsis"):
        state["project"]["synopsis"] = summary["synopsis"]
    if summary.get("genre"):
        state["project"]["genre"] = summary["genre"]

    new_eps = []
    for ep in generated.get("episodes") or []:
        num = int(ep.get("episodeNumber") or start_number)
        new_eps.append(
            {
                "id": new_id("ep_"),
                "projectId": pid,
                "episodeNumber": num,
                "title": ep.get("title") or f"第{num}集",
                "content": ep.get("content") or "",
                "status": "draft",
                "createdAt": ts,
                "updatedAt": ts,
            }
        )
    if replace_episodes:
        state["episodes"] = sorted(new_eps, key=lambda e: e["episodeNumber"])
    else:
        existing_nums = {e["episodeNumber"] for e in state.get("episodes") or []}
        for ep in new_eps:
            while ep["episodeNumber"] in existing_nums:
                ep["episodeNumber"] += 1
            existing_nums.add(ep["episodeNumber"])
            state.setdefault("episodes", []).append(ep)
        state["episodes"] = sorted(state["episodes"], key=lambda e: e["episodeNumber"])

    # entities: replace characters/scenes/props from generation when replace
    keep_other = []
    if not replace_episodes:
        keep_other = list(state.get("entities") or [])
    else:
        keep_other = []

    entities = list(keep_other) if not replace_episodes else []
    # When replacing, clear old entities of kinds we regenerate
    if replace_episodes:
        entities = []
    else:
        entities = [e for e in (state.get("entities") or [])]

    def upsert_entity(kind: str, name: str, variant: str, description: str, episodes: list, category: str = "", metadata: dict | None = None):
        for e in entities:
            if e.get("deletedAt"):
                continue
            if e["kind"] == kind and e["name"] == name and (e.get("variant") or "") == (variant or ""):
                e["description"] = description or e["description"]
                e["episodes"] = episodes or e.get("episodes") or []
                e["updatedAt"] = ts
                return
        entities.append(
            {
                "id": new_id("ent_"),
                "projectId": pid,
                "kind": kind,
                "name": name,
                "variant": variant or "",
                "description": description or "",
                "episodes": episodes or [],
                "category": category or "",
                "metadata": metadata or {},
                "selectedImageId": None,
                "images": [],
                "createdAt": ts,
                "updatedAt": ts,
            }
        )

    if replace_episodes:
        entities = []

    for ch in generated.get("characters") or []:
        looks = ch.get("looks") or [{"name": "默认形象", "description": ch.get("description") or ch.get("introduction") or "", "episodes": []}]
        for look in looks:
            upsert_entity(
                "character",
                ch.get("name") or "角色",
                look.get("name") or "默认形象",
                look.get("description") or "",
                look.get("episodes") or [],
                metadata={"role": ch.get("role"), "gender": ch.get("gender"), "introduction": ch.get("introduction"), "voiceDescription": ch.get("voiceDescription")},
            )
    for sc in generated.get("scenes") or []:
        upsert_entity("scene", sc.get("name") or "场景", "", sc.get("description") or "", sc.get("episodes") or [])
    for prop in generated.get("props") or []:
        upsert_entity(
            "prop",
            prop.get("name") or "道具",
            "",
            prop.get("description") or "",
            prop.get("episodes") or [],
            category=prop.get("category") or "item",
        )

    state["entities"] = entities
    return state


def generate_script(store: ProjectStore, project_id: str, episode_count: int, planned: int | None = None) -> dict:
    from providers.deepseek import chat_json

    state = store.load(project_id)
    if not state:
        raise FileNotFoundError("project not found")
    count = max(1, min(10, int(episode_count)))
    skill = load_skill("drama-script")
    p = state["project"]
    user = json.dumps(
        {
            "action": "generate",
            "episodeCount": count,
            "plannedEpisodes": planned,
            "title": p["title"],
            "brief": p.get("brief") or "",
            "genre": p.get("genre"),
            "visualStyle": p.get("visualStyle"),
            "visualStylePrompt": resolve_style_prompt(p.get("visualStyle") or ""),
            "ratio": p.get("ratio"),
        },
        ensure_ascii=False,
    )
    data = chat_json(system=skill + "\n\n只输出规定 JSON。", user=user, temperature=0.75, max_tokens=16000)
    state = _apply_generated_script(state, data, replace_episodes=True)
    if planned:
        state["project"]["plannedEpisodes"] = planned
    return store.save(state)


def continue_script(store: ProjectStore, project_id: str, episode_count: int, instruction: str = "", brief: str = "", as_finale: bool = False) -> dict:
    from providers.deepseek import chat_json

    state = store.load(project_id)
    if not state:
        raise FileNotFoundError("project not found")
    count = max(1, min(10, int(episode_count)))
    last = max((e["episodeNumber"] for e in state.get("episodes") or []), default=0)
    skill = load_skill("drama-script")
    p = state["project"]
    user = json.dumps(
        {
            "action": "continue",
            "episodeCount": count,
            "startEpisodeNumber": last + 1,
            "asFinale": as_finale,
            "instruction": instruction,
            "extraBrief": brief,
            "title": p["title"],
            "synopsis": p.get("synopsis"),
            "genre": p.get("genre"),
            "visualStyle": p.get("visualStyle"),
            "ratio": p.get("ratio"),
            "existingEpisodes": [
                {"episodeNumber": e["episodeNumber"], "title": e["title"], "content": e["content"][:2000]}
                for e in (state.get("episodes") or [])[-3:]
            ],
            "existingEntities": [
                {"kind": e["kind"], "name": e["name"], "variant": e.get("variant"), "description": e["description"][:200]}
                for e in (state.get("entities") or [])
                if not e.get("deletedAt")
            ],
        },
        ensure_ascii=False,
    )
    data = chat_json(system=skill + "\n\n续写后续集，不要改写已有集。只输出 JSON。", user=user, temperature=0.75, max_tokens=16000)
    state = _apply_generated_script(state, data, replace_episodes=False, start_number=last + 1)
    return store.save(state)


def rewrite_script(store: ProjectStore, project_id: str, start: int, count: int, instruction: str = "") -> dict:
    from providers.deepseek import chat_json

    state = store.load(project_id)
    if not state:
        raise FileNotFoundError("project not found")
    count = max(1, min(10, int(count)))
    start = max(1, int(start))
    end = start + count - 1
    targets = [e for e in state.get("episodes") or [] if start <= e["episodeNumber"] <= end]
    if not targets:
        raise RuntimeError("指定范围内没有分集")
    # block rewrite if confirmed and has shots
    for e in targets:
        if e.get("status") == "confirmed":
            has_shots = any(s.get("episodeId") == e["id"] and not s.get("deletedAt") for s in state.get("shots") or [])
            if has_shots:
                raise RuntimeError(f"第{e['episodeNumber']}集已有分镜，请先清除分镜再改写")
    skill = load_skill("drama-script")
    p = state["project"]
    user = json.dumps(
        {
            "action": "rewrite",
            "startEpisodeNumber": start,
            "episodeCount": count,
            "instruction": instruction,
            "title": p["title"],
            "brief": p.get("brief"),
            "genre": p.get("genre"),
            "visualStyle": p.get("visualStyle"),
            "ratio": p.get("ratio"),
            "episodesToRewrite": [
                {"episodeNumber": e["episodeNumber"], "title": e["title"], "content": e["content"]}
                for e in targets
            ],
        },
        ensure_ascii=False,
    )
    data = chat_json(system=skill + "\n\n只改写指定集，保持集号。只输出 JSON。", user=user, temperature=0.7, max_tokens=16000)
    by_num = {int(ep["episodeNumber"]): ep for ep in (data.get("episodes") or [])}
    ts = _now()
    for e in state["episodes"]:
        if start <= e["episodeNumber"] <= end and e["episodeNumber"] in by_num:
            src = by_num[e["episodeNumber"]]
            e["title"] = src.get("title") or e["title"]
            e["content"] = src.get("content") or e["content"]
            e["status"] = "draft"
            e["updatedAt"] = ts
    return store.save(state)


def patch_episode(store: ProjectStore, project_id: str, episode_id: str, fields: dict) -> dict:
    state = store.load(project_id)
    if not state:
        raise FileNotFoundError("project not found")
    for e in state.get("episodes") or []:
        if e["id"] == episode_id:
            if "title" in fields:
                e["title"] = fields["title"]
            if "content" in fields:
                e["content"] = fields["content"]
            e["updatedAt"] = _now()
            store.save(state)
            return e
    raise FileNotFoundError("episode not found")


def set_episode_status(store: ProjectStore, project_id: str, episode_ids: list[str], status: str) -> dict:
    state = store.load(project_id)
    if not state:
        raise FileNotFoundError("project not found")
    if status not in {"draft", "confirmed"}:
        raise ValueError("invalid status")
    ids = set(episode_ids)
    for e in state.get("episodes") or []:
        if e["id"] not in ids:
            continue
        if status == "draft":
            has_shots = any(s.get("episodeId") == e["id"] and not s.get("deletedAt") for s in state.get("shots") or [])
            if has_shots:
                raise RuntimeError(f"第{e['episodeNumber']}集已有分镜，无法取消定稿")
        e["status"] = status
        e["updatedAt"] = _now()
    return store.save(state)


def upsert_entity(store: ProjectStore, project_id: str, payload: dict) -> dict:
    state = store.load(project_id)
    if not state:
        raise FileNotFoundError("project not found")
    ts = _now()
    entity_id = payload.get("id") or payload.get("entityId")
    if entity_id:
        for e in state.get("entities") or []:
            if e["id"] == entity_id:
                for key in ("name", "variant", "description", "category"):
                    if key in payload:
                        e[key] = payload[key]
                if "episodes" in payload:
                    e["episodes"] = payload["episodes"]
                e["updatedAt"] = ts
                store.save(state)
                return e
        raise FileNotFoundError("entity not found")
    kind = payload.get("kind")
    if kind not in {"character", "scene", "prop"}:
        raise ValueError("invalid kind")
    ent = {
        "id": new_id("ent_"),
        "projectId": project_id,
        "kind": kind,
        "name": (payload.get("name") or "").strip(),
        "variant": payload.get("variant") or ("默认形象" if kind == "character" else ""),
        "description": (payload.get("description") or "").strip(),
        "episodes": payload.get("episodes") or [],
        "category": payload.get("category") or "",
        "metadata": payload.get("metadata") or {},
        "selectedImageId": None,
        "images": [],
        "createdAt": ts,
        "updatedAt": ts,
    }
    if not ent["name"] or not ent["description"]:
        raise ValueError("名称和视觉描述不能为空")
    state.setdefault("entities", []).append(ent)
    store.save(state)
    return ent


def soft_delete_entity(store: ProjectStore, project_id: str, entity_id: str) -> dict:
    state = store.load(project_id)
    if not state:
        raise FileNotFoundError("project not found")
    for e in state.get("entities") or []:
        if e["id"] == entity_id:
            e["deletedAt"] = _now()
            e["updatedAt"] = _now()
            return store.save(state)
    raise FileNotFoundError("entity not found")


def generate_entity_image(store: ProjectStore, project_id: str, entity_id: str, *, three_view: bool = False, redraw: bool = False) -> dict:
    from providers.seedream import generate_image

    state = store.load(project_id)
    if not state:
        raise FileNotFoundError("project not found")
    ent = next((e for e in state.get("entities") or [] if e["id"] == entity_id and not e.get("deletedAt")), None)
    if not ent:
        raise FileNotFoundError("entity not found")
    style = resolve_style_prompt(state["project"].get("visualStyle") or "")
    ratio = state["project"].get("ratio") or "9:16"
    name = ent["name"]
    variant = ent.get("variant") or ""
    desc = ent.get("description") or ""
    if ent["kind"] == "character":
        prompt = f"{style}。角色定妆照：{name} {variant}。{desc}。"
        if three_view:
            prompt += "三视图：正面、侧面、背面，同一人物同一服装，纯色背景。"
        else:
            prompt += "半身或全身定妆，清晰五官，纯色或简洁背景。"
    elif ent["kind"] == "scene":
        prompt = f"{style}。空镜场景：{name}。{desc}。画面中不要出现人物。"
    else:
        prompt = f"{style}。关键道具特写：{name}。{desc}。"
        if three_view:
            prompt += "多角度产品级展示。"

    ref = None
    if redraw and ent.get("selectedImageId"):
        img = next((i for i in ent.get("images") or [] if i["id"] == ent["selectedImageId"]), None)
        if img and img.get("path"):
            ref = store._dir(project_id) / img["path"]

    img_id = new_id("img_")
    rel = f"media/images/{img_id}.png"
    out = store._dir(project_id) / rel
    generate_image(prompt=prompt, ratio=ratio, out_path=out, reference_path=ref)
    version = {
        "id": img_id,
        "entityId": entity_id,
        "path": rel,
        "prompt": prompt,
        "createdAt": _now(),
    }
    ent.setdefault("images", []).append(version)
    ent["selectedImageId"] = img_id
    ent["updatedAt"] = _now()
    store.save(state)
    return version


def select_entity_image(store: ProjectStore, project_id: str, entity_id: str, image_id: str) -> dict:
    state = store.load(project_id)
    if not state:
        raise FileNotFoundError("project not found")
    for e in state.get("entities") or []:
        if e["id"] == entity_id:
            if not any(i["id"] == image_id for i in e.get("images") or []):
                raise FileNotFoundError("image not found")
            e["selectedImageId"] = image_id
            e["updatedAt"] = _now()
            return store.save(state)
    raise FileNotFoundError("entity not found")


def upload_entity_image(store: ProjectStore, project_id: str, entity_id: str, data: bytes, ext: str = "png") -> dict:
    state = store.load(project_id)
    if not state:
        raise FileNotFoundError("project not found")
    ent = next((e for e in state.get("entities") or [] if e["id"] == entity_id), None)
    if not ent:
        raise FileNotFoundError("entity not found")
    img_id = new_id("img_")
    rel = f"media/images/{img_id}.{ext.lstrip('.')}"
    path = store._dir(project_id) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    version = {
        "id": img_id,
        "entityId": entity_id,
        "path": rel,
        "prompt": "local-upload",
        "createdAt": _now(),
    }
    ent.setdefault("images", []).append(version)
    ent["selectedImageId"] = img_id
    ent["updatedAt"] = _now()
    store.save(state)
    return version


def _parse_ref_tags(prompt: str, entities: list[dict]) -> list[str]:
    """Map @Name or @Name-Variant tags to entity ids (max 9)."""
    tags = re.findall(r"@([^\s@,，。；;]+)", prompt or "")
    ids = []
    for tag in tags:
        name, _, variant = tag.partition("-")
        for e in entities:
            if e.get("deletedAt"):
                continue
            if e["name"] == name and (not variant or (e.get("variant") or "") == variant):
                if e["id"] not in ids and e.get("selectedImageId"):
                    ids.append(e["id"])
                break
        if len(ids) >= 9:
            break
    return ids


def generate_storyboard(store: ProjectStore, project_id: str, episode_id: str) -> dict:
    from providers.deepseek import chat_json

    state = store.load(project_id)
    if not state:
        raise FileNotFoundError("project not found")
    ep = next((e for e in state.get("episodes") or [] if e["id"] == episode_id), None)
    if not ep:
        raise FileNotFoundError("episode not found")
    if ep.get("status") != "confirmed":
        raise RuntimeError("请先定稿本集再拆分镜")
    # remove existing shots for episode
    if any(s.get("episodeId") == episode_id and s.get("status") == "generating" for s in state.get("shots") or []):
        raise RuntimeError("仍有视频正在生成，完成后才能重新拆分")
    state["shots"] = [s for s in (state.get("shots") or []) if s.get("episodeId") != episode_id]
    # clear edit for episode
    state["edits"] = [e for e in (state.get("edits") or []) if e.get("episodeId") != episode_id]

    entities = [e for e in (state.get("entities") or []) if not e.get("deletedAt")]
    available = [
        e
        for e in entities
        if not e.get("episodes") or ep["episodeNumber"] in (e.get("episodes") or [])
    ]
    skill = load_skill("drama-shot-prompt")
    p = state["project"]
    user = json.dumps(
        {
            "episodeNumber": ep["episodeNumber"],
            "episodeTitle": ep["title"],
            "content": ep["content"],
            "ratio": p.get("ratio"),
            "visualStyle": p.get("visualStyle"),
            "visualStylePrompt": resolve_style_prompt(p.get("visualStyle") or ""),
            "assets": [
                {
                    "kind": e["kind"],
                    "name": e["name"],
                    "variant": e.get("variant"),
                    "tag": f"@{e['name']}" + (f"-{e['variant']}" if e.get("variant") else ""),
                    "hasImage": bool(e.get("selectedImageId")),
                }
                for e in available
            ],
        },
        ensure_ascii=False,
    )
    data = chat_json(system=skill + "\n\n只输出 JSON。", user=user, temperature=0.6, max_tokens=12000)
    ts = _now()
    shots = []
    for i, sh in enumerate(data.get("shots") or [], 1):
        prompt = sh.get("prompt") or ""
        refs = _parse_ref_tags(prompt, available)
        shots.append(
            {
                "id": new_id("sh_"),
                "projectId": project_id,
                "episodeId": episode_id,
                "shotOrder": int(sh.get("shotOrder") or i),
                "prompt": prompt,
                "duration": max(4, min(15, int(sh.get("duration") or 5))),
                "referenceEntityIds": refs,
                "status": "pending",
                "providerTaskId": None,
                "error": None,
                "selectedVideoId": None,
                "videos": [],
                "sceneName": sh.get("sceneName") or "",
                "action": sh.get("action") or "",
                "dialogue": sh.get("dialogue") or "",
                "createdAt": ts,
                "updatedAt": ts,
            }
        )
    state["shots"].extend(shots)
    store.save(state)
    return shots


def patch_shot(store: ProjectStore, project_id: str, shot_id: str, fields: dict) -> dict:
    state = store.load(project_id)
    if not state:
        raise FileNotFoundError("project not found")
    for s in state.get("shots") or []:
        if s["id"] == shot_id and not s.get("deletedAt"):
            if s.get("status") == "generating":
                raise RuntimeError("生成中不可编辑")
            for key in ("prompt", "duration", "referenceEntityIds", "dialogue", "action", "sceneName"):
                if key in fields:
                    s[key] = fields[key]
            if "duration" in fields:
                s["duration"] = max(4, min(15, int(fields["duration"])))
            s["updatedAt"] = _now()
            store.save(state)
            return s
    raise FileNotFoundError("shot not found")


def add_shot(store: ProjectStore, project_id: str, episode_id: str) -> dict:
    state = store.load(project_id)
    if not state:
        raise FileNotFoundError("project not found")
    ep = next((e for e in state.get("episodes") or [] if e["id"] == episode_id), None)
    if not ep:
        raise FileNotFoundError("episode not found")
    existing = [
        s
        for s in (state.get("shots") or [])
        if s.get("episodeId") == episode_id and not s.get("deletedAt")
    ]
    order = max((int(s.get("shotOrder") or 0) for s in existing), default=0) + 1
    ts = _now()
    shot = {
        "id": new_id("sh_"),
        "projectId": project_id,
        "episodeId": episode_id,
        "shotOrder": order,
        "prompt": "",
        "duration": 5,
        "referenceEntityIds": [],
        "status": "pending",
        "providerTaskId": None,
        "error": None,
        "selectedVideoId": None,
        "videos": [],
        "sceneName": "",
        "action": "",
        "dialogue": "",
        "createdAt": ts,
        "updatedAt": ts,
    }
    state.setdefault("shots", []).append(shot)
    store.save(state)
    return shot


def soft_delete_shot(store: ProjectStore, project_id: str, shot_id: str) -> dict:
    state = store.load(project_id)
    if not state:
        raise FileNotFoundError("project not found")
    for s in state.get("shots") or []:
        if s["id"] == shot_id and not s.get("deletedAt"):
            if s.get("status") == "generating":
                raise RuntimeError("生成中不可删除")
            s["deletedAt"] = _now()
            s["updatedAt"] = _now()
            # drop from edit clips
            for edit in state.get("edits") or []:
                if edit.get("episodeId") == s.get("episodeId"):
                    edit["clips"] = [c for c in (edit.get("clips") or []) if c.get("shotId") != shot_id]
            store.save(state)
            return s
    raise FileNotFoundError("shot not found")


def _download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=300) as resp:
        dest.write_bytes(resp.read())


def start_shot_video(store: ProjectStore, project_id: str, shot_id: str, *, model: str, resolution: str) -> dict:
    from providers.seedance import create_task

    state = store.load(project_id)
    if not state:
        raise FileNotFoundError("project not found")
    shot = next((s for s in state.get("shots") or [] if s["id"] == shot_id and not s.get("deletedAt")), None)
    if not shot:
        raise FileNotFoundError("shot not found")
    if shot.get("status") == "generating":
        raise RuntimeError("该镜头正在生成")

    entities = {e["id"]: e for e in state.get("entities") or [] if not e.get("deletedAt")}
    content: list[dict] = [{"type": "text", "text": shot.get("prompt") or ""}]
    # resolve refs to data urls / paths as image_url - Seedance accepts URL; we use local file via data URL
    import base64

    for eid in (shot.get("referenceEntityIds") or [])[:9]:
        ent = entities.get(eid)
        if not ent or not ent.get("selectedImageId"):
            continue
        img = next((i for i in ent.get("images") or [] if i["id"] == ent["selectedImageId"]), None)
        if not img:
            continue
        path = store._dir(project_id) / img["path"]
        if not path.is_file():
            continue
        b64 = base64.b64encode(path.read_bytes()).decode("ascii")
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{b64}"},
                "role": "reference_image",
            }
        )

    task_id = create_task(
        model=model,
        content=content,
        ratio=state["project"].get("ratio") or "9:16",
        resolution=resolution,
        duration=int(shot.get("duration") or 5),
    )
    shot["status"] = "generating"
    shot["providerTaskId"] = task_id
    shot["error"] = None
    shot["updatedAt"] = _now()
    shot["_pendingModel"] = model
    shot["_pendingResolution"] = resolution
    store.save(state)

    def _poll() -> None:
        from providers.seedance import query_task

        for _ in range(120):
            try:
                st = store.load(project_id)
                sh = next((x for x in (st.get("shots") or []) if x["id"] == shot_id), None)
                if not sh:
                    return
                result = query_task(task_id)
                status = result.get("status")
                if status in {"succeeded"}:
                    vid_id = new_id("vid_")
                    rel = f"media/videos/{vid_id}.mp4"
                    dest = store._dir(project_id) / rel
                    if result.get("videoUrl"):
                        _download(result["videoUrl"], dest)
                    version = {
                        "id": vid_id,
                        "shotId": shot_id,
                        "path": rel if dest.is_file() else None,
                        "providerTaskId": task_id,
                        "model": model,
                        "duration": float(result.get("duration") or sh.get("duration") or 5),
                        "resolution": result.get("resolution") or resolution,
                        "prompt": sh.get("prompt") or "",
                        "rating": None,
                        "note": "",
                        "createdAt": _now(),
                    }
                    sh.setdefault("videos", []).append(version)
                    sh["selectedVideoId"] = vid_id
                    sh["status"] = "success"
                    sh["providerTaskId"] = task_id
                    sh["error"] = None
                    sh["updatedAt"] = _now()
                    store.save(st)
                    return
                if status in {"failed", "expired", "cancelled"}:
                    sh["status"] = "failed"
                    sh["error"] = result.get("error") or status
                    sh["updatedAt"] = _now()
                    store.save(st)
                    return
            except Exception as exc:
                st = store.load(project_id)
                sh = next((x for x in (st.get("shots") or []) if x["id"] == shot_id), None)
                if sh:
                    sh["status"] = "failed"
                    sh["error"] = str(exc)
                    sh["updatedAt"] = _now()
                    store.save(st)
                return
            import time

            time.sleep(5)

        st = store.load(project_id)
        sh = next((x for x in (st.get("shots") or []) if x["id"] == shot_id), None)
        if sh and sh.get("status") == "generating":
            sh["status"] = "failed"
            sh["error"] = "生成超时"
            sh["updatedAt"] = _now()
            store.save(st)

    threading.Thread(target=_poll, name=f"seedance-{shot_id}", daemon=True).start()
    return shot


def poll_shot(store: ProjectStore, project_id: str, shot_id: str) -> dict:
    state = store.load(project_id)
    if not state:
        raise FileNotFoundError("project not found")
    shot = next((s for s in state.get("shots") or [] if s["id"] == shot_id), None)
    if not shot:
        raise FileNotFoundError("shot not found")
    return shot


def select_take(store: ProjectStore, project_id: str, shot_id: str, video_id: str) -> dict:
    state = store.load(project_id)
    if not state:
        raise FileNotFoundError("project not found")
    for s in state.get("shots") or []:
        if s["id"] == shot_id:
            if not any(v["id"] == video_id for v in s.get("videos") or []):
                raise FileNotFoundError("video not found")
            s["selectedVideoId"] = video_id
            s["updatedAt"] = _now()
            return store.save(state)
    raise FileNotFoundError("shot not found")


def patch_take(store: ProjectStore, project_id: str, shot_id: str, video_id: str, fields: dict) -> dict:
    state = store.load(project_id)
    if not state:
        raise FileNotFoundError("project not found")
    for s in state.get("shots") or []:
        if s["id"] != shot_id:
            continue
        for v in s.get("videos") or []:
            if v["id"] == video_id:
                if "rating" in fields:
                    v["rating"] = fields["rating"]
                if "note" in fields:
                    v["note"] = fields["note"]
                store.save(state)
                return v
    raise FileNotFoundError("video not found")


def ensure_edit_draft(store: ProjectStore, project_id: str, episode_id: str) -> dict:
    state = store.load(project_id)
    if not state:
        raise FileNotFoundError("project not found")
    edit = next((e for e in state.get("edits") or [] if e.get("episodeId") == episode_id and not e.get("deletedAt")), None)
    if edit:
        return edit
    shots = sorted(
        [s for s in state.get("shots") or [] if s.get("episodeId") == episode_id and not s.get("deletedAt") and s.get("selectedVideoId")],
        key=lambda s: s["shotOrder"],
    )
    clips = []
    for s in shots:
        vid = next((v for v in s.get("videos") or [] if v["id"] == s["selectedVideoId"]), None)
        dur = float((vid or {}).get("duration") or s.get("duration") or 5)
        clips.append(
            {
                "id": new_id("clip_"),
                "shotId": s["id"],
                "enabled": True,
                "start": 0,
                "end": dur,
            }
        )
    edit = {
        "id": new_id("edit_"),
        "projectId": project_id,
        "episodeId": episode_id,
        "clips": clips,
        "outputPath": None,
        "updatedAt": _now(),
    }
    state.setdefault("edits", []).append(edit)
    store.save(state)
    return edit


def save_edit(store: ProjectStore, project_id: str, episode_id: str, clips: list[dict]) -> dict:
    state = store.load(project_id)
    if not state:
        raise FileNotFoundError("project not found")
    edit = next((e for e in state.get("edits") or [] if e.get("episodeId") == episode_id), None)
    if not edit:
        edit = {
            "id": new_id("edit_"),
            "projectId": project_id,
            "episodeId": episode_id,
            "clips": [],
            "outputPath": None,
            "updatedAt": _now(),
        }
        state.setdefault("edits", []).append(edit)
    edit["clips"] = clips
    edit["outputPath"] = None
    edit["updatedAt"] = _now()
    store.save(state)
    return edit


def export_edit_mp4(store: ProjectStore, project_id: str, episode_id: str) -> dict:
    from export_mp4 import ffmpeg_available

    if not ffmpeg_available():
        raise RuntimeError("未检测到 FFmpeg")
    state = store.load(project_id)
    if not state:
        raise FileNotFoundError("project not found")
    edit = ensure_edit_draft(store, project_id, episode_id)
    state = store.load(project_id)
    edit = next(e for e in state["edits"] if e["id"] == edit["id"])
    project = store._dir(project_id)
    shots_by_id = {s["id"]: s for s in state.get("shots") or []}
    enabled = [c for c in edit.get("clips") or [] if c.get("enabled")]
    if not enabled:
        raise RuntimeError("至少需要启用一个剪辑片段")

    import subprocess
    import tempfile
    import time as _time

    ratio = state["project"].get("ratio") or "9:16"
    w, h = (720, 1280) if ratio == "9:16" else ((1280, 720) if ratio == "16:9" else (1080, 1080))
    export_rel = f"media/exports/{episode_id}-{int(_time.time())}.mp4"
    out_path = project / export_rel

    with tempfile.TemporaryDirectory(prefix="om-edit-") as tmp:
        tmp_path = Path(tmp)
        parts = []
        for i, clip in enumerate(enabled):
            shot = shots_by_id.get(clip["shotId"])
            if not shot:
                raise RuntimeError(f"镜头缺失: {clip['shotId']}")
            vid = next((v for v in shot.get("videos") or [] if v["id"] == shot.get("selectedVideoId")), None)
            if not vid or not vid.get("path"):
                raise RuntimeError(f"镜头 {shot.get('shotOrder')} 缺少可用视频")
            src = project / vid["path"]
            if not src.is_file():
                raise RuntimeError(f"视频文件不存在: {vid['path']}")
            start = float(clip.get("start") or 0)
            end = float(clip.get("end") or vid.get("duration") or shot.get("duration") or 5)
            dur = max(0.1, end - start)
            part = tmp_path / f"{i:03d}.mp4"
            cmd = [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-ss",
                str(start),
                "-i",
                str(src),
                "-t",
                str(dur),
                "-vf",
                f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "20",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                "-movflags",
                "+faststart",
                str(part),
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True)
            if proc.returncode != 0:
                raise RuntimeError(proc.stderr.strip() or "ffmpeg trim failed")
            parts.append(part)
        list_file = tmp_path / "files.txt"
        list_file.write_text("\n".join(f"file '{p.as_posix()}'" for p in parts) + "\n", encoding="utf-8")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        proc = subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(list_file),
                "-c",
                "copy",
                "-movflags",
                "+faststart",
                str(out_path),
            ],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.strip() or "ffmpeg concat failed")

    edit["outputPath"] = export_rel
    edit["updatedAt"] = _now()
    store.save(state)
    return {
        "ok": True,
        "path": export_rel,
        "url": f"/api/media/{project_id}/{export_rel}",
        "bytes": out_path.stat().st_size,
        "clips": len(enabled),
    }


def patch_project(store: ProjectStore, project_id: str, fields: dict) -> dict:
    state = store.load(project_id)
    if not state:
        raise FileNotFoundError("project not found")
    p = state["project"]
    for key, src in [
        ("title", "title"),
        ("brief", "brief"),
        ("synopsis", "synopsis"),
        ("genre", "genre"),
        ("visualStyle", "visualStyle"),
        ("ratio", "ratio"),
        ("plannedEpisodes", "plannedEpisodes"),
    ]:
        if src in fields:
            p[key] = fields[src]
    return store.save(state)
