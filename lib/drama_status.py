"""CLI helper: print short-drama ledger + metrics for a project directory."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def summarize(project_dir: Path) -> dict:
    project_dir = Path(project_dir)
    out: dict = {"project_dir": str(project_dir)}
    ledger_path = project_dir / "shot_jobs.json"
    if ledger_path.exists():
        ledger = json.loads(ledger_path.read_text())
        out["ledger_stats"] = ledger.get("stats")
        out["paused"] = ledger.get("paused")
        out["episode_id"] = ledger.get("episode_id")
        out["jobs"] = len(ledger.get("jobs") or [])
    metrics_path = project_dir / "production_metrics.json"
    if metrics_path.exists():
        out["production_metrics"] = json.loads(metrics_path.read_text())
    bible = project_dir / "bible" / "character_bible.json"
    out["bible_present"] = bible.exists()
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Short-drama project status")
    parser.add_argument("project_dir", type=Path)
    args = parser.parse_args(argv)
    summary = summarize(args.project_dir)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
