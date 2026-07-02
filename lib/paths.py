"""Canonical repository paths — single source of truth.

The projects root is the most load-bearing path in the system: checkpoints
are written under it, tool events are attributed against it, and the Backlot
board watches it. Define it once.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PROJECTS_DIR = REPO_ROOT / "projects"
