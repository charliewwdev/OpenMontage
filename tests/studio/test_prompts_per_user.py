"""我的提示词 (per-user saved prompts): isolation, access rules, limits, legacy rows.

Every store test runs against the disk backend and, when
``OPENMONTAGE_TEST_DATABASE_URL`` points at a disposable Postgres database,
against real Postgres as well (otherwise the Postgres variants are skipped).
The Postgres fixture drops and recreates the prompt tables in that database.
"""

from __future__ import annotations

import contextvars
import json
import logging
import os
import re
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
STUDIO_SERVER = ROOT / "studio" / "server"
if str(STUDIO_SERVER) not in sys.path:
    sys.path.insert(0, str(STUDIO_SERVER))

import asset_library  # noqa: E402
import pg_backend  # noqa: E402
import prompt_store as ps  # noqa: E402
from auth_context import set_current_user  # noqa: E402

TEST_DB_ENV = "OPENMONTAGE_TEST_DATABASE_URL"
LEGACY = [
    {"id": "old-1", "title": "shared one", "text": "old shared prompt one", "category": "general", "updatedAt": 2},
    {"id": "old-2", "title": "shared two", "text": "old shared prompt two", "category": "style", "updatedAt": 1},
]


def as_user(uid, fn, *args, demo=False, **kwargs):
    """Run fn in a fresh context as the given request user (None = anonymous)."""

    def run():
        set_current_user({"userId": uid, "username": uid, **({"demo": True} if demo else {})} if uid else None)
        return fn(*args, **kwargs)

    return contextvars.copy_context().run(run)


def _reset_pg_globals():
    pool = pg_backend._pool
    if pool is not None:
        try:
            pool.closeall()
        except Exception:  # noqa: BLE001
            pass
    pg_backend._pool = None
    pg_backend._enabled = None
    pg_backend._pool_slots = None
    ps.PgBackend.reset_schema_cache()


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for name in (
        "STUDIO_PROMPTS_MAX_PER_USER",
        "STUDIO_PROMPTS_RATE_LIMIT",
        "STUDIO_PROMPT_TEXT_MAX",
        "STUDIO_PROMPT_TITLE_MAX",
        "STUDIO_DEMO_SAVE_PROMPTS",
        ps.LEGACY_OWNER_ENV,
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("STUDIO_AUTH_REQUIRED", "true")
    ps.rate_limiter.reset()
    yield
    ps.rate_limiter.reset()


@pytest.fixture(params=["disk", "postgres"])
def store(request, monkeypatch, tmp_path):
    """Yields (projects_root, backend_name)."""
    if request.param == "disk":
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.delenv("STUDIO_DATABASE_URL", raising=False)
        monkeypatch.setattr(pg_backend, "enabled", lambda: False)
        yield tmp_path, "disk"
        return
    url = os.environ.get(TEST_DB_ENV, "").strip()
    if not url:
        pytest.skip(f"{TEST_DB_ENV} not set (disposable Postgres for prompt store tests)")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("STUDIO_DATABASE_URL", url)
    _reset_pg_globals()
    assert pg_backend.init_schema()
    with pg_backend.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DROP TABLE IF EXISTS studio_prompts")
            cur.execute("DROP TABLE IF EXISTS studio_schema_migrations")
            cur.execute("DELETE FROM studio_kv WHERE key LIKE 'prompts:%%'")
    yield tmp_path, "postgres"
    _reset_pg_globals()


def seed_legacy(root: Path, kind: str, items=LEGACY):
    if kind == "postgres":
        pg_backend.upsert_kv(ps.LEGACY_KV_KEY, {"items": items})
        ps.PgBackend.reset_schema_cache()  # next access re-runs the (idempotent) import
    else:
        path = root / "_library" / "prompts.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"items": items}), encoding="utf-8")


def legacy_raw(root: Path, kind: str):
    if kind == "postgres":
        return pg_backend.load_kv(ps.LEGACY_KV_KEY)
    return json.loads((root / "_library" / "prompts.json").read_text(encoding="utf-8"))


def ids(view):
    return [x["id"] for x in view["prompts"]]


def err(fn, *args, **kwargs) -> ps.PromptError:
    with pytest.raises(ps.PromptError) as info:
        fn(*args, **kwargs)
    return info.value


# ------------------------------------------------------------------ isolation


def test_users_cannot_see_edit_or_delete_each_others_prompts(store):
    root, _ = store
    a, created = as_user("alice", ps.save_prompt, root, {"title": "A", "text": "alice prompt"})
    assert created and re.fullmatch(r"[0-9a-f]{32}", a["id"])
    assert ids(as_user("alice", ps.list_view, root)) == [a["id"]]
    assert as_user("bob", ps.list_view, root)["prompts"] == []

    e = err(as_user, "bob", ps.save_prompt, root, {"id": a["id"], "text": "hijack"})
    assert (e.status, e.code) == (404, "prompts_not_found")
    e = err(as_user, "bob", ps.delete_prompt, root, a["id"])
    assert (e.status, e.code) == (404, "prompts_not_found")
    assert as_user("alice", ps.list_view, root)["prompts"][0]["text"] == "alice prompt"

    upd, created = as_user("alice", ps.save_prompt, root, {"id": a["id"], "text": "alice v2", "category": "style"})
    assert not created and upd["text"] == "alice v2" and upd["category"] == "style"
    as_user("alice", ps.delete_prompt, root, a["id"])
    assert as_user("alice", ps.list_view, root)["total"] == 0


def test_github_style_and_unsafe_owner_ids(store):
    root, _ = store
    as_user("gh-12345", ps.save_prompt, root, {"text": "github user prompt"})
    assert as_user("gh-12345", ps.list_view, root)["total"] == 1
    for bad in ("../alice", "a/b", "..", "x\\y", "", " " * 3, "a" * 200):
        acc = as_user(bad or None, ps.current_access)
        assert acc.owner is None, bad


# ------------------------------------------------------------- access rules


def test_anonymous_read_only_when_login_required(store):
    root, kind = store
    seed_legacy(root, kind)
    view = as_user(None, ps.list_view, root)
    assert view["prompts"] == [] and view["requiresLogin"] is True and view["readOnlyReason"] == "login"
    assert err(as_user, None, ps.save_prompt, root, {"text": "x"}).status == 401
    assert err(as_user, None, ps.delete_prompt, root, "old-1").status == 401


def test_shared_demo_account_is_read_only_by_default(store, monkeypatch):
    root, _ = store
    view = as_user("demo", ps.list_view, root, demo=True)
    assert view["readOnlyReason"] == "shared_demo" and view["requiresLogin"] is False
    e = err(as_user, "demo", ps.save_prompt, root, {"text": "x"}, demo=True)
    assert (e.status, e.code) == (403, "prompts_shared_demo")
    # A real account whose id happens to be "demo" but is not the demo session is unaffected.
    assert as_user("demo", ps.save_prompt, root, {"text": "real"})[1] is True
    # Private single-user install: demo login may save.
    monkeypatch.setenv("STUDIO_DEMO_SAVE_PROMPTS", "1")
    assert as_user("demo", ps.save_prompt, root, {"text": "mine"}, demo=True)[1] is True


def test_single_user_install_without_login_adopts_legacy(store, monkeypatch):
    root, kind = store
    monkeypatch.setenv("STUDIO_AUTH_REQUIRED", "false")
    seed_legacy(root, kind)
    view = as_user(None, ps.list_view, root)
    assert sorted(x["text"] for x in view["prompts"]) == ["old shared prompt one", "old shared prompt two"]
    as_user(None, ps.save_prompt, root, {"text": "local"})
    assert as_user(None, ps.list_view, root)["total"] == 3
    assert legacy_raw(root, kind) == {"items": LEGACY}


# ------------------------------------------------------------------ validation


def test_validation_and_limits(store, monkeypatch):
    root, _ = store
    monkeypatch.setenv("STUDIO_PROMPT_TEXT_MAX", "100")
    monkeypatch.setenv("STUDIO_PROMPT_TITLE_MAX", "20")
    cases = [
        ({"text": "   "}, 400, "prompts_text_required"),
        ({"text": 5}, 400, "prompts_text_required"),
        ({"text": "x" * 101}, 400, "prompts_text_too_long"),
        ({"text": "ok", "title": "t" * 21}, 400, "prompts_title_too_long"),
        ({"text": "ok", "title": ["x"]}, 400, "prompts_bad_request"),
        ({"text": "ok", "category": "nope"}, 400, "prompts_bad_category"),
        ({"text": "ok", "id": "../etc"}, 404, "prompts_not_found"),
        (["not", "a", "dict"], 400, "prompts_bad_request"),
    ]
    for body, status, code in cases:
        e = err(as_user, "alice", ps.save_prompt, root, body)
        assert (e.status, e.code) == (status, code), body
    e = err(as_user, "alice", ps.save_prompt, root, {"text": "x" * 101})
    assert e.payload()["max"] == 100 and "100" in e.payload()["error"]
    item, _ = as_user("alice", ps.save_prompt, root, {"text": "  padded  ", "title": "  a   b "})
    assert item["text"] == "padded" and item["title"] == "a b"


def test_max_prompts_per_user_and_library_dedupe(store, monkeypatch):
    root, _ = store
    monkeypatch.setenv("STUDIO_PROMPTS_MAX_PER_USER", "3")
    origin = {"libraryId": "om-act-chase-001", "license": "CC-BY-4.0", "attribution": "© OpenMontage", "x": "dropped"}
    first, created = as_user("alice", ps.save_prompt, root, {"text": "lib v1", "origin": origin})
    assert created and first["origin"] == {"libraryId": "om-act-chase-001", "license": "CC-BY-4.0", "attribution": "© OpenMontage"}
    again, created = as_user("alice", ps.save_prompt, root, {"text": "lib v2", "origin": origin})
    assert not created and again["id"] == first["id"] and again["text"] == "lib v2"
    as_user("alice", ps.save_prompt, root, {"text": "two"})
    as_user("alice", ps.save_prompt, root, {"text": "three"})
    e = err(as_user, "alice", ps.save_prompt, root, {"text": "four"})
    assert (e.status, e.code, e.params["max"]) == (409, "prompts_limit_reached", 3)
    # Other users have their own budget.
    assert as_user("bob", ps.save_prompt, root, {"text": "bob"})[1] is True


def test_rate_limit(store, monkeypatch):
    root, _ = store
    monkeypatch.setenv("STUDIO_PROMPTS_RATE_LIMIT", "3/60")
    for i in range(3):
        as_user("alice", ps.save_prompt, root, {"text": f"p{i}"})
    e = err(as_user, "alice", ps.save_prompt, root, {"text": "p4"})
    assert (e.status, e.code) == (429, "prompts_rate_limited") and e.params["retryAfter"] >= 1
    assert as_user("bob", ps.save_prompt, root, {"text": "bob"})[1] is True


# ---------------------------------------------------------- list / pagination


def test_pagination_search_sort_category(store):
    root, _ = store
    for i in range(7):
        as_user("alice", ps.save_prompt, root,
                {"title": f"T{i}", "text": f"body {i} {'needle_50%' if i % 2 else ''}",
                 "category": "style" if i < 3 else "general"})
    v = as_user("alice", ps.list_view, root, limit=3)
    assert v["total"] == 7 and len(v["prompts"]) == 3 and v["hasMore"] and v["nextOffset"] == 3
    seen = []
    offset = 0
    while True:
        page = as_user("alice", ps.list_view, root, offset=offset, limit=3)
        seen += ids(page)
        if not page["hasMore"]:
            break
        offset = page["nextOffset"]
    assert len(seen) == len(set(seen)) == 7
    assert as_user("alice", ps.list_view, root, category="style")["total"] == 3
    # LIKE wildcards in the query are literals.
    assert as_user("alice", ps.list_view, root, q="needle_50%")["total"] == 3
    assert as_user("alice", ps.list_view, root, q="%")["total"] == 3
    names = [x["title"] for x in as_user("alice", ps.list_view, root, sort="name")["prompts"]]
    assert names == sorted(names, key=str.lower)
    assert as_user("alice", ps.list_view, root, limit=10_000)["limit"] == ps.LIST_MAX_LIMIT


# ----------------------------------------------------------------- legacy rows


def test_legacy_prompts_hidden_listed_and_assignable(store):
    root, kind = store
    seed_legacy(root, kind)
    assert as_user("alice", ps.list_view, root)["total"] == 0
    assert sorted(x["legacyId"] for x in ps.legacy_prompts(root)) == ["old-1", "old-2"]
    assert ps.assign_legacy(root, "alice", ["old-1"]) == 1
    assert ps.assign_legacy(root, "alice", ["old-1"]) == 0  # idempotent
    view = as_user("alice", ps.list_view, root)
    assert [x["text"] for x in view["prompts"]] == ["old shared prompt one"]
    assert "legacyId" not in view["prompts"][0]
    assert ps.assign_legacy(root, "alice") == 1
    assert as_user("bob", ps.list_view, root)["total"] == 0
    assert legacy_raw(root, kind) == {"items": LEGACY}
    assert len(ps.legacy_prompts(root)) == 2
    with pytest.raises(ValueError):
        ps.assign_legacy(root, "../x")
    counts = ps.owner_counts(root)
    assert counts.get("alice") == 2


def test_legacy_owner_env_adopts_once(store, monkeypatch):
    root, kind = store
    seed_legacy(root, kind)
    monkeypatch.setenv(ps.LEGACY_OWNER_ENV, "alice")
    assert as_user("alice", ps.list_view, root)["total"] == 2
    assert as_user("bob", ps.list_view, root)["total"] == 0
    for item in as_user("alice", ps.list_view, root)["prompts"]:
        as_user("alice", ps.delete_prompt, root, item["id"])
    assert as_user("alice", ps.list_view, root)["total"] == 0  # not re-adopted
    assert len(ps.legacy_prompts(root)) == 2


# ----------------------------------------------------------------- concurrency


def test_concurrent_creates_respect_the_limit(store, monkeypatch):
    root, _ = store
    monkeypatch.setenv("STUDIO_PROMPTS_MAX_PER_USER", "10")
    monkeypatch.setenv("STUDIO_PROMPTS_RATE_LIMIT", "1000/60")
    results: list[str] = []
    lock = threading.Lock()

    def worker(i: int, uid: str):
        try:
            as_user(uid, ps.save_prompt, root, {"text": f"{uid} {i}"})
            outcome = "ok"
        except ps.PromptError as exc:
            outcome = exc.code
        with lock:
            results.append(f"{uid}:{outcome}")

    threads = [threading.Thread(target=worker, args=(i, "alice" if i % 2 else "bob")) for i in range(40)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    for uid in ("alice", "bob"):
        assert results.count(f"{uid}:ok") == 10, results
        assert results.count(f"{uid}:prompts_limit_reached") == 10
        assert as_user(uid, ps.list_view, root)["total"] == 10


# ------------------------------------------------------ compat + logging audit


def test_whole_list_helpers_are_owner_scoped(store, monkeypatch):
    root, _ = store
    import auth_context

    monkeypatch.setattr(auth_context, "current_user_id", lambda: "alice")
    item = asset_library.upsert_prompt(root, {"title": "t", "text": "via helper", "category": "template"})
    monkeypatch.setattr(auth_context, "current_user_id", lambda: "bob")
    assert asset_library.load_prompts(root) == []
    monkeypatch.setattr(auth_context, "current_user_id", lambda: "alice")
    assert [x["id"] for x in asset_library.load_prompts(root)] == [item["id"]]
    monkeypatch.setattr(auth_context, "current_user_id", lambda: "")
    assert asset_library.load_prompts(root) == []
    with pytest.raises(ps.PromptError):
        asset_library.save_prompts(root, [{"text": "anon"}])


def test_logs_do_not_contain_prompt_text_or_owner_ids(store, caplog):
    root, _ = store
    secret = "SECRET-BODY-4242"
    with caplog.at_level(logging.DEBUG):
        item, _ = as_user("alice@example.com", ps.save_prompt, root, {"title": "SECRET-TITLE", "text": secret})
        as_user("alice@example.com", ps.save_prompt, root, {"id": item["id"], "text": secret + "2"})
        as_user("alice@example.com", ps.delete_prompt, root, item["id"])
    assert caplog.records, "expected audit log lines"
    assert secret not in caplog.text and "SECRET-TITLE" not in caplog.text
    assert "alice@example.com" not in caplog.text


# ------------------------------------------------------------- Postgres only


def test_postgres_migration_is_idempotent_and_indexed(store):
    root, kind = store
    if kind != "postgres":
        pytest.skip("Postgres only")
    seed_legacy(root, kind)
    first = ps.migrate(root)
    second = ps.migrate(root)
    assert first["applied"] == 1 and first["legacyImported"] == 2
    assert second == {"applied": 0, "legacyImported": 0}
    with pg_backend.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT indexname FROM pg_indexes WHERE tablename = 'studio_prompts'")
            names = {r[0] for r in cur.fetchall()}
            cur.execute("SELECT count(*) FROM studio_prompts WHERE owner_id IS NULL")
            legacy_rows = cur.fetchone()[0]
    assert {"idx_studio_prompts_owner_updated", "uq_studio_prompts_owner_library", "uq_studio_prompts_owner_legacy"} <= names
    assert legacy_rows == 2
    # The database itself rejects an empty body even if the app checks were bypassed.
    import psycopg2

    with pytest.raises(psycopg2.errors.CheckViolation):
        with pg_backend.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO studio_prompts (id, owner_id, body) VALUES ('x1', 'alice', '')")


# ------------------------------------------------------------------- admin CLI


def _cli():
    scripts = ROOT / "studio" / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    import prompts_admin

    return prompts_admin


def test_admin_cli_lists_and_assigns_legacy_prompts(store, monkeypatch, capsys):
    root, kind = store
    monkeypatch.setenv("PROJECTS_ROOT", str(root))
    seed_legacy(root, kind)
    cli = _cli()
    assert cli.main(["migrate"]) == 0
    capsys.readouterr()
    assert cli.main(["legacy-list"]) == 0
    out = capsys.readouterr().out
    assert "old-1" in out and "old-2" in out and "old shared prompt" not in out  # no bodies by default
    assert cli.main(["legacy-list", "--json", "--show-text"]) == 0
    rows = json.loads(capsys.readouterr().out)
    assert {r["legacyId"] for r in rows} == {"old-1", "old-2"} and rows[0]["text"]
    assert cli.main(["legacy-assign", "--to", "gh-9", "--ids", "old-2"]) == 0
    assert "copied 1" in capsys.readouterr().out
    assert cli.main(["legacy-assign", "--to", "gh-9", "--all"]) == 0
    assert "copied 1" in capsys.readouterr().out  # old-2 is not copied twice
    assert cli.main(["legacy-assign", "--to", "../evil", "--all"]) == 2
    assert cli.main(["legacy-assign", "--to", "gh-9"]) == 2
    capsys.readouterr()
    assert cli.main(["owners"]) == 0
    assert "gh-9" in capsys.readouterr().out
    assert as_user("gh-9", ps.list_view, root)["total"] == 2
    assert legacy_raw(root, kind)["items"] == LEGACY  # source untouched


def test_disk_prompt_files_import_into_postgres(store):
    root, kind = store
    if kind != "postgres":
        pytest.skip("Postgres only")
    path = root / ".users" / "gh-5" / "prompts.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"version": 1, "items": [
        {"id": "p1", "title": "a", "text": "disk prompt a", "category": "style", "createdAt": 1, "updatedAt": 2},
    ]}), encoding="utf-8")
    assert ps.import_user_files(root) == 1
    assert ps.import_user_files(root) == 0
    view = as_user("gh-5", ps.list_view, root)
    assert [p["text"] for p in view["prompts"]] == ["disk prompt a"]
    assert as_user("gh-6", ps.list_view, root)["total"] == 0


# ------------------------------------------------------------------------ HTTP


@pytest.fixture()
def client(store, monkeypatch):
    root, _ = store
    import app as studio_app
    from fastapi.testclient import TestClient

    monkeypatch.setattr(studio_app, "PROJECTS_ROOT", root)
    monkeypatch.setattr(
        studio_app,
        "_resolve_user",
        lambda token: {"userId": token.split(":")[0], "username": token, **({"demo": True} if token.endswith(":demo") else {})},
    )
    return TestClient(studio_app.app)


def _h(token: str, locale: str = "zh") -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "X-Studio-Locale": locale}


def test_http_api(client, monkeypatch):
    r = client.post("/api/platform/prompts", json={"text": "alice prompt"}, headers=_h("alice"))
    assert r.status_code == 200 and r.json()["created"] is True
    pid = r.json()["prompt"]["id"]

    body = client.get("/api/platform/prompts?limit=1", headers=_h("alice")).json()
    assert [x["id"] for x in body["prompts"]] == [pid] and body["readOnlyReason"] is None and body["categories"]
    assert client.get("/api/platform/prompts", headers=_h("bob")).json()["total"] == 0
    r = client.delete(f"/api/platform/prompts/{pid}", headers=_h("bob", "en"))
    assert r.status_code == 404 and r.json()["code"] == "prompts_not_found" and "doesn't exist" in r.json()["error"]
    r = client.post("/api/platform/prompts", json={"id": pid, "text": "x"}, headers=_h("bob"))
    assert r.status_code == 404

    anon = client.get("/api/platform/prompts").json()
    assert anon["prompts"] == [] and anon["requiresLogin"] is True
    assert client.post("/api/platform/prompts", json={"text": "x"}).status_code == 401

    r = client.post("/api/platform/prompts", json={"text": "x"}, headers=_h("demo:demo", "zh"))
    assert r.status_code == 403 and r.json()["code"] == "prompts_shared_demo" and "体验账号" in r.json()["error"]
    assert client.get("/api/platform/prompts", headers=_h("demo:demo")).json()["readOnlyReason"] == "shared_demo"

    r = client.post("/api/platform/prompts", content=b"{not json", headers=_h("alice"))
    assert r.status_code == 400 and r.json()["code"] == "prompts_bad_request"
    r = client.post("/api/platform/prompts", content=b'{"text":"' + b"x" * (70 * 1024) + b'"}', headers=_h("alice"))
    assert r.status_code == 413
    assert client.get("/api/platform/prompts?limit=5000", headers=_h("alice")).status_code == 422

    assert client.delete(f"/api/platform/prompts/{pid}", headers=_h("alice")).status_code == 200

    monkeypatch.setenv("STUDIO_PROMPTS_RATE_LIMIT", "2/60")
    ps.rate_limiter.reset()
    for _ in range(2):
        assert client.post("/api/platform/prompts", json={"text": "burst"}, headers=_h("carol")).status_code == 200
    r = client.post("/api/platform/prompts", json={"text": "burst"}, headers=_h("carol", "en"))
    assert r.status_code == 429 and r.json()["code"] == "prompts_rate_limited"
    assert int(r.headers["Retry-After"]) >= 1
