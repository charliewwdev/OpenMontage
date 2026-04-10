"""Archive.org stock video adapter.

Targets public-domain film and home-movie collections on archive.org:

    - **prelinger**: Rick Prelinger's archive of ephemeral films
      (industrial, educational, advertising, 1920s-1980s). The single
      best source of documentary-grade B-roll for 20th century themes.
    - **opensource_movies**: broader public-domain and CC-licensed film
      uploads — a grab bag but useful when Prelinger is thin on a topic.
    - **home_movies**: anonymous personal footage. The soul of any
      nostalgic or observational documentary montage lives here.

Archive.org requires no API key. Everything is open.

Fetch pattern
-------------
The search API (``advancedsearch.php``) returns metadata records with
identifiers but not file lists. To get downloadable URLs we need a
second call to ``/metadata/<identifier>`` per hit. This adapter pays
that round-trip cost during `search()` so the `Candidate` it returns
carries a ready-to-use `download_url`. For a per_page of 20, expect
~21 HTTP calls per search — slow but fully serial and cache-friendly.

Dimensions are sometimes missing from file metadata. When they are,
the `Candidate` carries `width=0, height=0` and the corpus builder is
expected to probe the clip with ffprobe post-download.

Licence
-------
Prelinger collection items are public domain. Broader
`opensource_movies` items are usually CC0 or CC-BY. We record the
collection and `licenseurl` (when present) so the agent can attribute
correctly if it wants to, but no attribution is legally required.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Optional

from .base import Candidate, SearchFilters


_SEARCH_URL = "https://archive.org/advancedsearch.php"
_METADATA_URL = "https://archive.org/metadata"
_DOWNLOAD_URL = "https://archive.org/download"

# Default collections to bias toward. Overridable via SearchFilters.extra
# in a future refinement; for now these are baked in because they give
# the best documentary-montage hit rate.
_DEFAULT_COLLECTIONS = ("prelinger", "opensource_movies", "home_movies")

# File formats we accept, in preference order. Archive.org runs every
# upload through a derivative pipeline so most items have multiple
# renditions — we want the best mp4.
_VIDEO_FORMAT_PRIORITY = (
    "h.264",                  # mp4, usually 480p or 720p
    "MPEG4",                  # older mp4 encoding
    "h.264 HD",               # less common, but best quality
    "512Kb MPEG4",            # last resort — lowest quality derivative
    "Matroska",               # mkv
    "WebM",                   # webm
)


class ArchiveOrgSource:
    """Adapter for public-domain video on archive.org.

    Satisfies `StockSource`. Stateless, no credentials.
    """

    name = "archive_org"
    display_name = "Archive.org"
    provider = "archive_org"
    priority = 20
    install_instructions = (
        "No setup required. Archive.org is available without API keys."
    )
    supports = {"video": True, "image": False}

    def is_available(self) -> bool:
        # No API key, no config. As long as the network is up, we're
        # available. The corpus builder will catch network errors in
        # the per-source try block.
        return True

    # ------------------------------------------------------------------
    # Public protocol
    # ------------------------------------------------------------------

    def search(self, query: str, filters: SearchFilters) -> list[Candidate]:
        """Search Archive.org for matching video items.

        Two-stage: (1) advancedsearch for identifiers, (2) per-item
        metadata fetch for file lists. Images are not supported — this
        adapter returns an empty list for `kind="image"` since
        Archive.org's image collections are a separate ecosystem (see
        `nasa.py` for astronomy imagery instead).
        """
        kind = (filters.kind or "video").lower()
        if kind not in ("video", "any"):
            return []

        import requests  # lazy

        q = self._build_query(query)
        params = [
            ("q", q),
            ("fl[]", "identifier"),
            ("fl[]", "title"),
            ("fl[]", "description"),
            ("fl[]", "creator"),
            ("fl[]", "date"),
            ("fl[]", "subject"),
            ("fl[]", "licenseurl"),
            ("fl[]", "collection"),
            ("rows", str(max(1, min(filters.per_page, 50)))),
            ("page", str(max(1, filters.page))),
            ("output", "json"),
        ]

        r = requests.get(_SEARCH_URL, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        docs = (data.get("response") or {}).get("docs", []) or []

        out: list[Candidate] = []
        for doc in docs:
            cand = self._hydrate_candidate(doc, filters)
            if cand is not None:
                out.append(cand)
        return out

    def download(self, candidate: Candidate, out_path: Path) -> Path:
        """Stream the candidate's file to `out_path`.

        Same pattern as the Pexels adapter — no caching, corpus builder
        decides.
        """
        import requests  # lazy

        if not candidate.download_url:
            raise ValueError(
                f"Candidate {candidate.clip_id} has no download_url"
            )

        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        with requests.get(
            candidate.download_url, stream=True, timeout=300
        ) as r:
            r.raise_for_status()
            with open(out_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=1 << 16):
                    if chunk:
                        f.write(chunk)
        return out_path

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _build_query(self, user_query: str) -> str:
        """Wrap the user's query with mediatype + collection filters.

        Archive.org's query language is Solr-style — parentheses and
        booleans work, and spaces default to AND. We quote the user
        query so multi-word phrases stay intact.
        """
        coll = " OR ".join(f"collection:{c}" for c in _DEFAULT_COLLECTIONS)
        user = user_query.strip()
        if not user:
            return f"mediatype:movies AND ({coll})"
        # Quote the user query as a phrase AND a loose-term search so
        # we get both precise matches and relevance-ranked hits.
        return f'mediatype:movies AND ({coll}) AND ({user})'

    def _hydrate_candidate(
        self, doc: dict, filters: SearchFilters
    ) -> Optional[Candidate]:
        """Turn a search-doc identifier into a full Candidate.

        Fetches the item's file list and picks the best playable
        rendition. Returns None if the item has no usable files or if
        the item's duration falls outside the filter range.
        """
        import requests  # lazy

        identifier = doc.get("identifier")
        if not identifier:
            return None

        try:
            r = requests.get(f"{_METADATA_URL}/{identifier}", timeout=30)
            r.raise_for_status()
            meta = r.json()
        except Exception:
            # Swallow per-item fetch failures — one bad item shouldn't
            # poison the whole search. Alternative would be to raise and
            # have corpus_builder catch per-source, but at this layer we
            # can keep going.
            return None

        files = meta.get("files") or []
        picked = _pick_video_file(files)
        if picked is None:
            return None

        duration = _parse_length(picked.get("length"))
        if filters.min_duration is not None and duration < filters.min_duration:
            return None
        if filters.max_duration is not None and 0 < duration < filters.max_duration:
            # 0 means "unknown" — keep those, reject only known-too-long
            pass
        if filters.max_duration is not None and duration > filters.max_duration:
            return None

        width = _safe_int(picked.get("width"))
        height = _safe_int(picked.get("height"))
        if filters.min_width is not None and width and width < filters.min_width:
            return None

        # Build the direct download URL. archive.org/download/<id>/<file>
        # is the stable public pattern and works without auth.
        file_name = picked.get("name", "")
        download_url = f"{_DOWNLOAD_URL}/{identifier}/{file_name}"

        # Tags: flatten title + description + subject. Archive.org is
        # verbose, so we truncate to keep the CLIP text encoder focused
        # on the most important tokens (77-token limit anyway).
        title = _to_text(doc.get("title"))
        description = _to_text(doc.get("description"))
        subject = _to_text(doc.get("subject"))
        source_tags = " ".join(
            s for s in (title, description, subject) if s
        ).strip()
        if len(source_tags) > 500:
            source_tags = source_tags[:500]

        creator = _to_text(doc.get("creator"))
        collection = _to_text(doc.get("collection"))
        license_url = _to_text(doc.get("licenseurl"))
        license_text = license_url or _license_from_collection(collection)

        return Candidate(
            source=self.name,
            source_id=identifier,
            source_url=f"https://archive.org/details/{identifier}",
            download_url=download_url,
            kind="video",
            width=width,
            height=height,
            duration=duration,
            creator=creator,
            license=license_text,
            source_tags=source_tags,
            thumbnail_url=f"https://archive.org/services/img/{identifier}",
            extra={
                "collection": collection,
                "date": _to_text(doc.get("date")),
                "format": picked.get("format"),
                "file_name": file_name,
                "file_size_bytes": _safe_int(picked.get("size")),
            },
        )


# ----------------------------------------------------------------------
# Module-level helpers
# ----------------------------------------------------------------------


def _pick_video_file(files: list[dict]) -> Optional[dict]:
    """Pick the best playable video file from an Archive.org files list.

    Preference order is defined by `_VIDEO_FORMAT_PRIORITY`. Within a
    format, we prefer the largest file (size as a quality proxy), and
    reject obvious thumbnails / derivative animations.
    """
    if not files:
        return None

    by_format: dict[str, list[dict]] = {}
    for f in files:
        fmt = (f.get("format") or "").strip()
        name = (f.get("name") or "").lower()
        # Skip non-video
        if fmt not in _VIDEO_FORMAT_PRIORITY:
            continue
        # Skip degenerate renditions and thumbnails regardless of format
        if any(tag in name for tag in ("thumb", "preview", ".gif")):
            continue
        by_format.setdefault(fmt, []).append(f)

    for fmt in _VIDEO_FORMAT_PRIORITY:
        bucket = by_format.get(fmt)
        if not bucket:
            continue
        bucket.sort(key=lambda f: _safe_int(f.get("size")), reverse=True)
        return bucket[0]
    return None


_HMS_RE = re.compile(r"^(\d+):(\d+):(\d+(?:\.\d+)?)$")
_MS_RE = re.compile(r"^(\d+):(\d+(?:\.\d+)?)$")


def _parse_length(value: Any) -> float:
    """Parse Archive.org's `length` field into seconds.

    The field is usually "HH:MM:SS.ss" or "MM:SS.ss" or a bare float
    as a string. Missing / unparseable values return 0.0 which the
    caller interprets as "unknown, pass any duration filter".
    """
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip()
    if not s:
        return 0.0
    m = _HMS_RE.match(s)
    if m:
        h, mn, sec = m.groups()
        return int(h) * 3600 + int(mn) * 60 + float(sec)
    m = _MS_RE.match(s)
    if m:
        mn, sec = m.groups()
        return int(mn) * 60 + float(sec)
    try:
        return float(s)
    except ValueError:
        return 0.0


def _safe_int(value: Any) -> int:
    """Parse a value to int, tolerating strings, None, and garbage."""
    if value is None:
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return 0


def _to_text(value: Any) -> str:
    """Flatten Archive.org's sometimes-list-sometimes-string fields.

    The search API returns `creator`, `subject`, and `description` as
    either a string or a list of strings depending on the item. We
    always join with spaces so the caller sees a single str.
    """
    if value is None:
        return ""
    if isinstance(value, list):
        return " ".join(str(x) for x in value if x is not None).strip()
    return str(value).strip()


def _license_from_collection(collection: str) -> str:
    """Infer licence text from a collection name when no licenseurl is set.

    Prelinger items are universally public domain; broader opensource
    collections usually are too but we're less sure, so we hedge.
    """
    col = collection.lower()
    if "prelinger" in col:
        return "Public Domain (Prelinger Archives)"
    if "home_movies" in col:
        return "Public Domain (archive.org home movies)"
    return "Public Domain / CC (archive.org — verify per item)"
