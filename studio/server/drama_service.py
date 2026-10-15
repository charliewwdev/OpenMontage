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

    def _as_dict(item: Any) -> dict | None:
        return item if isinstance(item, dict) else None

    def _ep_list(value: Any) -> list:
        if isinstance(value, list):
            return [x for x in value if isinstance(x, (int, float, str))]
        if isinstance(value, (int, float, str)) and str(value).strip():
            try:
                return [int(value)]
            except Exception:
                return []
        return []

    for ch in generated.get("characters") or []:
        ch = _as_dict(ch)
        if not ch:
            continue
        raw_looks = ch.get("looks")
        looks = [x for x in (raw_looks or []) if isinstance(x, dict)]
        if not looks:
            looks = [
                {
                    "name": "默认形象",
                    "description": ch.get("description") or ch.get("introduction") or "",
                    "episodes": [],
                }
            ]
        for look in looks:
            upsert_entity(
                "character",
                ch.get("name") or "角色",
                look.get("name") or "默认形象",
                look.get("description") or "",
                _ep_list(look.get("episodes")),
                metadata={
                    "role": ch.get("role"),
                    "gender": ch.get("gender"),
                    "introduction": ch.get("introduction"),
                    "voiceDescription": ch.get("voiceDescription"),
                },
            )
    for sc in generated.get("scenes") or []:
        sc = _as_dict(sc)
        if not sc:
            continue
        upsert_entity(
            "scene",
            sc.get("name") or "场景",
            "",
            sc.get("description") or "",
            _ep_list(sc.get("episodes")),
        )
    for prop in generated.get("props") or []:
        prop = _as_dict(prop)
        if not prop:
            continue
        upsert_entity(
            "prop",
            prop.get("name") or "道具",
            "",
            prop.get("description") or "",
            _ep_list(prop.get("episodes")),
            category=prop.get("category") or "item",
        )

    state["entities"] = entities
    return state


def generate_script(store: ProjectStore, project_id: str, episode_count: int, planned: int | None = None) -> dict:
    """Generate script episodes.

    Large series (4–10 eps) are created in batches of ≤3 to avoid truncated / invalid JSON
    from a single huge LLM response.
    """
    from providers.deepseek import chat_json

    state = store.load(project_id)
    if not state:
        raise FileNotFoundError("project not found")
    count = max(1, min(10, int(episode_count)))
    skill = load_skill("drama-script")
    p = state["project"]
    batch = 3 if count > 3 else count
    user = json.dumps(
        {
            "action": "generate",
            "episodeCount": batch,
            "plannedEpisodes": planned or count,
            "title": p["title"],
            "brief": p.get("brief") or "",
            "genre": p.get("genre"),
            "visualStyle": p.get("visualStyle"),
            "visualStylePrompt": resolve_style_prompt(p.get("visualStyle") or ""),
            "ratio": p.get("ratio"),
            "seriesTotal": count,
            "note": f"先写出第 1–{batch} 集，后续集将续写；保持人物与伏笔可贯穿全 {count} 集。",
        },
        ensure_ascii=False,
    )
    data = chat_json(
        system=skill + "\n\n只输出一个完整 JSON 对象，禁止 Markdown/注释/尾随逗号。",
        user=user,
        temperature=0.45,
        max_tokens=16000,
        retries=4,
    )
    state = _apply_generated_script(state, data, replace_episodes=True)
    if planned or count:
        state["project"]["plannedEpisodes"] = int(planned or count)
    store.save(state)

    # Continue in chunks until we reach the requested episode count.
    while True:
        state = store.load(project_id) or state
        have = len([e for e in (state.get("episodes") or []) if not e.get("deletedAt")])
        if have >= count:
            break
        chunk = min(3, count - have)
        as_finale = have + chunk >= count
        continue_script(
            store,
            project_id,
            chunk,
            instruction=f"续写第 {have + 1}–{have + chunk} 集，承接已有剧情与人物，共计划 {count} 集。",
            as_finale=as_finale,
        )
        state = store.load(project_id) or state
        now = len([e for e in (state.get("episodes") or []) if not e.get("deletedAt")])
        if now <= have:
            raise RuntimeError(
                f"剧本续写未增加集数（仍为 {have}/{count}）。请重试或减少单次集数。"
            )
    state = store.load(project_id) or state
    return state


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
    data = chat_json(
        system=skill + "\n\n续写后续集，不要改写已有集。只输出一个完整 JSON 对象，禁止 Markdown/注释/尾随逗号。",
        user=user,
        temperature=0.45,
        max_tokens=16000,
        retries=4,
    )
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
            content_changed = "content" in fields and fields["content"] != e.get("content")
            if "title" in fields:
                e["title"] = fields["title"]
            if "content" in fields:
                e["content"] = fields["content"]
            # Single-episode confirm/unconfirm (UI 「定稿」 button).
            if "status" in fields and fields["status"] in {"draft", "confirmed"}:
                if fields["status"] == "draft":
                    has_shots = any(
                        s.get("episodeId") == episode_id and not s.get("deletedAt")
                        for s in state.get("shots") or []
                    )
                    if has_shots:
                        raise RuntimeError(f"第{e['episodeNumber']}集已有分镜，无法取消定稿")
                e["status"] = fields["status"]
            e["updatedAt"] = _now()
            if content_changed:
                _mark_shots_stale(
                    state,
                    episode_id=episode_id,
                    reason="本集剧本已修改，已有成片镜头标记为过期，请核对分镜后重生成",
                )
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
                desc_changed = "description" in payload and payload["description"] != e.get("description")
                name_changed = "name" in payload and payload["name"] != e.get("name")
                for key in ("name", "variant", "description", "category"):
                    if key in payload:
                        e[key] = payload[key]
                if desc_changed or name_changed:
                    _mark_shots_stale(
                        state,
                        entity_id=entity_id,
                        reason=f"素材「{e.get('name') or entity_id}」档案已改，引用镜头建议重生成",
                    )
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


def generate_entity_image(
    store: ProjectStore,
    project_id: str,
    entity_id: str,
    *,
    three_view: bool = False,
    redraw: bool = False,
    force_illustration: bool = False,
) -> dict:
    from providers.media import generate_image

    state = store.load(project_id)
    if not state:
        raise FileNotFoundError("project not found")
    ent = next((e for e in state.get("entities") or [] if e["id"] == entity_id and not e.get("deletedAt")), None)
    if not ent:
        raise FileNotFoundError("entity not found")
    style = resolve_style_prompt(state["project"].get("visualStyle") or "")
    # Illustration only when explicitly requested (avoids flat cartoon locks for short drama).
    use_illustration = bool(force_illustration)
    if use_illustration and "插画" not in style and "动漫" not in style and "二次元" not in style and "写实" not in style:
        style = f"{style}。国漫插画风格，清晰线条与色块，非写实真人摄影"
    ratio = state["project"].get("ratio") or "9:16"
    name = ent["name"]
    variant = ent.get("variant") or ""
    desc = ent.get("description") or ""
    if ent["kind"] == "character":
        prompt = f"{style}。华语竖屏短剧角色定妆：单人特写，仅 {name} {variant}，不要第二个人物。{desc}。"
        if three_view:
            prompt += "三视图：正面、侧面、背面，同一人物同一服装，纯色背景。"
        else:
            prompt += (
                "半身或全身定妆，清晰五官与发型层次，服装面料与配饰细节完整，"
                "电影级柔光与轮廓光，浅景深，剧照质感，居中构图。"
            )
        if use_illustration:
            prompt += "虚构角色插画，避免真人照片质感。"
        else:
            prompt += (
                "虚构短剧角色，影视剧照质感与妆造完成度，"
                "不是简笔卡通、不是证件照、不是AI塑料脸。"
            )
    elif ent["kind"] == "scene":
        prompt = (
            f"{style}。短剧场景空镜：{name}。{desc}。"
            "制作设计完整：空间层次、道具陈设、材质与光影氛围，电影级构图，画面中不要出现人物。"
        )
    else:
        prompt = f"{style}。关键道具特写：{name}。{desc}。产品级质感，材质与反光真实。"
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
    store.persist_media(project_id, rel)
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
    # Prefer character still as project library cover
    proj = state.get("project") or {}
    if ent.get("kind") == "character" or not proj.get("coverPath"):
        proj["coverPath"] = rel
        proj["updatedAt"] = _now()
        state["project"] = proj
    _mark_shots_stale(
        state,
        entity_id=entity_id,
        reason=f"参考素材「{ent.get('name') or entity_id}」图片已更新，引用该素材的镜头建议重生成",
    )
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
            hit = next((i for i in (e.get("images") or []) if i.get("id") == image_id), None)
            if hit and hit.get("path") and (e.get("kind") == "character" or not (state.get("project") or {}).get("coverPath")):
                state.setdefault("project", {})["coverPath"] = hit["path"]
                state["project"]["updatedAt"] = _now()
            _mark_shots_stale(
                state,
                entity_id=entity_id,
                reason=f"参考素材「{e.get('name') or entity_id}」切换了定稿图，引用镜头建议重生成",
            )
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
    store.write_media(project_id, rel, data)
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
    _mark_shots_stale(
        state,
        entity_id=entity_id,
        reason=f"参考素材「{ent.get('name') or entity_id}」图片已更新，引用该素材的镜头建议重生成",
    )
    store.save(state)
    return version


_JUNK_TRIGGER = re.compile(
    r"(8[Kk]|大师级|体积光|超清|best\s*quality|masterpiece|ultra\s*detailed)",
    re.I,
)


def _spoken_line(dialogue: str) -> tuple[str, str]:
    """Return (speaker, spoken) from `角色：台词` or bare text."""
    raw = (dialogue or "").strip()
    if not raw:
        return "", ""
    m = re.match(r"^([^：:\n]{1,24})\s*[：:]\s*(.+)$", raw)
    if m:
        sp = m.group(1).strip()
        tx = re.sub(r'^[「"“]|[」"”]$', "", m.group(2).strip())
        return sp, tx
    return "", re.sub(r'^[「"“]|[」"”]$', "", raw)


def _compose_short_drama_prompt(
    *,
    style_hint: str = "",
    scene_name: str = "",
    action: str = "",
    dialogue: str = "",
    characters: list | None = None,
    shot_order: int = 1,
    duration: int = 4,
) -> str:
    """Build one SceneMixer-style beat: shot mark, who/where, one action, lip-sync, close lips."""
    chars = [str(c).strip() for c in (characters or []) if str(c).strip()]
    lead = f"@{chars[0]}" if chars else "@主角"
    other = f"@{chars[1]}" if len(chars) > 1 else ""
    scene = f"@{scene_name}" if scene_name else "场景中"
    act = (action or "完成一个明确可见动作").strip()
    speaker, spoken = _spoken_line(dialogue)
    dur = max(3, min(12, int(duration or 4)))
    head = f"【分镜{max(1, int(shot_order))}】{dur}s: "
    if shot_order and int(shot_order) > 1:
        head += f"承接分镜{int(shot_order) - 1}。"
    else:
        head += "起始："
    body = (
        f"中近景固定。画面主体为 {lead}"
        + (f"，{other} 在其对面或画面另一侧仅见肩线" if other else "，画面内仅此人")
        + f"。在 {scene}：{act}。"
    )
    if spoken:
        who_say = f"@{speaker}" if speaker else lead
        line = spoken.rstrip("。.!！?？")
        body += (
            f"{who_say}（语气克制、字字咬实）：{line}。"
            f"说完最后一个字闭唇，跟一个微动作。"
            + (f"{other} 闭唇、唇部未动。" if other and (not speaker or speaker != chars[1]) else "")
        )
    else:
        body += "无对白。"
    body += "光源写清方向与种类。环境音自然。保持人物样貌与服装与参考图一致，无字幕，无解说旁白。"
    prompt = head + body
    if style_hint and style_hint[:10] not in prompt:
        prompt = f"{style_hint.strip()}。{prompt}"
    return _JUNK_TRIGGER.sub("", prompt).strip()


def _normalize_short_drama_prompt(prompt: str, *, dialogue: str = "") -> str:
    """Strip junk triggers; ensure close-lips + no narration; at most one dialogue line."""
    text = _JUNK_TRIGGER.sub("", (prompt or "").strip())
    speaker, spoken = _spoken_line(dialogue)
    if spoken and spoken not in text and f"「{spoken}」" not in text and spoken not in text:
        who = f"@{speaker}" if speaker else "角色"
        text = f"{text.rstrip('。')}。{who}（语气克制）：{spoken}。说完最后一个字闭唇。"
    if spoken and "闭唇" not in text:
        text = f"{text.rstrip('。')}。说完最后一个字闭唇。"
    if "无解说旁白" not in text:
        text = f"{text.rstrip('。')}。保持人物样貌与服装与参考图一致，无字幕，无解说旁白"
    return text.strip("。 ")


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


# SceneMixer-aligned episode density: 12–30 shots, 3–6 minutes.
_STORYBOARD_SHOT_MIN = 12
_STORYBOARD_SHOT_MAX = 30
_STORYBOARD_DUR_MIN = 180
_STORYBOARD_DUR_MAX = 360


def _materialize_storyboard_shots(
    *,
    project_id: str,
    episode_id: str,
    raw_shots: list,
    available: list[dict],
    style_hint: str,
    start_order: int = 1,
) -> list[dict]:
    """Turn LLM shot objects into store rows (SceneMixer density: 5–12s each)."""
    ts = _now()
    shots: list[dict] = []
    for i, sh in enumerate(raw_shots or [], start_order):
        if not isinstance(sh, dict):
            continue
        prompt = (sh.get("prompt") or "").strip()
        action = (sh.get("action") or "").strip()
        dialogue = (sh.get("dialogue") or "").strip()
        scene_name = (sh.get("sceneName") or "").strip()
        shot_order = int(sh.get("shotOrder") or i)
        # Prefer 6–12s beats so 12–30 shots land in the 3–6 min band.
        default_dur = 8 if dialogue else 6
        duration = max(5, min(12, int(sh.get("duration") or default_dur)))
        if len(prompt) < 24 or prompt.lower() in {"subtle performance, cinematic", "cinematic", "performance"}:
            prompt = _compose_short_drama_prompt(
                style_hint=style_hint,
                scene_name=scene_name,
                action=action,
                dialogue=dialogue,
                characters=sh.get("characters") or [],
                shot_order=shot_order,
                duration=duration,
            )
        else:
            prompt = _normalize_short_drama_prompt(prompt, dialogue=dialogue)
            if f"【分镜{shot_order}】" not in prompt and "【分镜" not in prompt[:12]:
                prompt = f"【分镜{shot_order}】{duration}s: {prompt}"
        refs = _parse_ref_tags(prompt, available)
        shots.append(
            {
                "id": new_id("sh_"),
                "projectId": project_id,
                "episodeId": episode_id,
                "shotOrder": shot_order,
                "prompt": prompt,
                "duration": duration,
                "referenceEntityIds": refs,
                "status": "pending",
                "providerTaskId": None,
                "error": None,
                "selectedVideoId": None,
                "videos": [],
                "sceneName": scene_name,
                "action": action,
                "dialogue": dialogue,
                "createdAt": ts,
                "updatedAt": ts,
            }
        )
    return shots


def _top_up_shot_durations(shots: list[dict], need_sec: int) -> None:
    """Nudge durations up (cap 12) so episode total reaches the 3-minute floor."""
    if need_sec <= 0 or not shots:
        return
    left = need_sec
    guard = 0
    while left > 0 and guard < len(shots) * 12:
        guard += 1
        progressed = False
        for s in shots:
            if left <= 0:
                break
            if int(s.get("duration") or 0) >= 12:
                continue
            s["duration"] = int(s.get("duration") or 5) + 1
            left -= 1
            progressed = True
            # Keep prompt header in sync when present.
            prompt = str(s.get("prompt") or "")
            order = int(s.get("shotOrder") or 0)
            dur = int(s["duration"])
            if order and f"【分镜{order}】" in prompt:
                s["prompt"] = re.sub(
                    rf"【分镜{order}】\d+s:",
                    f"【分镜{order}】{dur}s:",
                    prompt,
                    count=1,
                )
        if not progressed:
            break


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
    style_hint = resolve_style_prompt(p.get("visualStyle") or "")
    assets = [
        {
            "kind": e["kind"],
            "name": e["name"],
            "variant": e.get("variant"),
            "tag": f"@{e['name']}" + (f"-{e['variant']}" if e.get("variant") else ""),
            "hasImage": bool(e.get("selectedImageId")),
        }
        for e in available
    ]
    base_ctx = {
        "episodeNumber": ep["episodeNumber"],
        "episodeTitle": ep["title"],
        "content": ep["content"],
        "ratio": p.get("ratio"),
        "visualStyle": p.get("visualStyle"),
        "visualStylePrompt": style_hint,
        "assets": assets,
        "shotCountMin": _STORYBOARD_SHOT_MIN,
        "shotCountMax": _STORYBOARD_SHOT_MAX,
        "shotCountTarget": 20,
        "episodeDurationSecMin": _STORYBOARD_DUR_MIN,
        "episodeDurationSecMax": _STORYBOARD_DUR_MAX,
        "episodeDurationSecTarget": 240,
        "note": (
            "必须输出 12–30 个分镜，各镜 duration 之和 180–360 秒（目标约 4 分钟 / 20 镜）。"
            "对齐 SceneMixer：一镜一节拍，对白与反应拆镜，写清机位/承接/闭唇/光源。"
        ),
    }
    system = skill + "\n\n只输出一个完整 JSON 对象（键 shots 为数组）。禁止 Markdown、注释与尾随逗号。"
    data = chat_json(
        system=system,
        user=json.dumps({**base_ctx, "action": "generate"}, ensure_ascii=False),
        temperature=0.35,
        max_tokens=24000,
        retries=4,
    )
    shots = _materialize_storyboard_shots(
        project_id=project_id,
        episode_id=episode_id,
        raw_shots=data.get("shots") or [],
        available=available,
        style_hint=style_hint,
        start_order=1,
    )

    # Continue in batches until density targets are met (LLM often returns sample-sized boards).
    guard = 0
    while guard < 4 and len(shots) < _STORYBOARD_SHOT_MAX:
        total_dur = sum(int(s.get("duration") or 0) for s in shots)
        if len(shots) >= _STORYBOARD_SHOT_MIN and total_dur >= _STORYBOARD_DUR_MIN:
            break
        need = min(8, _STORYBOARD_SHOT_MAX - len(shots))
        if need <= 0:
            break
        guard += 1
        cont_user = {
            **base_ctx,
            "action": "continue",
            "startShotOrder": len(shots) + 1,
            "addShotCount": need,
            "haveShotCount": len(shots),
            "haveDurationSec": total_dur,
            "remainingDurationSecMin": max(0, _STORYBOARD_DUR_MIN - total_dur),
            "previousShots": [
                {
                    "shotOrder": s.get("shotOrder"),
                    "sceneName": s.get("sceneName"),
                    "action": (s.get("action") or "")[:120],
                    "dialogue": (s.get("dialogue") or "")[:80],
                    "duration": s.get("duration"),
                }
                for s in shots[-6:]
            ],
            "note": (
                f"已有 {len(shots)} 镜 / {total_dur}s，请续写接下来约 {need} 镜，"
                f"承接上一镜轴线与剧情，补足至整集至少 {_STORYBOARD_SHOT_MIN} 镜且总时长≥{_STORYBOARD_DUR_MIN}s。"
            ),
        }
        more_data = chat_json(
            system=system + "\n续写后续分镜，不要重复已有 shotOrder。",
            user=json.dumps(cont_user, ensure_ascii=False),
            temperature=0.35,
            max_tokens=16000,
            retries=3,
        )
        more = _materialize_storyboard_shots(
            project_id=project_id,
            episode_id=episode_id,
            raw_shots=more_data.get("shots") or [],
            available=available,
            style_hint=style_hint,
            start_order=len(shots) + 1,
        )
        if not more:
            break
        # Re-number contiguously in case the model drifted.
        for idx, s in enumerate(more, len(shots) + 1):
            s["shotOrder"] = idx
        shots.extend(more)

    if len(shots) > _STORYBOARD_SHOT_MAX:
        shots = shots[:_STORYBOARD_SHOT_MAX]

    total_dur = sum(int(s.get("duration") or 0) for s in shots)
    if total_dur < _STORYBOARD_DUR_MIN:
        _top_up_shot_durations(shots, _STORYBOARD_DUR_MIN - total_dur)
        total_dur = sum(int(s.get("duration") or 0) for s in shots)
    # Prefer denser early/mid drama; drop trailing filler only if far over the 6-min ceiling.
    while (
        len(shots) > _STORYBOARD_SHOT_MIN
        and sum(int(s.get("duration") or 0) for s in shots) > _STORYBOARD_DUR_MAX
    ):
        shots.pop()

    if len(shots) < _STORYBOARD_SHOT_MIN:
        raise RuntimeError(
            f"分镜过少（{len(shots)} 镜），整集需要对齐 12–30 镜 / 3–6 分钟。请重试拆分或加厚剧本场次。"
        )

    state["shots"].extend(shots)
    store.save(state)
    return shots


def _mark_shots_stale(state: dict, *, entity_id: str | None = None, episode_id: str | None = None, reason: str = "") -> int:
    """Flag success shots that depend on changed upstream assets/script."""
    n = 0
    for s in state.get("shots") or []:
        if s.get("deletedAt"):
            continue
        if episode_id and s.get("episodeId") != episode_id:
            continue
        if entity_id and entity_id not in (s.get("referenceEntityIds") or []):
            continue
        if s.get("status") not in ("success", "stale"):
            continue
        if not (s.get("videos") or s.get("selectedVideoId")):
            continue
        s["status"] = "stale"
        s["staleReason"] = reason or "上游素材或提示词已变更，建议重新生成视频"
        s["updatedAt"] = _now()
        n += 1
    return n


def patch_shot(store: ProjectStore, project_id: str, shot_id: str, fields: dict) -> dict:
    state = store.load(project_id)
    if not state:
        raise FileNotFoundError("project not found")
    for s in state.get("shots") or []:
        if s["id"] == shot_id and not s.get("deletedAt"):
            if s.get("status") == "generating":
                raise RuntimeError("生成中不可编辑")
            changed_creative = False
            for key in ("prompt", "duration", "referenceEntityIds", "dialogue", "action", "sceneName"):
                if key in fields and fields[key] != s.get(key):
                    if key in ("prompt", "dialogue", "referenceEntityIds", "action"):
                        changed_creative = True
                    s[key] = fields[key]
            if "duration" in fields:
                s["duration"] = max(4, min(15, int(fields["duration"])))
            if changed_creative and s.get("status") == "success" and (s.get("videos") or s.get("selectedVideoId")):
                s["status"] = "stale"
                s["staleReason"] = "镜头提示词/对白/参考已修改，成片可能过期，请重新生成"
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


def cancel_shot_video(store: ProjectStore, project_id: str, shot_id: str) -> dict:
    """Reset a stuck/in-flight generating shot so the user can retry."""
    state = store.load(project_id)
    if not state:
        raise FileNotFoundError("project not found")
    shot = next((s for s in state.get("shots") or [] if s["id"] == shot_id and not s.get("deletedAt")), None)
    if not shot:
        raise FileNotFoundError("shot not found")
    if shot.get("status") != "generating":
        return shot
    shot["status"] = "pending" if not shot.get("selectedVideoId") else "success"
    shot["error"] = None
    shot["providerTaskId"] = None
    shot["updatedAt"] = _now()
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
    from media_qa import assert_media_ok

    dest.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=300) as resp:
        dest.write_bytes(resp.read())
    # Reject empty / non-media payloads so failed provider downloads never stick.
    assert_media_ok(dest, unlink_on_fail=True)


def start_shot_video(
    store: ProjectStore,
    project_id: str,
    shot_id: str,
    *,
    model: str,
    resolution: str,
    skip_refs: bool = False,
) -> dict:
    from providers.media import video_backend

    state = store.load(project_id)
    if not state:
        raise FileNotFoundError("project not found")
    shot = next((s for s in state.get("shots") or [] if s["id"] == shot_id and not s.get("deletedAt")), None)
    if not shot:
        raise FileNotFoundError("shot not found")
    if shot.get("status") == "generating":
        # Allow retry if the poll thread died / hung (stuck > 20 minutes).
        try:
            from datetime import datetime, timezone

            updated = shot.get("updatedAt") or shot.get("createdAt") or ""
            age_s = 0
            if updated:
                ts = datetime.fromisoformat(str(updated).replace("Z", "+00:00"))
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                age_s = (datetime.now(timezone.utc) - ts).total_seconds()
            if age_s < 20 * 60:
                raise RuntimeError("该镜头正在生成")
            shot["status"] = "pending"
            shot["error"] = "上次生成超时，已自动重置"
            shot["providerTaskId"] = None
        except RuntimeError:
            raise
        except Exception:
            raise RuntimeError("该镜头正在生成")

    entities = {e["id"]: e for e in state.get("entities") or [] if not e.get("deletedAt")}
    base_prompt = _normalize_short_drama_prompt(
        (shot.get("prompt") or "").strip(),
        dialogue=str(shot.get("dialogue") or ""),
    )
    ratio = state["project"].get("ratio") or "9:16"
    duration = int(shot.get("duration") or 5)

    # Prefer first existing entity reference image for I2V (ComfyUI / Seedance).
    ref_paths: list[Path] = []
    content: list[dict] = [{"type": "text", "text": base_prompt}]
    import base64

    if not skip_refs:
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
            ref_paths.append(path)
            b64 = base64.b64encode(path.read_bytes()).decode("ascii")
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{b64}"},
                    "role": "reference_image",
                }
            )

    backend = video_backend()
    if backend == "none":
        raise RuntimeError(
            "未配置出片后端：请填写火山 Seedance Key，或配置智川云 ComfyUI（MiniMax H3）地址。"
        )

    shot["status"] = "generating"
    shot["providerTaskId"] = None
    shot["error"] = None
    shot["updatedAt"] = _now()
    shot["_pendingModel"] = model
    shot["_pendingResolution"] = resolution
    shot["_videoBackend"] = backend
    store.save(state)

    if backend == "comfyui":
        def _run_comfy() -> None:
            from providers.media import generate_video_file
            from media_qa import assert_media_ok

            try:
                vid_id = new_id("vid_")
                rel = f"media/videos/{vid_id}.mp4"
                dest = store._dir(project_id) / rel
                result = generate_video_file(
                    prompt=base_prompt,
                    ratio=ratio,
                    duration=duration,
                    out_path=dest,
                    reference_path=ref_paths[0] if ref_paths else None,
                    resolution=resolution,
                )
                assert_media_ok(dest, unlink_on_fail=True)
                if dest.is_file():
                    store.persist_media(project_id, rel)
                st = store.load(project_id)
                sh = next((x for x in (st.get("shots") or []) if x["id"] == shot_id), None)
                if not sh:
                    return
                version = {
                    "id": vid_id,
                    "shotId": shot_id,
                    "path": rel if dest.is_file() else None,
                    "providerTaskId": None,
                    "model": result.get("model") or "minimax-h3",
                    "backend": "comfyui",
                    "duration": float(result.get("duration") or duration),
                    "resolution": result.get("resolution") or resolution,
                    "prompt": sh.get("prompt") or "",
                    "rating": None,
                    "note": "",
                    "createdAt": _now(),
                }
                sh.setdefault("videos", []).append(version)
                sh["selectedVideoId"] = vid_id
                sh["status"] = "success"
                sh["staleReason"] = None
                sh["providerTaskId"] = None
                sh["error"] = None
                sh["updatedAt"] = _now()
                store.save(st)
            except Exception as exc:
                st = store.load(project_id)
                sh = next((x for x in (st.get("shots") or []) if x["id"] == shot_id), None)
                if sh:
                    sh["status"] = "failed"
                    sh["error"] = str(exc)
                    sh["updatedAt"] = _now()
                    store.save(st)

        threading.Thread(target=_run_comfy, name=f"comfy-video-{shot_id}", daemon=True).start()
        return shot

    # Seedance async task + poll
    from providers.seedance import create_task

    task_id = create_task(
        model=model,
        content=content,
        ratio=ratio,
        resolution=resolution,
        duration=duration,
    )
    shot["providerTaskId"] = task_id
    shot["updatedAt"] = _now()
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
                        if dest.is_file():
                            store.persist_media(project_id, rel)
                    version = {
                        "id": vid_id,
                        "shotId": shot_id,
                        "path": rel if dest.is_file() else None,
                        "providerTaskId": task_id,
                        "model": model,
                        "backend": "seedance",
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
                    sh["staleReason"] = None
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


def sync_shot_video(store: ProjectStore, project_id: str, shot_id: str) -> dict:
    """Re-fetch a Seedance task and download video if the local path is missing."""
    from providers.seedance import query_task

    state = store.load(project_id)
    if not state:
        raise FileNotFoundError("project not found")
    shot = next((s for s in state.get("shots") or [] if s["id"] == shot_id and not s.get("deletedAt")), None)
    if not shot:
        raise FileNotFoundError("shot not found")
    task_id = shot.get("providerTaskId")
    if not task_id:
        raise RuntimeError("该镜头没有 providerTaskId，无法同步")

    result = query_task(task_id)
    status = result.get("status")
    if status not in {"succeeded", "success"}:
        raise RuntimeError(f"任务未成功：{status or 'unknown'}")
    video_url = result.get("videoUrl")
    if not video_url:
        raise RuntimeError("任务成功但未返回 video_url")

    existing = None
    if shot.get("selectedVideoId"):
        existing = next((v for v in shot.get("videos") or [] if v["id"] == shot["selectedVideoId"]), None)
    if existing and existing.get("path"):
        dest = store._dir(project_id) / existing["path"]
        if dest.is_file():
            return shot

    vid_id = (existing or {}).get("id") or new_id("vid_")
    rel = (existing or {}).get("path") or f"media/videos/{vid_id}.mp4"
    dest = store._dir(project_id) / rel
    _download(video_url, dest)
    if not dest.is_file():
        raise RuntimeError("视频下载失败")
    store.persist_media(project_id, rel)

    version = existing or {
        "id": vid_id,
        "shotId": shot_id,
        "providerTaskId": task_id,
        "model": shot.get("_pendingModel") or "",
        "duration": float(result.get("duration") or shot.get("duration") or 5),
        "resolution": result.get("resolution") or shot.get("_pendingResolution") or "",
        "prompt": shot.get("prompt") or "",
        "rating": None,
        "note": "",
        "createdAt": _now(),
    }
    version["path"] = rel
    version["providerTaskId"] = task_id
    version["duration"] = float(result.get("duration") or version.get("duration") or 5)
    if existing:
        for i, v in enumerate(shot.get("videos") or []):
            if v["id"] == existing["id"]:
                shot["videos"][i] = version
                break
    else:
        shot.setdefault("videos", []).append(version)
    shot["selectedVideoId"] = version["id"]
    shot["status"] = "success"
    shot["staleReason"] = None
    shot["error"] = None
    shot["updatedAt"] = _now()
    store.save(state)
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
    prev = edit.get("clips") or []
    edit["clips"] = clips
    # Only invalidate export when the timeline actually changed.
    if json.dumps(prev, sort_keys=True, ensure_ascii=False) != json.dumps(clips, sort_keys=True, ensure_ascii=False):
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
    # Prefer 1080p vertical export so 720p Seedance sources keep short-drama sharpness.
    w, h = (1080, 1920) if ratio == "9:16" else ((1920, 1080) if ratio == "16:9" else (1080, 1080))
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
                "medium",
                "-crf",
                "18",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
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

        # Short drama default: keep Seedance native dialogue track, only underlay soft BGM.
        # Optional TTS dub replaces native audio only when kind=dialogue was explicitly generated.
        audio_rel = ""
        bgm_rel = ""
        for item in state.get("audios") or []:
            if item.get("episodeId") != episode_id:
                continue
            if item.get("kind") == "bgm" and item.get("path"):
                bgm_rel = item["path"]
            elif item.get("kind") == "dialogue" and item.get("path"):
                audio_rel = item["path"]
        has_shot_dialogue = any(
            str(shots_by_id.get(c.get("shotId"), {}).get("dialogue") or "").strip() for c in enabled
        )
        # Prefer native Seedance lip-sync when shots already carry dialogue in-prompt.
        use_tts_dub = bool(audio_rel) and not has_shot_dialogue
        if use_tts_dub or bgm_rel or has_shot_dialogue:
            audio_src = project / audio_rel if audio_rel and use_tts_dub else None
            bgm_src = project / bgm_rel if bgm_rel else None
            mixed_rel = export_rel.replace(".mp4", "-voiced.mp4")
            mixed_path = project / mixed_rel
            try:
                from audio_tts import generate_bgm_mp3, mix_video_with_audio

                if not (bgm_src and bgm_src.is_file()):
                    total_dur = sum(
                        max(0.1, float(c.get("end") or 5) - float(c.get("start") or 0)) for c in enabled
                    )
                    bgm_auto = project / f"media/audio/{episode_id}-bgm.mp3"
                    generate_bgm_mp3(bgm_auto, duration_sec=max(20.0, total_dur + 4), mood="drama")
                    store.persist_media(project_id, f"media/audio/{episode_id}-bgm.mp3")
                    bgm_src = bgm_auto
                if audio_src and audio_src.is_file():
                    mix_video_with_audio(
                        out_path,
                        audio_src,
                        mixed_path,
                        bgm_path=bgm_src if bgm_src and bgm_src.is_file() else None,
                        dialogue_volume=1.0,
                        bgm_volume=0.12,
                    )
                elif bgm_src and bgm_src.is_file():
                    # BGM under Seedance native track (dialogue already in clip)
                    mix_video_with_audio(
                        out_path,
                        bgm_src,
                        mixed_path,
                        bgm_path=None,
                        dialogue_volume=0.12,
                        video_audio_volume=1.0,
                        keep_video_audio=True,
                    )
                if mixed_path.is_file():
                    out_path = mixed_path
                    export_rel = mixed_rel
            except Exception:
                pass

    edit["outputPath"] = export_rel
    edit["updatedAt"] = _now()
    store.save(state)
    if out_path.is_file():
        store.persist_media(project_id, export_rel)
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
