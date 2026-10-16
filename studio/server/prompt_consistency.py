"""Check a shot prompt against its dialogue and the project asset bible.

Vision QA only asks「画面像不像提示词」. This gate asks the earlier question:
「提示词有没有把对白、角色、场景、道具写错或写丢」.

Rules (deterministic, no extra model call):
- The speaker named in ``角色：对白`` must appear in the prompt.
- If the line names a visible piece of evidence (scar, ring, letter…),
  the prompt must show that evidence.
- A prop the line does not mention (phone, screen) must not steal the shot.
- ``@名字`` in the prompt must exist on a character / scene / prop in the bible.
"""

from __future__ import annotations

import re
from typing import Any

# Dialogue token → prompt must contain one of ``must``. ``focus`` is the repair clause.
_EVIDENCE: list[dict[str, Any]] = [
    {
        "id": "scar",
        "dialogue": ("伤疤", "旧疤", "疤痕", "手腕", "疤"),
        "must": ("疤", "手腕"),
        "focus": "大特写手腕内侧浅白色旧疤，拇指按在疤上，疤痕是画面主体",
    },
    {
        "id": "ring",
        "dialogue": ("戒指",),
        "must": ("戒指",),
        "focus": "画面主体是这枚戒指",
    },
    {
        "id": "letter",
        "dialogue": ("信件", "信封", "这封信"),
        "must": ("信",),
        "focus": "画面主体是这封信",
    },
    {
        "id": "photo",
        "dialogue": ("照片", "相片"),
        "must": ("照片", "相片"),
        "focus": "画面主体是这张照片",
    },
    {
        "id": "key",
        "dialogue": ("钥匙",),
        "must": ("钥匙",),
        "focus": "画面主体是这把钥匙",
    },
    {
        "id": "gun",
        "dialogue": ("手枪", "枪支", "收枪", "持枪"),
        "must": ("枪",),
        "focus": "画面主体含这把枪",
    },
    {
        "id": "blade",
        "dialogue": ("刀", "剑"),
        "must": ("刀", "剑"),
        "focus": "画面主体是这件兵器",
    },
]

# Props that often hijack a shot when the line is about something else.
_DISTRACTORS = ("手机", "屏幕", "平板", "偷拍")

_SPEAKER_RE = re.compile(r"^([^：:\n（(]{1,12})[：:]")
_AT_RE = re.compile(r"@([^\s@,，。；;（）()]+)")


def _dialogue_body(dialogue: str) -> str:
    text = (dialogue or "").strip()
    if "：" in text:
        return text.split("：", 1)[1]
    if ":" in text:
        return text.split(":", 1)[1]
    return text


def _speaker(dialogue: str) -> str:
    m = _SPEAKER_RE.match((dialogue or "").strip())
    return m.group(1).strip() if m else ""


def _strip_clauses(prompt: str, token: str) -> str:
    parts = re.split(r"[。；;]", prompt)
    kept = [p.strip() for p in parts if p.strip() and token not in p]
    if not kept:
        return prompt
    return "。".join(kept) + "。"


def check_shot_prompt(
    shot: dict[str, Any],
    *,
    entity_names: set[str] | None = None,
) -> dict[str, Any]:
    """Return ``{ok, issues}`` without mutating the shot."""
    prompt = str(shot.get("prompt") or "")
    dialogue = str(shot.get("dialogue") or "")
    body = _dialogue_body(dialogue)
    names = entity_names or set()
    issues: list[dict[str, str]] = []

    speaker = _speaker(dialogue)
    if speaker and speaker not in prompt:
        issues.append(
            {
                "code": "speaker_missing",
                "detail": f"对白说话人「{speaker}」没有出现在提示词里",
            }
        )

    for ev in _EVIDENCE:
        if not any(tok in body or tok in dialogue for tok in ev["dialogue"]):
            continue
        if any(tok in prompt for tok in ev["must"]):
            continue
        issues.append(
            {
                "code": "evidence_missing",
                "detail": f"对白提到「{ev['dialogue'][0]}」，提示词没有把它画出来",
            }
        )

    for token in _DISTRACTORS:
        if token in prompt and token not in body and token not in dialogue:
            # Only flag when the line already names some other evidence,
            # so a phone-call shot is not punished.
            line_has_other = any(
                any(tok in body or tok in dialogue for tok in ev["dialogue"]) for ev in _EVIDENCE
            )
            if line_has_other or token in ("手机", "屏幕", "偷拍"):
                if line_has_other:
                    issues.append(
                        {
                            "code": "distractor_prop",
                            "detail": f"对白没提「{token}」，提示词却把它写成了画面",
                        }
                    )

    for tag in _AT_RE.findall(prompt):
        base = tag.split("-", 1)[0]
        if names and base not in names:
            issues.append(
                {
                    "code": "unknown_asset",
                    "detail": f"提示词 @{base} 不在本集角色/场景/道具库",
                }
            )

    scene = str(shot.get("sceneName") or "").strip()
    location = str(shot.get("location") or "").strip()
    if scene and scene not in prompt and scene not in location:
        issues.append(
            {
                "code": "scene_missing",
                "detail": f"镜头场景「{scene}」没有写进提示词",
            }
        )

    # Dedupe by detail
    seen: set[str] = set()
    uniq: list[dict[str, str]] = []
    for item in issues:
        if item["detail"] in seen:
            continue
        seen.add(item["detail"])
        uniq.append(item)
    return {"ok": not uniq, "issues": uniq}


def repair_shot_prompt(
    shot: dict[str, Any],
    *,
    entity_names: set[str] | None = None,
) -> dict[str, Any]:
    """Rewrite the prompt so dialogue evidence wins, then re-check.

    Returns the same shape as ``check_shot_prompt`` plus ``repaired`` and ``prompt``.
    Does not save; caller writes ``shot['prompt']``.
    """
    prompt = str(shot.get("prompt") or "")
    dialogue = str(shot.get("dialogue") or "")
    body = _dialogue_body(dialogue)
    before = check_shot_prompt(shot, entity_names=entity_names)
    if before["ok"]:
        return {**before, "repaired": False, "prompt": prompt}

    speaker = _speaker(dialogue)
    if speaker and speaker not in prompt:
        prompt = f"说话人 @{speaker}。" + prompt

    for ev in _EVIDENCE:
        if not any(tok in body or tok in dialogue for tok in ev["dialogue"]):
            continue
        if any(tok in prompt for tok in ev["must"]):
            continue
        prompt = f"{ev['focus']}。" + prompt

    line_has_other = any(
        any(tok in body or tok in dialogue for tok in ev["dialogue"]) for ev in _EVIDENCE
    )
    if line_has_other:
        for token in _DISTRACTORS:
            if token in prompt and token not in body and token not in dialogue:
                prompt = _strip_clauses(prompt, token)

    scene = str(shot.get("sceneName") or "").strip()
    if scene and scene not in prompt:
        prompt = prompt.rstrip("。") + f"。场景：{scene}。"

    shot_view = {**shot, "prompt": prompt}
    after = check_shot_prompt(shot_view, entity_names=entity_names)
    return {**after, "repaired": prompt != str(shot.get("prompt") or ""), "prompt": prompt}


def entity_name_set(entities: list[dict[str, Any]] | None) -> set[str]:
    return {str(e.get("name") or "").strip() for e in (entities or []) if e.get("name") and not e.get("deletedAt")}
