"""Extract plain text from uploaded script files."""

from __future__ import annotations

import re
from pathlib import Path


def guess_title(text: str, filename: str = "") -> str:
    for line in (text or "").splitlines():
        cleaned = line.strip().lstrip("#").strip()
        if cleaned:
            return cleaned[:40]
    stem = Path(filename or "未命名剧本").stem
    return stem[:40] or "未命名剧本"


def extract_text(filename: str, data: bytes) -> str:
    name = (filename or "").lower()
    if name.endswith(".docx"):
        return _docx_text(data)
    # txt / md / fallback
    for enc in ("utf-8", "utf-8-sig", "gb18030", "latin-1"):
        try:
            return data.decode(enc)
        except Exception:
            continue
    return data.decode("utf-8", errors="ignore")


def _docx_text(data: bytes) -> str:
    try:
        import io

        from docx import Document  # type: ignore

        doc = Document(io.BytesIO(data))
        parts = [p.text.strip() for p in doc.paragraphs if p.text and p.text.strip()]
        return "\n\n".join(parts)
    except ImportError as exc:
        raise RuntimeError("服务器未安装 python-docx，无法解析 DOCX") from exc
    except Exception as exc:
        raise RuntimeError(f"DOCX 解析失败：{exc}") from exc


_SPEAKER_LINE = re.compile(r"^([^：:\n「」\"“]{1,24})\s*[：:]\s*(.+)$")
_QUOTED = re.compile(r"[「\"“]([^」\"”]{2,120})[」\"”]")
_STAGE_HINT = re.compile(r"^(内景|外景|场景|镜头|SHOT|\[)", re.I)


def extract_dialogue_lines(content: str, limit: int = 40) -> list[dict[str, str]]:
    """Pull spoken lines from episode markdown-ish text (speaker + quote)."""
    text = (content or "").strip()
    if not text:
        return []
    lines: list[dict[str, str]] = []
    seen: set[str] = set()

    def push(speaker: str, spoken: str) -> None:
        sp = re.sub(r"(问|说|道|喊|叫|答)$", "", (speaker or "旁白").strip())[:24] or "旁白"
        tx = re.sub(r'^[「"“]|[」"”]$', "", (spoken or "").strip())
        # Drop stage directions so TTS does not read（冷笑）/（低声）
        tx = re.sub(r"[（(][^）)]{0,24}[）)]", "", tx).strip()
        tx = re.sub(r"\s+", "", tx) if re.fullmatch(r"[\u4e00-\u9fff\s，。！？、…]+", tx or "") else tx.strip()
        if len(tx) < 2:
            return
        key = f"{sp}::{tx}"
        if key in seen:
            return
        seen.add(key)
        lines.append({"speaker": sp, "text": tx})

    for raw in text.splitlines():
        line = raw.strip()
        if not line or re.match(r"^#{1,6}\s", line) or re.match(r"^[-*]{3,}$", line):
            continue
        if _STAGE_HINT.match(line) and len(line) < 40:
            continue

        m = _SPEAKER_LINE.match(line)
        if m:
            push(m.group(1), m.group(2))
            continue

        for qm in _QUOTED.finditer(line):
            before = line[: qm.start()]
            name_hit = re.search(r"([\u4e00-\u9fff·]{2,12})[^「\"“]{0,12}$", before)
            push(name_hit.group(1) if name_hit else "对白", qm.group(1))

    if not lines:
        for raw in text.splitlines():
            line = re.sub(r"^[-*]\s+", "", raw).strip()
            if 8 <= len(line) <= 80 and not _STAGE_HINT.match(line):
                push("旁白", line)
            if len(lines) >= 6:
                break
    return lines[:limit]


def dialogue_lines_for_episode(
    content: str,
    shots: list | None = None,
    *,
    limit: int = 40,
) -> list[dict[str, str]]:
    """Prefer structured speaker+text lines for multi-voice drama dubbing.

    Never prefixes with 「X说：」— each line is spoken as the character.
    Shot `dialogue` fields (in shot order) win when they yield ≥2 lines.
    """
    shot_lines: list[dict[str, str]] = []
    for sh in sorted(shots or [], key=lambda s: int(s.get("shotOrder") or 0)):
        raw = str(sh.get("dialogue") or "").strip()
        if len(raw) < 2:
            continue
        # "角色：台词" or bare quote
        m = _SPEAKER_LINE.match(raw)
        if m:
            sp = re.sub(r"(问|说|道|喊|叫|答)$", "", m.group(1).strip())[:24] or "对白"
            tx = re.sub(r'^[「"“]|[」"”]$', "", m.group(2).strip())
            if len(tx) >= 2:
                shot_lines.append({"speaker": sp, "text": tx})
                continue
        chars = sh.get("characters") or []
        speaker = str(chars[0]).strip() if chars else "对白"
        shot_lines.append({"speaker": speaker[:24] or "对白", "text": raw[:400]})
    if len(shot_lines) >= 2:
        return shot_lines[:limit]

    items = extract_dialogue_lines(content, limit=limit)
    if items:
        return items
    # Last resort: short narration chunks (still without 「说：」)
    compact: list[dict[str, str]] = []
    for raw in (content or "").splitlines():
        line = raw.strip()
        if not line or _STAGE_HINT.match(line) or re.match(r"^#{1,6}\s", line):
            continue
        if 8 <= len(line) <= 80:
            compact.append({"speaker": "旁白", "text": line})
        if len(compact) >= 6:
            break
    return compact[:limit]


def dialogue_from_episode(content: str, limit: int = 1200) -> str:
    """Flatten spoken lines for preview/legacy; spoken text only (no「X说：」)."""
    items = dialogue_lines_for_episode(content, limit=60)
    if not items:
        return ""
    joined = "。".join(item["text"] for item in items)
    return joined[:limit]
