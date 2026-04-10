"""Stock media source adapters.

Unified-protocol wrappers around free stock APIs (Pexels, Archive.org,
NASA, ...) used by `corpus_builder` to populate the local clip corpus.
See `base.py` for the protocol contract and the "adding a new source"
checklist.

Registry
--------
`all_sources()` returns one instance of every adapter known to the
package, in a stable order. `available_sources()` filters to the ones
whose `is_available()` returns True right now. The corpus builder
queries the latter during fan-out; it never imports adapters directly.

To register a new adapter: add its class to the `_REGISTRY` tuple
below. Order matters only as a tiebreak when two sources return
matching clips.
"""
from __future__ import annotations

from .archive_org import ArchiveOrgSource
from .base import Candidate, SearchFilters, StockSource
from .nasa import NasaSource
from .pexels import PexelsSource

__all__ = [
    "Candidate",
    "SearchFilters",
    "StockSource",
    "PexelsSource",
    "ArchiveOrgSource",
    "NasaSource",
    "all_sources",
    "available_sources",
    "get_source",
]

# Explicit, ordered list of every adapter class the package exposes.
# The corpus builder iterates this (filtered by availability) during
# fan-out. Order matters only as a tiebreak for identical clip ids.
_REGISTRY: tuple[type, ...] = (
    PexelsSource,
    ArchiveOrgSource,
    NasaSource,
)


def all_sources() -> list[StockSource]:
    """Instantiate every registered adapter, whether available or not.

    Returned instances are cheap — adapters keep no state beyond env
    var reads, so constructing them has no cost. Use this when you
    want to show the user what sources exist regardless of whether
    their credentials are configured.
    """
    return [cls() for cls in _REGISTRY]


def available_sources() -> list[StockSource]:
    """Return only the adapters whose `is_available()` is True.

    This is what the corpus builder uses during a normal run. An empty
    list means no sources are configured — the caller should surface
    that to the user with install instructions, not silently produce
    an empty corpus.
    """
    return [s for s in all_sources() if s.is_available()]


def get_source(name: str) -> StockSource:
    """Look up a single adapter by its `name` attribute.

    Raises `KeyError` if no registered adapter claims that name. Useful
    for tests and for agents that want to pin to a specific source
    (e.g. "only Archive.org for this topic").
    """
    for s in all_sources():
        if s.name == name:
            return s
    raise KeyError(f"No stock source registered with name={name!r}")
