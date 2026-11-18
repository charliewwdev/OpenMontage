#!/usr/bin/env python3
"""Admin tool for 我的提示词 (per-user saved prompts).

Uses the same storage as the studio: Postgres when DATABASE_URL /
STUDIO_DATABASE_URL is set, otherwise files under PROJECTS_ROOT. Run it inside
the studio container (or with the same env vars) so it sees the same data:

    python studio/scripts/prompts_admin.py migrate
    python studio/scripts/prompts_admin.py legacy-list [--json] [--show-text]
    python studio/scripts/prompts_admin.py legacy-assign --to gh-12345 --all
    python studio/scripts/prompts_admin.py legacy-assign --to gh-12345 --ids old-1,old-2
    python studio/scripts/prompts_admin.py owners

Legacy prompts are the ones saved before prompts became per user. They are
never modified or deleted; ``legacy-assign`` copies them into one account
(idempotent: the same legacy prompt is copied to an account at most once).
Prompt text is not printed unless --show-text is given.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

STUDIO_SERVER = Path(__file__).resolve().parents[1] / "server"
sys.path.insert(0, str(STUDIO_SERVER))

import pg_backend  # noqa: E402
import prompt_store  # noqa: E402


def _root() -> Path:
    return Path(os.environ.get("PROJECTS_ROOT", str(Path(__file__).resolve().parents[1] / "projects"))).resolve()


def _ts(value: float) -> str:
    return datetime.fromtimestamp(value, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def cmd_migrate(args: argparse.Namespace) -> int:
    if not pg_backend.enabled():
        print("disk storage: nothing to migrate (legacy file stays at PROJECTS_ROOT/_library/prompts.json)")
        return 0
    if not pg_backend.init_schema():
        print("error: cannot reach Postgres", file=sys.stderr)
        return 1
    stats = prompt_store.migrate(_root())
    print(f"migrations applied: {stats['applied']}, legacy prompts imported: {stats['legacyImported']}")
    return 0


def cmd_legacy_list(args: argparse.Namespace) -> int:
    items = prompt_store.legacy_prompts(_root())
    if args.json:
        out = []
        for it in items:
            row = {k: it[k] for k in ("legacyId", "title", "category", "updatedAt")}
            row["chars"] = len(it["text"])
            if args.show_text:
                row["text"] = it["text"]
            out.append(row)
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0
    print(f"{len(items)} legacy prompt(s) [{'postgres' if pg_backend.enabled() else 'disk'}]")
    for it in items:
        line = f"  {it['legacyId']:<34} {it['category']:<12} {_ts(it['updatedAt'])}  {len(it['text']):>5} chars  {it['title'][:40]}"
        print(line)
        if args.show_text:
            print("      " + it["text"].replace("\n", "\n      "))
    return 0


def cmd_legacy_assign(args: argparse.Namespace) -> int:
    if not args.all and not args.ids:
        print("error: pass --all or --ids", file=sys.stderr)
        return 2
    ids = None if args.all else [x.strip() for x in args.ids.split(",") if x.strip()]
    try:
        added = prompt_store.assign_legacy(_root(), args.to, ids, force=args.force)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except prompt_store.PromptError as exc:
        print(f"error: {exc.code}", file=sys.stderr)
        return 1
    print(f"copied {added} legacy prompt(s) to {args.to}")
    return 0


def cmd_owners(args: argparse.Namespace) -> int:
    counts = prompt_store.owner_counts(_root())
    for owner, n in counts.items():
        print(f"  {owner:<40} {n}")
    print(f"{len(counts)} owner(s), {sum(counts.values())} prompt(s)")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("migrate", help="create/upgrade the Postgres schema and import legacy prompts").set_defaults(fn=cmd_migrate)
    p = sub.add_parser("legacy-list", help="list legacy (owner-less) prompts")
    p.add_argument("--json", action="store_true")
    p.add_argument("--show-text", action="store_true", help="also print prompt text")
    p.set_defaults(fn=cmd_legacy_list)
    p = sub.add_parser("legacy-assign", help="copy legacy prompts to one account")
    p.add_argument("--to", required=True, help="target user id, e.g. gh-12345")
    p.add_argument("--ids", help="comma-separated legacy ids (see legacy-list)")
    p.add_argument("--all", action="store_true")
    p.add_argument("--force", action="store_true", help="ignore STUDIO_PROMPTS_MAX_PER_USER")
    p.set_defaults(fn=cmd_legacy_assign)
    sub.add_parser("owners", help="prompt count per account").set_defaults(fn=cmd_owners)
    args = ap.parse_args(argv)
    return int(args.fn(args))


if __name__ == "__main__":
    raise SystemExit(main())
