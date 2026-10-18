"""Media routers. Backend choice lives in image_factory / video_factory."""

from __future__ import annotations

from .image_factory import generate_image, image_backend
from .video_factory import generate_video_file, resolve_video_model, video_backend


def _secret(name: str, default: str = "") -> str:
    try:
        from settings_store import get_secret

        return (get_secret(name, default) or default or "").strip()
    except Exception:
        return default


def media_qa_enabled() -> bool:
    raw = (_secret("STUDIO_MEDIA_QA") or "1").strip().lower()
    return raw not in {"0", "false", "off", "no"}


__all__ = [
    "generate_image",
    "generate_video_file",
    "image_backend",
    "media_qa_enabled",
    "resolve_video_model",
    "video_backend",
]
