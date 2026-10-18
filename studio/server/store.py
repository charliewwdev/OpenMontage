"""JSON file project store shaped like Xuefeng ProjectBundle."""

from __future__ import annotations

import json
import re
import shutil
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from store_lock import project_lock


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def slugify(name: str) -> str:
    import hashlib

    s = re.sub(r"[^\w\u4e00-\u9fff\-]+", "-", name.strip(), flags=re.UNICODE)
    s = re.sub(r"-+", "-", s).strip("-").lower()
    ascii_only = re.sub(r"[^a-z0-9\-]+", "", s)
    if len(ascii_only) >= 2:
        return ascii_only[:64]
    digest = hashlib.sha1(name.strip().encode("utf-8")).hexdigest()[:8]
    return f"drama-{digest}"


def new_id(prefix: str = "") -> str:
    return f"{prefix}{uuid.uuid4().hex[:12]}" if prefix else uuid.uuid4().hex


def ensure_seed_projects(projects_root: Path, seed_root: Path | None = None) -> list[str]:
    """Copy packaged seed projects into PROJECTS_ROOT when missing (empty volume safe).

    Also upgrades an existing seed project when the packaged seed has media files
    but the volume copy is still media-empty (common after first boot before media
    was added to the seed package).
    """
    root = Path(projects_root)
    root.mkdir(parents=True, exist_ok=True)
    if seed_root is None:
        seed_root = Path(__file__).resolve().parents[1] / "seed"
    seed_root = Path(seed_root)
    if not seed_root.is_dir():
        return []
    copied: list[str] = []
    for src in sorted(seed_root.iterdir()):
        if not src.is_dir() or src.name.startswith("."):
            continue
        dest = root / src.name
        if not dest.exists():
            shutil.copytree(src, dest)
            copied.append(src.name)
            continue
        src_media = src / "media"
        if not src_media.is_dir():
            continue
        src_files = [p for p in src_media.rglob("*") if p.is_file()]
        if not src_files:
            continue
        dest_media = dest / "media"
        dest_files = [p for p in dest_media.rglob("*") if p.is_file()] if dest_media.is_dir() else []
        if len(dest_files) >= 3:
            continue
        for f in src_files:
            rel = f.relative_to(src)
            target = dest / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, target)
        seed_state = src / "studio_state.json"
        if seed_state.is_file():
            shutil.copy2(seed_state, dest / "studio_state.json")
        copied.append(f"{src.name}:media")
    return copied


class ProjectStore:
    def __init__(self, projects_root: Path):
        self.root = projects_root
        self.root.mkdir(parents=True, exist_ok=True)
        self._pg = False
        try:
            import pg_backend as _pg

            self._pg = bool(_pg.enabled())
        except Exception:
            self._pg = False

    def _dir(self, project_id: str) -> Path | None:
        if not project_id or "/" in project_id or "\\" in project_id or project_id.startswith("."):
            return None
        path = (self.root / project_id).resolve()
        if not str(path).startswith(str(self.root.resolve())):
            return None
        return path

    def _studio_path(self, project: Path) -> Path:
        return project / "studio_state.json"

    def _pg_upsert(self, state: dict[str, Any]) -> None:
        if not self._pg:
            return
        try:
            import pg_backend as _pg

            _pg.upsert_project(state)
        except Exception as exc:
            # Disk write already succeeded; log but do not fail the request.
            import logging

            logging.getLogger("studio.store").warning("pg upsert failed: %s", exc)

    def _pg_delete(self, project_id: str) -> None:
        if not self._pg:
            return
        try:
            import pg_backend as _pg

            _pg.delete_project(project_id)
        except Exception as exc:
            import logging

            logging.getLogger("studio.store").warning("pg delete failed: %s", exc)

    def list_ids(self) -> list[str]:
        ids: set[str] = set()
        if self.root.is_dir():
            ids.update(
                p.name for p in self.root.iterdir() if p.is_dir() and not p.name.startswith(".")
            )
        if self._pg:
            try:
                import pg_backend as _pg

                ids.update(_pg.list_project_ids())
            except Exception:
                pass
        return sorted(ids)

    def _ensure_media_dirs(self, project: Path) -> None:
        project.mkdir(parents=True, exist_ok=True)
        (project / "media" / "images").mkdir(parents=True, exist_ok=True)
        (project / "media" / "videos").mkdir(parents=True, exist_ok=True)
        (project / "media" / "covers").mkdir(parents=True, exist_ok=True)
        (project / "media" / "exports").mkdir(parents=True, exist_ok=True)

    def _load_unlocked(self, project_id: str) -> dict[str, Any] | None:
        project = self._dir(project_id)
        path = self._studio_path(project) if project else None

        # Postgres is source of truth when enabled — never write studio_state.json.
        if self._pg:
            try:
                import pg_backend as _pg

                pg_state = _pg.load_project(project_id)
            except Exception:
                pg_state = None
            else:
                if pg_state:
                    if project:
                        try:
                            self._ensure_media_dirs(project)
                        except Exception:
                            pass
                    return pg_state

        disk_state: dict[str, Any] | None = None
        if path and path.exists():
            try:
                disk_state = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                disk_state = None
        if disk_state:
            # One-shot migrate orphan disk project into PG; do not rewrite disk.
            if self._pg:
                self._pg_upsert(disk_state)
            return disk_state

        if project and project.is_dir():
            return self._migrate_legacy(project)
        return None

    def _save_unlocked(self, state: dict[str, Any]) -> dict[str, Any]:
        project_id = state["project"]["id"]
        project = self._dir(project_id)
        if not project:
            raise ValueError("invalid project id")
        self._ensure_media_dirs(project)
        state["project"]["updatedAt"] = _now()
        if self._pg:
            # PG only for project state — no studio_state.json on disk.
            self._pg_upsert(state)
            return state
        self._studio_path(project).write_text(
            json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        self._mirror_artifacts(project, state)
        return state

    def load(self, project_id: str) -> dict[str, Any] | None:
        # Shared reads stay unlocked for latency; writers use ``transaction`` / ``save``.
        return self._load_unlocked(project_id)

    def save(self, state: dict[str, Any]) -> dict[str, Any]:
        project_id = state["project"]["id"]
        with project_lock(self.root, project_id):
            return self._save_unlocked(state)

    @contextmanager
    def transaction(self, project_id: str) -> Iterator[dict[str, Any] | None]:
        """Exclusive load → mutate → save for multi-worker RMW safety."""
        with project_lock(self.root, project_id):
            state = self._load_unlocked(project_id)
            yield state
            if state is not None:
                self._save_unlocked(state)

    def delete(self, project_id: str) -> bool:
        project = self._dir(project_id)
        deleted = False
        if project and project.is_dir():
            shutil.rmtree(project)
            deleted = True
        if self._pg:
            try:
                import pg_backend as _pg

                if _pg.delete_project(project_id):
                    deleted = True
            except Exception:
                self._pg_delete(project_id)
        return deleted

    def media_dir(self, project_id: str, kind: str = "images") -> Path:
        project = self._dir(project_id)
        assert project
        path = project / "media" / kind
        path.mkdir(parents=True, exist_ok=True)
        return path

    def write_media(
        self,
        project_id: str,
        rel: str,
        data: bytes,
        content_type: str | None = None,
    ) -> Path:
        """Write media bytes to disk cache and Postgres (source of truth)."""
        project = self._dir(project_id)
        if not project:
            raise ValueError("invalid project id")
        rel_norm = rel.replace("\\", "/").lstrip("/")
        if ".." in Path(rel_norm).parts:
            raise ValueError("invalid media path")
        path = project / rel_norm
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        self.persist_media(project_id, rel_norm, data=data, content_type=content_type)
        return path

    def persist_media(
        self,
        project_id: str,
        rel: str,
        data: bytes | None = None,
        content_type: str | None = None,
    ) -> None:
        """Sync an on-disk (or provided) media file into Postgres."""
        if not self._pg:
            return
        rel_norm = rel.replace("\\", "/").lstrip("/")
        try:
            import pg_backend as _pg

            blob = data
            if blob is None:
                project = self._dir(project_id)
                if not project:
                    return
                path = project / rel_norm
                if not path.is_file():
                    return
                blob = path.read_bytes()
            if not blob:
                return
            _pg.upsert_media(project_id, rel_norm, blob, content_type=content_type)
        except Exception as exc:
            import logging

            logging.getLogger("studio.store").warning(
                "pg media upsert %s/%s failed: %s", project_id, rel_norm, exc
            )

    def ensure_media(self, project_id: str, rel: str) -> Path | None:
        """Ensure media exists on disk; hydrate from Postgres when missing."""
        project = self._dir(project_id)
        if not project:
            return None
        rel_norm = rel.replace("\\", "/").lstrip("/")
        if ".." in Path(rel_norm).parts:
            return None
        path = project / rel_norm
        if path.is_file() and path.stat().st_size > 0:
            return path
        hit = None
        if self._pg:
            try:
                import pg_backend as _pg

                hit = _pg.load_media(project_id, rel_norm)
            except Exception:
                hit = None
        if not hit:
            try:
                import object_store as _oss

                if _oss.enabled():
                    hit = _oss.get_media(project_id, rel_norm)
            except Exception:
                hit = None
        if not hit:
            return path if path.is_file() else None
        blob, _ctype = hit
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(blob)
        return path

    def create_project(
        self,
        *,
        title: str,
        brief: str = "",
        genre: str | None = None,
        visual_style: str | None = None,
        ratio: str | None = None,
        name: str | None = None,
        owner_id: str | None = None,
    ) -> dict[str, Any]:
        try:
            from platform_config import default_genre, default_ratio, default_visual_style

            genre = genre or default_genre()
            ratio = ratio or default_ratio()
            visual_style = visual_style or default_visual_style()
        except Exception:
            genre = genre or "都市情感"
            ratio = ratio or "9:16"
            visual_style = visual_style or ""
        if not owner_id:
            try:
                from auth_context import current_user_id

                owner_id = current_user_id() or None
            except Exception:
                owner_id = None
        base = slugify(name or title)
        # Guard against empty / unsafe folder names (e.g. bare "-1" from bad clients)
        if not base or base in {".", ".."} or base.startswith("-") or "/" in base or "\\" in base:
            base = slugify(f"drama-{title}") or f"drama-{new_id()[:8]}"
        project_id = base
        i = 2
        existing = set(self.list_ids())
        while project_id in existing or (self.root / project_id).exists():
            project_id = f"{base}-{i}"
            i += 1
        ts = _now()
        state = {
            "project": {
                "id": project_id,
                "title": title.strip(),
                "brief": brief.strip(),
                "synopsis": "",
                "genre": genre,
                "visualStyle": visual_style,
                "ratio": ratio or "9:16",
                "plannedEpisodes": None,
                "ownerId": owner_id or "",
                "createdAt": ts,
                "updatedAt": ts,
            },
            "episodes": [],
            "entities": [],
            "shots": [],
            "edits": [],
            "audios": [],
        }
        return self.save(state)

    def bundle(self, project_id: str) -> dict[str, Any] | None:
        state = self.load(project_id)
        if not state:
            return None
        # Repair sticky qaFailed when selected still already passes (failed redraw leftover).
        try:
            from drama_service import heal_entity_qa_flags

            if heal_entity_qa_flags(state):
                self.save(state)
                state = self.load(project_id) or state
        except Exception:
            pass
        # attach media urls (mtime query busts browser cache after in-place alpha punch)
        for ent in state.get("entities") or []:
            for img in ent.get("images") or []:
                rel = img.get("path") or ""
                bust = ""
                if rel:
                    try:
                        mp = self._dir(project_id) / rel
                        if mp.is_file():
                            bust = f"?t={int(mp.stat().st_mtime)}"
                    except Exception:
                        bust = ""
                img["url"] = f"/api/media/{project_id}/{rel}{bust}" if rel else None
            sel = ent.get("selectedImageId")
            ent["selectedImage"] = next((i for i in (ent.get("images") or []) if i["id"] == sel), None)
        for shot in state.get("shots") or []:
            for vid in shot.get("videos") or []:
                vid["url"] = f"/api/media/{project_id}/{vid['path']}" if vid.get("path") else None
            sel = shot.get("selectedVideoId")
            shot["selectedVideo"] = next((v for v in (shot.get("videos") or []) if v["id"] == sel), None)
        for edit in state.get("edits") or []:
            edit["outputUrl"] = (
                f"/api/media/{project_id}/{edit['outputPath']}" if edit.get("outputPath") else None
            )
        for audio in state.get("audios") or []:
            if audio.get("path"):
                audio["url"] = f"/api/media/{project_id}/{audio['path']}"
        return state

    def _media_exists(self, project_id: str, rel: str | None) -> bool:
        if not rel:
            return False
        try:
            ensured = self.ensure_media(project_id, rel)
            if ensured and ensured.is_file():
                return True
            if self._pg:
                import pg_backend as _pg

                return _pg.media_exists(project_id, rel.replace("\\", "/"))
            return False
        except Exception:
            return False

    def _entity_image_rel(self, ent: dict[str, Any]) -> str | None:
        images = ent.get("images") or []
        if not images:
            return None
        sel = ent.get("selectedImageId")
        hit = next((i for i in images if i.get("id") == sel), None)
        if not hit:
            hit = images[0]
        rel = (hit or {}).get("path") or ""
        return rel or None

    def _resolve_cover(
        self,
        project_id: str,
        project: dict[str, Any],
        ents: list[dict[str, Any]],
        shots: list[dict[str, Any]],
        state: dict[str, Any],
    ) -> tuple[str | None, str | None]:
        """Return (coverUrl, coverVideoUrl). Prefer stills; fall back to video preview."""
        cover_path = (project.get("coverPath") or "").strip()
        if cover_path and self._media_exists(project_id, cover_path):
            return f"/api/media/{project_id}/{cover_path}", None

        for kind in ("character", "scene", "prop"):
            for ent in ents:
                if ent.get("kind") != kind:
                    continue
                rel = self._entity_image_rel(ent)
                if rel and self._media_exists(project_id, rel):
                    return f"/api/media/{project_id}/{rel}", None

        # Any image path recorded even if kind missing
        for ent in ents:
            rel = self._entity_image_rel(ent)
            if rel and self._media_exists(project_id, rel):
                return f"/api/media/{project_id}/{rel}", None

        # Finished edit / shot video as motion cover
        for edit in state.get("edits") or []:
            out = edit.get("outputPath") or ""
            if out and self._media_exists(project_id, out):
                return None, f"/api/media/{project_id}/{out}"

        ordered = sorted(shots, key=lambda s: int(s.get("shotOrder") or 0))
        for shot in ordered:
            sel = shot.get("selectedVideoId")
            videos = shot.get("videos") or []
            hit = next((v for v in videos if v.get("id") == sel), None)
            if not hit and videos:
                hit = next((v for v in videos if v.get("path") or v.get("url")), videos[0])
            rel = (hit or {}).get("path") or ""
            if rel and self._media_exists(project_id, rel):
                return None, f"/api/media/{project_id}/{rel}"

        return None, None

    def list_items(self, owner_id: str | None = None) -> list[dict[str, Any]]:
        uid = owner_id
        if uid is None:
            try:
                from auth_context import current_user_id

                uid = current_user_id() or None
            except Exception:
                uid = None
        items = []
        for pid in self.list_ids():
            state = self.load(pid)
            if not state:
                continue
            p = state.get("project")
            if not isinstance(p, dict):
                continue
            if p.get("hidden"):
                continue
            # Soft multi-tenant: each user sees own projects + seed templates
            proj_owner = str(p.get("ownerId") or "").strip()
            if uid and uid != "demo":
                is_seed = pid.startswith("welcome") or bool(p.get("seed"))
                if proj_owner and proj_owner != uid:
                    continue
                if not proj_owner and not is_seed:
                    continue
            eps = state.get("episodes") or []
            ents = [e for e in (state.get("entities") or []) if not e.get("deletedAt")]
            shots = [s for s in (state.get("shots") or []) if not s.get("deletedAt")]
            cover_url, cover_video_url = self._resolve_cover(pid, p, ents, shots, state)
            items.append(
                {
                    **p,
                    "coverUrl": cover_url,
                    "coverVideoUrl": cover_video_url,
                    "progress": {
                        "episodes": {
                            "total": len(eps),
                            "confirmed": sum(1 for e in eps if e.get("status") == "confirmed"),
                        },
                        "characters": {
                            "total": sum(1 for e in ents if e["kind"] == "character"),
                            "withImage": sum(
                                1 for e in ents if e["kind"] == "character" and e.get("selectedImageId")
                            ),
                        },
                        "scenes": {
                            "total": sum(1 for e in ents if e["kind"] == "scene"),
                            "withImage": sum(
                                1 for e in ents if e["kind"] == "scene" and e.get("selectedImageId")
                            ),
                        },
                        "props": {
                            "total": sum(1 for e in ents if e["kind"] == "prop"),
                            "withImage": sum(
                                1 for e in ents if e["kind"] == "prop" and e.get("selectedImageId")
                            ),
                        },
                        "audios": {
                            "total": len(state.get("audios") or []),
                        },
                        "shots": {
                            "total": len(shots),
                            "completed": sum(1 for s in shots if s.get("status") == "success"),
                            "generating": sum(1 for s in shots if s.get("status") == "generating"),
                            "failed": sum(1 for s in shots if s.get("status") == "failed"),
                        },
                    },
                }
            )
        items.sort(key=lambda x: x.get("updatedAt") or "", reverse=True)
        return items

    def _migrate_legacy(self, project: Path) -> dict[str, Any] | None:
        script_path = project / "script.json"
        if not script_path.exists():
            return None
        script = json.loads(script_path.read_text(encoding="utf-8"))
        bible = {}
        for p in (project / "character_bible.json", project / "bible" / "character_bible.json"):
            if p.exists():
                bible = json.loads(p.read_text(encoding="utf-8"))
                break
        sb = {}
        if (project / "storyboard.json").exists():
            sb = json.loads((project / "storyboard.json").read_text(encoding="utf-8"))
        ts = _now()
        pid = project.name
        novel = ""
        if (project / "source" / "NOVEL.md").exists():
            novel = (project / "source" / "NOVEL.md").read_text(encoding="utf-8")
        episodes = []
        for ep in script.get("episodes") or []:
            episodes.append(
                {
                    "id": ep.get("id") or new_id("ep_"),
                    "projectId": pid,
                    "episodeNumber": ep.get("episodeNumber") or ep.get("index") or 1,
                    "title": ep.get("title") or script.get("title") or pid,
                    "content": ep.get("content") or "",
                    "status": ep.get("status") or "draft",
                    "createdAt": ts,
                    "updatedAt": ts,
                }
            )
        if not episodes and script.get("sections"):
            content = "\n\n".join(
                f"【{s.get('label') or s.get('id')}】\n{s.get('text') or ''}" for s in script["sections"]
            )
            episodes = [
                {
                    "id": new_id("ep_"),
                    "projectId": pid,
                    "episodeNumber": 1,
                    "title": script.get("title") or pid,
                    "content": content,
                    "status": "draft",
                    "createdAt": ts,
                    "updatedAt": ts,
                }
            ]
        entities = []
        for c in bible.get("characters") or []:
            entities.append(
                {
                    "id": c.get("id") or new_id("ent_"),
                    "projectId": pid,
                    "kind": "character",
                    "name": c.get("display_name") or c.get("name") or "角色",
                    "variant": "默认形象",
                    "description": c.get("appearance") or "",
                    "episodes": [],
                    "category": "",
                    "metadata": {"role": c.get("role")},
                    "selectedImageId": None,
                    "images": [],
                    "createdAt": ts,
                    "updatedAt": ts,
                }
            )
        for loc in bible.get("locations") or []:
            entities.append(
                {
                    "id": loc.get("id") or new_id("ent_"),
                    "projectId": pid,
                    "kind": "scene",
                    "name": loc.get("name") or "场景",
                    "variant": "",
                    "description": loc.get("description") or "",
                    "episodes": [],
                    "category": "",
                    "metadata": {},
                    "selectedImageId": None,
                    "images": [],
                    "createdAt": ts,
                    "updatedAt": ts,
                }
            )
        for prop in bible.get("props") or []:
            entities.append(
                {
                    "id": prop.get("id") or new_id("ent_"),
                    "projectId": pid,
                    "kind": "prop",
                    "name": prop.get("name") or "道具",
                    "variant": "",
                    "description": prop.get("description") or "",
                    "episodes": [],
                    "category": prop.get("category") or "item",
                    "metadata": {},
                    "selectedImageId": None,
                    "images": [],
                    "createdAt": ts,
                    "updatedAt": ts,
                }
            )
        ep_id = episodes[0]["id"] if episodes else None
        shots = []
        for i, sh in enumerate(sb.get("shots") or [], 1):
            shots.append(
                {
                    "id": sh.get("id") or new_id("sh_"),
                    "projectId": pid,
                    "episodeId": ep_id,
                    "shotOrder": sh.get("index") or i,
                    "prompt": sh.get("video_prompt") or sh.get("description") or "",
                    "duration": int(sh.get("duration_sec") or 5),
                    "referenceEntityIds": sh.get("character_ids") or [],
                    "status": "pending",
                    "providerTaskId": None,
                    "error": None,
                    "selectedVideoId": None,
                    "videos": [],
                    "createdAt": ts,
                    "updatedAt": ts,
                }
            )
        state = {
            "project": {
                "id": pid,
                "title": script.get("title") or pid,
                "brief": script.get("brief") or novel[:4000],
                "synopsis": script.get("synopsis") or "",
                "genre": script.get("genre") or "短剧",
                "visualStyle": script.get("visual_style") or bible.get("visual_style") or "",
                "ratio": script.get("aspect_ratio") or sb.get("aspect_ratio") or "9:16",
                "plannedEpisodes": None,
                "createdAt": ts,
                "updatedAt": ts,
            },
            "episodes": episodes,
            "entities": entities,
            "shots": shots,
            "edits": [],
        }
        return self.save(state)

    def _mirror_artifacts(self, project: Path, state: dict[str, Any]) -> None:
        p = state["project"]
        script = {
            "version": "1.0",
            "title": p["title"],
            "synopsis": p.get("synopsis") or "",
            "brief": p.get("brief") or "",
            "genre": p.get("genre"),
            "visual_style": p.get("visualStyle"),
            "aspect_ratio": p.get("ratio"),
            "episodes": [
                {
                    "id": e["id"],
                    "episodeNumber": e["episodeNumber"],
                    "title": e["title"],
                    "content": e["content"],
                    "status": e["status"],
                }
                for e in state.get("episodes") or []
            ],
        }
        (project / "script.json").write_text(
            json.dumps(script, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        bible = {
            "version": "1.0",
            "visual_style": p.get("visualStyle"),
            "characters": [
                {
                    "id": e["id"],
                    "display_name": e["name"],
                    "appearance": e["description"],
                    "role": (e.get("metadata") or {}).get("role") or "supporting",
                }
                for e in state.get("entities") or []
                if e["kind"] == "character" and not e.get("deletedAt")
            ],
            "locations": [
                {"id": e["id"], "name": e["name"], "description": e["description"]}
                for e in state.get("entities") or []
                if e["kind"] == "scene" and not e.get("deletedAt")
            ],
            "props": [
                {
                    "id": e["id"],
                    "name": e["name"],
                    "description": e["description"],
                    "category": e.get("category") or "item",
                }
                for e in state.get("entities") or []
                if e["kind"] == "prop" and not e.get("deletedAt")
            ],
        }
        (project / "character_bible.json").write_text(
            json.dumps(bible, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        storyboard = {
            "version": "1.0",
            "episode_id": (state.get("episodes") or [{}])[0].get("id") if state.get("episodes") else None,
            "aspect_ratio": p.get("ratio") or "9:16",
            "shots": [
                {
                    "id": s["id"],
                    "index": s["shotOrder"],
                    "description": s.get("prompt"),
                    "duration_sec": s.get("duration"),
                    "prompt": s.get("prompt"),
                }
                for s in state.get("shots") or []
                if not s.get("deletedAt")
            ],
        }
        (project / "storyboard.json").write_text(
            json.dumps(storyboard, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
