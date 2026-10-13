#!/usr/bin/env python3
"""Build welcome-ep01 seed media + studio_state.json for demo walkthrough.

Primary stills come from studio/public/style-previews (CJK drama looks).
Optional Pinterest pinimg downloads are best-effort (often blocked offline).
"""

from __future__ import annotations

import json
import shutil
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEED = ROOT / "seed" / "welcome-ep01"
PREVIEWS = ROOT / "public" / "style-previews"

PIN_ASSETS = [
    ("char_linxia_pin.jpg", "https://i.pinimg.com/474x/aa/8f/6b/aa8f6b92d1b9f7c36189511ba45fd395.jpg"),
    ("char_zhouyu_pin.jpg", "https://i.pinimg.com/474x/5a/99/ba/5a99bae434f18b959c5917cbf8369a08.jpg"),
    ("scene_doorway_pin.jpg", "https://i.pinimg.com/474x/08/22/f0/0822f00f15842fa94b41476686515b0d.jpg"),
    ("scene_backrooms_pin.jpg", "https://i.pinimg.com/474x/ee/d1/4c/eed14c22f9a7e11477b9579bedeb2a2b.jpg"),
    ("prop_atmosphere_pin.jpg", "https://i.pinimg.com/474x/32/f1/24/32f124f32308bed0de912fcf13a54908.jpg"),
]

LOCAL_COPIES = [
    ("char_zhouyu_style.webp", "008-new_cn_urban_drama_realism_style.webp"),
    ("char_zhouyu_alt.webp", "002-palace_intrigue_cover_q50.webp"),
    ("char_linxia_style.webp", "007-new_kdrama_urban_soft_light_style.webp"),
    ("char_linxia_alt.webp", "004-new_guzhuang_romance_soft_light_style.webp"),
    ("scene_suspense.webp", "003-new_cn_suspense_cold_realism_style.webp"),
    ("scene_city_night.webp", "006-new_jdrama_life_naturalism_style.webp"),
    ("scene_alley.webp", "009-wuxia_jianghu_cover_q50.webp"),
    ("prop_detail_a.webp", "012-novel_style_row_054.webp"),
    ("prop_detail_b.webp", "013-novel_style_row_042.webp"),
    ("shot_ref_01.webp", "014-novel_style_row_033.webp"),
    ("shot_ref_02.webp", "019-novel_style_row_044.webp"),
    ("shot_ref_03.webp", "021-novel_style_row_037.webp"),
    ("style_board.webp", "001-retro_atomic_punk_cover_800x600.webp"),
]


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def download(url: str, dest: Path) -> bool:
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://www.pinterest.com/",
            "Accept": "image/avif,image/webp,image/*,*/*;q=0.8",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = resp.read()
        if len(data) < 1000:
            return False
        dest.write_bytes(data)
        print(f"  downloaded {dest.name} ({dest.stat().st_size} bytes)")
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"  skip pin {dest.name}: {exc}")
        return False


def main() -> None:
    media = SEED / "media" / "images"
    media.mkdir(parents=True, exist_ok=True)
    (SEED / "media" / "videos").mkdir(parents=True, exist_ok=True)
    (SEED / "media" / "exports").mkdir(parents=True, exist_ok=True)

    print("==> Copying style-previews into seed media")
    for dest_name, src_name in LOCAL_COPIES:
        src = PREVIEWS / src_name
        if not src.is_file():
            print(f"  skip missing {src_name}")
            continue
        shutil.copy2(src, media / dest_name)
        print(f"  copied {dest_name}")

    import os

    if os.environ.get("BUILD_SEED_SKIP_PINS", "").strip() in {"1", "true", "yes"}:
        print("==> Skipping Pinterest pinimg (BUILD_SEED_SKIP_PINS)")
    else:
        print("==> Optional Pinterest pinimg stills")
        for dest_name, url in PIN_ASSETS:
            download(url, media / dest_name)

    ts = _now()
    pid = "welcome-ep01"
    ep_id = "ep_welcome01"

    def img(name: str, image_id: str, label: str) -> dict | None:
        path = media / name
        if not path.is_file() or path.stat().st_size < 500:
            return None
        rel = f"media/images/{name}"
        return {
            "id": image_id,
            "path": rel,
            "label": label,
            "source": "seed",
            "createdAt": ts,
        }

    def collect(*pairs: tuple[str, str, str]) -> list[dict]:
        out: list[dict] = []
        for name, iid, label in pairs:
            item = img(name, iid, label)
            if item:
                out.append(item)
        return out

    zhouyu_imgs = collect(
        ("char_zhouyu_style.webp", "img_zhouyu_style", "都市写实造型"),
        ("char_zhouyu_alt.webp", "img_zhouyu_alt", "气质参考"),
        ("char_zhouyu_pin.jpg", "img_zhouyu_pin", "Pinterest 参考"),
    )
    linxia_imgs = collect(
        ("char_linxia_style.webp", "img_linxia_style", "韩系都市软光"),
        ("char_linxia_alt.webp", "img_linxia_alt", "柔光造型"),
        ("char_linxia_pin.jpg", "img_linxia_pin", "Pinterest 参考"),
    )
    scene_a = collect(
        ("scene_suspense.webp", "img_scene_suspense", "冷悬疑空镜"),
        ("scene_city_night.webp", "img_scene_city", "都市夜景"),
    )
    scene_b = collect(
        ("scene_alley.webp", "img_scene_alley", "夜巷氛围"),
        ("scene_doorway_pin.jpg", "img_scene_door", "神秘门廊"),
        ("scene_backrooms_pin.jpg", "img_scene_back", "空旷空间"),
    )
    prop_imgs = collect(
        ("prop_detail_a.webp", "img_prop_a", "关键道具细节"),
        ("prop_detail_b.webp", "img_prop_b", "道具备选"),
        ("prop_atmosphere_pin.jpg", "img_prop_pin", "通话氛围"),
        ("style_board.webp", "img_prop_mood", "视觉情绪板"),
    )
    shot_refs = collect(
        ("shot_ref_01.webp", "img_shot_01", "分镜参考 01"),
        ("shot_ref_02.webp", "img_shot_02", "分镜参考 02"),
        ("shot_ref_03.webp", "img_shot_03", "分镜参考 03"),
    )

    entities = [
        {
            "id": "char_周屿",
            "projectId": pid,
            "kind": "character",
            "name": "周屿",
            "variant": "默认形象",
            "description": "短剧男主。都市夜戏冷青光下的疲惫与决绝，短发，深色夹克。",
            "episodes": [ep_id],
            "category": "protagonist",
            "metadata": {"role": "protagonist"},
            "selectedImageId": zhouyu_imgs[0]["id"] if zhouyu_imgs else None,
            "images": zhouyu_imgs,
            "createdAt": ts,
            "updatedAt": ts,
        },
        {
            "id": "char_林夏",
            "projectId": pid,
            "kind": "character",
            "name": "林夏",
            "variant": "默认形象",
            "description": "短剧女主。便利店冷白灯下的紧张神情，长发，浅色外套。",
            "episodes": [ep_id],
            "category": "lead",
            "metadata": {"role": "supporting"},
            "selectedImageId": linxia_imgs[0]["id"] if linxia_imgs else None,
            "images": linxia_imgs,
            "createdAt": ts,
            "updatedAt": ts,
        },
        {
            "id": "loc_sc01",
            "projectId": pid,
            "kind": "scene",
            "name": "空荡便利店",
            "variant": "夜戏",
            "description": "灯管闪烁的便利店柜台，手机扣在台面上，时间紧迫。",
            "episodes": [ep_id],
            "category": "",
            "metadata": {},
            "selectedImageId": scene_a[0]["id"] if scene_a else None,
            "images": scene_a,
            "createdAt": ts,
            "updatedAt": ts,
        },
        {
            "id": "loc_sc02",
            "projectId": pid,
            "kind": "scene",
            "name": "城市夜巷",
            "variant": "外景",
            "description": "信号发出后的城市夜景，冷青与琥珀对比。",
            "episodes": [ep_id],
            "category": "",
            "metadata": {},
            "selectedImageId": scene_b[0]["id"] if scene_b else None,
            "images": scene_b,
            "createdAt": ts,
            "updatedAt": ts,
        },
        {
            "id": "prop_phone",
            "projectId": pid,
            "kind": "prop",
            "name": "林夏的手机",
            "variant": "关键道具",
            "description": "倒计时三分钟的通话与短信，推动剧情转折。",
            "episodes": [ep_id],
            "category": "item",
            "metadata": {},
            "selectedImageId": prop_imgs[0]["id"] if prop_imgs else None,
            "images": prop_imgs,
            "createdAt": ts,
            "updatedAt": ts,
        },
        {
            "id": "board_refs",
            "projectId": pid,
            "kind": "prop",
            "name": "分镜情绪板",
            "variant": "参考",
            "description": "开场三镜的构图与光比参考，可在分镜台复用。",
            "episodes": [ep_id],
            "category": "reference",
            "metadata": {},
            "selectedImageId": shot_refs[0]["id"] if shot_refs else None,
            "images": shot_refs,
            "createdAt": ts,
            "updatedAt": ts,
        },
    ]

    script = {}
    if (SEED / "script.json").is_file():
        script = json.loads((SEED / "script.json").read_text(encoding="utf-8"))
    brief = script.get("brief") or (
        "林夏：别回那通电话。\n周屿：太晚了。信号已经发出去了。\n\n"
        "空荡的便利店灯管闪了一下。林夏把手机扣在柜台上。\n"
        "林夏：我们还有最后三分钟。\n周屿：够改写结局吗？\n"
    )
    episodes = []
    for ep in script.get("episodes") or []:
        episodes.append(
            {
                "id": ep.get("id") or ep_id,
                "projectId": pid,
                "episodeNumber": ep.get("episodeNumber") or 1,
                "title": ep.get("title") or script.get("title") or "欢迎来到 Drama Studio",
                "content": ep.get("content") or brief,
                "status": "confirmed",
                "createdAt": ts,
                "updatedAt": ts,
            }
        )
    if not episodes:
        episodes = [
            {
                "id": ep_id,
                "projectId": pid,
                "episodeNumber": 1,
                "title": "欢迎来到 Drama Studio",
                "content": brief,
                "status": "confirmed",
                "createdAt": ts,
                "updatedAt": ts,
            }
        ]

    sb = {}
    if (SEED / "storyboard.json").is_file():
        sb = json.loads((SEED / "storyboard.json").read_text(encoding="utf-8"))
    shots = []
    for i, sh in enumerate(sb.get("shots") or [], 1):
        shots.append(
            {
                "id": sh.get("id") or f"sh_{i:02d}",
                "projectId": pid,
                "episodeId": episodes[0]["id"],
                "shotOrder": sh.get("index") or i,
                "prompt": sh.get("video_prompt") or sh.get("description") or "",
                "duration": int(sh.get("duration_sec") or 5),
                "referenceEntityIds": sh.get("character_ids") or ["char_周屿", "char_林夏"],
                "status": "pending",
                "providerTaskId": None,
                "error": None,
                "selectedVideoId": None,
                "videos": [],
                "createdAt": ts,
                "updatedAt": ts,
            }
        )
    if not shots:
        shots = [
            {
                "id": "sh_01",
                "projectId": pid,
                "episodeId": episodes[0]["id"],
                "shotOrder": 1,
                "prompt": "便利店夜戏，林夏扣下手机，灯管闪烁，9:16",
                "duration": 5,
                "referenceEntityIds": ["char_林夏", "loc_sc01"],
                "status": "pending",
                "providerTaskId": None,
                "error": None,
                "selectedVideoId": None,
                "videos": [],
                "createdAt": ts,
                "updatedAt": ts,
            }
        ]

    cover = "media/images/char_linxia_style.webp"
    if not (media / "char_linxia_style.webp").is_file():
        cover = None

    state = {
        "project": {
            "id": pid,
            "title": script.get("title") or "欢迎来到 Drama Studio",
            "brief": brief,
            "synopsis": script.get("synopsis") or "三分钟倒计时里，一对旧识决定是否改写结局。",
            "genre": script.get("genre") or "短剧",
            "visualStyle": "当代都市夜戏，冷青与琥珀对比",
            "ratio": "9:16",
            "plannedEpisodes": 1,
            "createdAt": ts,
            "updatedAt": ts,
            "coverPath": cover,
        },
        "episodes": episodes,
        "entities": entities,
        "shots": shots,
        "edits": [],
    }

    out = SEED / "studio_state.json"
    out.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    files = sorted(p for p in media.iterdir() if p.is_file() and p.stat().st_size > 500)
    total = sum(p.stat().st_size for p in files)
    print(f"OK {out.name}: {len(entities)} entities, {sum(len(e['images']) for e in entities)} images, {len(files)} files ({total/1024:.0f} KB)")


if __name__ == "__main__":
    main()
