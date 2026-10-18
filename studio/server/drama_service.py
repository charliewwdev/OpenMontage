"""Business logic for Xuefeng-parity Drama Studio flows."""

from __future__ import annotations

import json
import re
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
    from skill_runtime import get_skill_runtime

    skill = load_skill("script-brief")
    runtime = get_skill_runtime("script-brief").get("runtime") or {}
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
        temperature=float(runtime.get("temperature") or 0.6),
        max_tokens=int(runtime.get("max_tokens") or 4096),
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
    from skill_runtime import get_skill_runtime

    state = store.load(project_id)
    if not state:
        raise FileNotFoundError("project not found")
    count = max(1, min(10, int(episode_count)))
    skill = load_skill("drama-script")
    runtime = get_skill_runtime("drama-script").get("runtime") or {}
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
        temperature=float(runtime.get("temperature") or 0.45),
        max_tokens=int(runtime.get("max_tokens") or 16000),
        retries=int(runtime.get("retries") or 4),
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
    # Smaller batches need fewer tokens; large ceilings truncate mid-JSON on some gateways.
    tok = 6000 if count <= 1 else (10000 if count <= 2 else 14000)
    data = chat_json(
        system=(
            skill
            + "\n\n续写后续集，不要改写已有集。只输出一个完整 JSON 对象，"
            "禁止 Markdown/注释/尾随逗号；字符串内不要未转义引号；每集 content 精简。"
        ),
        user=user,
        temperature=0.4,
        max_tokens=tok,
        retries=5,
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
                for key in ("name", "variant", "description", "category", "imageStatus", "imageError"):
                    if key in payload:
                        e[key] = payload[key]
                if payload.get("clearQaFailed"):
                    e.pop("qaFailed", None)
                    e.pop("qaFailReason", None)
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


def _clean_desc(text: str) -> str:
    t = " ".join(str(text or "").strip().split())
    return t.rstrip("。.;；,，")


def _split_character_desc(desc: str) -> tuple[str, str]:
    """Keep identity/wardrobe first; push leading place/time cues to atmosphere.

    LLM asset bibles often start with「夜间室内…」which makes T2I latch onto
    city/night empty shots instead of the named person.
    """
    raw = _clean_desc(desc)
    if not raw:
        return "", ""
    env_heads = (
        "夜间室内",
        "夜晚室内",
        "夜晚",
        "夜间",
        "深夜",
        "白昼",
        "白天",
        "室内",
        "室外",
        "高层",
        "窗外",
    )
    for head in env_heads:
        if raw.startswith(head):
            rest = raw[len(head) :].lstrip("，,、 ")
            if rest:
                return rest, head
    # Trailing light/place clauses ("血色月光…") make T2I draw scenery instead of the person.
    parts = [p.strip() for p in raw.replace(";", "；").split("；") if p.strip()]
    light_keys = ("月光", "逆光", "晨光", "灯光", "血月", "山壁", "林间", "空镜")
    if len(parts) > 1 and any(k in parts[-1] for k in light_keys):
        return "；".join(parts[:-1]), parts[-1]
    return raw, ""


def _boost_restates_wrong_subject(text: str) -> bool:
    """Learned QA notes often name the unwanted portrait. Putting that in the prompt redraws it."""
    low = text.lower()
    return any(
        tok in low
        for tok in ("portrait", "woman", "person", "face", "人物", "人像", "全身", "婚纱")
    )


def build_entity_image_prompt(
    state: dict[str, Any],
    ent: dict[str, Any],
    *,
    three_view: bool = False,
    force_illustration: bool = False,
    qa_reason: str = "",
    projects_root: Path | None = None,
) -> dict[str, Any]:
    """Build T2I prompt via registered entity prompt strategies + Skill experience patches."""
    from entity_prompts import PromptBuildContext, resolve_entity_prompt_strategy
    from skill_runtime import (
        apply_experience_to_prompt,
        get_skill_runtime,
        match_experience_patches,
    )

    skill = get_skill_runtime("drama-entity-still")
    runtime = skill.get("runtime") or {}
    _ = load_skill("drama-entity-still")
    style = resolve_style_prompt((state.get("project") or {}).get("visualStyle") or "")
    use_illustration = bool(force_illustration)
    if use_illustration and "插画" not in style and "动漫" not in style and "二次元" not in style and "写实" not in style:
        style = f"{style}。国漫插画风格，清晰线条与色块，非写实真人摄影"
    name = ent.get("name") or ""
    variant = ent.get("variant") or ""
    desc = _clean_desc(ent.get("description") or "")
    kind = ent.get("kind") or "prop"
    look, atmosphere = _split_character_desc(desc) if kind == "character" else ("", "")
    ctx = PromptBuildContext(
        kind=kind,
        name=name,
        variant=variant,
        desc=desc,
        style=style,
        three_view=three_view,
        force_illustration=use_illustration,
        runtime=runtime,
        look=look,
        atmosphere=atmosphere,
    )
    strategy = resolve_entity_prompt_strategy(ctx)
    prompt, negative = strategy.build(ctx)

    applied_patches = match_experience_patches(
        skill_id="drama-entity-still",
        kind=kind,
        variant=variant,
        reason=qa_reason or "",
        projects_root=projects_root,
    )
    if kind in {"scene", "prop"}:
        applied_patches = [
            p
            for p in applied_patches
            if not _boost_restates_wrong_subject(str(p.get("promptBoost") or ""))
        ]
    prompt, negative = apply_experience_to_prompt(prompt, negative, applied_patches)
    return {
        "prompt": prompt,
        "negativePrompt": negative,
        "kind": kind,
        "name": name,
        "variant": variant,
        "description": desc,
        "style": style,
        "skillId": "drama-entity-still",
        "promptStrategy": strategy.id,
        "experiencePatchIds": [p.get("id") for p in applied_patches if p.get("id")],
    }


def preview_entity_prompt(
    store: ProjectStore,
    project_id: str,
    entity_id: str,
    *,
    three_view: bool = False,
) -> dict[str, Any]:
    state = store.load(project_id)
    if not state:
        raise FileNotFoundError("project not found")
    ent = next((e for e in state.get("entities") or [] if e["id"] == entity_id and not e.get("deletedAt")), None)
    if not ent:
        raise FileNotFoundError("entity not found")
    built = build_entity_image_prompt(state, ent, three_view=three_view)
    selected = next(
        (i for i in (ent.get("images") or []) if i.get("id") == ent.get("selectedImageId")),
        None,
    )
    return {
        **built,
        "entityId": entity_id,
        "selectedImagePrompt": (selected or {}).get("prompt") or "",
        "selectedImageQa": (selected or {}).get("qa") or {},
        "selectedQaPass": bool((selected or {}).get("qaPass")),
    }


_DEFAULT_STILL_VARIANTS = {"", "默认形象", "默认造型", "default"}
_STILL_REF_LOCK = {
    "character": (
        " Keep the SAME face identity as the reference image;"
        " only change wardrobe and injury as described."
    ),
    "scene": (
        " Keep the SAME location and layout as the reference image;"
        " only adjust set dressing and light as described. No people."
    ),
    "prop": (
        " Keep the SAME object as the reference image;"
        " only adjust the described material and details. No people."
    ),
}

# Vision QA used to require「绷带占满画面」— RealVis never hits that, so retries loop forever.
_INJURY_ACHIEVABLE_BIBLE = (
    "East Asian man, chest-up medium shot. "
    "White cotton/gauze medical wrap visible on the upper body "
    "(shoulder, clavicle, upper chest, or upper arm near the shoulder — a gauze-like sling counts). "
    "Dark coat optional. Face may look pale/sweaty. "
    "Pass whenever white medical wrap is clearly visible on the upper body; "
    "fail only for blue plastic / towel-only / face-cuts-only with clean shoulders."
)


def _is_injury_variant(variant: str) -> bool:
    return any(tok in str(variant or "") for tok in ("受伤", "绷带", "伤", "bandage", "injury"))


def _soften_injury_entity_bible(ent: dict[str, Any]) -> str:
    """Replace impossible bible wording so judge + prompt stay aligned."""
    raw = str(ent.get("description") or "").strip()
    if not _is_injury_variant(str(ent.get("variant") or "")):
        return raw
    low = raw.lower()
    if any(
        tok in raw or tok in low
        for tok in ("dominate", "最醒目", "largest white", "must be the first", "占满")
    ):
        softened = _INJURY_ACHIEVABLE_BIBLE
        if raw and softened not in raw:
            ent["description"] = softened
            ent["descriptionHardened"] = raw[:500]
        return softened
    if not raw:
        ent["description"] = _INJURY_ACHIEVABLE_BIBLE
        return _INJURY_ACHIEVABLE_BIBLE
    return raw


def _passed_selected_still(
    store: ProjectStore,
    project_id: str,
    ent: dict[str, Any],
) -> Path | None:
    sid = ent.get("selectedImageId")
    if not sid:
        return None
    img = next((i for i in (ent.get("images") or []) if i.get("id") == sid), None)
    if not img or not img.get("path") or img.get("qaPass") is False:
        return None
    path = store._dir(project_id) / img["path"]
    return path if path.is_file() else None


def _entity_still_ref_path(
    store: ProjectStore,
    project_id: str,
    state: dict[str, Any],
    ent: dict[str, Any],
) -> Path | None:
    """QA-passed still for this character, scene, or prop. Variants prefer the default."""
    kind = ent.get("kind") or ""
    if kind not in _STILL_REF_LOCK:
        return None
    name = (ent.get("name") or "").strip()
    variant = (ent.get("variant") or "").strip()
    prefer_default = bool(variant) and variant not in _DEFAULT_STILL_VARIANTS
    candidates: list[dict[str, Any]] = []
    if prefer_default and name:
        for other in state.get("entities") or []:
            if other.get("deletedAt") or other.get("id") == ent.get("id"):
                continue
            if (other.get("kind") or "") != kind:
                continue
            if (other.get("name") or "").strip() != name:
                continue
            other_variant = (other.get("variant") or "").strip()
            if other_variant in _DEFAULT_STILL_VARIANTS:
                candidates.insert(0, other)
            else:
                candidates.append(other)
    for other in candidates + [ent]:
        path = _passed_selected_still(store, project_id, other)
        if path is not None:
            return path
    return None


def start_entity_image_job(
    store: ProjectStore,
    project_id: str,
    entity_id: str,
    *,
    three_view: bool = False,
    redraw: bool = False,
    force_illustration: bool = False,
) -> dict[str, Any]:
    """Enqueue entity still generation (Redis worker or bounded pool); return immediately."""
    from job_queue import enqueue

    state = store.load(project_id)
    if not state:
        raise FileNotFoundError("project not found")
    ent = next((e for e in state.get("entities") or [] if e["id"] == entity_id and not e.get("deletedAt")), None)
    if not ent:
        raise FileNotFoundError("entity not found")
    # Allow re-enqueue when stuck in generating (worker crash / lost Redis job).
    # redraw=True always forces a fresh queue entry.
    if ent.get("imageStatus") == "generating" and not redraw:
        # Soft-block only if updated within the last 3 minutes (likely in-flight).
        from datetime import datetime, timezone

        updated = str(ent.get("updatedAt") or "")
        fresh = False
        try:
            ts = datetime.fromisoformat(updated.replace("Z", "+00:00"))
            fresh = (datetime.now(timezone.utc) - ts).total_seconds() < 180
        except Exception:
            fresh = False
        if fresh:
            raise RuntimeError(f"「{ent.get('name') or entity_id}」正在出图")
    ent["imageStatus"] = "generating"
    ent["imageError"] = None
    ent.pop("qaFailed", None)
    ent.pop("qaFailReason", None)
    ent["updatedAt"] = _now()
    store.save(state)

    stub = enqueue(
        "entity_image",
        {
            "projectId": project_id,
            "entityId": entity_id,
            "threeView": three_view,
            "redraw": redraw,
            "forceIllustration": force_illustration,
        },
    )
    return {
        "entityId": entity_id,
        "name": ent.get("name"),
        "kind": ent.get("kind"),
        "imageStatus": "generating",
        "queued": True,
        "async": True,
        "jobId": stub.get("jobId"),
        "backend": stub.get("backend"),
    }


def generate_entity_image(
    store: ProjectStore,
    project_id: str,
    entity_id: str,
    *,
    three_view: bool = False,
    redraw: bool = False,
    force_illustration: bool = False,
    wait: bool = True,
) -> dict:
    """Generate (+ QA-loop) an entity still.

    ``wait=False`` enqueues on the bounded media thread pool and returns a job stub.
    ``wait=True`` (default for internal workers) runs synchronously in the current thread.
    """
    if not wait:
        return start_entity_image_job(
            store,
            project_id,
            entity_id,
            three_view=three_view,
            redraw=redraw,
            force_illustration=force_illustration,
        )

    from entity_prompts import PromptBuildContext, resolve_entity_prompt_strategy
    from providers.media import generate_image
    from skill_runtime import apply_experience_to_prompt, match_experience_patches, record_qa_failure

    state = store.load(project_id)
    if not state:
        raise FileNotFoundError("project not found")
    ent = next((e for e in state.get("entities") or [] if e["id"] == entity_id and not e.get("deletedAt")), None)
    if not ent:
        raise FileNotFoundError("entity not found")
    # Ensure generating flag while sync path runs (also set by async enqueue).
    ent["imageStatus"] = "generating"
    ent["imageError"] = None
    projects_root = store.root
    built = build_entity_image_prompt(
        state,
        ent,
        three_view=three_view,
        force_illustration=force_illustration,
        projects_root=projects_root,
    )
    prompt = built["prompt"]
    negative = built.get("negativePrompt")
    kind = built["kind"]
    ratio = state["project"].get("ratio") or "9:16"
    look, atmosphere = _split_character_desc(_clean_desc(ent.get("description") or "")) if kind == "character" else ("", "")
    prompt_ctx = PromptBuildContext(
        kind=kind,
        name=str(ent.get("name") or ""),
        variant=str(ent.get("variant") or ""),
        desc=_clean_desc(ent.get("description") or ""),
        style=str(built.get("style") or ""),
        three_view=three_view,
        force_illustration=force_illustration,
        look=look,
        atmosphere=atmosphere,
    )
    prompt_strategy = resolve_entity_prompt_strategy(prompt_ctx)

    ref = None
    denoise: float | None = None
    variant = str(ent.get("variant") or "")
    injury_edit = kind == "character" and _is_injury_variant(variant)
    injury_bible = _soften_injury_entity_bible(ent) if injury_edit else ""
    if kind in _STILL_REF_LOCK and not injury_edit:
        # Default / non-injury: img2img from a passed still.
        # Injury MUST NOT start from a clean headshot — that locks Intact wardrobe.
        ref = _entity_still_ref_path(store, project_id, state, ent)
        if ref is not None:
            prompt += _STILL_REF_LOCK[kind]

    def _gen_once(
        ptext: str,
        neg: str | None,
        img_id: str,
        *,
        reference_path: Path | None,
        strength: float | None,
    ) -> tuple[str, Path]:
        rel_path = f"media/images/{img_id}.png"
        dest = store._dir(project_id) / rel_path
        generate_image(
            prompt=ptext,
            ratio=ratio,
            out_path=dest,
            reference_path=reference_path,
            negative_prompt=neg,
            denoise=strength,
        )
        store.persist_media(project_id, rel_path)
        return rel_path, dest

    from prompt_qa import entity_qa_max_attempts, judge_image_against_prompt, qa_meets_bar, qa_min_score

    max_attempts = entity_qa_max_attempts()
    # Injury: always run the full short ladder (env max=1 used to abort after one T2I).
    if injury_edit:
        max_attempts = 4
    # Props often stick to character portraits on the first Comfy pass — give them a short ladder.
    if kind == "prop":
        max_attempts = max(max_attempts, 3)
    min_score = qa_min_score()
    pass_bar = min_score
    if injury_edit:
        # Stay on the injury strategy prompt — never hard-swap to a fixed “East Asian man” template.
        denoise = None
        ref = None
    base_prompt = prompt
    best: dict[str, Any] | None = None
    last_reason = ""

    for attempt in range(1, max_attempts + 1):
        ptext, neg = prompt_strategy.paraphrase_attempt(
            prompt_ctx,
            attempt=attempt,
            base_prompt=base_prompt,
            base_negative=negative,
            last_reason=last_reason,
        )
        attempt_ref = ref
        attempt_denoise = denoise
        judge_desc = injury_bible if injury_edit else str(ent.get("description") or "")
        if injury_edit:
            if attempt >= 3 and ref is None:
                # Last resort: loose img2img from default face so wardrobe can rebuild.
                face_ref = _entity_still_ref_path(store, project_id, state, ent)
                if face_ref is not None:
                    attempt_ref = face_ref
                    attempt_denoise = 0.94
            judge_desc = _INJURY_ACHIEVABLE_BIBLE
        if attempt > 1 and last_reason and not injury_edit:
            record_qa_failure(
                skill_id="drama-entity-still",
                kind=kind,
                variant=str(ent.get("variant") or ""),
                reason=last_reason,
                entity_name=str(ent.get("name") or ""),
                projects_root=projects_root,
            )
            retry_patches = match_experience_patches(
                skill_id="drama-entity-still",
                kind=kind,
                variant=str(ent.get("variant") or ""),
                reason=last_reason,
                projects_root=projects_root,
            )
            if kind in {"scene", "prop"}:
                retry_patches = [
                    p
                    for p in retry_patches
                    if not _boost_restates_wrong_subject(str(p.get("promptBoost") or ""))
                ]
            ptext, neg = apply_experience_to_prompt(ptext, neg, retry_patches)
            ptext += prompt_strategy.retry_clause(prompt_ctx, attempt=attempt, max_attempts=max_attempts)
        elif attempt > 1 and not injury_edit:
            ptext = ptext + prompt_strategy.retry_clause(prompt_ctx, attempt=attempt, max_attempts=max_attempts)
        elif injury_edit and attempt > 1 and last_reason:
            record_qa_failure(
                skill_id="drama-entity-still",
                kind=kind,
                variant=str(ent.get("variant") or ""),
                reason=last_reason,
                entity_name=str(ent.get("name") or ""),
                projects_root=projects_root,
            )
        img_id = new_id("img_")
        try:
            rel, out = _gen_once(
                ptext,
                neg,
                img_id,
                reference_path=attempt_ref,
                strength=attempt_denoise,
            )
        except Exception as exc:  # noqa: BLE001
            last_reason = str(exc)[:200]
            qa = {
                "pass": False,
                "score": 0,
                "reason": f"generate_error:{last_reason}",
                "skipped": False,
                "attempts": attempt,
            }
            cand = {
                "id": img_id,
                "entityId": entity_id,
                "path": None,
                "prompt": ptext,
                "negativePrompt": neg,
                "qa": qa,
                "qaPass": False,
                "createdAt": _now(),
            }
            if best is None:
                best = cand
            continue
        try:
            qa = judge_image_against_prompt(
                out,
                prompt=ptext,
                kind=kind,
                entity_name=str(ent.get("name") or ""),
                entity_description=judge_desc,
            )
        except Exception as exc:  # noqa: BLE001
            # Fail closed — never soft-pass when the judge itself crashes.
            qa = {
                "pass": False,
                "score": 0,
                "reason": f"qa_exception:{exc}",
                "skipped": True,
            }
        qa["attempts"] = attempt
        if last_reason:
            qa["prevReason"] = last_reason
        last_reason = str(qa.get("reason") or "")
        cand = {
            "id": img_id,
            "entityId": entity_id,
            "path": rel,
            "prompt": ptext,
            "negativePrompt": neg,
            "qa": qa,
            "qaPass": qa_meets_bar(qa, min_score=pass_bar),
            "createdAt": _now(),
        }
        if best is None:
            best = cand
        else:
            prev_score = float((best.get("qa") or {}).get("score") or 0)
            cur_score = float(qa.get("score") or 0)
            if cand["qaPass"] or (not best.get("qaPass") and cur_score >= prev_score):
                best = cand
        if cand["qaPass"]:
            break

    version = best or {
        "id": new_id("img_"),
        "entityId": entity_id,
        "path": None,
        "prompt": base_prompt,
        "negativePrompt": negative,
        "qa": {"pass": False, "score": 0, "reason": "no_attempt", "skipped": False, "attempts": 0},
        "qaPass": False,
        "createdAt": _now(),
    }
    if version.get("path"):
        ent.setdefault("images", []).append(version)
    # Promote to selected when QA passes. If QA fails but we have a still, still show it
    # in the rail (avoid perpetual「无图」). Never sticky-fail when the kept selection still passes.
    from prompt_qa import is_soft_pass_qa

    def _still_ok(img: dict[str, Any] | None) -> bool:
        return bool(
            img
            and img.get("path")
            and img.get("qaPass") is True
            and not is_soft_pass_qa(img.get("qa"))
        )

    if version.get("qaPass") and version.get("path"):
        ent["selectedImageId"] = version["id"]
        ent.pop("qaFailed", None)
        ent.pop("qaFailReason", None)
        ent.pop("imageError", None)
    elif version.get("path"):
        prev = next((i for i in (ent.get("images") or []) if i.get("id") == ent.get("selectedImageId")), None)
        if _still_ok(prev):
            # Redraw failed, but the previously selected still is still good — keep it and do not
            # flip entity.qaFailed (that caused「外层未过 / 内层描述已过」).
            if injury_edit:
                qa_meta = version.setdefault("qa", {})
                qa_meta["ladderExhausted"] = True
                qa_meta["strategy"] = "injury_img2img_then_t2i"
        else:
            ent["selectedImageId"] = version["id"]
            ent["qaFailed"] = True
            ent["qaFailReason"] = str((version.get("qa") or {}).get("reason") or "qa_failed")
            if injury_edit:
                qa_meta = version.setdefault("qa", {})
                qa_meta["ladderExhausted"] = True
                qa_meta["strategy"] = "injury_img2img_then_t2i"
    elif not ent.get("selectedImageId"):
        ent["qaFailed"] = True
        ent["qaFailReason"] = str((version.get("qa") or {}).get("reason") or "qa_failed")
    else:
        # Keep old selection only if it still looks like a real pass.
        prev = next((i for i in (ent.get("images") or []) if i.get("id") == ent.get("selectedImageId")), None)
        if _still_ok(prev):
            ent.pop("qaFailed", None)
            ent.pop("qaFailReason", None)
        else:
            ent["qaFailed"] = True
            ent["qaFailReason"] = str((version.get("qa") or {}).get("reason") or "qa_failed")
    if not version.get("qaPass"):
        fail_reason = str((version.get("qa") or {}).get("reason") or last_reason or "qa_failed")
        try:
            record_qa_failure(
                skill_id="drama-entity-still",
                kind=kind,
                variant=str(ent.get("variant") or ""),
                reason=fail_reason,
                entity_name=str(ent.get("name") or ""),
                projects_root=projects_root,
            )
        except Exception:
            pass
    ent["updatedAt"] = _now()
    ent["imageStatus"] = "done" if version.get("path") else "failed"
    if version.get("qaPass"):
        ent.pop("imageError", None)
    elif version.get("path"):
        ent["imageError"] = str((version.get("qa") or {}).get("reason") or "qa_failed")[:300]
    else:
        ent["imageError"] = str(
            (version.get("qa") or {}).get("reason") or last_reason or "generate_failed"
        )[:300]
    # Prefer character still as project library cover
    proj = state.get("project") or {}
    if version.get("qaPass") and version.get("path") and (
        ent.get("kind") == "character" or not proj.get("coverPath")
    ):
        proj["coverPath"] = version["path"]
        proj["updatedAt"] = _now()
        state["project"] = proj
    if version.get("qaPass") and version.get("path"):
        _mark_shots_stale(
            state,
            entity_id=entity_id,
            reason=f"参考素材「{ent.get('name') or entity_id}」图片已更新，引用该素材的镜头建议重生成",
        )
    store.save(state)
    return version


def recheck_entity_qa(
    store: ProjectStore,
    project_id: str,
    *,
    entity_ids: list[str] | None = None,
    clear_soft_pass: bool = True,
    regenerate_failed: bool = False,
) -> dict[str, Any]:
    """Re-run vision QA on selected stills for characters / scenes / props."""
    from prompt_qa import is_soft_pass_qa, judge_image_against_prompt, qa_meets_bar, qa_min_score

    state = store.load(project_id)
    if not state:
        raise FileNotFoundError("project not found")
    min_score = qa_min_score()
    wanted = {str(x) for x in (entity_ids or []) if x} or None
    results: list[dict[str, Any]] = []
    regen_ids: list[str] = []

    for ent in state.get("entities") or []:
        if ent.get("deletedAt"):
            continue
        if wanted is not None and ent.get("id") not in wanted:
            continue
        kind = ent.get("kind") or "prop"
        sid = ent.get("selectedImageId")
        imgs = [i for i in (ent.get("images") or []) if i.get("path")]
        sel = next((i for i in imgs if i.get("id") == sid), None)
        # If soft-pass demotion cleared selection, still re-judge the newest still on disk.
        if not sel and imgs:
            sel = imgs[-1]
        if not sel or not sel.get("path"):
            results.append(
                {
                    "entityId": ent.get("id"),
                    "name": ent.get("name"),
                    "kind": kind,
                    "status": "no_image",
                    "qaPass": False,
                }
            )
            ent["qaFailed"] = True
            ent["qaFailReason"] = "no_image"
            continue
        path = store._dir(project_id) / sel["path"]
        if not path.is_file():
            results.append(
                {
                    "entityId": ent.get("id"),
                    "name": ent.get("name"),
                    "kind": kind,
                    "status": "missing_file",
                    "qaPass": False,
                }
            )
            ent["qaFailed"] = True
            ent["qaFailReason"] = "missing_file"
            continue
        prompt = sel.get("prompt") or build_entity_image_prompt(state, ent)["prompt"]
        try:
            qa = judge_image_against_prompt(
                path,
                prompt=prompt,
                kind=kind,
                entity_name=str(ent.get("name") or ""),
                entity_description=str(ent.get("description") or ""),
            )
        except Exception as exc:  # noqa: BLE001
            qa = {"pass": False, "score": 0, "reason": f"qa_exception:{exc}", "skipped": True}
        qa_pass = qa_meets_bar(qa, min_score=min_score) and not is_soft_pass_qa(qa)
        sel["qa"] = qa
        sel["qaPass"] = qa_pass
        sel["prompt"] = prompt
        status = "pass" if qa_pass else "fail"
        if qa_pass:
            ent["selectedImageId"] = sel["id"]
            ent.pop("qaFailed", None)
            ent.pop("qaFailReason", None)
        elif clear_soft_pass:
            # Demote soft-pass / mismatch selections so the UI stops treating them as OK.
            ent["qaFailed"] = True
            ent["qaFailReason"] = str(qa.get("reason") or "qa_failed")
            # Keep the image in history but clear selection when soft-pass garbage / hard mismatch.
            if is_soft_pass_qa(qa) or float(qa.get("score") or 0) < 0.4:
                if ent.get("selectedImageId") == sel.get("id"):
                    ent["selectedImageId"] = None
                status = "cleared"
            if regenerate_failed:
                regen_ids.append(str(ent.get("id")))
        else:
            ent["qaFailed"] = True
            ent["qaFailReason"] = str(qa.get("reason") or "qa_failed")
            if regenerate_failed:
                regen_ids.append(str(ent.get("id")))
        ent["updatedAt"] = _now()
        results.append(
            {
                "entityId": ent.get("id"),
                "name": ent.get("name"),
                "kind": kind,
                "variant": ent.get("variant") or "",
                "status": status,
                "qaPass": qa_pass,
                "score": qa.get("score"),
                "reason": qa.get("reason"),
            }
        )

    store.save(state)
    regenerated: list[dict[str, Any]] = []
    if regenerate_failed and regen_ids:
        for eid in regen_ids:
            try:
                # Enqueue — do not block the recheck HTTP request on Comfy.
                regenerated.append(
                    generate_entity_image(store, project_id, eid, redraw=False, wait=False)
                )
            except Exception as exc:  # noqa: BLE001
                regenerated.append({"entityId": eid, "error": str(exc)})
        state = store.load(project_id) or state

    summary = {
        "total": len(results),
        "pass": sum(1 for r in results if r.get("qaPass")),
        "fail": sum(1 for r in results if not r.get("qaPass")),
        "cleared": sum(1 for r in results if r.get("status") == "cleared"),
        "results": results,
        "regenerated": regenerated,
    }
    return summary


def fill_entity_stills(
    store: ProjectStore,
    project_id: str,
    *,
    episode_id: str | None = None,
    segment_order: int | None = None,
    kinds: list[str] | None = None,
    entity_ids: list[str] | None = None,
    only_missing: bool = True,
    force_refresh_kinds: list[str] | None = None,
    wait_generate: bool = False,
) -> dict[str, Any]:
    """Skill-aligned asset fill: generate stills for entities missing image or QA.

    Uses the same ``generate_entity_image`` path (drama-entity-still + fail-closed QA loop)
    that the Studio agent / out-gate depend on — not a detached Skills-page flow.
    ``wait_generate=False`` (default) enqueues each still on the shared media queue.
    ``force_refresh_kinds`` re-generates matching kinds even when qaPass is already true
    (used to unify cast still framing after prompt lock changes).
    """
    state = store.load(project_id)
    if not state:
        raise FileNotFoundError("project not found")
    kind_set = {k for k in (kinds or ["character", "scene"]) if k}
    force_kinds = {k for k in (force_refresh_kinds or []) if k}
    alive = [e for e in (state.get("entities") or []) if not e.get("deletedAt")]
    by_id = {e["id"]: e for e in alive}

    target_ids: list[str] = []
    if entity_ids:
        target_ids = [str(x) for x in entity_ids if str(x) in by_id]
    elif episode_id:
        ep_shots = [
            s
            for s in (state.get("shots") or [])
            if s.get("episodeId") == episode_id and not s.get("deletedAt")
        ]
        if segment_order is not None:
            ep_shots = [s for s in ep_shots if int(s.get("segmentOrder") or 0) == int(segment_order)]
        seen: set[str] = set()
        for s in ep_shots:
            for eid in s.get("referenceEntityIds") or []:
                if eid in seen:
                    continue
                ent = by_id.get(eid)
                if not ent or (ent.get("kind") or "") not in kind_set:
                    continue
                seen.add(eid)
                target_ids.append(eid)
        # Also pull by @name / sceneName so unbound refs still get filled.
        import re as _re

        names: set[str] = set()
        for s in ep_shots:
            for m in _re.finditer(r"@([^\s@,，。；;（）()]+)", s.get("prompt") or ""):
                names.add(m.group(1).split("-")[0])
            if s.get("sceneName"):
                names.add(str(s["sceneName"]))
        for ent in alive:
            if ent["id"] in seen:
                continue
            if (ent.get("kind") or "") not in kind_set:
                continue
            if (ent.get("name") or "") in names:
                seen.add(ent["id"])
                target_ids.append(ent["id"])
    else:
        target_ids = [e["id"] for e in alive if (e.get("kind") or "") in kind_set]

    def _needs_fill(ent: dict[str, Any]) -> bool:
        if (ent.get("kind") or "") in force_kinds:
            return True
        img = _selected_entity_image(ent)
        if not img or not img.get("path"):
            return True
        if not only_missing:
            return True
        from prompt_qa import is_soft_pass_qa, qa_meets_bar

        qa = img.get("qa") or {}
        return not (
            img.get("qaPass") is True and qa_meets_bar(qa) and not is_soft_pass_qa(qa)
        )

    todo = [eid for eid in target_ids if _needs_fill(by_id[eid])]
    # Default: enqueue on shared media queue (HTTP returns immediately).
    wait = bool(wait_generate)
    results: list[dict[str, Any]] = []
    queued = 0
    for eid in todo:
        ent = by_id[eid]
        try:
            ver = generate_entity_image(store, project_id, eid, wait=wait)
            if ver.get("queued") or ver.get("async"):
                queued += 1
                results.append(
                    {
                        "entityId": eid,
                        "name": ent.get("name"),
                        "kind": ent.get("kind"),
                        "variant": ent.get("variant") or "",
                        "queued": True,
                        "imageStatus": "generating",
                        "skill": "drama-entity-still",
                    }
                )
            else:
                results.append(
                    {
                        "entityId": eid,
                        "name": ent.get("name"),
                        "kind": ent.get("kind"),
                        "variant": ent.get("variant") or "",
                        "qaPass": bool(ver.get("qaPass")),
                        "score": (ver.get("qa") or {}).get("score"),
                        "reason": (ver.get("qa") or {}).get("reason"),
                        "imageId": ver.get("id"),
                        "skill": "drama-entity-still",
                    }
                )
        except Exception as exc:  # noqa: BLE001
            results.append(
                {
                    "entityId": eid,
                    "name": ent.get("name"),
                    "kind": ent.get("kind"),
                    "variant": ent.get("variant") or "",
                    "qaPass": False,
                    "error": str(exc),
                    "skill": "drama-entity-still",
                }
            )
        state = store.load(project_id) or state
        by_id = {e["id"]: e for e in (state.get("entities") or []) if not e.get("deletedAt")}

    return {
        "skill": "drama-entity-still",
        "async": True,
        "requested": len(target_ids),
        "attempted": len(todo),
        "queued": queued,
        "pass": sum(1 for r in results if r.get("qaPass")),
        "fail": sum(1 for r in results if r.get("error") or (r.get("qaPass") is False and not r.get("queued"))),
        "results": results,
    }


def effective_segment_video_prompt(
    store: ProjectStore,
    project_id: str,
    *,
    episode_id: str,
    segment_order: int,
) -> dict[str, Any]:
    """Return the exact text prompt that would be sent to the video model for a segment."""
    state = store.load(project_id)
    if not state:
        raise FileNotFoundError("project not found")
    ep_shots = [
        s
        for s in (state.get("shots") or [])
        if s.get("episodeId") == episode_id and not s.get("deletedAt")
    ]
    segments = group_shots_by_segment(ep_shots)
    seg = next((g for g in segments if int(g["segmentOrder"]) == int(segment_order)), None)
    if not seg:
        raise FileNotFoundError(f"片段 {segment_order} 不存在")
    combined = build_segment_prompt(seg)
    lead = seg.get("lead") or {}
    entities = {e["id"]: e for e in state.get("entities") or [] if not e.get("deletedAt")}
    refs: list[dict[str, Any]] = []
    for s in seg.get("shots") or []:
        for eid in s.get("referenceEntityIds") or []:
            ent = entities.get(eid)
            if not ent:
                continue
            if any(r.get("id") == eid for r in refs):
                continue
            refs.append(
                {
                    "id": eid,
                    "name": ent.get("name"),
                    "kind": ent.get("kind"),
                    "variant": ent.get("variant") or "",
                    "description": (ent.get("description") or "")[:300],
                    "hasImage": bool(ent.get("selectedImageId")),
                }
            )
    shot_prompts = [
        {
            "shotId": s.get("id"),
            "beatIndex": s.get("beatIndex") or s.get("shotOrder"),
            "prompt": s.get("prompt") or "",
            "dialogue": s.get("dialogue") or "",
            "action": s.get("action") or "",
        }
        for s in (seg.get("shots") or [])
    ]
    return {
        "segmentOrder": int(segment_order),
        "episodeId": episode_id,
        "videoPrompt": combined,
        "duration": int(seg.get("duration") or lead.get("segmentDuration") or 12),
        "references": refs,
        "shots": shot_prompts,
        "note": "videoPrompt 为合并后发给 Seedance/Comfy 的正文；references 会作为参考图一并提交。",
    }


def recheck_video_qa(
    store: ProjectStore,
    project_id: str,
    *,
    shot_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Re-judge selected videos against prompt + referenced cast/scene/prop bible."""
    state = store.load(project_id)
    if not state:
        raise FileNotFoundError("project not found")
    wanted = {str(x) for x in (shot_ids or []) if x} or None
    entities = [e for e in (state.get("entities") or []) if not e.get("deletedAt")]
    by_id = {e["id"]: e for e in entities}
    results: list[dict[str, Any]] = []

    for sh in state.get("shots") or []:
        if sh.get("deletedAt"):
            continue
        if wanted is not None and sh.get("id") not in wanted:
            continue
        vid = next((v for v in (sh.get("videos") or []) if v.get("id") == sh.get("selectedVideoId")), None)
        if not vid or not vid.get("path"):
            continue
        path = store._dir(project_id) / vid["path"]
        prompt_used = vid.get("prompt") or sh.get("prompt") or ""
        ref_ents = [by_id[eid] for eid in (sh.get("referenceEntityIds") or []) if eid in by_id]
        qa = _judge_video_file(path, prompt=prompt_used, entities=ref_ents)
        vid["qa"] = qa
        vid["qaPass"] = bool(qa.get("qaPass"))
        if vid["qaPass"]:
            sh["status"] = "success"
            sh["error"] = None
        else:
            sh["status"] = "failed"
            sh["error"] = f"质检未达标: {qa.get('reason') or 'mismatch'}"
        sh["updatedAt"] = _now()
        results.append(
            {
                "shotId": sh.get("id"),
                "segmentOrder": sh.get("segmentOrder"),
                "qaPass": vid["qaPass"],
                "score": qa.get("score"),
                "reason": qa.get("reason"),
            }
        )
        _propagate_segment_video(state, sh)

    store.save(state)
    return {
        "total": len(results),
        "pass": sum(1 for r in results if r.get("qaPass")),
        "fail": sum(1 for r in results if not r.get("qaPass")),
        "results": results,
    }


def sync_entity_qa_flags(ent: dict[str, Any]) -> bool:
    """Clear sticky qaFailed / restore selection when a still currently passes. Returns True if changed."""
    from prompt_qa import is_soft_pass_qa, qa_meets_bar

    def _ok(img: dict[str, Any] | None) -> bool:
        if not img or not img.get("path"):
            return False
        qa = img.get("qa") or {}
        return bool(img.get("qaPass") is True) and qa_meets_bar(qa) and not is_soft_pass_qa(qa)

    imgs = [i for i in (ent.get("images") or []) if i.get("path")]
    sid = ent.get("selectedImageId")
    sel = next((i for i in imgs if i.get("id") == sid), None)
    changed = False
    if not _ok(sel):
        # Prefer newest passing still when selection is empty or currently failing.
        for img in reversed(imgs):
            if _ok(img):
                if ent.get("selectedImageId") != img.get("id"):
                    ent["selectedImageId"] = img.get("id")
                    changed = True
                sel = img
                break
    if not _ok(sel):
        return changed
    if ent.get("qaFailed") or ent.get("qaFailReason") or ent.get("imageError") or ent.get("imageStatus") == "failed":
        ent.pop("qaFailed", None)
        ent.pop("qaFailReason", None)
        ent.pop("imageError", None)
        if ent.get("imageStatus") == "failed":
            ent["imageStatus"] = "done"
        changed = True
    if changed:
        ent["updatedAt"] = _now()
    return changed


def heal_entity_qa_flags(state: dict[str, Any]) -> int:
    """Repair sticky qaFailed and orphaned passing stills left by failed redraws / soft demotions."""
    n = 0
    for ent in state.get("entities") or []:
        if ent.get("deletedAt"):
            continue
        if sync_entity_qa_flags(ent):
            n += 1
    return n


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
            sync_entity_qa_flags(e)
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
    dur = max(2, min(8, int(duration or 4)))
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


def _parse_ref_tags(prompt: str, entities: list[dict], *, require_image: bool = False) -> list[str]:
    """Map @Name or @Name-Variant tags to entity ids (max 9)."""
    tags = re.findall(r"@([^\s@,，。；;]+)", prompt or "")
    ids = []
    for tag in tags:
        name, _, variant = tag.partition("-")
        for e in entities:
            if e.get("deletedAt"):
                continue
            if e["name"] == name and (not variant or (e.get("variant") or "") == variant):
                if require_image and not e.get("selectedImageId"):
                    continue
                if e["id"] not in ids:
                    ids.append(e["id"])
                break
        if len(ids) >= 9:
            break
    return ids


def _resolve_shot_entity_ids(
    shot: dict,
    entities: list[dict],
    *,
    require_image: bool = False,
    episode_number: int | None = None,
) -> list[str]:
    """Bind characters / scenes / props mentioned in a beat to entity ids.

    Matching order: explicit @tags → characters[] → dialogue speaker → sceneName/location
    → longest entity-name substring in prompt/action. Prefer episode-tagged entities when
    the same name appears twice; still bind names even if episodes[] is wrong/stale.
    """
    alive = [e for e in (entities or []) if not e.get("deletedAt")]
    if not alive:
        return []

    def _ok(e: dict) -> bool:
        return (not require_image) or bool(e.get("selectedImageId"))

    def _rank(e: dict) -> tuple:
        eps = e.get("episodes") or []
        on_ep = 0 if (episode_number is None or not eps or episode_number in eps) else 1
        has_img = 0 if e.get("selectedImageId") else 1
        return (on_ep, has_img, len(str(e.get("name") or "")))

    by_name: dict[str, list[dict]] = {}
    for e in alive:
        by_name.setdefault(str(e.get("name") or "").strip(), []).append(e)

    def _pick_name(name: str) -> str | None:
        name = (name or "").strip()
        if not name or name not in by_name:
            return None
        cands = [e for e in by_name[name] if _ok(e)]
        if not cands:
            return None
        cands.sort(key=_rank)
        return cands[0]["id"]

    ids: list[str] = []

    def _add(eid: str | None) -> None:
        if eid and eid not in ids and len(ids) < 9:
            ids.append(eid)

    for eid in _parse_ref_tags(str(shot.get("prompt") or ""), alive, require_image=require_image):
        _add(eid)

    for name in shot.get("characters") or []:
        if isinstance(name, str):
            _add(_pick_name(name))
        elif isinstance(name, dict):
            _add(_pick_name(str(name.get("name") or "")))

    dialogue = str(shot.get("dialogue") or "").strip()
    if dialogue:
        m = re.match(r"^([^：:\n]{1,24})\s*[：:]", dialogue)
        if m:
            _add(_pick_name(m.group(1).strip()))

    for key in ("sceneName", "location"):
        _add(_pick_name(str(shot.get(key) or "")))

    # Substring scan: longest names first to avoid partial collisions.
    blob = " ".join(
        str(shot.get(k) or "")
        for k in ("prompt", "action", "dialogue", "sceneName", "location", "openingState")
    )
    names = sorted(
        (n for n in by_name if n and len(n) >= 2),
        key=len,
        reverse=True,
    )
    for name in names:
        if name in blob:
            _add(_pick_name(name))
        if len(ids) >= 9:
            break

    return ids[:9]


def bind_episode_refs(store: ProjectStore, project_id: str, episode_id: str) -> list[dict]:
    """Re-scan episode shots and fill referenceEntityIds from names in prompts/dialogue."""
    state = store.load(project_id)
    if not state:
        raise FileNotFoundError("project not found")
    ep = next((e for e in state.get("episodes") or [] if e["id"] == episode_id), None)
    ep_num = int(ep["episodeNumber"]) if ep else None
    entities = [e for e in (state.get("entities") or []) if not e.get("deletedAt")]
    changed = 0
    out = []
    for s in state.get("shots") or []:
        if s.get("episodeId") != episode_id or s.get("deletedAt"):
            continue
        refs = _resolve_shot_entity_ids(s, entities, require_image=False, episode_number=ep_num)
        prev = list(s.get("referenceEntityIds") or [])
        if refs != prev:
            s["referenceEntityIds"] = refs
            s["updatedAt"] = _now()
            changed += 1
        out.append(s)
    if changed:
        store.save(state)
    return out


# SceneMixer-aligned: ~12 segments × 3–4 beats; episode ~2.5–6 min.
_STORYBOARD_SEG_MIN = 10
_STORYBOARD_SEG_MAX = 14
_STORYBOARD_SHOT_MIN = 30  # 10×3
_STORYBOARD_SHOT_MAX = 56  # 14×4
_STORYBOARD_DUR_MIN = 150
_STORYBOARD_DUR_MAX = 360
_SEGMENT_DUR_MIN = 10
_SEGMENT_DUR_MAX = 15


def _materialize_one_beat(
    *,
    project_id: str,
    episode_id: str,
    sh: dict,
    available: list[dict],
    style_hint: str,
    shot_order: int,
    segment_order: int,
    beat_index: int,
    segment_meta: dict | None = None,
    ts: str | None = None,
) -> dict:
    """One SceneMixer beat → store shot row (video unit is the segment, not the beat)."""
    ts = ts or _now()
    meta = segment_meta or {}
    prompt = (sh.get("prompt") or "").strip()
    action = (sh.get("action") or "").strip()
    dialogue = (sh.get("dialogue") or "").strip()
    scene_name = (sh.get("sceneName") or meta.get("location") or "").strip()
    default_dur = 4 if dialogue else 3
    duration = max(2, min(8, int(sh.get("duration") or default_dur)))
    if len(prompt) < 12 or prompt.lower() in {"subtle performance, cinematic", "cinematic", "performance"}:
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
    is_lead = int(beat_index) == 1
    draft = {
        "prompt": prompt,
        "dialogue": dialogue,
        "action": action,
        "sceneName": scene_name,
        "location": (meta.get("location") or scene_name or "").strip(),
        "characters": sh.get("characters") or [],
        "openingState": (meta.get("openingState") or "").strip() if is_lead else "",
    }
    refs = _resolve_shot_entity_ids(draft, available, require_image=False)
    return {
        "id": new_id("sh_"),
        "projectId": project_id,
        "episodeId": episode_id,
        "shotOrder": shot_order,
        "segmentOrder": int(segment_order),
        "beatIndex": int(beat_index),
        "isSegmentLead": is_lead,
        "location": (meta.get("location") or scene_name or "").strip(),
        "timeOfDay": (meta.get("timeOfDay") or "").strip(),
        "weather": (meta.get("weather") or "").strip(),
        "openingState": (meta.get("openingState") or "").strip() if is_lead else "",
        "setDressing": (meta.get("setDressing") or "").strip() if is_lead else "",
        "ambientSound": (meta.get("ambientSound") or "").strip(),
        "segmentDuration": int(meta.get("duration") or 0) or None,
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


def _materialize_storyboard_shots(
    *,
    project_id: str,
    episode_id: str,
    raw_shots: list,
    available: list[dict],
    style_hint: str,
    start_order: int = 1,
) -> list[dict]:
    """Legacy flat shots → rows; auto-pack into segments of 3–4 beats / ~12–15s."""
    ts = _now()
    shots: list[dict] = []
    seg_order = 1
    beat_in_seg = 0
    seg_dur = 0
    for i, sh in enumerate(raw_shots or [], start_order):
        if not isinstance(sh, dict):
            continue
        # Start a new segment every 4 beats or when segment duration would exceed 15s.
        default_dur = 4 if (sh.get("dialogue") or "").strip() else 3
        guess = max(2, min(8, int(sh.get("duration") or default_dur)))
        if beat_in_seg >= 4 or (beat_in_seg >= 3 and seg_dur + guess > _SEGMENT_DUR_MAX):
            seg_order += 1
            beat_in_seg = 0
            seg_dur = 0
        beat_in_seg += 1
        row = _materialize_one_beat(
            project_id=project_id,
            episode_id=episode_id,
            sh=sh,
            available=available,
            style_hint=style_hint,
            shot_order=i,
            segment_order=seg_order,
            beat_index=beat_in_seg,
            segment_meta={"location": (sh.get("sceneName") or "").strip(), "duration": 0},
            ts=ts,
        )
        seg_dur += int(row["duration"])
        shots.append(row)
    # Fill segmentDuration on leads
    by_seg: dict[int, list[dict]] = {}
    for s in shots:
        by_seg.setdefault(int(s["segmentOrder"]), []).append(s)
    for seg_shots in by_seg.values():
        total = sum(int(x.get("duration") or 0) for x in seg_shots)
        for x in seg_shots:
            x["segmentDuration"] = total
    return shots


def _materialize_storyboard_segments(
    *,
    project_id: str,
    episode_id: str,
    raw_segments: list,
    available: list[dict],
    style_hint: str,
) -> list[dict]:
    """SceneMixer segments[] → flat shot rows with segmentOrder / beatIndex."""
    ts = _now()
    shots: list[dict] = []
    shot_order = 0
    for seg in raw_segments or []:
        if not isinstance(seg, dict):
            continue
        seg_order = int(seg.get("segmentOrder") or (shots[-1]["segmentOrder"] + 1 if shots else 1))
        beats = seg.get("beats") or seg.get("shots") or []
        if not isinstance(beats, list) or not beats:
            continue
        meta = {
            "location": (seg.get("location") or "").strip(),
            "timeOfDay": (seg.get("timeOfDay") or "").strip(),
            "weather": (seg.get("weather") or "").strip(),
            "openingState": (seg.get("openingState") or "").strip(),
            "setDressing": (seg.get("setDressing") or "").strip(),
            "ambientSound": (seg.get("ambientSound") or "").strip(),
            "duration": int(seg.get("duration") or 0),
        }
        seg_shots: list[dict] = []
        for bi, beat in enumerate(beats[:4], 1):
            if not isinstance(beat, dict):
                continue
            shot_order += 1
            row = _materialize_one_beat(
                project_id=project_id,
                episode_id=episode_id,
                sh=beat,
                available=available,
                style_hint=style_hint,
                shot_order=shot_order,
                segment_order=seg_order,
                beat_index=bi,
                segment_meta=meta,
                ts=ts,
            )
            seg_shots.append(row)
        if not seg_shots:
            continue
        total = sum(int(x.get("duration") or 0) for x in seg_shots)
        # Prefer model segment duration when in band; else sum of beats.
        seg_dur = int(meta.get("duration") or 0)
        if seg_dur < _SEGMENT_DUR_MIN or seg_dur > _SEGMENT_DUR_MAX:
            seg_dur = max(_SEGMENT_DUR_MIN, min(_SEGMENT_DUR_MAX, total or _SEGMENT_DUR_MIN))
        for x in seg_shots:
            x["segmentDuration"] = seg_dur
            if meta.get("ambientSound") and "环境音" not in (x.get("prompt") or "") and x.get("isSegmentLead"):
                x["prompt"] = f"{(x.get('prompt') or '').rstrip('。')}。环境音：{meta['ambientSound']}"
        shots.extend(seg_shots)
    return shots


def group_shots_by_segment(shots: list[dict]) -> list[dict]:
    """Return [{segmentOrder, duration, shots, lead}, ...] sorted."""
    buckets: dict[int, list[dict]] = {}
    for s in shots or []:
        if s.get("deletedAt"):
            continue
        so = int(s.get("segmentOrder") or s.get("shotOrder") or 0)
        if so <= 0:
            so = 1
        buckets.setdefault(so, []).append(s)
    out = []
    for so in sorted(buckets):
        group = sorted(
            buckets[so],
            key=lambda x: (int(x.get("beatIndex") or 0), int(x.get("shotOrder") or 0)),
        )
        lead = next((x for x in group if x.get("isSegmentLead")), group[0])
        dur = int(lead.get("segmentDuration") or 0) or sum(int(x.get("duration") or 0) for x in group)
        out.append({"segmentOrder": so, "duration": dur, "shots": group, "lead": lead})
    return out


def build_segment_prompt(segment: dict) -> str:
    """Combine segment header + beat prompts for one Seedance/H3 call."""
    lead = segment.get("lead") or (segment.get("shots") or [None])[0] or {}
    parts: list[str] = []
    loc = (lead.get("location") or lead.get("sceneName") or "").strip()
    if loc:
        parts.append(f"地点：{loc}")
    if lead.get("timeOfDay"):
        parts.append(f"时间：{lead['timeOfDay']}")
    if lead.get("weather"):
        parts.append(f"天气：{lead['weather']}")
    if lead.get("openingState"):
        parts.append(f"起始画面状态：{lead['openingState']}")
    if lead.get("setDressing"):
        parts.append(f"场上布景：{lead['setDressing']}")
    for beat in segment.get("shots") or []:
        p = (beat.get("prompt") or "").strip()
        if p:
            parts.append(p)
    if lead.get("ambientSound"):
        parts.append(f"环境音：{lead['ambientSound']}")
    parts.append("保持人物样貌与服装与参考图一致，无字幕，无解说旁白。")
    return "\n".join(parts)


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
            if int(s.get("duration") or 0) >= 8:
                continue
            s["duration"] = int(s.get("duration") or 3) + 1
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


def migrate_episode_segments(store: ProjectStore, project_id: str, episode_id: str) -> list[dict]:
    """Assign segmentOrder/beatIndex to legacy flat shots without wiping videos."""
    state = store.load(project_id)
    if not state:
        raise FileNotFoundError("project not found")
    shots = [
        s
        for s in (state.get("shots") or [])
        if s.get("episodeId") == episode_id and not s.get("deletedAt")
    ]
    if not shots:
        return []
    if all(int(s.get("segmentOrder") or 0) > 0 for s in shots):
        # Segments already assigned — still refresh name→entity refs for the desk.
        return bind_episode_refs(store, project_id, episode_id)
    ordered = sorted(shots, key=lambda s: int(s.get("shotOrder") or 0))
    seg_order = 1
    beat_in_seg = 0
    seg_dur = 0
    for s in ordered:
        guess = max(2, min(8, int(s.get("duration") or 4)))
        if beat_in_seg >= 4 or (beat_in_seg >= 3 and seg_dur + guess > _SEGMENT_DUR_MAX):
            seg_order += 1
            beat_in_seg = 0
            seg_dur = 0
        beat_in_seg += 1
        seg_dur += guess
        s["segmentOrder"] = seg_order
        s["beatIndex"] = beat_in_seg
        s["isSegmentLead"] = beat_in_seg == 1
        s.setdefault("location", s.get("sceneName") or "")
        s.setdefault("timeOfDay", "")
        s.setdefault("weather", "")
        s.setdefault("openingState", "")
        s.setdefault("setDressing", "")
        s.setdefault("ambientSound", "")
        s["updatedAt"] = _now()
    for g in group_shots_by_segment(ordered):
        total = sum(int(x.get("duration") or 0) for x in g["shots"])
        for x in g["shots"]:
            x["segmentDuration"] = max(_SEGMENT_DUR_MIN, min(_SEGMENT_DUR_MAX, total or _SEGMENT_DUR_MIN))
    store.save(state)
    # Also attach cast/prop/scene refs so the segment desk can show them.
    return bind_episode_refs(store, project_id, episode_id)


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
    from skill_runtime import get_skill_runtime

    skill = load_skill("drama-shot-prompt")
    runtime = get_skill_runtime("drama-shot-prompt").get("runtime") or {}
    seg_min = int(runtime.get("segment_count_min") or _STORYBOARD_SEG_MIN)
    seg_max = int(runtime.get("segment_count_max") or _STORYBOARD_SEG_MAX)
    seg_target = int(runtime.get("segment_count_target") or 12)
    dur_min = int(runtime.get("episode_duration_sec_min") or _STORYBOARD_DUR_MIN)
    dur_max = int(runtime.get("episode_duration_sec_max") or _STORYBOARD_DUR_MAX)
    dur_target = int(runtime.get("episode_duration_sec_target") or 162)
    beats = str(runtime.get("beats_per_segment") or "3-4")
    seg_dur = str(runtime.get("segment_duration_sec") or "10-15")
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
        "segmentCountMin": seg_min,
        "segmentCountMax": seg_max,
        "segmentCountTarget": seg_target,
        "beatsPerSegment": beats,
        "segmentDurationSec": seg_dur,
        "episodeDurationSecMin": dur_min,
        "episodeDurationSecMax": dur_max,
        "episodeDurationSecTarget": dur_target,
        "note": (
            f"必须输出 segments 数组：{seg_min}–{seg_max} 个片段，每段 {beats} 个 beats，每段 duration {seg_dur} 秒。"
            "对齐 SceneMixer《染血玉令》：一段一次出片；一镜一节拍；对白与反应拆镜；写清机位/承接/闭唇/光源。"
        ),
    }
    system = (
        skill
        + "\n\n只输出一个完整 JSON 对象（键 segments 为数组）。禁止 Markdown、注释与尾随逗号。"
    )
    data = chat_json(
        system=system,
        user=json.dumps({**base_ctx, "action": "generate"}, ensure_ascii=False),
        temperature=float(runtime.get("temperature") or 0.35),
        max_tokens=int(runtime.get("max_tokens") or 28000),
        retries=4,
    )
    if data.get("segments"):
        shots = _materialize_storyboard_segments(
            project_id=project_id,
            episode_id=episode_id,
            raw_segments=data.get("segments") or [],
            available=available,
            style_hint=style_hint,
        )
    else:
        # Backward compat if model still returns flat shots[]
        shots = _materialize_storyboard_shots(
            project_id=project_id,
            episode_id=episode_id,
            raw_shots=data.get("shots") or [],
            available=available,
            style_hint=style_hint,
            start_order=1,
        )

    # Continue adding segments until density targets are met.
    guard = 0
    while guard < 3:
        segments = group_shots_by_segment(shots)
        total_dur = sum(int(s.get("duration") or 0) for s in shots)
        if len(segments) >= seg_min and total_dur >= dur_min:
            break
        need_seg = min(4, seg_max - len(segments))
        if need_seg <= 0:
            break
        guard += 1
        cont_user = {
            **base_ctx,
            "action": "continue",
            "startSegmentOrder": len(segments) + 1,
            "addSegmentCount": need_seg,
            "haveSegmentCount": len(segments),
            "haveBeatCount": len(shots),
            "haveDurationSec": total_dur,
            "remainingDurationSecMin": max(0, dur_min - total_dur),
            "previousSegments": [
                {
                    "segmentOrder": g["segmentOrder"],
                    "duration": g["duration"],
                    "location": (g["lead"].get("location") or "")[:80],
                    "beatCount": len(g["shots"]),
                    "lastAction": ((g["shots"][-1].get("action") or "")[:100]),
                }
                for g in segments[-3:]
            ],
            "note": (
                f"已有 {len(segments)} 段 / {len(shots)} 拍 / {total_dur}s，"
                f"请续写接下来约 {need_seg} 个 segments（每段 {beats} beats），"
                f"补足至至少 {seg_min} 段且总时长≥{dur_min}s。"
            ),
        }
        more_data = chat_json(
            system=system + "\n续写后续片段，不要重复已有 segmentOrder。",
            user=json.dumps(cont_user, ensure_ascii=False),
            temperature=float(runtime.get("temperature") or 0.35),
            max_tokens=20000,
            retries=3,
        )
        if more_data.get("segments"):
            more = _materialize_storyboard_segments(
                project_id=project_id,
                episode_id=episode_id,
                raw_segments=more_data.get("segments") or [],
                available=available,
                style_hint=style_hint,
            )
        else:
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
        # Re-number shotOrder contiguously; keep relative segmentOrder from model when possible.
        base_seg = max((int(s.get("segmentOrder") or 0) for s in shots), default=0)
        for s in more:
            if int(s.get("segmentOrder") or 0) <= base_seg:
                s["segmentOrder"] = base_seg + 1
                base_seg = int(s["segmentOrder"])
        for idx, s in enumerate(more, len(shots) + 1):
            s["shotOrder"] = idx
        shots.extend(more)

    # Cap by segment count first
    segments = group_shots_by_segment(shots)
    if len(segments) > seg_max:
        keep_orders = {g["segmentOrder"] for g in segments[:seg_max]}
        shots = [s for s in shots if int(s.get("segmentOrder") or 0) in keep_orders]

    total_dur = sum(int(s.get("duration") or 0) for s in shots)
    if total_dur < dur_min:
        _top_up_shot_durations(shots, dur_min - total_dur)
        # refresh segmentDuration
        for g in group_shots_by_segment(shots):
            d = sum(int(x.get("duration") or 0) for x in g["shots"])
            for x in g["shots"]:
                x["segmentDuration"] = max(_SEGMENT_DUR_MIN, min(_SEGMENT_DUR_MAX, d))

    while True:
        segments = group_shots_by_segment(shots)
        total_dur = sum(int(s.get("duration") or 0) for s in shots)
        if len(segments) <= seg_min or total_dur <= dur_max:
            break
        drop = segments[-1]["segmentOrder"]
        shots = [s for s in shots if int(s.get("segmentOrder") or 0) != drop]

    segments = group_shots_by_segment(shots)
    if len(segments) < seg_min:
        raise RuntimeError(
            f"片段过少（{len(segments)} 段 / {len(shots)} 拍），"
            f"整集需对齐 {seg_min}–{seg_max} 段（每段 {beats} 镜，约 {seg_dur}s）。请重试拆分。"
        )

    from prompt_consistency import entity_name_set, repair_shot_prompt

    names = entity_name_set(entities)
    for s in shots:
        fixed = repair_shot_prompt(s, entity_names=names)
        if fixed.get("repaired"):
            s["prompt"] = fixed["prompt"]
        s["promptConsistency"] = {"ok": bool(fixed.get("ok")), "issues": fixed.get("issues") or []}

    state["shots"].extend(shots)
    store.save(state)
    # Name-scan prompts/dialogue so workspace left rail is populated even without @tags.
    return bind_episode_refs(store, project_id, episode_id)


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
    last_seg = max((int(s.get("segmentOrder") or 0) for s in existing), default=0) or 1
    beats_in_last = sum(1 for s in existing if int(s.get("segmentOrder") or 0) == last_seg)
    if beats_in_last >= 4:
        last_seg += 1
        beat_index = 1
    else:
        beat_index = beats_in_last + 1
    ts = _now()
    shot = {
        "id": new_id("sh_"),
        "projectId": project_id,
        "episodeId": episode_id,
        "shotOrder": order,
        "segmentOrder": last_seg,
        "beatIndex": beat_index,
        "isSegmentLead": beat_index == 1,
        "location": "",
        "timeOfDay": "",
        "weather": "",
        "openingState": "",
        "setDressing": "",
        "ambientSound": "",
        "segmentDuration": None,
        "prompt": "",
        "duration": 4,
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


def _propagate_segment_video(state: dict, lead: dict) -> None:
    """Copy lead take status/video onto other beats in the same segment."""
    sibs = set(lead.get("_segmentSiblingIds") or [])
    if not sibs:
        return
    vid = lead.get("selectedVideoId")
    version = next((v for v in (lead.get("videos") or []) if v.get("id") == vid), None) if vid else None
    now = _now()
    for s in state.get("shots") or []:
        if s.get("id") not in sibs:
            continue
        if lead.get("status") == "success" and version:
            shared = {**version, "shotId": s["id"], "note": (version.get("note") or "") or "segment-shared"}
            vids = s.setdefault("videos", [])
            if not any(v.get("id") == vid for v in vids):
                vids.append(shared)
            s["selectedVideoId"] = vid
            s["status"] = "success"
            s["error"] = None
            s["staleReason"] = None
            s["providerTaskId"] = lead.get("providerTaskId")
        elif lead.get("status") == "failed":
            s["status"] = "failed"
            s["error"] = lead.get("error") or "片段生成失败"
            s["providerTaskId"] = None
        s["updatedAt"] = now


class EntityQaBlockedError(RuntimeError):
    """Raised when referenced entity stills have not passed QA and force is off."""

    def __init__(self, blockers: list[dict[str, Any]], *, message: str = ""):
        self.blockers = list(blockers or [])
        labels = []
        for b in self.blockers[:6]:
            name = b.get("name") or b.get("entityId") or "?"
            kind = b.get("kindLabel") or b.get("kind") or "素材"
            labels.append(f"{kind}「{name}」")
        summary = "、".join(labels) + ("…" if len(self.blockers) > 6 else "")
        super().__init__(
            message
            or (
                f"素材质检未过，已阻断出片（{len(self.blockers)} 项）：{summary}。"
                "请先重生/复核素材，或传 forceEntityQa=true 强制出片。"
            )
        )


def _selected_entity_image(ent: dict[str, Any] | None) -> dict[str, Any] | None:
    if not ent:
        return None
    sid = ent.get("selectedImageId")
    if not sid:
        return None
    return next((i for i in (ent.get("images") or []) if i.get("id") == sid), None)


def entity_ref_qa_blockers(
    entities_by_id: dict[str, dict[str, Any]],
    entity_ids: list[str] | None,
) -> list[dict[str, Any]]:
    """Return blockers for referenced entities whose selected still is not QA-ready."""
    from prompt_qa import is_soft_pass_qa, qa_meets_bar

    kind_label = {"character": "角色", "scene": "场景", "prop": "道具"}
    blockers: list[dict[str, Any]] = []
    seen: set[str] = set()
    for eid in entity_ids or []:
        eid = str(eid or "").strip()
        if not eid or eid in seen:
            continue
        seen.add(eid)
        ent = entities_by_id.get(eid)
        if not ent:
            blockers.append(
                {
                    "entityId": eid,
                    "name": eid,
                    "kind": "unknown",
                    "kindLabel": "素材",
                    "issue": "missing_entity",
                    "reason": "引用的素材不存在",
                }
            )
            continue
        name = (ent.get("name") or eid).strip() or eid
        kind = str(ent.get("kind") or "unknown")
        label = kind_label.get(kind, "素材")
        img = _selected_entity_image(ent)
        if not img or not img.get("path"):
            blockers.append(
                {
                    "entityId": eid,
                    "name": name,
                    "kind": kind,
                    "kindLabel": label,
                    "issue": "no_image",
                    "reason": "尚无可用参考图",
                }
            )
            continue
        qa = img.get("qa") or {}
        soft = is_soft_pass_qa(qa)
        meets = bool(img.get("qaPass") is True) and qa_meets_bar(qa) and not soft
        if meets:
            continue
        if soft:
            issue = "soft_pass"
            reason = str(qa.get("reason") or "质检无效（软通过/跳过）")
        elif img.get("qaPass") is False or not qa_meets_bar(qa):
            issue = "qa_fail"
            reason = str(qa.get("reason") or ent.get("qaFailReason") or "质检未达标")
        else:
            issue = "qa_pending"
            reason = str(qa.get("reason") or "尚未通过质检")
        blockers.append(
            {
                "entityId": eid,
                "name": name,
                "kind": kind,
                "kindLabel": label,
                "issue": issue,
                "reason": reason[:220],
                "score": qa.get("score"),
            }
        )
    return blockers


def assert_entity_refs_ready_for_video(
    state: dict[str, Any],
    entity_ids: list[str] | None,
    *,
    force: bool = False,
    skip_refs: bool = False,
) -> list[dict[str, Any]]:
    """Hard-gate video generation on entity still QA unless forced or text-only."""
    if force or skip_refs:
        return []
    by_id = {e["id"]: e for e in (state.get("entities") or []) if e.get("id") and not e.get("deletedAt")}
    blockers = entity_ref_qa_blockers(by_id, entity_ids)
    if blockers:
        raise EntityQaBlockedError(blockers)
    return []


def revise_segment(
    store: ProjectStore,
    project_id: str,
    episode_id: str,
    segment_order: int,
    *,
    instruction: str = "",
    model: str = "",
    resolution: str = "720p",
    skip_refs: bool = False,
    start_video: bool = True,
    force_entity_qa: bool = False,
) -> dict:
    """Apply visual / dialogue revisions to a segment, then optionally regenerate its video.

    - Syncs each beat's ``dialogue`` into its prompt (lip-sync line).
    - Optionally rewrites beat prompts with a short ``instruction`` (LLM when available,
      otherwise appends a 画面调整 note).
    - Starts segment video generation when ``start_video`` is true.
    """
    state = store.load(project_id)
    if not state:
        raise FileNotFoundError("project not found")
    ep_shots = [
        s
        for s in (state.get("shots") or [])
        if s.get("episodeId") == episode_id and not s.get("deletedAt")
    ]
    segments = group_shots_by_segment(ep_shots)
    seg = next((g for g in segments if int(g["segmentOrder"]) == int(segment_order)), None)
    if not seg:
        raise FileNotFoundError(f"片段 {segment_order} 不存在")
    if any(s.get("status") == "generating" for s in seg["shots"]):
        raise RuntimeError(f"片段 {segment_order} 正在生成，请稍后再改")

    instruction = (instruction or "").strip()
    rewritten: dict[str, str] = {}
    if instruction:
        try:
            from providers.deepseek import chat_json

            beats_payload = [
                {
                    "beatIndex": int(b.get("beatIndex") or i + 1),
                    "prompt": (b.get("prompt") or "")[:800],
                    "dialogue": (b.get("dialogue") or "")[:200],
                }
                for i, b in enumerate(seg["shots"])
            ]
            data = chat_json(
                system=(
                    "你是短剧分镜改写助手。根据用户的画面调整要求，改写每个 beat 的 prompt。"
                    "保留人物名、台词口型、景别连贯与「承接分镜N」结构；不要加字幕/解说旁白；"
                    "输出 JSON：{beats:[{beatIndex, prompt}]}。"
                ),
                user=(
                    f"画面调整要求：{instruction}\n"
                    f"当前片段 beats：{json.dumps(beats_payload, ensure_ascii=False)}"
                ),
            )
            for item in data.get("beats") or []:
                if not isinstance(item, dict):
                    continue
                bi = int(item.get("beatIndex") or 0)
                p = (item.get("prompt") or "").strip()
                if bi and p:
                    rewritten[bi] = p
        except Exception:
            rewritten = {}

    now = _now()
    for beat in seg["shots"]:
        dialogue = str(beat.get("dialogue") or "").strip()
        bi = int(beat.get("beatIndex") or 0)
        if bi in rewritten:
            prompt = rewritten[bi]
        else:
            prompt = str(beat.get("prompt") or "").strip()
            if instruction:
                note = f"画面调整要求：{instruction}"
                if note not in prompt:
                    prompt = f"{prompt.rstrip('。')}。{note}" if prompt else note
        if dialogue:
            prompt = _normalize_short_drama_prompt(prompt, dialogue=dialogue)
        if prompt != (beat.get("prompt") or ""):
            beat["prompt"] = prompt
            if beat.get("status") in ("success", "stale") and (beat.get("videos") or beat.get("selectedVideoId")):
                beat["status"] = "stale"
                beat["staleReason"] = "画面/台词已调整，请重新生成本段"
            beat["updatedAt"] = now

    # Prefer refreshed refs after dialogue/speaker changes.
    ep = next((e for e in state.get("episodes") or [] if e["id"] == episode_id), None)
    ep_num = int(ep["episodeNumber"]) if ep else None
    entities = [e for e in (state.get("entities") or []) if not e.get("deletedAt")]
    for beat in seg["shots"]:
        beat["referenceEntityIds"] = _resolve_shot_entity_ids(
            beat, entities, require_image=False, episode_number=ep_num
        )

    store.save(state)
    if not start_video:
        return seg["lead"]
    return start_segment_video(
        store,
        project_id,
        episode_id,
        segment_order,
        model=model,
        resolution=resolution,
        skip_refs=skip_refs,
        force_entity_qa=force_entity_qa,
    )


def start_segment_video(
    store: ProjectStore,
    project_id: str,
    episode_id: str,
    segment_order: int,
    *,
    model: str,
    resolution: str,
    skip_refs: bool = False,
    force_entity_qa: bool = False,
) -> dict:
    """Generate one video for a SceneMixer segment (all beats in one Seedance/H3 call)."""
    state = store.load(project_id)
    if not state:
        raise FileNotFoundError("project not found")
    ep_shots = [
        s
        for s in (state.get("shots") or [])
        if s.get("episodeId") == episode_id and not s.get("deletedAt")
    ]
    segments = group_shots_by_segment(ep_shots)
    seg = next((g for g in segments if int(g["segmentOrder"]) == int(segment_order)), None)
    if not seg:
        raise FileNotFoundError(f"片段 {segment_order} 不存在")
    lead = seg["lead"]
    if _reset_stale_segment_generating(seg["shots"]):
        store.save(state)
    if any(s.get("status") == "generating" for s in seg["shots"]):
        raise RuntimeError(f"片段 {segment_order} 正在生成")
    # Union reference images from all beats in the segment.
    ref_ids: list[str] = []
    for s in seg["shots"]:
        for eid in s.get("referenceEntityIds") or []:
            if eid not in ref_ids:
                ref_ids.append(eid)
    # Gate BEFORE marking siblings generating (avoids stuck state on QA block).
    assert_entity_refs_ready_for_video(
        state,
        ref_ids,
        force=force_entity_qa,
        skip_refs=skip_refs,
    )
    # Align each beat's prompt with its dialogue / asset bible before the video call.
    from prompt_consistency import entity_name_set, repair_shot_prompt

    names = entity_name_set(state.get("entities") or [])
    consistency: list[dict[str, Any]] = []
    for s in seg["shots"]:
        fixed = repair_shot_prompt(s, entity_names=names)
        if fixed.get("repaired"):
            s["prompt"] = fixed["prompt"]
            s["updatedAt"] = _now()
        s["promptConsistency"] = {"ok": fixed.get("ok"), "issues": fixed.get("issues") or []}
        if not fixed.get("ok"):
            consistency.append({"shotId": s.get("id"), "issues": fixed.get("issues")})
    if consistency:
        lead["promptConsistency"] = {"ok": False, "shots": consistency}
    combined = build_segment_prompt(seg)
    seg_dur = max(_SEGMENT_DUR_MIN, min(_SEGMENT_DUR_MAX, int(seg.get("duration") or 12)))
    lead["referenceEntityIds"] = ref_ids[:9]
    lead["_segmentPromptOverride"] = combined
    lead["_segmentDurationOverride"] = seg_dur
    lead["_segmentSiblingIds"] = [s["id"] for s in seg["shots"] if s["id"] != lead["id"]]
    if force_entity_qa:
        lead["_forcedEntityQa"] = True
    for s in seg["shots"]:
        if s["id"] == lead["id"]:
            continue
        s["status"] = "generating"
        s["error"] = None
        s["updatedAt"] = _now()
    store.save(state)
    return start_shot_video(
        store,
        project_id,
        lead["id"],
        model=model,
        resolution=resolution,
        skip_refs=skip_refs,
        force_entity_qa=force_entity_qa,
    )


def start_shot_video(
    store: ProjectStore,
    project_id: str,
    shot_id: str,
    *,
    model: str,
    resolution: str,
    skip_refs: bool = False,
    force_entity_qa: bool = False,
) -> dict:
    from providers.media import video_backend

    state = store.load(project_id)
    if not state:
        raise FileNotFoundError("project not found")
    shot = next((s for s in state.get("shots") or [] if s["id"] == shot_id and not s.get("deletedAt")), None)
    if not shot:
        raise FileNotFoundError("shot not found")
    if shot.get("status") == "generating" and not shot.get("_segmentPromptOverride"):
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
    override = (shot.get("_segmentPromptOverride") or "").strip()
    base_prompt = override or _normalize_short_drama_prompt(
        (shot.get("prompt") or "").strip(),
        dialogue=str(shot.get("dialogue") or ""),
    )
    ratio = state["project"].get("ratio") or "9:16"
    duration = int(shot.get("_segmentDurationOverride") or shot.get("duration") or 5)
    duration = max(4, min(15, duration))

    ref_entity_ids = list(shot.get("referenceEntityIds") or [])[:9]
    # Segment path already asserted; re-assert for single-shot / retry paths.
    assert_entity_refs_ready_for_video(
        state,
        ref_entity_ids,
        force=force_entity_qa,
        skip_refs=skip_refs,
    )

    # Prefer first existing entity reference image for I2V (ComfyUI / Seedance).
    ref_paths: list[Path] = []
    content: list[dict] = [{"type": "text", "text": base_prompt}]
    import base64

    if not skip_refs:
        for eid in ref_entity_ids:
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
    if force_entity_qa:
        shot["_forcedEntityQa"] = True
    else:
        shot.pop("_forcedEntityQa", None)
    store.save(state)

    payload: dict[str, Any] = {
        "projectId": project_id,
        "shotId": shot_id,
        "model": model,
        "resolution": resolution,
        "backend": backend,
        "forceEntityQa": force_entity_qa,
        "basePrompt": base_prompt,
        "ratio": ratio,
        "duration": duration,
        "refPath": str(ref_paths[0]) if ref_paths else None,
    }

    from providers.video_factory import require_video_backend

    require_video_backend(backend).submit(
        store=store,
        shot=shot,
        state=state,
        payload=payload,
        content=content,
        model=model,
        ratio=ratio,
        resolution=resolution,
        duration=duration,
    )
    return shot


def run_shot_video_job(
    store: ProjectStore,
    project_id: str,
    shot_id: str,
    *,
    model: str,
    resolution: str,
    backend: str,
    force_entity_qa: bool = False,
    base_prompt: str = "",
    ratio: str = "9:16",
    duration: int = 5,
    ref_path: str | None = None,
    seedance_task_id: str | None = None,
) -> None:
    """Blocking video job. The runner is looked up from the video backend registry."""
    from providers.video_factory import run_registered_video_job

    run_registered_video_job(
        backend,
        store=store,
        project_id=project_id,
        shot_id=shot_id,
        model=model,
        resolution=resolution,
        force_entity_qa=force_entity_qa,
        base_prompt=base_prompt,
        ratio=ratio,
        duration=duration,
        ref_path=ref_path,
        seedance_task_id=seedance_task_id,
    )


def _judge_video_file(
    path: Path,
    *,
    prompt: str,
    entities: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Prompt-fit QA for a finished video file; attaches qaPass using the shared score bar."""
    try:
        from prompt_qa import judge_video_against_prompt, qa_meets_bar, qa_min_score

        qa = judge_video_against_prompt(
            path,
            prompt=prompt,
            kind="shot",
            entities=entities or [],
        )
        qa["qaPass"] = qa_meets_bar(qa, min_score=qa_min_score())
        return qa
    except Exception as exc:  # noqa: BLE001
        # Never soft-pass — that promoted rainy-night→daytime garden mismatches.
        return {
            "pass": False,
            "score": 0,
            "reason": f"qa_exception:{exc}",
            "skipped": True,
            "qaPass": False,
        }


def _wait_shot_terminal(
    store: ProjectStore,
    project_id: str,
    shot_id: str,
    *,
    timeout_s: float = 900,
) -> dict:
    import time

    deadline = time.time() + max(30.0, float(timeout_s))
    while time.time() < deadline:
        shot = poll_shot(store, project_id, shot_id)
        status = str(shot.get("status") or "")
        if status in {"success", "failed", "cancelled"}:
            return shot
        time.sleep(4)
    shot = poll_shot(store, project_id, shot_id)
    if shot.get("status") == "generating":
        shot["status"] = "failed"
        shot["error"] = shot.get("error") or "生成超时"
        shot["updatedAt"] = _now()
        state = store.load(project_id) or {}
        for s in state.get("shots") or []:
            if s.get("id") == shot_id:
                s.update(shot)
                break
        store.save(state)
    return poll_shot(store, project_id, shot_id)


def _reset_stale_segment_generating(shots: list[dict[str, Any]], *, max_age_s: float = 20 * 60) -> bool:
    """Clear generating flags left behind after a worker restart or a timed-out render."""
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    changed = False
    for shot in shots:
        if shot.get("status") != "generating":
            continue
        updated = str(shot.get("updatedAt") or shot.get("createdAt") or "")
        age_s = max_age_s
        try:
            ts = datetime.fromisoformat(updated.replace("Z", "+00:00"))
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            age_s = (now - ts).total_seconds()
        except Exception:
            age_s = max_age_s
        if age_s < max_age_s:
            continue
        shot["status"] = "pending"
        shot["error"] = "上次生成超时，已自动重置"
        shot["providerTaskId"] = None
        shot["updatedAt"] = _now()
        changed = True
    return changed


def _segment_video_already_passed(lead: dict[str, Any] | None) -> bool:
    if not lead or lead.get("staleReason") or lead.get("status") != "success":
        return False
    selected = next(
        (v for v in (lead.get("videos") or []) if v.get("id") == lead.get("selectedVideoId")),
        None,
    )
    return bool(selected and selected.get("qaPass") is True and selected.get("path"))


def ensure_segment_video_qa(
    store: ProjectStore,
    project_id: str,
    episode_id: str,
    segment_order: int,
    *,
    model: str,
    resolution: str,
    skip_refs: bool = False,
    max_attempts: int | None = None,
) -> dict:
    """Generate a segment video and revise until prompt-fit QA passes or attempts are exhausted."""
    from prompt_qa import video_qa_max_attempts

    attempts = max_attempts if max_attempts is not None else video_qa_max_attempts()
    attempts = max(1, min(10, int(attempts)))
    state = store.load(project_id) or {}
    ep_shots = [
        s
        for s in (state.get("shots") or [])
        if s.get("episodeId") == episode_id and not s.get("deletedAt")
    ]
    seg = next(
        (g for g in group_shots_by_segment(ep_shots) if int(g["segmentOrder"]) == int(segment_order)),
        None,
    )
    if seg and _segment_video_already_passed(seg.get("lead")):
        return seg["lead"]
    last_reason = ""
    lead: dict[str, Any] | None = None
    for attempt in range(1, attempts + 1):
        if attempt == 1 and not last_reason:
            lead = start_segment_video(
                store,
                project_id,
                episode_id,
                segment_order,
                model=model,
                resolution=resolution,
                skip_refs=skip_refs,
            )
        else:
            instruction = (
                f"质检重试 {attempt}/{attempts}：画面必须严格符合分镜提示词。"
                + (f"失败原因：{last_reason}" if last_reason else "")
            )
            lead = revise_segment(
                store,
                project_id,
                episode_id,
                segment_order,
                instruction=instruction,
                model=model,
                resolution=resolution,
                skip_refs=skip_refs,
                start_video=True,
            )
        lead_id = str((lead or {}).get("id") or "")
        if not lead_id:
            raise RuntimeError(f"片段 {segment_order} 未返回 lead shot")
        finished = _wait_shot_terminal(store, project_id, lead_id, timeout_s=1200)
        vids = finished.get("videos") or []
        selected = next((v for v in vids if v.get("id") == finished.get("selectedVideoId")), None)
        qa = (selected or {}).get("qa") or {}
        qa_pass = bool((selected or {}).get("qaPass") or qa.get("qaPass"))
        if finished.get("status") == "success" and qa_pass:
            return finished
        last_reason = str(
            finished.get("error")
            or qa.get("reason")
            or "mismatch"
        )[:240]
        # Reset failed lead so revise can re-submit cleanly.
        state = store.load(project_id) or {}
        for s in state.get("shots") or []:
            if s.get("id") == lead_id and s.get("status") == "failed":
                s["status"] = "pending"
                s["providerTaskId"] = None
                s["updatedAt"] = _now()
        store.save(state)
    raise RuntimeError(
        f"片段 {segment_order} 质检未达标（{attempts} 次）：{last_reason or 'unknown'}"
    )


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
    ready = [
        s
        for s in state.get("shots") or []
        if s.get("episodeId") == episode_id and not s.get("deletedAt") and s.get("selectedVideoId")
    ]
    has_segments = any(int(s.get("segmentOrder") or 0) > 0 for s in ready)
    if has_segments:
        # One timeline clip per SceneMixer segment (lead beat holds the take).
        ready = [
            s
            for s in ready
            if s.get("isSegmentLead") or int(s.get("beatIndex") or 0) == 1
        ]
    shots = sorted(ready, key=lambda s: (int(s.get("segmentOrder") or 0), int(s.get("shotOrder") or 0)))
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
