"""Skill runtime: SKILL.md is the source of truth for entity-still prompts.

Also accumulates QA failure experience under PROJECTS_ROOT/.skill_experience/
so Skill 管理页 and retry loops share the same patches.
"""

from __future__ import annotations

import json
import re
import threading
import time
from pathlib import Path
from typing import Any

_LOCK = threading.Lock()
_SKILL_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}

# Built-in seeds (also mirrored in SKILL.md Runtime YAML). Merged with on-disk experience.
_DEFAULT_EXPERIENCE: list[dict[str, Any]] = [
    {
        "id": "injury-bandage",
        "skillId": "drama-entity-still",
        "kinds": ["character"],
        "matchReason": ["bandage", "绷带", "white bandage", "injury", "受伤", "blood stain", "血迹"],
        "matchVariant": ["受伤", "绷带", "伤"],
        "promptBoost": (
            "Show thick WHITE medical gauze bandage on the LEFT shoulder/upper chest, "
            "and a blood-stained or torn dark coat. Half-body framing so the bandage is visible. "
            "Keep the same East Asian male face when a reference is used."
        ),
        "negativeBoost": (
            "clean uninjured clothes, no bandage, pristine coat, forehead wound only, "
            "cheek cut only, blue plastic sheet, towel around neck"
        ),
        "source": "seed",
        "hits": 0,
    },
    {
        "id": "identity-lock",
        "skillId": "drama-entity-still",
        "kinds": ["character"],
        "matchReason": ["face", "identity", "different person", "五官", "不像", "wrong face"],
        "matchVariant": [],
        "promptBoost": (
            "Identity lock: same East Asian face as reference still — identical bone structure, "
            "eyes, nose, jawline and hairline; only wardrobe/injury state may change."
        ),
        "negativeBoost": "different face, face swap, new identity, younger or older face",
        "source": "seed",
        "hits": 0,
    },
    {
        "id": "scene-no-people",
        "skillId": "drama-entity-still",
        "kinds": ["scene"],
        "matchReason": ["person", "people", "face", "character", "人物", "人脸"],
        "matchVariant": [],
        "promptBoost": "Empty location plate only — absolutely no human figures, no faces, no silhouettes.",
        "negativeBoost": "person, people, face, portrait, crowd, silhouette",
        "source": "seed",
        "hits": 0,
    },
]


def skills_root() -> Path:
    return Path(__file__).resolve().parents[1] / "skills"


def experience_dir(projects_root: Path | None = None) -> Path:
    root = Path(projects_root or _projects_root() or ".")
    path = root / ".skill_experience"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _projects_root() -> Path | None:
    import os

    raw = (os.environ.get("PROJECTS_ROOT") or "").strip()
    return Path(raw) if raw else None


def load_skill_md(skill_id: str) -> str:
    path = skills_root() / skill_id / "SKILL.md"
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8")


def _parse_runtime_yaml(md: str) -> dict[str, Any]:
    """Extract ```yaml ... ``` block under ## Runtime (best-effort, no PyYAML required)."""
    m = re.search(r"##\s*Runtime\b.*?\n```ya?ml\s*\n(.*?)```", md, flags=re.S | re.I)
    if not m:
        return {}
    block = m.group(1)
    # Minimal subset parser for our skill files (key: value / nested lists of maps).
    try:
        import yaml  # type: ignore

        data = yaml.safe_load(block)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def get_skill_runtime(skill_id: str = "drama-entity-still") -> dict[str, Any]:
    now = time.time()
    with _LOCK:
        hit = _SKILL_CACHE.get(skill_id)
        if hit and now - hit[0] < 30:
            return hit[1]
    md = load_skill_md(skill_id)
    runtime = _parse_runtime_yaml(md)
    out = {
        "skillId": skill_id,
        "title": skill_id,
        "runtime": runtime,
        "md": md,
    }
    with _LOCK:
        _SKILL_CACHE[skill_id] = (now, out)
    return out


def experience_path(skill_id: str, projects_root: Path | None = None) -> Path:
    return experience_dir(projects_root) / f"{skill_id}.json"


def load_experience(skill_id: str = "drama-entity-still", projects_root: Path | None = None) -> list[dict[str, Any]]:
    path = experience_path(skill_id, projects_root)
    learned: list[dict[str, Any]] = []
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                learned = list(data.get("patches") or [])
            elif isinstance(data, list):
                learned = data
        except Exception:
            learned = []
    by_id = {p["id"]: dict(p) for p in _DEFAULT_EXPERIENCE if p.get("id")}
    for p in learned:
        if not isinstance(p, dict) or not p.get("id"):
            continue
        pid = str(p["id"])
        if pid in by_id:
            merged = {**by_id[pid], **p}
            merged["hits"] = int(by_id[pid].get("hits") or 0) + int(p.get("hits") or 0)
            by_id[pid] = merged
        else:
            by_id[pid] = dict(p)
    # Runtime YAML seeds
    runtime = get_skill_runtime(skill_id).get("runtime") or {}
    for p in runtime.get("experience_seeds") or []:
        if not isinstance(p, dict) or not p.get("id"):
            continue
        pid = str(p["id"])
        base = by_id.get(pid, {})
        by_id[pid] = {
            **base,
            **p,
            "skillId": skill_id,
            "source": base.get("source") or "skill_md",
            "hits": int(base.get("hits") or 0),
        }
    return list(by_id.values())


def save_experience(skill_id: str, patches: list[dict[str, Any]], projects_root: Path | None = None) -> None:
    path = experience_path(skill_id, projects_root)
    payload = {
        "skillId": skill_id,
        "updatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "patches": patches,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def record_qa_failure(
    *,
    skill_id: str = "drama-entity-still",
    kind: str,
    variant: str = "",
    reason: str,
    entity_name: str = "",
    projects_root: Path | None = None,
) -> list[dict[str, Any]]:
    """Bump matching patches or create a learned stub from the failure reason."""
    reason_l = (reason or "").strip()
    if not reason_l or reason_l.startswith("generate_error:未配置"):
        return []
    patches = load_experience(skill_id, projects_root)
    matched: list[dict[str, Any]] = []
    for p in patches:
        if _patch_matches(p, kind=kind, variant=variant, reason=reason_l):
            p["hits"] = int(p.get("hits") or 0) + 1
            p["lastReason"] = reason_l[:240]
            p["lastEntity"] = entity_name
            p["updatedAt"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            matched.append(p)
    if not matched:
        # Auto-learn a lightweight patch from recurring tokens.
        slug = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "-", reason_l.lower())[:40].strip("-") or "misc"
        pid = f"auto-{slug}"
        existing = next((p for p in patches if p.get("id") == pid), None)
        if existing:
            existing["hits"] = int(existing.get("hits") or 0) + 1
            existing["lastReason"] = reason_l[:240]
            matched = [existing]
        else:
            tokens = re.findall(r"[A-Za-z]{4,}|[\u4e00-\u9fff]{2,}", reason_l)[:6]
            stub = {
                "id": pid,
                "skillId": skill_id,
                "kinds": [kind] if kind else [],
                "matchReason": tokens or [reason_l[:40]],
                "matchVariant": [],
                "promptBoost": f"Fix previous QA failure: {reason_l[:180]}",
                "negativeBoost": "",
                "source": "learned",
                "hits": 1,
                "lastReason": reason_l[:240],
                "lastEntity": entity_name,
                "updatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            patches.append(stub)
            matched = [stub]
    # Persist only non-seed or seeds with hits (keep file useful).
    to_save = [p for p in patches if p.get("source") == "learned" or int(p.get("hits") or 0) > 0]
    save_experience(skill_id, to_save, projects_root)
    return matched


def _patch_matches(patch: dict[str, Any], *, kind: str, variant: str, reason: str) -> bool:
    kinds = [str(k) for k in (patch.get("kinds") or []) if k]
    if kinds and kind and kind not in kinds:
        return False
    reason_l = reason.lower()
    variant_l = (variant or "").lower()
    for token in patch.get("matchVariant") or []:
        if str(token).lower() in variant_l:
            return True
    for token in patch.get("matchReason") or []:
        if str(token).lower() in reason_l:
            return True
    return False


def match_experience_patches(
    *,
    skill_id: str = "drama-entity-still",
    kind: str,
    variant: str = "",
    reason: str = "",
    projects_root: Path | None = None,
) -> list[dict[str, Any]]:
    patches = load_experience(skill_id, projects_root)
    out = []
    for p in patches:
        # Variant-only match when no reason yet (first attempt).
        if reason:
            if _patch_matches(p, kind=kind, variant=variant, reason=reason):
                out.append(p)
        else:
            kinds = [str(k) for k in (p.get("kinds") or []) if k]
            if kinds and kind not in kinds:
                continue
            for token in p.get("matchVariant") or []:
                if str(token).lower() in (variant or "").lower():
                    out.append(p)
                    break
    return out


def apply_experience_to_prompt(
    prompt: str,
    negative: str | None,
    patches: list[dict[str, Any]],
) -> tuple[str, str | None]:
    boosts = [str(p.get("promptBoost") or "").strip() for p in patches if p.get("promptBoost")]
    negs = [str(p.get("negativeBoost") or "").strip() for p in patches if p.get("negativeBoost")]
    if boosts:
        prompt = prompt.rstrip() + " " + " ".join(boosts)
    if negs:
        extra = ", ".join(negs)
        negative = f"{negative}, {extra}" if negative else extra
    return prompt, negative


def experience_summary(skill_id: str = "drama-entity-still", projects_root: Path | None = None) -> dict[str, Any]:
    patches = load_experience(skill_id, projects_root)
    learned = [p for p in patches if p.get("source") == "learned"]
    seeds = [p for p in patches if p.get("source") != "learned"]
    top = sorted(patches, key=lambda p: int(p.get("hits") or 0), reverse=True)[:8]
    return {
        "skillId": skill_id,
        "patchCount": len(patches),
        "learnedCount": len(learned),
        "seedCount": len(seeds),
        "totalHits": sum(int(p.get("hits") or 0) for p in patches),
        "topFailures": [
            {
                "id": p.get("id"),
                "hits": int(p.get("hits") or 0),
                "source": p.get("source"),
                "lastReason": p.get("lastReason") or "",
                "lastEntity": p.get("lastEntity") or "",
                "promptBoost": (p.get("promptBoost") or "")[:160],
            }
            for p in top
            if int(p.get("hits") or 0) > 0 or p.get("source") == "learned"
        ],
        "patches": patches,
    }
