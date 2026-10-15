"""Personal asset library + prompt store (有彩-style 个人资产)."""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

_LIBRARY_ID = "_library"
_UPLOAD_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".mp4", ".webm", ".svg", ".wav", ".mp3", ".pdf", ".txt", ".md", ".docx"}
_DOC_EXTS = {".pdf", ".txt", ".md", ".docx"}

ASSET_CATEGORIES = (
    ("all", "全部分类"),
    ("character", "👤 角色"),
    ("scene", "🏞️ 场景"),
    ("prop", "💍 道具"),
    ("style", "🎨 风格"),
    ("storyboard", "🎬 分镜"),
    ("final", "🎞️ 成片"),
    ("music", "🎵 音乐"),
    ("voice", "🎙️ 语音"),
    ("audio", "🎧 音频"),
    ("sfx", "🔊 音效"),
    ("image", "🖼️ 图片"),
    ("video", "🎥 视频"),
    ("other", "📁 其他"),
)

PROMPT_CATEGORIES = (
    ("all", "全部"),
    ("general", "通用"),
    ("style", "风格"),
    ("composition", "构图"),
    ("lighting", "光影"),
    ("character", "人物"),
    ("scene", "场景"),
    ("camera", "运镜"),
    ("quality", "画质"),
    ("audio", "音频"),
    ("text", "文本"),
    ("template", "模板"),
)


def library_id() -> str:
    return _LIBRARY_ID


def upload_exts() -> set[str]:
    return set(_UPLOAD_EXTS)


def ensure_library_root(projects_root: Path) -> Path:
    root = projects_root / _LIBRARY_ID
    (root / "media" / "uploads").mkdir(parents=True, exist_ok=True)
    payload = {
        "project": {
            "id": _LIBRARY_ID,
            "title": "个人素材库",
            "updatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "hidden": True,
        },
        "episodes": [],
        "entities": [],
        "shots": [],
    }
    pg_on = False
    try:
        import pg_backend as _pg

        pg_on = bool(_pg.enabled())
        if pg_on and _pg.load_project(_LIBRARY_ID) is None:
            _pg.upsert_project(payload)
    except Exception:  # noqa: BLE001
        pg_on = False

    if not pg_on:
        # Local/dev without Postgres: keep a disk stub so listing still works.
        state = root / "studio_state.json"
        if not state.is_file():
            state.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        else:
            try:
                existing = json.loads(state.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                existing = {}
            if not isinstance(existing.get("project"), dict):
                state.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    # prompts.json only when PG prompts KV is unavailable (save_prompts handles PG).
    if not pg_on:
        prompts = root / "prompts.json"
        if not prompts.is_file():
            prompts.write_text(json.dumps({"items": []}, ensure_ascii=False, indent=2), encoding="utf-8")
    return root


def asset_kind(suffix: str) -> str:
    s = suffix.lower()
    if s in {".mp4", ".webm"}:
        return "video"
    if s in {".wav", ".mp3"}:
        return "audio"
    if s in _DOC_EXTS:
        return "doc"
    return "image"


def guess_category(rel: str, kind: str) -> str:
    blob = rel.lower().replace("\\", "/")
    name = blob.rsplit("/", 1)[-1]
    # Style refs like char_linxia_style.webp → 风格, not 角色.
    if "_style" in name or name.startswith("style_") or "/style/" in blob or "风格" in blob:
        return "style"
    # Explicit filename prefixes used by studio generations (before path keywords).
    prefix_rules = (
        ("character", ("char_", "character_", "角色")),
        ("scene", ("scene_", "场景", "location_", "loc_")),
        ("prop", ("prop_", "道具")),
        ("storyboard", ("shot_", "storyboard_", "分镜")),
        ("final", ("export_", "render_")),
    )
    for cat, prefixes in prefix_rules:
        if any(name.startswith(p) or f"/{p}" in blob for p in prefixes):
            return cat
    rules = (
        ("character", ("character", "角色", "cast", "actor", "portrait")),
        ("scene", ("scene", "场景", "location", "空镜")),
        ("prop", ("prop", "道具")),
        ("storyboard", ("storyboard", "shot", "分镜", "take")),
        ("final", ("export", "exports", "render", "renders", "成片", "final")),
        ("music", ("music", "bgm", "音乐", "score")),
        ("voice", ("voice", "tts", "speech", "语音", "配音")),
        ("sfx", ("sfx", "音效")),
        ("style", ("look", "mood")),
    )
    for cat, kws in rules:
        if any(k in blob for k in kws):
            return cat
    if kind == "audio":
        return "music"
    if kind == "video":
        return "video"
    if kind == "image":
        return "image"
    return "other"


def scan_media_assets(pid: str, title: str, root: Path) -> list[dict[str, Any]]:
    from media_qa import inspect_media

    items: list[dict[str, Any]] = []
    media = root / "media"
    if not media.is_dir():
        return items
    for path in sorted(media.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in _UPLOAD_EXTS:
            continue
        rel = path.relative_to(root).as_posix()
        kind = asset_kind(path.suffix)
        uploaded = pid == _LIBRARY_ID or rel.startswith("media/uploads/")
        health = inspect_media(path, kind=kind if kind in {"image", "video", "audio"} else None)
        items.append(
            {
                "id": f"{pid}:{rel}",
                "projectId": pid,
                "projectTitle": title or pid,
                "path": rel,
                "name": path.name,
                "url": f"/api/media/{pid}/{rel}",
                "kind": kind,
                "category": guess_category(rel, kind),
                "source": "upload" if uploaded else "ai",
                "size": path.stat().st_size,
                "updatedAt": path.stat().st_mtime,
                "uploaded": uploaded,
                "broken": bool(health.get("broken")),
                "qaReason": health.get("reason") or "",
            }
        )
    return items


def collect_assets(store: Any, projects_root: Path) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    lib_root = ensure_library_root(projects_root)
    items.extend(scan_media_assets(_LIBRARY_ID, "个人素材库", lib_root))
    for project in store.list_items():
        pid = str(project.get("id") or "")
        if not pid or pid == _LIBRARY_ID:
            continue
        root = store._dir(pid)
        if not root or not root.is_dir():
            continue
        items.extend(scan_media_assets(pid, str(project.get("title") or pid), root))
    items.sort(key=lambda x: x["updatedAt"], reverse=True)
    return items


def filter_assets(
    items: list[dict[str, Any]],
    *,
    kind: str = "all",
    source: str = "all",
    category: str = "all",
    q: str = "",
    sort: str = "latest",
    health: str = "healthy",
) -> list[dict[str, Any]]:
    view = list(items)
    k = (kind or "all").strip().lower()
    if k and k not in ("all", "全部", "*"):
        view = [x for x in view if str(x.get("kind") or "") == k]
    src = (source or "all").strip().lower()
    if src and src not in ("all", "全部", "全部来源", "*"):
        view = [x for x in view if str(x.get("source") or "") == src]
    cat = (category or "all").strip().lower()
    if cat and cat not in ("all", "全部", "全部分类", "*"):
        view = [x for x in view if str(x.get("category") or "") == cat]
    h = (health or "healthy").strip().lower()
    if h in ("healthy", "ok", "健康"):
        view = [x for x in view if not x.get("broken")]
    elif h in ("broken", "损坏", "bad"):
        view = [x for x in view if x.get("broken")]
    # health=all / 全部 → keep both
    query = (q or "").strip().lower()
    if query:
        view = [
            x
            for x in view
            if query in str(x.get("name") or "").lower()
            or query in str(x.get("path") or "").lower()
            or query in str(x.get("projectTitle") or "").lower()
            or query in str(x.get("category") or "").lower()
        ]
    sort_key = (sort or "latest").strip().lower()
    if sort_key in ("oldest", "最早"):
        view.sort(key=lambda x: x.get("updatedAt") or 0)
    elif sort_key in ("hot", "hottest", "最热"):
        view.sort(key=lambda x: (x.get("size") or 0, x.get("updatedAt") or 0), reverse=True)
    else:
        view.sort(key=lambda x: x.get("updatedAt") or 0, reverse=True)
    return view


def delete_asset(projects_root: Path, store: Any, project_id: str, rel_path: str) -> bool:
    pid = (project_id or "").strip()
    rel = (rel_path or "").strip().lstrip("/")
    if not pid or not rel or ".." in rel:
        return False
    if pid == _LIBRARY_ID:
        root = ensure_library_root(projects_root)
    else:
        root = store._dir(pid)
    if not root:
        return False
    target = (root / rel).resolve()
    try:
        target.relative_to(root.resolve())
    except ValueError:
        return False
    if not target.is_file():
        return False
    target.unlink()
    return True


def _prompts_path(projects_root: Path) -> Path:
    return ensure_library_root(projects_root) / "prompts.json"


def load_prompts(projects_root: Path) -> list[dict[str, Any]]:
    path = _prompts_path(projects_root)
    data: Any = None
    try:
        import pg_backend as _pg

        if _pg.enabled():
            hit = _pg.load_kv("prompts:_library")
            if isinstance(hit, dict):
                data = hit
            elif path.is_file():
                # One-shot migrate disk → PG if row missing
                disk = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(disk, dict):
                    _pg.upsert_kv("prompts:_library", disk)
                    data = disk
    except Exception:  # noqa: BLE001
        data = None
    if data is None and path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            data = None
    if data is None:
        return []
    items = data.get("items") if isinstance(data, dict) else data
    out = [x for x in (items or []) if isinstance(x, dict) and str(x.get("text") or "").strip()]
    return out


def save_prompts(projects_root: Path, items: list[dict[str, Any]]) -> None:
    path = _prompts_path(projects_root)
    payload = {"items": items}
    try:
        import pg_backend as _pg

        if _pg.enabled():
            _pg.upsert_kv("prompts:_library", payload)
            return
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"保存 prompts 到 Postgres 失败: {exc}") from exc
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def list_prompts(
    projects_root: Path,
    *,
    category: str = "all",
    q: str = "",
    sort: str = "latest",
) -> list[dict[str, Any]]:
    items = load_prompts(projects_root)
    cat = (category or "all").strip().lower()
    if cat and cat not in ("all", "全部", "*"):
        items = [x for x in items if str(x.get("category") or "general").lower() == cat]
    query = (q or "").strip().lower()
    if query:
        items = [
            x
            for x in items
            if query in str(x.get("title") or "").lower()
            or query in str(x.get("text") or "").lower()
            or query in str(x.get("category") or "").lower()
        ]
    sort_key = (sort or "latest").strip().lower()
    if sort_key in ("oldest", "最早"):
        items.sort(key=lambda x: x.get("updatedAt") or 0)
    elif sort_key in ("name", "名称"):
        items.sort(key=lambda x: str(x.get("title") or x.get("text") or "").lower())
    else:
        items.sort(key=lambda x: x.get("updatedAt") or 0, reverse=True)
    return items


def upsert_prompt(projects_root: Path, body: dict[str, Any]) -> dict[str, Any]:
    items = load_prompts(projects_root)
    prompt_id = str(body.get("id") or "").strip()
    title = str(body.get("title") or "").strip()
    text = str(body.get("text") or "").strip()
    category = str(body.get("category") or "general").strip() or "general"
    if not text:
        raise ValueError("text required")
    now = time.time()
    if prompt_id:
        for item in items:
            if str(item.get("id")) == prompt_id:
                item["title"] = title or item.get("title") or text[:40]
                item["text"] = text
                item["category"] = category
                item["updatedAt"] = now
                save_prompts(projects_root, items)
                return item
    item = {
        "id": prompt_id or uuid.uuid4().hex,
        "title": title or text[:40],
        "text": text,
        "category": category,
        "createdAt": now,
        "updatedAt": now,
    }
    items.insert(0, item)
    save_prompts(projects_root, items)
    return item


def delete_prompt(projects_root: Path, prompt_id: str) -> bool:
    items = load_prompts(projects_root)
    next_items = [x for x in items if str(x.get("id")) != prompt_id]
    if len(next_items) == len(items):
        return False
    save_prompts(projects_root, next_items)
    return True
