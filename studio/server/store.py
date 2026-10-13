"""JSON file project store shaped like Xuefeng ProjectBundle."""

from __future__ import annotations

import json
import re
import shutil
import time
import uuid
from pathlib import Path
from typing import Any


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


class ProjectStore:
    def __init__(self, projects_root: Path):
        self.root = projects_root
        self.root.mkdir(parents=True, exist_ok=True)

    def _dir(self, project_id: str) -> Path | None:
        if not project_id or "/" in project_id or "\\" in project_id or project_id.startswith("."):
            return None
        path = (self.root / project_id).resolve()
        if not str(path).startswith(str(self.root.resolve())):
            return None
        return path

    def _studio_path(self, project: Path) -> Path:
        return project / "studio_state.json"

    def list_ids(self) -> list[str]:
        if not self.root.is_dir():
            return []
        return sorted(p.name for p in self.root.iterdir() if p.is_dir() and not p.name.startswith("."))

    def load(self, project_id: str) -> dict[str, Any] | None:
        project = self._dir(project_id)
        if not project or not project.is_dir():
            return None
        path = self._studio_path(project)
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        # migrate from legacy bootstrap artifacts if present
        return self._migrate_legacy(project)

    def save(self, state: dict[str, Any]) -> dict[str, Any]:
        project_id = state["project"]["id"]
        project = self._dir(project_id)
        if not project:
            raise ValueError("invalid project id")
        project.mkdir(parents=True, exist_ok=True)
        (project / "media" / "images").mkdir(parents=True, exist_ok=True)
        (project / "media" / "videos").mkdir(parents=True, exist_ok=True)
        (project / "media" / "exports").mkdir(parents=True, exist_ok=True)
        state["project"]["updatedAt"] = _now()
        self._studio_path(project).write_text(
            json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        # keep lightweight mirrors for OpenMontage tooling
        self._mirror_artifacts(project, state)
        return state

    def delete(self, project_id: str) -> bool:
        project = self._dir(project_id)
        if not project or not project.is_dir():
            return False
        shutil.rmtree(project)
        return True

    def media_dir(self, project_id: str, kind: str = "images") -> Path:
        project = self._dir(project_id)
        assert project
        path = project / "media" / kind
        path.mkdir(parents=True, exist_ok=True)
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
        base = slugify(name or title)
        project_id = base
        i = 2
        while (self.root / project_id).exists():
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
                "createdAt": ts,
                "updatedAt": ts,
            },
            "episodes": [],
            "entities": [],
            "shots": [],
            "edits": [],
        }
        return self.save(state)

    def bundle(self, project_id: str) -> dict[str, Any] | None:
        state = self.load(project_id)
        if not state:
            return None
        # attach media urls
        for ent in state.get("entities") or []:
            for img in ent.get("images") or []:
                img["url"] = f"/api/media/{project_id}/{img['path']}"
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
        return state

    def list_items(self) -> list[dict[str, Any]]:
        items = []
        for pid in self.list_ids():
            state = self.load(pid)
            if not state:
                continue
            p = state["project"]
            eps = state.get("episodes") or []
            ents = [e for e in (state.get("entities") or []) if not e.get("deletedAt")]
            shots = [s for s in (state.get("shots") or []) if not s.get("deletedAt")]
            items.append(
                {
                    **p,
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
