"""Advertising pins are gone from the inspiration seed and stay hidden if already stored."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STUDIO_SERVER = ROOT / "studio" / "server"
if str(STUDIO_SERVER) not in sys.path:
    sys.path.insert(0, str(STUDIO_SERVER))

import inspire_store  # noqa: E402

CONFIG = ROOT / "studio" / "config"


def _seed_items():
    return json.loads((CONFIG / "pinterest_seed.json").read_text(encoding="utf-8"))["items"]


def test_seed_has_no_ad_boards_or_blocked_ids():
    bl = inspire_store.blocklist()
    assert len(bl["ids"]) == 116
    for item in _seed_items():
        assert not inspire_store.is_blocked(item), item["id"]
        assert str(item.get("board") or "").lower() not in bl["boards"]


def test_is_blocked_by_id_board_and_paid_link():
    some_id = sorted(inspire_store.blocklist()["ids"])[0]
    assert inspire_store.is_blocked(item_id=some_id)
    assert inspire_store.is_blocked({"id": "x", "board": "Ad-only Pins"})
    assert inspire_store.is_blocked({"id": "x", "meta": {"board": "ad-only pins"}})
    assert inspire_store.is_blocked({"id": "x", "link": "https://a.example/?utm_medium=paid-social"})
    assert not inspire_store.is_blocked({"id": "x", "board": "Film Grab", "link": "https://filmgrab.com/"})


def test_already_stored_ad_pins_are_hidden_on_disk(tmp_path, monkeypatch):
    monkeypatch.setenv("PROJECTS_ROOT", str(tmp_path))
    import pg_backend

    monkeypatch.setattr(pg_backend, "enabled", lambda: False)
    blocked_id = sorted(inspire_store.blocklist()["ids"])[0]
    disk = tmp_path / ".inspire"
    disk.mkdir()
    for iid in (blocked_id, "keepme"):
        (disk / f"{iid}.bin").write_bytes(b"x" * 10)
        (disk / f"{iid}.json").write_text(json.dumps({"id": iid, "title": iid}), encoding="utf-8")
    rows, total = inspire_store.list_local(limit=50)
    assert [r["id"] for r in rows] == ["keepme"] and total == 1
    assert inspire_store.load_blob(blocked_id) is None
    assert inspire_store.load_blob("keepme") is not None
