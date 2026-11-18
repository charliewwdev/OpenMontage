"""Prompt library (提示词库): shipped data, read-only API and save-to-my-prompts."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
STUDIO_SERVER = ROOT / "studio" / "server"
if str(STUDIO_SERVER) not in sys.path:
    sys.path.insert(0, str(STUDIO_SERVER))

import prompt_library  # noqa: E402

DATA = ROOT / "studio" / "config" / "prompt_library"
LIBRARY = ROOT / "prompts" / "library"
LOCALES = ROOT / "studio" / "config" / "locales"
ALLOWED_LICENSES = {"CC-BY-4.0", "CC0-1.0", "Apache-2.0", "MIT"}
BANNED = re.compile(r"免费|从零|零成本|\bfree\b|from scratch|no subscription|calesthio", re.IGNORECASE)


def _items() -> list[dict]:
    return json.loads((DATA / "prompts.json").read_text(encoding="utf-8"))


# ------------------------------------------------------------------ data


def test_every_entry_carries_source_license_and_attribution():
    items = _items()
    assert len(items) == json.loads((DATA / "stats.json").read_text(encoding="utf-8"))["total"]
    ids = [x["id"] for x in items]
    assert len(ids) == len(set(ids))
    for x in items:
        assert x["license"] in ALLOWED_LICENSES, x["id"]
        assert x["attribution"].strip(), x["id"]
        assert x["source"]["name"] and x["source"]["url"], x["id"]
        assert x["license_url"].startswith("https://"), x["id"]
        assert x["prompt_zh"].strip() and x["prompt_en"].strip(), x["id"]
        assert x["title"]["zh"].strip() and x["title"]["en"].strip(), x["id"]


def test_license_texts_and_attribution_ship_with_the_data():
    for d in (LIBRARY, DATA):
        assert (d / "ATTRIBUTION.md").is_file()
        for name in ("Apache-2.0.txt", "CC-BY-4.0.txt", "CC0-1.0.txt", "awesome-ad-video-prompts-LICENSE.txt"):
            assert (d / "LICENSES" / name).stat().st_size > 0, (d, name)
    assert (DATA / "ATTRIBUTION.md").read_text(encoding="utf-8") == (LIBRARY / "ATTRIBUTION.md").read_text(
        encoding="utf-8"
    )
    used = {x["license"] for x in _items()}
    if "Apache-2.0" in used:
        assert "Apache License" in (DATA / "LICENSES" / "Apache-2.0.txt").read_text(encoding="utf-8")


def test_basic_examples_are_exactly_the_vbench_one_liners():
    for x in _items():
        is_vbench = x["source"]["name"].startswith("Vchitect/VBench")
        assert ("基础例句" in x["tags"]) == is_vbench, x["id"]


def test_ai_translation_flag_only_on_imported_entries():
    for x in _items():
        if x["translated"] == "machine":
            assert x["source"]["name"] != "OpenMontage", x["id"]
            assert "AI-assisted" in x["attribution"], x["id"]


def test_no_banned_promo_words_in_entries_or_ui_copy():
    for x in _items():
        blob = " ".join([x["title"]["zh"], x["title"]["en"], x["prompt_zh"], x["prompt_en"]])
        assert not BANNED.search(blob), x["id"]
    for lang in ("zh", "en"):
        pack = json.loads((LOCALES / f"{lang}.json").read_text(encoding="utf-8"))
        for key, value in pack.items():
            if key.startswith("ui_prompt_library_") or key in ("ui_assets_prompt_library", "ui_assets_my_prompts"):
                assert not BANNED.search(value), (lang, key)


def test_ui_keys_exist_in_both_locales():
    zh = json.loads((LOCALES / "zh.json").read_text(encoding="utf-8"))
    en = json.loads((LOCALES / "en.json").read_text(encoding="utf-8"))
    keys = {k for k in zh if k.startswith("ui_prompt_library_")}
    assert keys and keys == {k for k in en if k.startswith("ui_prompt_library_")}
    src = (ROOT / "studio" / "src" / "components" / "platform" / "PromptLibraryTab.jsx").read_text(encoding="utf-8")
    for key in set(re.findall(r'tr\("(ui_[a-z0-9_]+)"', src)):
        assert key in zh and key in en, key
    for stage in prompt_library.facets()["stages"]:
        assert f"ui_prompt_library_stage_{stage}" in zh


# ------------------------------------------------------------------ query


def test_pagination_covers_everything_once():
    total = prompt_library.facets()["total"]
    seen: list[str] = []
    offset = 0
    while True:
        page = prompt_library.query(offset=offset, limit=100)
        seen.extend(x["id"] for x in page["items"])
        if not page["hasMore"]:
            assert page["nextOffset"] is None
            break
        offset = page["nextOffset"]
    assert len(seen) == total == len(set(seen))


def test_limit_is_clamped():
    assert prompt_library.query(limit=10_000)["limit"] == prompt_library.MAX_LIMIT
    assert prompt_library.query(limit=-5)["limit"] == 1


def test_filters_category_subcategory_stage_model_source_tag():
    res = prompt_library.query(category="actions", subcategory="chase", limit=100)
    assert res["total"] > 0
    assert all(x["category"] == "actions" and x["subcategory"] == "chase" for x in res["items"])

    res = prompt_library.query(stage="script", limit=100)
    assert res["total"] > 0 and all(x["stage"] == "script" for x in res["items"])

    res = prompt_library.query(model="seedance", limit=100)  # case-insensitive
    assert res["total"] > 0 and all(x["model"] == "Seedance" for x in res["items"])

    orig = prompt_library.query(source="original", limit=1)["total"]
    third = prompt_library.query(source="third-party", limit=1)["total"]
    assert orig > 0 and third > 0 and orig + third == prompt_library.facets()["total"]

    res = prompt_library.query(tags=["基础例句"], limit=100)
    assert res["total"] == sum(1 for x in _items() if "基础例句" in x["tags"])
    assert all(x["basicExample"] for x in res["items"])

    assert prompt_library.query(category="all")["total"] == prompt_library.facets()["total"]


def test_search_matches_both_languages_and_all_terms():
    zh = prompt_library.query(q="菜市场", limit=100)
    en = prompt_library.query(q="WET market", limit=100)
    assert "om-act-chase-001" in {x["id"] for x in zh["items"]}
    assert "om-act-chase-001" in {x["id"] for x in en["items"]}
    assert prompt_library.query(q="market zzzz-no-such-term")["total"] == 0


def test_decorated_flags():
    by_id = prompt_library.load()["byId"]
    vb = next(x for x in by_id.values() if x["source"]["name"].startswith("Vchitect"))
    assert vb["basicExample"] and not vb["original"]
    tr = next(x for x in by_id.values() if x["translated"] == "machine")
    assert tr["aiTranslated"]
    assert by_id["om-act-chase-001"]["original"] and not by_id["om-act-chase-001"]["aiTranslated"]


# ------------------------------------------------------------------ HTTP


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("PROJECTS_ROOT", str(tmp_path))
    monkeypatch.delenv("DATABASE_URL", raising=False)
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()
    app.include_router(prompt_library.router)
    return TestClient(app)


def test_api_list_meta_item(client):
    r = client.get("/api/platform/prompts/library", params={"category": "camera", "limit": 5, "offset": 5})
    assert r.status_code == 200
    body = r.json()
    assert body["offset"] == 5 and len(body["items"]) <= 5
    assert all(x["category"] == "camera" for x in body["items"])

    r = client.get("/api/platform/prompts/library", params=[("tag", "基础例句"), ("tag", "VBench"), ("limit", 3)])
    assert r.status_code == 200 and r.json()["total"] > 0

    meta = client.get("/api/platform/prompts/library/meta").json()
    assert {c["key"] for c in meta["categories"]} >= {"actions", "camera", "negative"}
    assert meta["creditsUrl"].endswith("prompts/library/ATTRIBUTION.md")
    assert "generic" in meta["models"]

    assert client.get("/api/platform/prompts/library/items/om-act-chase-001").json()["item"]["id"] == "om-act-chase-001"
    assert client.get("/api/platform/prompts/library/items/nope").status_code == 404
    assert client.get("/api/platform/prompts/library", params={"limit": 1000}).status_code == 422


def test_library_routes_are_public_get_only(tmp_path, monkeypatch):
    monkeypatch.setenv("PROJECTS_ROOT", str(tmp_path))
    monkeypatch.setenv("STUDIO_AUTH_REQUIRED", "true")
    import app as studio_app

    assert studio_app._path_is_public("/api/platform/prompts/library", "GET")
    assert studio_app._path_is_public("/api/platform/prompts/library/meta", "GET")
    # Saving into "my prompts" stays behind login.
    assert not studio_app._path_is_public("/api/platform/prompts", "POST")

    from fastapi.testclient import TestClient

    c = TestClient(studio_app.app)
    r = c.get("/api/platform/prompts/library", params={"limit": 2})  # no Authorization header
    assert r.status_code == 200 and len(r.json()["items"]) == 2
    assert c.post("/api/platform/prompts", json={"text": "x"}).status_code == 401


# ------------------------------------------------------------------ save to my prompts


def test_save_library_entry_keeps_attribution_and_dedupes(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    import asset_library
    import pg_backend

    monkeypatch.setattr(pg_backend, "enabled", lambda: False)
    # Saved prompts belong to a user (per-user store follow-up); run as a logged-in user.
    import auth_context

    monkeypatch.setattr(auth_context, "current_user_id", lambda: "alice")
    origin = {
        "libraryId": "rapidata-002",
        "source": "Rapidata/text-2-video-human-preferences-veo3",
        "license": "Apache-2.0",
        "attribution": "Prompt from Rapidata ... licensed Apache-2.0",
        "bogus": "dropped",
    }
    a = asset_library.upsert_prompt(tmp_path, {"title": "t", "text": "first", "category": "template", "origin": origin})
    b = asset_library.upsert_prompt(tmp_path, {"title": "t", "text": "second", "category": "template", "origin": origin})
    assert a["id"] == b["id"]
    items = asset_library.load_prompts(tmp_path)
    assert len(items) == 1 and items[0]["text"] == "second"
    assert items[0]["origin"]["license"] == "Apache-2.0"
    assert "bogus" not in items[0]["origin"]
    # Plain prompts are unaffected.
    c = asset_library.upsert_prompt(tmp_path, {"text": "mine"})
    assert "origin" not in c
