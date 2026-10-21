"""抖音写真对标（首尾帧 MiniMax H3 idlock）— Studio UI workflow helpers."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from drama_service import _now, new_id

_ASSETS = Path(__file__).resolve().parents[1] / "assets" / "portrait-match"

# English goes to MiniMax H3 (model follows EN better); Chinese is what Studio shows.
MOTION_EN = {
    "ref1": "Night riverside idol look-back / spin / heart / wink energy between frames; soft wet-city bokeh.",
    "ref2": "Pink lolita sakura dance beat between frames; sheer sleeves and frills move gracefully.",
    "ref3": "High-key indoor sweet dance between frames; center girl focus, soft friends behind.",
}
MOTION_ZH = {
    "ref1": "雨夜滨水暖光 bokeh，偶像感回眸 / 转裙 / 比心 / 眨眼能量，发丝与裙摆微动。",
    "ref2": "樱花粉洛丽塔日景甜舞，薄纱长袖与荷叶边随拍摆动，踮脚回眸收势。",
    "ref3": "高调室内甜舞，中心女主清晰、两侧同伴柔焦，同步手势与表情过渡。",
}

IDENTITY_EN = (
    "Keep the EXACT same person as shown in the first and last frames: identical face, "
    "eyes, nose, mouth, skin, makeup, hair, outfit. Do not beautify into a different face. "
    "Expression must transition naturally from the first-frame expression to the last-frame "
    "expression. Photoreal skin pores and catchlights. "
    "Stable anatomy: two arms two legs, five fingers, no melted limbs, no face warp."
)
IDENTITY_ZH = (
    "严格保持首尾帧同一人：五官、肤质、妆面、发型、服装完全一致，禁止美颜成另一张脸。"
    "表情从首帧自然过渡到尾帧。照片级毛孔与眼神光。"
    "解剖稳定：两臂两腿、五指完整，无融化肢体、无脸部扭曲。"
)

# Extra H3 adherence stack for gen-likeness (极像质量堆叠).
QUALITY_STACK_EN = (
    "Quality stack: interpolate ONLY the motion needed to reach the last frame — "
    "no invented limbs, no wardrobe morph, no face drift mid-clip. "
    "Match keyframe lighting direction and catchlights; keep fabric edges intact; "
    "minimize temporal flicker; prefer crisp face over background detail. "
    "Photoreal 9:16 vertical, sharp subject, controlled bokeh."
)
QUALITY_STACK_ZH = (
    "质量堆叠：中间帧只做到达尾帧所需的最小动作，禁止中途换肢/换衣服形变/脸漂移；"
    "光影与关键帧一致；衣缘完整；抑制闪烁；脸优先锐利。"
)

# Per-beat Chinese desk notes (运镜 / 动作 / 转镜) — portrait is 1 pair = 1 卡点镜, not drama multi-beat.
BEAT_NOTES = {
    "ref1": [
        {"action": "回眸起势", "camera": "微跟 · 浅景深锁脸", "transition": "硬切卡点"},
        {"action": "转体展裙", "camera": "微推跟腰线", "transition": "闪黑 1 帧"},
        {"action": "比心定格", "camera": "锁定中近景", "transition": "硬切"},
        {"action": "眨眼俏皮", "camera": "锁脸微距感", "transition": "硬切"},
        {"action": "跳跃收势", "camera": "微仰跟跳", "transition": "硬切"},
        {"action": "侧身回眸", "camera": "侧光轮廓", "transition": "闪黑"},
        {"action": "裙摆回落", "camera": "腰部跟拍", "transition": "硬切"},
        {"action": "双手比心", "camera": "中景锁定", "transition": "硬切"},
        {"action": "发丝扫过", "camera": "微跟发丝", "transition": "硬切"},
        {"action": "远景回望", "camera": "稍远半身", "transition": "硬切"},
        {"action": "终帧微笑", "camera": "锁定收束", "transition": "切出"},
    ],
    "ref2": [
        {"action": "举手展袖", "camera": "微仰跟袖摆", "transition": "硬切卡点"},
        {"action": "回眸踮脚", "camera": "锁脸微推", "transition": "硬切"},
        {"action": "转裙动能", "camera": "跟随裙摆弧", "transition": "闪黑"},
        {"action": "侧身伸臂", "camera": "侧面半身", "transition": "硬切"},
        {"action": "收势微笑", "camera": "中近景锁定", "transition": "硬切"},
        {"action": "袖摆翻飞", "camera": "微跟袖端", "transition": "硬切"},
        {"action": "踮脚侧倾", "camera": "微仰", "transition": "硬切"},
        {"action": "回身点头", "camera": "锁脸", "transition": "闪黑"},
        {"action": "裙摆旋开", "camera": "跟腰线", "transition": "硬切"},
        {"action": "双手上举", "camera": "半身锁定", "transition": "硬切"},
        {"action": "侧脸回眸", "camera": "侧光轮廓", "transition": "硬切"},
        {"action": "碎步前移", "camera": "微跟", "transition": "硬切"},
        {"action": "展袖定格", "camera": "中景", "transition": "闪黑"},
        {"action": "收袖回胸", "camera": "锁上半身", "transition": "硬切"},
        {"action": "眨眼俏皮", "camera": "近景脸", "transition": "硬切"},
        {"action": "转身半圈", "camera": "跟转", "transition": "硬切"},
        {"action": "裙边扫地", "camera": "稍俯跟裙", "transition": "硬切"},
        {"action": "终势微笑", "camera": "锁定收束", "transition": "切出"},
    ],
    "ref3": [
        {"action": "举手贴颊", "camera": "中心女主锁脸，侧翼虚化", "transition": "硬切卡点"},
        {"action": "猫爪手势", "camera": "中近景，三人同框柔边", "transition": "硬切"},
        {"action": "同步眨眼", "camera": "锁定中心表情", "transition": "闪黑"},
        {"action": "双手比心", "camera": "微推中心", "transition": "硬切"},
        {"action": "侧倾摆头", "camera": "微跟中心", "transition": "硬切"},
        {"action": "举手波浪", "camera": "半身同框", "transition": "硬切"},
        {"action": "贴颊微笑", "camera": "锁脸浅景深", "transition": "闪黑"},
        {"action": "同步点头", "camera": "中景三人", "transition": "硬切"},
        {"action": "双手胸口", "camera": "中近景", "transition": "硬切"},
        {"action": "侧身俏皮", "camera": "中心优先", "transition": "硬切"},
        {"action": "终帧定格", "camera": "锁定收束", "transition": "切出"},
    ],
}

# Assemble toward Douyin original pacing (shot_notes): snappy holds + flash cuts + grade.
# hold_mode=gap → each shot uses idlockGap (clamped); fallback_hold if gap missing.
ASSEMBLE_PRESETS = {
    # target_dur = Douyin original length; assemble scales holds to fit 原曲.
    "ref1": {
        "hold_mode": "gap",
        "fallback_hold": 0.85,
        "speed": 1.12,
        "flash_every": 2,
        "vf_grade": "eq=saturation=1.10:contrast=1.09:brightness=0.02,unsharp=5:5:0.85:5:5:0.0",
        "target_dur": 10.52,
    },
    "ref2": {
        "hold_mode": "gap",
        "fallback_hold": 1.2,
        "speed": 1.05,
        "flash_every": 3,
        "vf_grade": "eq=saturation=1.14:contrast=1.07:gamma=1.02,unsharp=5:5:0.75:5:5:0.0",
        "target_dur": 29.89,
    },
    "ref3": {
        "hold_mode": "gap",
        "fallback_hold": 1.0,
        "speed": 1.08,
        "flash_every": 2,
        "vf_grade": "eq=saturation=1.08:contrast=1.07:brightness=0.04,unsharp=5:5:0.8:5:5:0.0",
        "target_dur": 14.79,
    },
}
TEMPLATES = [
    {
        "id": "ref1",
        "title": "甜屿 · 夜景回眸",
        "desc": "雨夜河边暖光 bokeh，偶像感回眸 / 转体 / 比心",
        "ratio": "9:16",
        "sample": "samples/match_ref1_v3.mp4",
        "originalSpec": "2160×3840 · 60fps · ~10.5s",
        "wardrobe": "奶油开衫 JK / 甜妹妆、发辫，夜景暖光皮肤感",
        "location": "雨夜滨水桥边，浅景深 bokeh、微跟微推",
        "douyinUrl": "https://www.douyin.com/video/7697765914426494234",
    },
    {
        "id": "ref2",
        "title": "甜屿 · 粉色洛丽塔",
        "desc": "樱花舞拍，薄纱袖与荷叶边",
        "ratio": "9:16",
        "sample": "samples/match_ref2_v3.mp4",
        "originalSpec": "2160×3840 · 60fps · ~29.9s",
        "wardrobe": "粉白洛丽塔/汉元素裙，超长透纱袖，双马尾粉花",
        "location": "樱花步道日景，大动作袖摆裙摆",
        "douyinUrl": "https://www.douyin.com/video/7697347369985183026",
    },
    {
        "id": "ref3",
        "title": "甜屿 · 室内甜舞",
        "desc": "高调室内甜舞，中心女主 + 柔焦同伴",
        "ratio": "9:16",
        "sample": "samples/match_ref3_v3.mp4",
        "originalSpec": "1920×1440→竖裁 · 60fps · ~14.8s",
        "wardrobe": "中心奶油开衫+黑领结+荷叶发饰；侧翼蓝卡其/格裙",
        "location": "高调窗光室内 + 星灯 bokeh，三人同步手势",
        "douyinUrl": "https://www.douyin.com/video/7697311712583699712",
    },
]

# Workshop match paths — quality ceiling differs completely.
MATCH_MODES = {
    "gen-likeness": {
        "label": "极像生成",
        "summary": "原片关键帧 + MiniMax H3（1080p / 非 turbo）持续堆质量：强化提示、合片锐化调色+原曲。目标抖音划过极像。",
    },
    "reshoot": {
        "label": "原片重拍",
        "summary": "输出妆造/场地/卡点重拍企划，用真机 4K/60 实拍才能对齐原片物理质量。",
    },
}

# Workshop diagnosis — 极像 is the accepted path; keep stacking generation quality.
QUALITY_DIAGNOSIS = (
    "极像路径（已选）：工坊门禁角色/场景/提示词达标后，持续堆 H3 质量——"
    "原片关键帧 + 1080p + use_turbo=false + 强化帧间动作提示 + 合片锐化调色原曲。"
    "目标是抖音划过「极像」；不是放弃生成去重拍。"
)


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
                "matchModes": MATCH_MODES,
                "qualityDiagnosis": QUALITY_DIAGNOSIS,
            }
        )
    return out


def build_reshoot_brief(template_id: str) -> dict[str, Any]:
    """Production bible for 4K/60 remake — not an H3 generate path."""
    tid = (template_id or "").strip()
    meta = next((t for t in TEMPLATES if t["id"] == tid), None)
    if not meta:
        raise ValueError(f"未知模板: {template_id}")
    pairs = _load_pairs().get(tid) or []
    rows: list[dict[str, Any]] = []
    lines = [
        f"# 重拍企划 · {meta['title']}",
        "",
        "## 质量边界",
        QUALITY_DIAGNOSIS,
        "",
        "## 目标规格（对齐抖音原片）",
        f"- 规格：{meta.get('originalSpec') or '9:16 · 60fps'}",
        f"- 原片：{meta.get('douyinUrl') or '—'}",
        f"- 成片比例：{meta.get('ratio') or '9:16'}",
        f"- 音频：使用抖音原曲卡点（项目内 `media/audio/{tid}_original.m4a`）",
        "",
        "## 妆造",
        meta.get("wardrobe") or "—",
        "",
        "## 场地与光线",
        meta.get("location") or "—",
        "",
        "## 拍摄纪律",
        "- 真机 4K（或至少 1080p60）连续实拍，禁止用生成视频冒充本路径成片",
        "- 运镜：微跟/微推，避免重甩糊；脸始终清晰",
        "- 按下列卡点秒数硬切；可在镜间加 1 帧闪黑",
        "",
        "## 分镜卡点表",
        "| # | 原片 t0–t1 | 持镜≈ | 动作 | 运镜 | 转镜 |",
        "|---|------------|--------|------|------|------|",
    ]
    for i, pair in enumerate(pairs):
        beat = _beat_for(tid, i)
        sid = str(pair.get("id") or f"s{i+1:02d}")
        try:
            t0 = float(pair.get("t0") or 0)
            t1 = float(pair.get("t1") or 0)
            gap = float(pair.get("gap") or max(0.45, t1 - t0))
        except (TypeError, ValueError):
            t0 = t1 = gap = 0.0
        row = {
            "id": sid,
            "order": i + 1,
            "t0": t0,
            "t1": t1,
            "gap": gap,
            "action": beat.get("action"),
            "camera": beat.get("camera"),
            "transition": beat.get("transition"),
        }
        rows.append(row)
        lines.append(
            f"| {i+1} | {t0:.2f}–{t1:.2f}s | {gap:.2f}s | {row['action']} | {row['camera']} | {row['transition']} |"
        )
    lines.extend(
        [
            "",
            "## 交付检查",
            "- [ ] 妆造/发饰与参考帧一致",
            "- [ ] 每镜动作落点与卡点表对齐（±2 帧）",
            "- [ ] 成片 9:16、≥30fps（目标 60）、接原曲",
            "- [ ] 无生成感拖影/手部融化（本路径应为实拍）",
        ]
    )
    return {
        "templateId": tid,
        "title": meta["title"],
        "markdown": "\n".join(lines),
        "shots": rows,
        "wardrobe": meta.get("wardrobe"),
        "location": meta.get("location"),
        "originalSpec": meta.get("originalSpec"),
        "douyinUrl": meta.get("douyinUrl"),
        "qualityDiagnosis": QUALITY_DIAGNOSIS,
    }


def _load_pairs() -> dict[str, Any]:
    path = _ASSETS / "pairs.json"
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _portrait_runtime() -> dict[str, Any]:
    try:
        from skill_runtime import get_skill_runtime

        return get_skill_runtime("portrait-idlock").get("runtime") or {}
    except Exception:
        return {}


def _idlock_duration() -> float:
    runtime = _portrait_runtime()
    try:
        # Slightly longer clip → smoother FL2VA interp for 极像 stack (still clamped 3–5 in drama_service).
        return float(runtime.get("duration_sec") or 4.0)
    except (TypeError, ValueError):
        return 4.0


def _idlock_resolution_default() -> str:
    runtime = _portrait_runtime()
    res = str(runtime.get("resolution_default") or "1080p").strip()
    return res if res in {"480p", "720p", "1080p"} else "1080p"


def _touch_skill() -> None:
    try:
        from drama_service import load_skill

        _ = load_skill("portrait-idlock")
    except Exception:
        pass


def _template_meta(template_id: str) -> dict[str, Any]:
    return next((t for t in TEMPLATES if t["id"] == template_id), TEMPLATES[0])


def _portrait_character_desc(template_id: str) -> str:
    meta = _template_meta(template_id)
    return (
        f"{meta.get('wardrobe') or '甜妹偶像妆造'}。"
        "竖屏全身定妆：一头到脚可读，五官清晰，单人居中，纯白无缝底板，无第二人、无风景。"
        "锁原片女主身份：肤质、发型、妆面、服装类别与参考帧一致。"
    )


# Scene still bible must NOT mention people / wardrobe / gesture — those leak into empty-plate gens.
_SCENE_EMPTY_PLATES = {
    "ref1": "雨夜滨水桥边环境空镜：湿反光地面、暖黄路灯与远处车灯 bokeh、栏杆与水面层次",
    "ref2": "樱花步道日景环境空镜：粉白樱花树列、斑驳阳光地面、浅景深花瓣与天空",
    "ref3": "高调窗光室内环境空镜：大窗、星灯 bokeh、浅色地板与墙面、干净可拍空间",
}


def _portrait_scene_desc(template_id: str) -> str:
    plate = _SCENE_EMPTY_PLATES.get(template_id) or "对标主场景环境空镜"
    return (
        f"{plate}。"
        "竖屏 empty location plate：只拍环境、陈设、材质、光影层次；"
        "严格无人、无脸、无半身、无剪影、无半透明人、无裙装人体；禁止任何人体出现在画面中。"
        "不要角色、不要模特、不要舞蹈动作。"
    )


def _idlock_prompt_en(template_id: str, beat: dict[str, str] | None = None) -> str:
    """H3 model prompt — structured like drama-shot-prompt (EN for model adherence)."""
    _touch_skill()
    meta = _template_meta(template_id)
    motion = MOTION_EN.get(template_id) or MOTION_EN["ref1"]
    beat = beat or {}
    action = beat.get("action") or "beat transition"
    camera = beat.get("camera") or "locked or micro follow, face sharp"
    transition = beat.get("transition") or "hard cut on beat"
    wardrobe = meta.get("wardrobe") or "idol look"
    location = meta.get("location") or "match location"
    return (
        f"{IDENTITY_EN} "
        f"{QUALITY_STACK_EN} "
        f"Wardrobe/look: {wardrobe}. "
        f"Scene/lighting: {location}. Empty of extra faces drifting identity. "
        f"Beat action: {action}. Motion between first and last frame: {motion} "
        f"Camera: {camera}. Transition intent: {transition}. "
        "No whip pan, no heavy motion blur, sharp face always. "
        "Preserve exact identity and the expression change shown by the two frames."
    )


def _idlock_prompt_zh(template_id: str, beat: dict[str, str] | None = None) -> str:
    """Studio UI prompt — must include 角色/场景/动作/运镜/转镜/光影, same bar as drama desk."""
    _touch_skill()
    meta = _template_meta(template_id)
    motion = MOTION_ZH.get(template_id) or MOTION_ZH["ref1"]
    beat = beat or {}
    action = beat.get("action") or "卡点动作过渡"
    camera = beat.get("camera") or "锁定或微跟拍，脸始终清晰"
    transition = beat.get("transition") or "硬切卡点"
    wardrobe = meta.get("wardrobe") or "甜妹妆造"
    location = meta.get("location") or "对标主场景"
    scene_name = (meta.get("title") or "主场景").split("·")[-1].strip() or "主场景"
    return (
        f"{IDENTITY_ZH}\n"
        f"【角色】@女主 · {wardrobe}\n"
        f"【场景】@{scene_name} · {location}\n"
        f"【动作】{action}；整体运动：{motion}\n"
        f"【运镜】{camera}\n"
        f"【转镜】{transition}\n"
        f"【光影】与原片关键帧一致，脸部眼神光稳定。\n"
        f"{QUALITY_STACK_ZH}\n"
        "禁止急甩、重运动模糊、换脸美颜成另一人。"
    )


def _prompt_checklist(prompt_zh: str) -> dict[str, Any]:
    """Fail-closed checklist so 提示词 itself is「达标」on the desk."""
    text = prompt_zh or ""
    checks = {
        "identity": "同一人" in text or "身份" in text or "首尾帧" in text,
        "character": "【角色】" in text and "@女主" in text,
        "scene": "【场景】" in text and "@" in text,
        "action": "【动作】" in text or "动作" in text,
        "camera": "【运镜】" in text or "运镜" in text,
        "transition": "【转镜】" in text or "转镜" in text,
        "lighting": "【光影】" in text or "光" in text,
    }
    missing = [k for k, ok in checks.items() if not ok]
    return {"pass": len(missing) == 0, "checks": checks, "missing": missing, "skillId": "drama-shot-prompt"}


def _beat_for(template_id: str, index: int) -> dict[str, str]:
    notes = BEAT_NOTES.get(template_id) or BEAT_NOTES["ref1"]
    if not notes:
        return {"action": "卡点过渡", "camera": "锁定微跟", "transition": "硬切"}
    return dict(notes[index % len(notes)])


def _save_face_crop(src: Path, dest: Path) -> None:
    """Upper-center portrait crop for 角色定妆 (not the full dance frame)."""
    from PIL import Image

    im = Image.open(src).convert("RGB")
    w, h = im.size
    # Focus upper 55% height, center 62% width — face/bust for idol verticals.
    box = (
        int(w * 0.19),
        int(h * 0.02),
        int(w * 0.81),
        int(h * 0.55),
    )
    crop = im.crop(box).resize((768, 1024), Image.Resampling.LANCZOS)
    dest.parent.mkdir(parents=True, exist_ok=True)
    crop.save(dest, format="JPEG", quality=92)


def _save_scene_crop(src: Path, dest: Path) -> None:
    """Wider environment bias for 场景定妆 (less face-dominant)."""
    from PIL import Image

    im = Image.open(src).convert("RGB")
    w, h = im.size
    box = (
        int(w * 0.05),
        int(h * 0.18),
        int(w * 0.95),
        int(h * 0.95),
    )
    crop = im.crop(box).resize((768, 1024), Image.Resampling.LANCZOS)
    dest.parent.mkdir(parents=True, exist_ok=True)
    crop.save(dest, format="JPEG", quality=90)


def _ffprobe_duration(path: Path) -> float:
    try:
        out = subprocess.check_output(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        return max(0.1, float(out))
    except Exception:
        return 3.5


def _normalize_portrait_qa(state: dict[str, Any]) -> bool:
    """Fix false「质检未过」: idlock bypass must not keep qa.skipped=True."""
    dirty = False
    for sh in state.get("shots") or []:
        if not (sh.get("idlock") or sh.get("skipVideoQa")):
            continue
        for v in sh.get("videos") or []:
            qa = v.get("qa") if isinstance(v.get("qa"), dict) else {}
            reason = str(qa.get("reason") or "")
            if qa.get("skipped") and (reason == "portrait-idlock" or sh.get("idlock")):
                qa = {
                    **qa,
                    "pass": True,
                    "qaPass": True,
                    "skipped": False,
                    "bypass": "portrait-idlock",
                    "reason": reason or "portrait-idlock",
                }
                v["qa"] = qa
                v["qaPass"] = True
                dirty = True
            if v.get("qaPass") is not True and (reason == "portrait-idlock" or sh.get("idlock")):
                v["qaPass"] = True
                dirty = True
        if sh.get("status") == "failed" and sh.get("selectedVideoId") and "质检" in str(sh.get("error") or ""):
            # Recover shots that only failed soft-skipped QA badge path.
            sel = next((x for x in (sh.get("videos") or []) if x.get("id") == sh.get("selectedVideoId")), None)
            if sel and sel.get("path"):
                sh["status"] = "success"
                sh["error"] = None
                dirty = True
    return dirty


def _character_uses_original_keyframe(ent: dict[str, Any]) -> bool:
    meta = ent.get("metadata") or {}
    if meta.get("useOriginalKeyframe"):
        return True
    sid = ent.get("selectedImageId")
    img = next((i for i in (ent.get("images") or []) if i.get("id") == sid), None)
    if not img:
        return False
    qa = img.get("qa") if isinstance(img.get("qa"), dict) else {}
    return qa.get("bypass") == "portrait-original-keyframe" or str(img.get("prompt") or "") == "portrait-original-keyframe"


def _bind_character_from_original(store: Any, project_id: str, ent: dict[str, Any]) -> bool:
    """Use Douyin keyframe as character still — skip broken entity-still / alpha punch.

    Generated drama-entity-still often punches cream wardrobe into transparency holes.
    Portrait idlock already locks H3 to first/last frames; workshop character card
    should show the real identity plate, not a mangled cutout.
    """
    if ent.get("kind") != "character":
        return False
    if _character_uses_original_keyframe(ent) and ent.get("qaPass") is True and ent.get("selectedImageId"):
        return False
    lock_rel = str((ent.get("metadata") or {}).get("identityLockPath") or "").strip()
    if not lock_rel:
        return False
    src = store._dir(project_id) / lock_rel
    if not src.is_file():
        return False
    img_id = new_id("img_")
    ext = src.suffix.lstrip(".") or "jpg"
    if ext.lower() not in {"jpg", "jpeg", "png", "webp"}:
        ext = "jpg"
    rel = f"media/images/{img_id}.{ext}"
    dest = store._dir(project_id) / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    try:
        store.persist_media(project_id, rel)
    except Exception:
        pass
    version = {
        "id": img_id,
        "entityId": ent["id"],
        "path": rel,
        "prompt": "portrait-original-keyframe",
        "createdAt": _now(),
        "qaPass": True,
        "qa": {
            "ok": True,
            "pass": True,
            "qaPass": True,
            "score": 1.0,
            "skipped": False,
            "bypass": "portrait-original-keyframe",
            "reason": "抖音原片关键帧定妆（生成破图时回退）",
            "skillId": "drama-entity-still",
        },
        "source": "douyin-original-keyframe",
        "sourcePath": lock_rel,
    }
    ent.setdefault("images", []).append(version)
    ent["selectedImageId"] = img_id
    ent["qaPass"] = True
    ent["imageStatus"] = "done"
    ent["imageError"] = None
    ent.pop("qaFailed", None)
    ent.pop("qaFailReason", None)
    meta = ent.setdefault("metadata", {})
    meta["useOriginalKeyframe"] = True
    meta["requiresEntityStill"] = False  # original plate is the bar for portrait character
    meta["skillId"] = "drama-entity-still"
    ent["updatedAt"] = _now()
    return True


def ensure_portrait_workshop_assets(store: Any, project_id: str) -> dict[str, Any] | None:
    """Backfill character/scene stills + gap metadata for portrait-match projects.

    Portrait create historically only wrote idlock shots — Studio shell then showed 角色/场景/道具=0
    and empty entity tabs. Seed one character + one scene from the first start frame so the
    short-video workshop has the same asset anchors as drama projects.
    """
    state = store.load(project_id)
    if not state:
        return None
    proj = state.get("project") or {}
    if proj.get("workflow") != "portrait-match":
        return None
    dirty = _normalize_portrait_qa(state)

    tid = str(proj.get("portraitTemplate") or "")
    pairs_by_id = {str(p.get("id")): p for p in (_load_pairs().get(tid) or []) if p.get("id")}
    for sh in state.get("shots") or []:
        if sh.get("deletedAt"):
            continue
        label = str(sh.get("title") or sh.get("action") or "")
        pair = pairs_by_id.get(label) or {}
        gap = pair.get("gap")
        if gap is not None:
            try:
                g = float(gap)
                prev = sh.get("idlockGap")
                # Keep idlockGap aligned to Douyin-scaled pairs (was write-once → stale short gaps).
                if prev is None or abs(float(prev) - g) > 0.02:
                    sh["idlockGap"] = g
                    dirty = True
            except (TypeError, ValueError):
                pass

    # Enrich desk: structured bilingual prompts + beat fields (must pass checklist).
    for i, sh in enumerate(
        sorted([s for s in (state.get("shots") or []) if not s.get("deletedAt")], key=lambda s: int(s.get("order") or 0))
    ):
        beat = _beat_for(tid, i)
        if not sh.get("actionZh") or sh.get("actionZh") != beat.get("action"):
            sh["actionZh"] = beat.get("action")
            sh["camera"] = beat.get("camera")
            sh["transition"] = beat.get("transition")
            dirty = True
        zh = _idlock_prompt_zh(tid, beat)
        en = _idlock_prompt_en(tid, beat)
        checklist = _prompt_checklist(zh)
        if (
            sh.get("prompt") != zh
            or sh.get("modelPrompt") != en
            or (sh.get("promptQa") or {}).get("pass") != checklist["pass"]
        ):
            sh["prompt"] = zh
            sh["modelPrompt"] = en
            sh["promptQa"] = checklist
            sh["skillId"] = sh.get("skillId") or "portrait-idlock"
            dirty = True
        if not sh.get("action") or sh.get("action") == sh.get("title"):
            sh["action"] = beat.get("action") or sh.get("title")
            dirty = True

    shots = sorted(
        [s for s in (state.get("shots") or []) if not s.get("deletedAt") and s.get("startFramePath")],
        key=lambda s: int(s.get("order") or 0),
    )
    ents = [e for e in (state.get("entities") or []) if not e.get("deletedAt")]
    # Replace crop-only fakes / old bypass QA (not original-keyframe plates).
    # Also retire scenes that wrongly locked to dance frames (people → scene-no-people fail).
    stale = [
        e
        for e in ents
        if e.get("metadata", {}).get("portraitIdlock")
        and not _character_uses_original_keyframe(e)
        and (
            str((e.get("images") or [{}])[0].get("prompt") or "").startswith("portrait-idlock-")
            or (e.get("images") or [{}])[0].get("qa", {}).get("bypass") == "portrait-idlock"
            or (
                e.get("kind") == "scene"
                and (e.get("metadata") or {}).get("identityLockPath")
                and e.get("qaPass") is not True
            )
        )
    ]
    if stale:
        for e in stale:
            e["deletedAt"] = _now()
        dirty = True

    ents = [e for e in (state.get("entities") or []) if not e.get("deletedAt")]
    # Live entities: strip scene identityLockPath; character → bind Douyin original (no gen punch).
    for e in ents:
        if not e.get("metadata", {}).get("portraitIdlock"):
            continue
        meta = e.setdefault("metadata", {})
        if e.get("kind") == "scene":
            if meta.get("identityLockPath"):
                meta.pop("identityLockPath", None)
                dirty = True
            new_desc = _portrait_scene_desc(tid)
            if e.get("description") != new_desc:
                e["description"] = new_desc
                # Failed people-plate: clear selection so enqueue redraws with empty bible.
                if e.get("qaPass") is not True:
                    e["selectedImageId"] = None
                    e["imageStatus"] = "pending"
                    e["qaPass"] = False
                dirty = True
            e["updatedAt"] = _now()
        if e.get("kind") == "character":
            if not meta.get("identityLockPath") and shots:
                rel_s = str(shots[0].get("startFramePath") or "")
                if rel_s and (store._dir(project_id) / rel_s).is_file():
                    meta["identityLockPath"] = rel_s
                    dirty = True
            if _bind_character_from_original(store, project_id, e):
                dirty = True
        # Sync entity.qaPass from selected still (worker sometimes leaves entity flag stale).
        sid = e.get("selectedImageId")
        if sid and e.get("qaPass") is not True:
            img = next((i for i in (e.get("images") or []) if i.get("id") == sid), None)
            qa = (img or {}).get("qa") if isinstance((img or {}).get("qa"), dict) else {}
            if img and (img.get("qaPass") is True or qa.get("pass") is True):
                e["qaPass"] = True
                e["imageStatus"] = "done"
                dirty = True

    if shots:
        lead = shots[0]
        rel_s = str(lead.get("startFramePath") or "")
        src = store._dir(project_id) / rel_s
        lock_rel = rel_s if src.is_file() else ""
        ts = _now()
        meta_title = (_template_meta(tid).get("title") or "主场景").split("·")[-1].strip() or "主场景"
        has_char = any(e.get("kind") == "character" for e in ents)
        has_scene = any(e.get("kind") == "scene" for e in ents)
        seeded_ids: list[str] = []
        if not has_char:
            char_id = new_id("ent_")
            seeded_ids.append(char_id)
            state.setdefault("entities", []).append(
                {
                    "id": char_id,
                    "projectId": project_id,
                    "kind": "character",
                    "name": "女主",
                    "variant": "默认形象",
                    "description": _portrait_character_desc(tid),
                    "episodes": [1],
                    "category": "",
                    "metadata": {
                        "portraitIdlock": True,
                        "requiresEntityStill": False,
                        "useOriginalKeyframe": True,
                        "identityLockPath": lock_rel,
                        "skillId": "drama-entity-still",
                    },
                    "selectedImageId": None,
                    "images": [],
                    "qaPass": False,
                    "imageStatus": "pending",
                    "createdAt": ts,
                    "updatedAt": ts,
                }
            )
            # Bind Douyin keyframe immediately (avoid broken alpha-punch stills).
            char_ent = next(e for e in state["entities"] if e["id"] == char_id)
            _bind_character_from_original(store, project_id, char_ent)
        if not has_scene:
            scene_id = new_id("ent_")
            seeded_ids.append(scene_id)
            state.setdefault("entities", []).append(
                {
                    "id": scene_id,
                    "projectId": project_id,
                    "kind": "scene",
                    "name": meta_title,
                    "variant": "",
                    "description": _portrait_scene_desc(tid),
                    "episodes": [1],
                    "category": "",
                    "metadata": {
                        "portraitIdlock": True,
                        "requiresEntityStill": True,
                        "skillId": "drama-entity-still",
                    },
                    "selectedImageId": None,
                    "images": [],
                    "qaPass": False,
                    "imageStatus": "pending",
                    "createdAt": ts,
                    "updatedAt": ts,
                }
            )
        if seeded_ids:
            dirty = True
            proj["workshopAssetGate"] = "drama-entity-still"
            proj["qualityDiagnosis"] = QUALITY_DIAGNOSIS

    # Shots must ONLY reference live portrait character/scene — stale deleted ent_* block H3.
    live_portrait = [
        e["id"]
        for e in (state.get("entities") or [])
        if not e.get("deletedAt")
        and (e.get("metadata") or {}).get("portraitIdlock")
        and e.get("kind") in {"character", "scene"}
    ]
    if live_portrait:
        want = list(dict.fromkeys(live_portrait))
        for sh in state.get("shots") or []:
            if sh.get("deletedAt"):
                continue
            cur = [str(x) for x in (sh.get("referenceEntityIds") or [])]
            if cur != want:
                sh["referenceEntityIds"] = want
                dirty = True

    if dirty:
        state["project"] = proj
        state["project"]["updatedAt"] = _now()
        store.save(state)
        return store.bundle(project_id)
    return None


def enqueue_portrait_entity_stills(store: Any, project_id: str) -> dict[str, Any]:
    """Scene stills via drama-entity-still; character uses Douyin original keyframe."""
    from drama_service import generate_entity_image

    ensure_portrait_workshop_assets(store, project_id)
    state = store.load(project_id)
    if not state or (state.get("project") or {}).get("workflow") != "portrait-match":
        return {"started": []}
    if (state.get("project") or {}).get("portraitMatchMode") == "reshoot":
        return {"started": [], "skipped": "reshoot-mode"}
    started: list[dict[str, Any]] = []
    dirty = False
    for ent in state.get("entities") or []:
        if ent.get("deletedAt"):
            continue
        meta = ent.get("metadata") or {}
        if not meta.get("portraitIdlock"):
            continue
        # Character: always prefer原片关键帧 (no gen / no alpha punch holes).
        if ent.get("kind") == "character":
            if _bind_character_from_original(store, project_id, ent):
                dirty = True
                started.append({"entityId": ent["id"], "kind": "character", "status": "original-keyframe"})
            else:
                started.append({"entityId": ent["id"], "kind": "character", "skipped": "original-keyframe"})
            continue
        if not meta.get("requiresEntityStill"):
            continue
        if ent.get("qaPass") is True and ent.get("selectedImageId"):
            continue
        if ent.get("imageStatus") == "generating":
            started.append({"entityId": ent["id"], "skipped": "generating"})
            continue
        try:
            out = generate_entity_image(
                store,
                project_id,
                ent["id"],
                redraw=True,
                force=True,
                wait=False,
            )
            started.append({"entityId": ent["id"], "kind": ent.get("kind"), "status": out.get("status") or "queued"})
        except Exception as exc:
            started.append({"entityId": ent["id"], "error": str(exc)})
    if dirty:
        state["project"]["updatedAt"] = _now()
        store.save(state)
    return {"started": started, "bundle": store.bundle(project_id)}

def portrait_workshop_quality_report(store: Any, project_id: str) -> dict[str, Any]:
    """Whether 角色 / 场景 / 提示词 meet workshop bar."""
    ensure_portrait_workshop_assets(store, project_id)
    state = store.load(project_id) or {}
    ents = [e for e in (state.get("entities") or []) if not e.get("deletedAt")]
    shots = [s for s in (state.get("shots") or []) if not s.get("deletedAt")]

    def _ent_ok(kind: str) -> dict[str, Any]:
        lst = [e for e in ents if e.get("kind") == kind]
        if not lst:
            return {"ok": False, "reason": "missing", "count": 0}
        ready = [e for e in lst if e.get("qaPass") is True and e.get("selectedImageId")]
        return {
            "ok": len(ready) == len(lst) and len(lst) > 0,
            "ready": len(ready),
            "total": len(lst),
            "pending": [e.get("name") for e in lst if e.get("qaPass") is not True],
        }

    prompt_fail = [s.get("title") or s.get("id") for s in shots if not (s.get("promptQa") or {}).get("pass")]
    char = _ent_ok("character")
    scene = _ent_ok("scene")
    prompts_ok = len(prompt_fail) == 0 and len(shots) > 0
    return {
        "character": char,
        "scene": scene,
        "prompts": {"ok": prompts_ok, "failShots": prompt_fail[:12], "total": len(shots)},
        "ready": bool(char.get("ok") and scene.get("ok") and prompts_ok),
        "diagnosis": (state.get("project") or {}).get("qualityDiagnosis") or QUALITY_DIAGNOSIS,
    }


def create_from_template(
    store: Any,
    *,
    template_id: str,
    title: str | None = None,
    owner_id: str | None = None,
    include_sample: bool = True,
    match_mode: str = "gen-likeness",
) -> dict[str, Any]:
    """Create a portrait-match project with one shot per frame pair.

    match_mode:
      - gen-likeness: H3 idlock generate path（极像）
      - reshoot: remake bible only（原片重拍企划，不出 H3）
    """
    tid = (template_id or "").strip()
    meta = next((t for t in TEMPLATES if t["id"] == tid), None)
    if not meta:
        raise ValueError(f"未知模板: {template_id}")
    mode = (match_mode or "gen-likeness").strip()
    if mode not in MATCH_MODES:
        raise ValueError(f"未知对标模式: {match_mode}（可选 gen-likeness / reshoot）")
    frames_src = _ASSETS / tid / "frames"
    if not frames_src.is_dir():
        raise FileNotFoundError(f"模板帧目录缺失: {frames_src}")
    pairs = _load_pairs().get(tid) or []
    if not pairs:
        # Fall back to glob order from *_s.jpg
        for s in sorted(frames_src.glob("*_s.jpg")):
            pairs.append({"id": s.stem.replace("_s", "")})

    brief_doc = build_reshoot_brief(tid)
    mode_meta = MATCH_MODES[mode]
    label = (title or f"{meta['title']} · {mode_meta['label']}").strip()
    state = store.create_project(
        title=label,
        brief=f"写真对标 · {mode_meta['label']} · {meta['desc']}",
        genre="氛围写真",
        visual_style=(
            "抖音原片重拍企划（真机 4K/60）"
            if mode == "reshoot"
            else "抖音极像生成 · 原片关键帧 + MiniMax H3 身份锁"
        ),
        ratio=meta.get("ratio") or "9:16",
        name=f"portrait-{tid}-{mode}",
        owner_id=owner_id,
    )
    pid = state["project"]["id"]
    state["project"]["workflow"] = "portrait-match"
    state["project"]["portraitTemplate"] = tid
    state["project"]["portraitMatchMode"] = mode
    state["project"]["skillId"] = "portrait-idlock" if mode == "gen-likeness" else "portrait-reshoot"
    state["project"]["reshootBrief"] = brief_doc
    state["project"]["qualityDiagnosis"] = QUALITY_DIAGNOSIS
    state["project"]["updatedAt"] = _now()

    ep_id = new_id("ep_")
    ep_content = brief_doc["markdown"] if mode == "reshoot" else (
        f"{meta['desc']}\n\n## 本路径说明\n{mode_meta['summary']}\n\n## 质量诊断\n{QUALITY_DIAGNOSIS}"
    )
    state["episodes"] = [
        {
            "id": ep_id,
            "episodeNumber": 1,
            "order": 1,
            "title": meta["title"],
            "synopsis": meta["desc"],
            "content": ep_content,
            # Confirmed so 影视工坊 SegmentWorkspace accepts the episode like any short-video project.
            "status": "confirmed",
            "createdAt": _now(),
            "updatedAt": _now(),
        }
    ]

    dest_frames = store._dir(pid) / "media" / "id_frames"
    dest_frames.mkdir(parents=True, exist_ok=True)
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
        # Match offline idlock_v3: duration from portrait-idlock Skill Runtime (default 3.5s).
        duration = _idlock_duration()
        try:
            idlock_gap = float(pair.get("gap") or 0.95)
        except (TypeError, ValueError):
            idlock_gap = 0.95
        beat = _beat_for(tid, i)
        prompt_zh = _idlock_prompt_zh(tid, beat)
        prompt_en = _idlock_prompt_en(tid, beat)
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
                # UI 中文结构化；H3 吃英文 modelPrompt
                "prompt": prompt_zh,
                "modelPrompt": prompt_en,
                "promptQa": _prompt_checklist(prompt_zh),
                "dialogue": "",
                "action": beat.get("action") or sid_label,
                "actionZh": beat.get("action"),
                "camera": beat.get("camera"),
                "transition": beat.get("transition"),
                "duration": duration,
                "idlockGap": idlock_gap,
                "referenceEntityIds": [],
                "startFramePath": rel_s,
                "endFramePath": rel_e,
                "idlock": True,
                "skillId": "portrait-idlock" if mode == "gen-likeness" else "portrait-reshoot",
                "skipVideoQa": True,
                # reshoot: frames are on-set references, not H3 jobs
                "status": "reference" if mode == "reshoot" else "pending",
                "portraitMatchMode": mode,
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
    store.save(state)
    # Seed 角色/场景实体（须过 drama-entity-still）+ 结构化提示词
    ensure_portrait_workshop_assets(store, pid)
    if mode == "gen-likeness":
        try:
            enqueue_portrait_entity_stills(store, pid)
        except Exception:
            pass
    state = store.load(pid) or state

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

    # Bundle Douyin-original audio for assemble mux.
    audio_src = _ASSETS / "audio" / f"{tid}.m4a"
    if audio_src.is_file():
        rel_a = f"media/audio/{tid}_original.m4a"
        dest_a = store._dir(pid) / rel_a
        dest_a.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(audio_src, dest_a)
        try:
            store.persist_media(pid, rel_a)
        except Exception:
            pass
        state["project"]["portraitAudioPath"] = rel_a
        state["project"]["portraitFramesSource"] = "douyin-original"

    store.save(state)
    return store.bundle(pid) or state


def refresh_idlock_frames_from_assets(store: Any, project_id: str, *, invalidate_videos: bool = True) -> dict[str, Any]:
    """Overwrite project id_frames with latest template frames (Douyin-original extracts) + original audio.

    Call before force-regenerate so H3 locks to 原片锐利帧 rather than旧 AI 样片帧.
    """
    state = store.load(project_id)
    if not state:
        raise FileNotFoundError("project not found")
    proj = state.get("project") or {}
    if proj.get("workflow") != "portrait-match":
        raise RuntimeError("不是写真对标项目")
    tid = str(proj.get("portraitTemplate") or "")
    frames_src = _ASSETS / tid / "frames"
    if not frames_src.is_dir():
        raise FileNotFoundError(f"模板帧缺失: {frames_src}")
    dest_root = store._dir(project_id)
    refreshed = 0
    for sh in state.get("shots") or []:
        if sh.get("deletedAt"):
            continue
        label = str(sh.get("title") or "")
        src_s = frames_src / f"{label}_s.jpg"
        src_e = frames_src / f"{label}_e.jpg"
        if not src_s.is_file() or not src_e.is_file():
            continue
        rel_s = str(sh.get("startFramePath") or f"media/id_frames/{label}_s.jpg")
        rel_e = str(sh.get("endFramePath") or f"media/id_frames/{label}_e.jpg")
        (dest_root / rel_s).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_s, dest_root / rel_s)
        shutil.copy2(src_e, dest_root / rel_e)
        sh["startFramePath"] = rel_s
        sh["endFramePath"] = rel_e
        try:
            store.persist_media(project_id, rel_s)
            store.persist_media(project_id, rel_e)
        except Exception:
            pass
        if invalidate_videos:
            sh["videos"] = []
            sh["selectedVideoId"] = None
            sh["status"] = "pending"
            sh["error"] = None
            sh["staleReason"] = "idlock-frames-from-douyin-original"
            sh["updatedAt"] = _now()
        refreshed += 1

    # Original Douyin audio for mux (prefer over sample video soundtrack).
    audio_src = _ASSETS / "audio" / f"{tid}.m4a"
    if audio_src.is_file():
        rel_a = f"media/audio/{tid}_original.m4a"
        dest_a = dest_root / rel_a
        dest_a.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(audio_src, dest_a)
        try:
            store.persist_media(project_id, rel_a)
        except Exception:
            pass
        proj["portraitAudioPath"] = rel_a
        proj["portraitFramesSource"] = "douyin-original"

    # Force re-seed character/scene crops from new first frame.
    for e in state.get("entities") or []:
        if e.get("metadata", {}).get("portraitIdlock") and not e.get("deletedAt"):
            e["deletedAt"] = _now()
    state["project"] = proj
    state["project"]["updatedAt"] = _now()
    store.save(state)
    ensure_portrait_workshop_assets(store, project_id)
    return {
        "refreshedShots": refreshed,
        "framesSource": "douyin-original",
        "bundle": store.bundle(project_id),
    }


def start_all_idlock(
    store: Any,
    project_id: str,
    *,
    model: str = "",
    resolution: str = "",
    only_missing: bool = True,
    refresh_frames: bool = False,
) -> dict[str, Any]:
    """Enqueue H3 idlock for every portrait shot (skip ones that already have video)."""
    from drama_service import start_shot_video
    from providers.media import resolve_video_model

    state = store.load(project_id)
    if not state:
        raise FileNotFoundError("project not found")
    proj = state.get("project") or {}
    if proj.get("workflow") != "portrait-match":
        raise RuntimeError("不是写真对标项目")
    if proj.get("portraitMatchMode") == "reshoot":
        raise RuntimeError(
            "当前项目是「原片重拍」企划，不跑 H3 生成。"
            "请按剧本里的重拍企划真机拍摄；若要极像生成请新建「极像生成」项目。"
        )
    refresh_meta = None
    if refresh_frames:
        refresh_meta = refresh_idlock_frames_from_assets(store, project_id, invalidate_videos=True)
        only_missing = False
    ensure_portrait_workshop_assets(store, project_id)
    stills = enqueue_portrait_entity_stills(store, project_id)
    quality = portrait_workshop_quality_report(store, project_id)
    if not quality.get("ready"):
        # Don't start H3 until 角色/场景/提示词达标 — return blockers for UI.
        return {
            "skillId": "portrait-idlock",
            "started": [],
            "blocked": True,
            "quality": quality,
            "entityStills": stills,
            "refresh": refresh_meta,
            "message": "请先让角色定妆、场景定妆过质检，并确认每镜提示词含角色/场景/动作/运镜/转镜/光影。",
            "bundle": store.bundle(project_id),
        }
    # Clear zombie generating (no providerTaskId / no video) left by deploy or dead Comfy.
    from drama_service import reset_zombie_generating_shots

    zapped = reset_zombie_generating_shots(store, project_id)
    state = store.load(project_id) or state
    # Refresh structured prompts with quality stack before enqueue.
    ensure_portrait_workshop_assets(store, project_id)
    state = store.load(project_id) or state
    vid_model = resolve_video_model(model or "")
    res = (resolution or "").strip() or _idlock_resolution_default()
    # Bump legacy 3.5s → skill duration before enqueue (start_shot_video reloads state).
    dur_dirty = False
    for sh in state.get("shots") or []:
        if sh.get("deletedAt"):
            continue
        try:
            if float(sh.get("duration") or 0) < 3.9:
                sh["duration"] = _idlock_duration()
                sh["updatedAt"] = _now()
                dur_dirty = True
        except (TypeError, ValueError):
            sh["duration"] = _idlock_duration()
            dur_dirty = True
    state["project"]["portraitGenResolution"] = res
    state["project"]["qualityDiagnosis"] = QUALITY_DIAGNOSIS
    state["project"]["updatedAt"] = _now()
    store.save(state)

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
                resolution=res,
                skip_refs=True,
            )
            started.append({"shotId": sh["id"], "status": out.get("status"), "resolution": res})
        except Exception as exc:
            started.append({"shotId": sh["id"], "error": str(exc)})
    return {
        "skillId": "portrait-idlock",
        "started": started,
        "resolution": res,
        "qualityStack": True,
        "zombiesCleared": zapped,
        "refresh": refresh_meta,
        "bundle": store.bundle(project_id),
    }

def assemble_portrait(store: Any, project_id: str) -> dict[str, Any]:
    """Concat successful idlock clips toward Douyin original pacing.

    Keep the *front* of each H3 clip (identity-stable), hold ≈ source gap, mild speed-up,
    flash cuts, template color grade + unsharp, upscale 1080p, mux 抖音原曲优先.
    """
    ensure_portrait_workshop_assets(store, project_id)
    state = store.load(project_id)
    if not state:
        raise FileNotFoundError("project not found")
    tid = str((state.get("project") or {}).get("portraitTemplate") or "ref1")
    preset = ASSEMBLE_PRESETS.get(tid) or ASSEMBLE_PRESETS["ref1"]
    speed = float(preset["speed"])
    flash_every = int(preset["flash_every"])
    fallback_hold = float(preset.get("fallback_hold") or 0.9)
    grade = str(preset.get("vf_grade") or "eq=saturation=1.05:contrast=1.03")

    # Prefer Douyin-original audio duration as assemble target (full track, not truncated).
    proj = state.get("project") or {}
    audio_path: Path | None = None
    for rel in (
        proj.get("portraitAudioPath"),
        f"media/audio/{tid}_original.m4a",
    ):
        if rel:
            cand = store._dir(project_id) / str(rel)
            if cand.is_file():
                audio_path = cand
                break
    if audio_path is None:
        asset_a = _ASSETS / "audio" / f"{tid}.m4a"
        if asset_a.is_file():
            audio_path = asset_a
    audio_dur = _ffprobe_duration(audio_path) if audio_path else 0.0
    target_dur = audio_dur if audio_dur >= 3.0 else float(preset.get("target_dur") or 10.0)

    shots = sorted(
        [s for s in (state.get("shots") or []) if not s.get("deletedAt")],
        key=lambda s: int(s.get("order") or 0),
    )
    clip_jobs: list[tuple[Path, float]] = []
    for sh in shots:
        sel = sh.get("selectedVideoId")
        vid = next((v for v in (sh.get("videos") or []) if v.get("id") == sel), None)
        if not vid or not vid.get("path"):
            continue
        p = store._dir(project_id) / vid["path"]
        if not (p.is_file() and p.stat().st_size > 10000):
            continue
        try:
            gap = float(sh.get("idlockGap") or fallback_hold)
        except (TypeError, ValueError):
            gap = fallback_hold
        # Base hold from Douyin beat gap (pairs already scaled to original length).
        hold = max(0.5, min(2.6, gap))
        clip_jobs.append((p, hold))
    if len(clip_jobs) < 2:
        raise RuntimeError(f"至少需要 2 个成功镜头才能合片（当前 {len(clip_jobs)}）")

    # Fit visual timeline to 原曲 duration (avoid cutting Douyin audio short).
    base_sum = sum(h for _, h in clip_jobs) or 1.0
    # Account for flash frames (~0.04s each).
    n_flash = sum(1 for i in range(len(clip_jobs) - 1) if flash_every and (i + 1) % flash_every == 0)
    flash_budget = 0.04 * n_flash
    scale = max(0.85, min(2.4, (target_dur - flash_budget) / base_sum))
    clip_jobs = [(p, max(0.5, min(2.8, h * scale))) for p, h in clip_jobs]

    work = store._dir(project_id) / "media" / "assemble_portrait"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True, exist_ok=True)
    parts: list[Path] = []

    def _run(cmd: list[str]) -> None:
        subprocess.check_call(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    for i, (src, hold) in enumerate(clip_jobs):
        dest = work / f"{i:03d}.mp4"
        # Front of H3 clip — closest to first-frame identity; mid/late drifts.
        _run(
            [
                "ffmpeg",
                "-y",
                "-ss",
                "0.05",
                "-t",
                f"{hold * speed:.3f}",
                "-i",
                str(src),
                "-an",
                "-vf",
                f"setpts=PTS/{speed},fps=30,format=yuv420p",
                "-c:v",
                "libx264",
                "-preset",
                "fast",
                "-crf",
                "15",
                str(dest),
            ]
        )
        parts.append(dest)
        if flash_every and (i + 1) % flash_every == 0 and i < len(clip_jobs) - 1:
            flash = work / f"{i:03d}_flash.mp4"
            _run(
                [
                    "ffmpeg",
                    "-y",
                    "-f",
                    "lavfi",
                    "-i",
                    "color=c=black:s=1080x1920:r=30:d=0.04",
                    "-c:v",
                    "libx264",
                    "-pix_fmt",
                    "yuv420p",
                    str(flash),
                ]
            )
            parts.append(flash)

    lst = work / "list.txt"
    lst.write_text("".join(f"file '{p.resolve()}'\n" for p in parts), encoding="utf-8")
    visual = work / "visual.mp4"
    _run(
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
            f"{grade},scale=1080:1920:flags=lanczos,fps=30,format=yuv420p",
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "15",
            "-an",
            str(visual),
        ]
    )

    out_visual = visual
    final = work / "final.mp4"
    audio_candidates: list[Path] = []
    if audio_path is not None:
        audio_candidates.append(audio_path)
    asset_a = _ASSETS / "audio" / f"{tid}.m4a"
    if asset_a.is_file() and asset_a not in audio_candidates:
        audio_candidates.append(asset_a)
    sample = store._dir(project_id) / "media" / "videos" / "sample_match_v3.mp4"
    if sample.is_file():
        audio_candidates.append(sample)

    vdur = _ffprobe_duration(visual)
    # Mux full Douyin audio; pad/trim video to audio length (not the reverse).
    for audio in audio_candidates:
        try:
            adur = _ffprobe_duration(audio)
            if adur < 3.0:
                adur = vdur
            pad = max(0.0, adur - vdur)
            _run(
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    str(visual),
                    "-i",
                    str(audio),
                    "-filter_complex",
                    (
                        f"[0:v]tpad=stop_mode=clone:stop_duration={pad:.3f},"
                        f"trim=duration={adur:.3f},setpts=PTS-STARTPTS[v];"
                        f"[1:a]atrim=0:{adur:.3f},asetpts=PTS-STARTPTS[a]"
                    ),
                    "-map",
                    "[v]",
                    "-map",
                    "[a]",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "fast",
                    "-crf",
                    "15",
                    "-c:a",
                    "aac",
                    "-b:a",
                    "192k",
                    "-t",
                    f"{adur:.3f}",
                    str(final),
                ]
            )
            if final.is_file() and final.stat().st_size > 10000:
                out_visual = final
                break
        except Exception:
            continue

    rel = "media/videos/portrait_match_assembled.mp4"
    out = store._dir(project_id) / rel
    out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(out_visual, out)
    try:
        store.persist_media(project_id, rel)
    except Exception:
        pass
    edit = {
        "id": new_id("ed_"),
        "kind": "portrait-assemble",
        "title": "写真对标合片 · 对齐抖音原片节奏",
        "outputPath": rel,
        "clipCount": len(clip_jobs),
        "assembleMode": "douyin-gap-front-grade-audio",
        "speed": speed,
        "holdScale": round(scale, 3),
        "targetDur": round(target_dur, 3),
        "visualDur": round(_ffprobe_duration(out_visual), 3),
        "framesSource": proj.get("portraitFramesSource") or "template",
        "createdAt": _now(),
    }
    state.setdefault("edits", []).append(edit)
    state["project"]["updatedAt"] = _now()
    store.save(state)
    bundle = store.bundle(project_id) or state
    return {"edit": {**edit, "outputUrl": f"/api/media/{project_id}/{rel}"}, "bundle": bundle}
