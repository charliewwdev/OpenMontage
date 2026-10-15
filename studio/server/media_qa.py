"""Hard quality gates for generated / downloaded media (size + container magic).

Drama Studio does not run aesthetic scoring; this module only rejects empty or
structurally invalid files so broken outputs never enter the asset library as
"成功" stills/videos.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

# Minimum payload sizes — well below real Seedream / Seedance outputs.
_MIN_IMAGE = 256
_MIN_VIDEO = 1024
_MIN_AUDIO = 256


class MediaQAError(RuntimeError):
    pass


def _suffix(path: Path) -> str:
    return path.suffix.lower().lstrip(".")


def _kind_for(path: Path, kind: str | None = None) -> str:
    if kind:
        return kind
    suf = _suffix(path)
    if suf in {"png", "jpg", "jpeg", "webp", "gif", "bmp"}:
        return "image"
    if suf in {"mp4", "webm", "mov", "mkv"}:
        return "video"
    if suf in {"mp3", "wav", "m4a", "aac", "ogg"}:
        return "audio"
    return "other"


def _looks_like_image(head: bytes, suf: str) -> bool:
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return True
    if head[:3] == b"\xff\xd8\xff":
        return True
    if len(head) >= 12 and head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return True
    if head[:6] in (b"GIF87a", b"GIF89a"):
        return True
    # Allow extension mismatch only when magic is clear; otherwise fail closed.
    if suf in {"png", "jpg", "jpeg", "webp", "gif"}:
        return False
    return False


def _looks_like_video(head: bytes) -> bool:
    # ISO BMFF (mp4/mov): ....ftyp
    if len(head) >= 8 and head[4:8] == b"ftyp":
        return True
    if head.startswith(b"\x1aE\xdf\xa3"):  # EBML / webm / mkv
        return True
    return False


def _looks_like_audio(head: bytes, suf: str) -> bool:
    if head.startswith(b"ID3"):
        return True
    if len(head) >= 2 and head[0] == 0xFF and (head[1] & 0xE0) == 0xE0:
        return True  # MPEG frame sync
    if head.startswith(b"RIFF") and b"WAVE" in head[:16]:
        return True
    if head.startswith(b"OggS"):
        return True
    if suf in {"mp3", "wav", "m4a", "aac", "ogg"}:
        # m4a may be ftyp-based
        if len(head) >= 8 and head[4:8] == b"ftyp":
            return True
        return False
    return False


def inspect_media(path: Path | str, *, kind: str | None = None) -> dict[str, Any]:
    """Return health metadata; never raises."""
    p = Path(path)
    k = _kind_for(p, kind)
    if not p.is_file():
        return {"ok": False, "broken": True, "reason": "missing", "kind": k, "size": 0}
    size = p.stat().st_size
    if size <= 0:
        return {"ok": False, "broken": True, "reason": "empty", "kind": k, "size": 0}

    mins = {"image": _MIN_IMAGE, "video": _MIN_VIDEO, "audio": _MIN_AUDIO}
    min_size = mins.get(k, 1)
    if size < min_size:
        return {"ok": False, "broken": True, "reason": "too_small", "kind": k, "size": size}

    try:
        head = p.read_bytes()[:64]
    except OSError as exc:
        return {"ok": False, "broken": True, "reason": f"read_error:{exc}", "kind": k, "size": size}

    suf = _suffix(p)
    if k == "image" and not _looks_like_image(head, suf):
        return {"ok": False, "broken": True, "reason": "bad_image_magic", "kind": k, "size": size}
    if k == "video" and not _looks_like_video(head):
        return {"ok": False, "broken": True, "reason": "bad_video_magic", "kind": k, "size": size}
    if k == "audio" and not _looks_like_audio(head, suf):
        return {"ok": False, "broken": True, "reason": "bad_audio_magic", "kind": k, "size": size}

    return {"ok": True, "broken": False, "reason": "", "kind": k, "size": size}


def assert_media_ok(path: Path | str, *, kind: str | None = None, unlink_on_fail: bool = True) -> dict[str, Any]:
    """Raise MediaQAError when the file is empty or structurally invalid."""
    p = Path(path)
    info = inspect_media(p, kind=kind)
    if info.get("ok"):
        return info
    reason = info.get("reason") or "invalid"
    if unlink_on_fail and p.is_file():
        try:
            p.unlink()
        except OSError:
            pass
    raise MediaQAError(f"媒体质量检测未通过（{reason}，{info.get('size') or 0} bytes）")
