"""Community skill posts — Postgres is source of truth when DATABASE_URL is set."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger("studio.community_skills")

KV_KEY = "skills:community"


def _disk_path(projects_root: Path) -> Path:
    return Path(projects_root) / ".community_skills.json"


def _pg_enabled() -> bool:
    try:
        import pg_backend as _pg

        return bool(_pg.enabled())
    except Exception:
        return False


def load_community_skills(projects_root: Path) -> list[dict[str, Any]]:
    root = Path(projects_root)
    if _pg_enabled():
        try:
            import pg_backend as _pg

            hit = _pg.load_kv(KV_KEY)
            items = hit.get("items") if isinstance(hit, dict) else None
            if isinstance(items, list):
                return [x for x in items if isinstance(x, dict) and x.get("id")]
        except Exception as exc:
            logger.warning("community skills pg load failed: %s", exc)

        # Migrate disk → PG once
        path = _disk_path(root)
        if path.is_file():
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(raw, list):
                    out = [x for x in raw if isinstance(x, dict) and x.get("id")]
                    if out:
                        import pg_backend as _pg

                        _pg.upsert_kv(KV_KEY, {"items": out})
                    return out
            except Exception:
                pass
        return []

    path = _disk_path(root)
    if not path.is_file():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(raw, list):
        return []
    return [x for x in raw if isinstance(x, dict) and x.get("id")]


def save_community_skills(projects_root: Path, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    root = Path(projects_root)
    clean = [x for x in items if isinstance(x, dict) and x.get("id")][:100]
    if _pg_enabled():
        try:
            import pg_backend as _pg

            _pg.upsert_kv(KV_KEY, {"items": clean})
            return clean
        except Exception as exc:
            logger.warning("community skills pg save failed: %s", exc)
            raise RuntimeError(f"保存社区 Skills 到 Postgres 失败: {exc}") from exc

    path = _disk_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(clean, ensure_ascii=False, indent=2), encoding="utf-8")
    return clean
