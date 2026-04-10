"""Wikimedia Commons stock media adapter.

Provides image and video search over Wikimedia Commons using the
MediaWiki API. Commons is a uniquely useful documentary source because
it mixes public-domain historical imagery, recent CC-licensed videos,
and educational media under one searchable catalogue.
"""
from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Any

from .base import Candidate, SearchFilters


_API_URL = "https://commons.wikimedia.org/w/api.php"
_USER_AGENT = "OpenMontageBot/0.1 (https://github.com/charliewwdev/OpenMontage)"
_COMMONS_LICENSE = "Wikimedia Commons (verify per-file license)"
_HTML_TAG_RE = re.compile(r"<[^>]+>")


class WikimediaSource:
    """Adapter for Wikimedia Commons media search."""

    name = "wikimedia"
    display_name = "Wikimedia Commons"
    provider = "wikimedia"
    priority = 25
    install_instructions = (
        "No setup required. Wikimedia Commons media search works without API keys."
    )
    supports = {"video": True, "image": True}

    def is_available(self) -> bool:
        return True

    def search(self, query: str, filters: SearchFilters) -> list[Candidate]:
        import requests  # lazy

        params = {
            "action": "query",
            "format": "json",
            "generator": "search",
            "gsrsearch": _build_search_query(query, filters.kind),
            "gsrnamespace": 6,
            "gsrlimit": max(1, min(filters.per_page, 50)),
            "gsroffset": max(0, (max(filters.page, 1) - 1) * max(1, min(filters.per_page, 50))),
            "prop": "imageinfo|info",
            "iiprop": "url|size|mime|extmetadata|mediatype",
            "iiurlwidth": 640,
            "inprop": "url",
        }

        r = requests.get(
            _API_URL,
            params=params,
            headers={"User-Agent": _USER_AGENT},
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()
        pages = list(((data.get("query") or {}).get("pages") or {}).values())
        pages.sort(key=lambda page: int(page.get("index", 0)))

        out: list[Candidate] = []
        for page in pages:
            cand = _page_to_candidate(page, filters)
            if cand is not None:
                out.append(cand)
        return out

    def download(self, candidate: Candidate, out_path: Path) -> Path:
        import requests  # lazy

        if not candidate.download_url:
            raise ValueError(f"Candidate {candidate.clip_id} has no download_url")

        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        with requests.get(
            candidate.download_url,
            stream=True,
            timeout=300,
            headers={"User-Agent": _USER_AGENT},
        ) as r:
            r.raise_for_status()
            with open(out_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=1 << 16):
                    if chunk:
                        f.write(chunk)
        return out_path


def _build_search_query(query: str, kind: str) -> str:
    user_query = query.strip()
    kind = (kind or "video").lower()
    if kind == "video":
        return f"filetype:video {user_query}".strip()
    if kind == "image":
        return f"filetype:image {user_query}".strip()
    return user_query


def _page_to_candidate(page: dict[str, Any], filters: SearchFilters) -> Candidate | None:
    infos = page.get("imageinfo") or []
    if not infos:
        return None
    info = infos[0]
    mime = (info.get("mime") or "").lower()
    kind = _kind_from_mime(mime, page.get("title", ""))

    requested_kind = (filters.kind or "video").lower()
    if requested_kind == "video" and kind != "video":
        return None
    if requested_kind == "image" and kind != "image":
        return None

    width = int(info.get("width") or 0)
    height = int(info.get("height") or 0)
    duration = float(info.get("duration") or 0.0)

    if filters.min_width is not None and width and width < filters.min_width:
        return None
    if filters.min_duration is not None and duration and duration < filters.min_duration:
        return None
    if filters.max_duration is not None and duration and duration > filters.max_duration:
        return None
    if filters.orientation and not _matches_orientation(filters.orientation, width, height):
        return None

    meta = info.get("extmetadata") or {}
    object_name = _meta_value(meta, "ObjectName")
    description = _meta_value(meta, "ImageDescription")
    categories = _meta_value(meta, "Categories")
    creator = _meta_value(meta, "Artist")
    license_name = _meta_value(meta, "LicenseShortName")
    usage_terms = _meta_value(meta, "UsageTerms")
    source_tags = " ".join(part for part in (object_name, description, categories) if part).strip()
    if len(source_tags) > 500:
        source_tags = source_tags[:500]

    title = page.get("title", "")
    page_id = str(page.get("pageid") or title.replace("File:", "", 1))
    source_url = info.get("descriptionurl") or page.get("canonicalurl") or ""

    return Candidate(
        source=WikimediaSource.name,
        source_id=page_id,
        source_url=source_url,
        download_url=info.get("url", "") or "",
        kind=kind,
        width=width,
        height=height,
        duration=duration,
        creator=creator,
        license=license_name or usage_terms or _COMMONS_LICENSE,
        source_tags=source_tags,
        thumbnail_url=info.get("thumburl", "") or info.get("url", "") or "",
        extra={
            "mime": mime,
            "title": title,
            "mediatype": info.get("mediatype"),
            "descriptionshorturl": info.get("descriptionshorturl"),
        },
    )


def _kind_from_mime(mime: str, title: str) -> str:
    if mime.startswith("video/") or title.lower().endswith((".webm", ".ogv", ".ogg")):
        return "video"
    return "image"


def _matches_orientation(orientation: str, width: int, height: int) -> bool:
    if not width or not height:
        return True
    if orientation == "landscape":
        return width >= height
    if orientation == "portrait":
        return height > width
    if orientation == "square":
        return width == height
    return True


def _meta_value(meta: dict[str, Any], key: str) -> str:
    raw = ((meta.get(key) or {}).get("value")) or ""
    if not raw:
        return ""
    text = html.unescape(str(raw))
    text = _HTML_TAG_RE.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text
