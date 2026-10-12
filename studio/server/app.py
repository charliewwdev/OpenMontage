#!/usr/bin/env python3
"""Drama Studio API + static UI for local / Coolify deployment."""

from __future__ import annotations

import json
import mimetypes
import os
import re
import shutil
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

ROOT = Path(os.environ.get("OPENMONTAGE_ROOT", Path(__file__).resolve().parents[2])).resolve()
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from bootstrap import bootstrap_project, rebuild_project, slugify  # noqa: E402
from export_mp4 import export_episode_mp4, ffmpeg_available  # noqa: E402
from generate_worker import get_state as get_generate_state  # noqa: E402
from generate_worker import start_generate, write_entity_board  # noqa: E402
from lib.drama_status import summarize  # noqa: E402
from lib.pipeline_loader import get_stage_order, load_pipeline  # noqa: E402
from lib.subgraph_validate import validate_subgraph, validate_subgraph_file  # noqa: E402

PROJECTS_ROOT = Path(os.environ.get("PROJECTS_ROOT", str(ROOT / "projects"))).resolve()
DIST_DIR = Path(os.environ.get("STUDIO_DIST", str(Path(__file__).resolve().parents[1] / "dist"))).resolve()
HOST = os.environ.get("HOST", os.environ.get("STUDIO_HOST", "0.0.0.0"))
PORT = int(os.environ.get("PORT", os.environ.get("STUDIO_API_PORT", "8787")))

ARTIFACT_FILES = {
    "script": "script.json",
    "research": "research_brief.json",
    "proposal": "proposal_packet.json",
    "episode_breakdown": "episode_breakdown.json",
    "character_bible": "character_bible.json",
    "storyboard": "storyboard.json",
    "ledger": "shot_jobs.json",
    "metrics": "production_metrics.json",
    "qa": "drama_qa_report.json",
}

SIX_STEPS = [
    {"id": "script", "label": "剧本", "artifacts": ["script", "episode_breakdown"]},
    {"id": "characters", "label": "角色", "artifacts": ["character_bible"]},
    {"id": "locations", "label": "场景", "artifacts": ["character_bible", "episode_breakdown"]},
    {"id": "props", "label": "道具", "artifacts": ["character_bible"]},
    {"id": "storyboard", "label": "分镜", "artifacts": ["storyboard", "ledger"]},
    {"id": "edit", "label": "剪辑", "artifacts": ["storyboard", "ledger", "metrics"]},
]

CAPABILITY_ENV = [
    ("FAL_KEY", "fal.ai 图像/视频"),
    ("OPENAI_API_KEY", "OpenAI"),
    ("GOOGLE_API_KEY", "Google / Gemini"),
    ("PEXELS_API_KEY", "Pexels 库存"),
    ("PIXABAY_API_KEY", "Pixabay 库存"),
    ("ARK_API_KEY", "Seedance / Ark"),
    ("DASHSCOPE_API_KEY", "DashScope"),
    ("ELEVENLABS_API_KEY", "ElevenLabs TTS"),
    ("MINIMAX_API_KEY", "MiniMax"),
    ("KLING_API_KEY", "Kling"),
    ("REPLICATE_API_TOKEN", "Replicate"),
]


def _json_response(handler: BaseHTTPRequestHandler, code: int, payload: dict) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, PATCH, PUT, OPTIONS")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _read_json(handler: BaseHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length") or 0)
    if length <= 0:
        return {}
    return json.loads(handler.rfile.read(length))


def _safe_project(name: str) -> Path | None:
    if not name or "/" in name or "\\" in name or name.startswith("."):
        return None
    path = (PROJECTS_ROOT / name).resolve()
    if not str(path).startswith(str(PROJECTS_ROOT)):
        return None
    return path


def _artifact_path(project: Path, kind: str) -> Path | None:
    rel = ARTIFACT_FILES.get(kind)
    if not rel:
        return None
    path = project / rel
    if not path.exists() and kind == "character_bible":
        alt = project / "bible" / "character_bible.json"
        if alt.exists():
            return alt
    return path


def _load_artifact(project: Path, kind: str):
    path = _artifact_path(project, kind)
    if not path or not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _save_artifact(project: Path, kind: str, data: dict) -> Path:
    path = _artifact_path(project, kind)
    if path is None:
        raise ValueError(f"unknown artifact kind: {kind}")
    # Prefer top-level character_bible.json for writes
    if kind == "character_bible":
        path = project / "character_bible.json"
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def _project_bundle(name: str) -> dict:
    project = _safe_project(name)
    if not project or not project.is_dir():
        return {"error": "project not found"}
    arts = {}
    for kind in ARTIFACT_FILES:
        data = _load_artifact(project, kind)
        if data is not None:
            arts[kind] = data
    step_status = []
    for step in SIX_STEPS:
        present = [a for a in step["artifacts"] if a in arts]
        if step["id"] == "props":
            bible = arts.get("character_bible") or {}
            props = bible.get("props") or bible.get("prop_assets") or []
            state = "done" if props else ("partial" if bible else "empty")
        elif len(present) == len(step["artifacts"]):
            state = "done"
        elif present:
            state = "partial"
        else:
            state = "empty"
        step_status.append({"id": step["id"], "label": step["label"], "state": state, "present": present})
    source = ""
    novel = project / "source" / "NOVEL.md"
    if novel.exists():
        source = novel.read_text(encoding="utf-8")[:4000]
    return {
        "name": name,
        "path": str(project),
        "artifacts": arts,
        "steps": step_status,
        "status": summarize(project),
        "source_excerpt": source,
    }


def _capabilities() -> dict:
    keys = []
    for env_key, label in CAPABILITY_ENV:
        present = bool(os.environ.get(env_key) or (env_key == "FAL_KEY" and os.environ.get("FAL_AI_API_KEY")))
        keys.append({"key": env_key, "label": label, "configured": present})
    configured = sum(1 for k in keys if k["configured"])
    return {
        "configured": configured,
        "total": len(keys),
        "keys": keys,
        "mode": "online" if configured else "offline-bootstrap",
        "ffmpeg": ffmpeg_available(),
        "export_ready": True,
    }


def _serve_static(handler: BaseHTTPRequestHandler, url_path: str) -> bool:
    if not DIST_DIR.is_dir():
        return False
    rel = url_path.lstrip("/") or "index.html"
    candidate = (DIST_DIR / rel).resolve()
    if not str(candidate).startswith(str(DIST_DIR)):
        return False
    if not candidate.is_file():
        candidate = DIST_DIR / "index.html"
        if not candidate.is_file():
            return False
    data = candidate.read_bytes()
    ctype = mimetypes.guess_type(str(candidate))[0] or "application/octet-stream"
    handler.send_response(200)
    handler.send_header("Content-Type", ctype)
    handler.send_header("Content-Length", str(len(data)))
    handler.send_header("Cache-Control", "no-cache" if candidate.name == "index.html" else "public, max-age=3600")
    handler.end_headers()
    handler.wfile.write(data)
    return True


def _export_timeline(storyboard: dict, ledger: dict | None) -> dict:
    jobs = {j.get("shot_id"): j for j in (ledger or {}).get("jobs") or []}
    clips = []
    t = 0.0
    for shot in storyboard.get("shots") or []:
        dur = float(shot.get("duration_sec") or 3)
        job = jobs.get(shot["id"]) or {}
        clips.append(
            {
                "shot_id": shot["id"],
                "start": round(t, 3),
                "end": round(t + dur, 3),
                "duration_sec": dur,
                "description": shot.get("description"),
                "dialogue": shot.get("dialogue"),
                "status": job.get("status") or "pending",
                "clip_path": job.get("clip_path") or shot.get("clip_path"),
                "keyframe_path": job.get("keyframe_path") or shot.get("keyframe_path"),
            }
        )
        t += dur
    return {
        "episode_id": storyboard.get("episode_id"),
        "aspect_ratio": storyboard.get("aspect_ratio") or "9:16",
        "total_duration_sec": round(t, 3),
        "clips": clips,
        "ffmpeg_concat": "\n".join(
            f"file '{c['clip_path']}'" for c in clips if c.get("clip_path")
        ),
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def do_OPTIONS(self) -> None:
        _json_response(self, 204, {})

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        if path == "/api/health":
            return _json_response(
                self,
                200,
                {
                    "ok": True,
                    "service": "openmontage-drama-studio",
                    "root": str(ROOT),
                    "projects_root": str(PROJECTS_ROOT),
                    "dist": DIST_DIR.is_dir(),
                },
            )

        if path == "/api/config":
            return _json_response(
                self,
                200,
                {
                    "product": "OpenMontage Drama Studio",
                    "public_url": os.environ.get("STUDIO_PUBLIC_URL", ""),
                    "api_base_url": os.environ.get("API_BASE_URL", ""),
                    "six_steps": SIX_STEPS,
                    "desks": [
                        {"id": "director", "label": "编导台"},
                        {"id": "canvas", "label": "画布"},
                        {"id": "edit", "label": "剪辑室"},
                    ],
                    "capabilities": _capabilities(),
                },
            )

        if path == "/api/capabilities":
            return _json_response(self, 200, _capabilities())

        if path == "/api/pipeline/short-drama":
            manifest = load_pipeline("short-drama")
            return _json_response(
                self,
                200,
                {
                    "name": manifest["name"],
                    "stages": get_stage_order(manifest),
                    "stage_details": [
                        {
                            "name": s["name"],
                            "human_approval_default": s.get("human_approval_default"),
                            "subgraph_refs": s.get("subgraph_refs"),
                        }
                        for s in manifest["stages"]
                    ],
                    "subgraph_refs": manifest.get("subgraph_refs", {}),
                },
            )

        if path == "/api/subgraphs":
            root = ROOT / "workflow_defs" / "subgraphs"
            items = []
            if root.is_dir():
                for p in sorted(root.glob("*.workflow.json")):
                    doc = json.loads(p.read_text(encoding="utf-8"))
                    items.append(
                        {
                            "id": doc.get("id"),
                            "path": str(p.relative_to(ROOT)),
                            "title": doc.get("title"),
                        }
                    )
            return _json_response(self, 200, {"subgraphs": items})

        if path.startswith("/api/subgraphs/") and path.endswith("/graph"):
            subgraph_id = path.split("/")[3]
            path_file = ROOT / "workflow_defs" / "subgraphs" / f"{subgraph_id}.workflow.json"
            if not path_file.exists():
                return _json_response(self, 404, {"error": "subgraph not found"})
            doc = json.loads(path_file.read_text(encoding="utf-8"))
            return _json_response(
                self, 200, {"document": doc, "validation": validate_subgraph_file(path_file)}
            )

        if path == "/api/projects":
            names = []
            if PROJECTS_ROOT.is_dir():
                names = sorted(
                    [p.name for p in PROJECTS_ROOT.iterdir() if p.is_dir() and not p.name.startswith(".")]
                )
            return _json_response(self, 200, {"projects": names, "root": str(PROJECTS_ROOT)})

        if path == "/api/project/bundle":
            name = (qs.get("name") or [None])[0]
            if not name:
                return _json_response(self, 400, {"error": "name required"})
            bundle = _project_bundle(name)
            if bundle.get("error"):
                return _json_response(self, 404, bundle)
            return _json_response(self, 200, bundle)

        if path == "/api/project/status":
            name = (qs.get("name") or [None])[0]
            if not name:
                return _json_response(self, 400, {"error": "name required"})
            project = _safe_project(name)
            if not project or not project.is_dir():
                return _json_response(self, 404, {"error": "project not found"})
            return _json_response(self, 200, summarize(project))

        if path == "/api/project/artifact":
            name = (qs.get("name") or [None])[0]
            kind = (qs.get("kind") or [None])[0]
            if not name or not kind:
                return _json_response(self, 400, {"error": "name and kind required"})
            project = _safe_project(name)
            if not project:
                return _json_response(self, 400, {"error": "invalid project"})
            data = _load_artifact(project, kind)
            if data is None:
                return _json_response(self, 404, {"error": f"{kind} not found"})
            return _json_response(self, 200, {"kind": kind, "data": data})

        if path == "/api/project/storyboard":
            name = (qs.get("name") or [None])[0]
            if not name:
                return _json_response(self, 400, {"error": "name required"})
            project = _safe_project(name)
            if not project:
                return _json_response(self, 400, {"error": "invalid project"})
            data = _load_artifact(project, "storyboard")
            if data is None:
                return _json_response(self, 404, {"error": "storyboard.json not found"})
            return _json_response(self, 200, {"storyboard": data})

        if path == "/api/project/ledger":
            name = (qs.get("name") or [None])[0]
            if not name:
                return _json_response(self, 400, {"error": "name required"})
            project = _safe_project(name)
            if not project:
                return _json_response(self, 400, {"error": "invalid project"})
            data = _load_artifact(project, "ledger")
            if data is None:
                return _json_response(self, 404, {"error": "shot_jobs.json not found"})
            return _json_response(self, 200, {"ledger": data})

        if path == "/api/project/export/timeline":
            name = (qs.get("name") or [None])[0]
            if not name:
                return _json_response(self, 400, {"error": "name required"})
            project = _safe_project(name)
            if not project:
                return _json_response(self, 400, {"error": "invalid project"})
            sb = _load_artifact(project, "storyboard")
            if not sb:
                return _json_response(self, 404, {"error": "storyboard missing"})
            ledger = _load_artifact(project, "ledger")
            return _json_response(self, 200, {"timeline": _export_timeline(sb, ledger)})

        if path == "/api/project/generate/status":
            state = get_generate_state()
            # Flatten for UI polling (running / processed at top level)
            return _json_response(self, 200, {**state, "state": state})

        if path == "/api/project/source":
            name = (qs.get("name") or [None])[0]
            if not name:
                return _json_response(self, 400, {"error": "name required"})
            project = _safe_project(name)
            if not project or not project.is_dir():
                return _json_response(self, 404, {"error": "project not found"})
            novel = project / "source" / "NOVEL.md"
            text = novel.read_text(encoding="utf-8") if novel.exists() else ""
            return _json_response(
                self,
                200,
                {"project": name, "source": text, "chars": len(text)},
            )

        if path == "/api/project/exports":
            name = (qs.get("name") or [None])[0]
            if not name:
                return _json_response(self, 400, {"error": "name required"})
            project = _safe_project(name)
            if not project or not project.is_dir():
                return _json_response(self, 404, {"error": "project not found"})
            export_dir = project / "exports"
            items = []
            if export_dir.is_dir():
                for p in sorted(export_dir.glob("*.mp4"), key=lambda x: x.stat().st_mtime, reverse=True):
                    items.append(
                        {
                            "path": str(p.relative_to(project)),
                            "url": f"/api/media/{name}/{p.relative_to(project)}",
                            "bytes": p.stat().st_size,
                            "mtime": int(p.stat().st_mtime),
                        }
                    )
            return _json_response(self, 200, {"exports": items, "ffmpeg": ffmpeg_available()})

        if path.startswith("/api/media/"):
            parts = path.split("/")
            if len(parts) < 5:
                return _json_response(self, 400, {"error": "bad media path"})
            name = unquote(parts[3])
            rel = unquote("/".join(parts[4:]))
            project = _safe_project(name)
            if not project or not project.is_dir():
                return _json_response(self, 404, {"error": "project not found"})
            if ".." in rel.split("/"):
                return _json_response(self, 400, {"error": "invalid path"})
            file_path = (project / rel).resolve()
            if not str(file_path).startswith(str(project)) or not file_path.is_file():
                return _json_response(self, 404, {"error": "file not found"})
            data = file_path.read_bytes()
            ctype = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
            if file_path.suffix.lower() == ".svg":
                ctype = "image/svg+xml"
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "public, max-age=60")
            self.end_headers()
            self.wfile.write(data)
            return None

        if path.startswith("/api/"):
            return _json_response(self, 404, {"error": "not found"})

        if _serve_static(self, path):
            return None
        return _json_response(self, 404, {"error": "UI not built; run npm run build in studio/"})

    def do_PUT(self) -> None:
        return self._write()

    def do_PATCH(self) -> None:
        return self._write()

    def do_POST(self) -> None:
        return self._write()

    def _write(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        body = _read_json(self)

        if path == "/api/subgraphs/validate":
            if body.get("path"):
                result = validate_subgraph_file(ROOT / body["path"])
            else:
                errors = validate_subgraph(body.get("document") or {})
                result = {"valid": not errors, "errors": errors}
            return _json_response(self, 200, result)

        if path == "/api/projects":
            title = (body.get("title") or "").strip()
            source = (body.get("source_text") or body.get("novel") or body.get("brief") or "").strip()
            name = (body.get("name") or title or "").strip()
            if not title or not source:
                return _json_response(self, 400, {"error": "title and source_text required"})
            if len(source) < 20:
                return _json_response(self, 400, {"error": "source_text too short (min ~20 chars)"})
            try:
                result = bootstrap_project(
                    PROJECTS_ROOT,
                    name=name,
                    title=title,
                    source_text=source,
                    aspect_ratio=body.get("aspect_ratio") or body.get("ratio") or "9:16",
                    visual_style=body.get("visual_style")
                    or body.get("visualStyle")
                    or "当代都市夜戏，电影感冷暖对比",
                    genre=body.get("genre") or "都市逆袭",
                )
            except FileExistsError as exc:
                return _json_response(self, 409, {"error": str(exc)})
            except Exception as exc:
                return _json_response(self, 500, {"error": str(exc)})
            bundle = _project_bundle(result["name"])
            return _json_response(self, 201, {"created": result, "bundle": bundle})

        if path == "/api/project/rebuild":
            name = body.get("project") or body.get("name")
            source = (body.get("source_text") or body.get("novel") or "").strip()
            if not name or not source:
                return _json_response(self, 400, {"error": "project and source_text required"})
            if len(source) < 20:
                return _json_response(self, 400, {"error": "source_text too short"})
            project = _safe_project(name)
            if not project or not project.is_dir():
                return _json_response(self, 404, {"error": "project not found"})
            try:
                result = rebuild_project(
                    project,
                    title=(body.get("title") or "").strip() or None,
                    source_text=source,
                    aspect_ratio=body.get("aspect_ratio"),
                    visual_style=body.get("visual_style"),
                    genre=body.get("genre"),
                )
            except Exception as exc:
                return _json_response(self, 500, {"error": str(exc)})
            return _json_response(self, 200, {"rebuilt": result, "bundle": _project_bundle(name)})

        if path == "/api/project/entity/generate":
            name = body.get("project")
            entity = body.get("entity")
            item_id = body.get("item_id") or body.get("id")
            if not name or entity not in {"character", "location", "prop"} or not item_id:
                return _json_response(self, 400, {"error": "project, entity, item_id required"})
            project = _safe_project(name)
            if not project or not project.is_dir():
                return _json_response(self, 404, {"error": "project not found"})
            bible = _load_artifact(project, "character_bible") or {}
            key = {"character": "characters", "location": "locations", "prop": "props"}[entity]
            item = next((x for x in (bible.get(key) or []) if x.get("id") == item_id), None)
            if not item:
                return _json_response(self, 404, {"error": "entity not found"})
            path_svg = write_entity_board(
                project, entity, item, visual_style=bible.get("visual_style") or ""
            )
            rel = str(path_svg.relative_to(project))
            # persist reference on bible item
            item = {**item, "reference_image": rel, "selected_image": rel}
            arr = list(bible.get(key) or [])
            for i, existing in enumerate(arr):
                if existing.get("id") == item_id:
                    arr[i] = item
                    break
            bible[key] = arr
            _save_artifact(project, "character_bible", bible)
            return _json_response(
                self,
                200,
                {
                    "ok": True,
                    "path": rel,
                    "url": f"/api/media/{name}/{rel}",
                    "bible": bible,
                    "bundle": _project_bundle(name),
                },
            )

        if path == "/api/project/export/mp4":
            name = body.get("project") or body.get("name")
            if not name:
                return _json_response(self, 400, {"error": "project required"})
            project = _safe_project(name)
            if not project or not project.is_dir():
                return _json_response(self, 404, {"error": "project not found"})
            sb = _load_artifact(project, "storyboard")
            if not sb:
                return _json_response(self, 404, {"error": "storyboard missing"})
            ledger = _load_artifact(project, "ledger")
            try:
                result = export_episode_mp4(
                    project, sb, ledger, shot_ids=body.get("shot_ids")
                )
            except Exception as exc:
                return _json_response(self, 500, {"error": str(exc), "ffmpeg": ffmpeg_available()})
            # write lightweight metrics
            metrics = {
                "version": "1.0",
                "last_export": result,
                "ffmpeg": True,
            }
            (project / "production_metrics.json").write_text(
                json.dumps(metrics, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
            )
            return _json_response(self, 200, {**result, "bundle": _project_bundle(name)})

        if path == "/api/project/artifact":
            name = body.get("project") or body.get("name")
            kind = body.get("kind")
            data = body.get("data")
            if not name or not kind or data is None:
                return _json_response(self, 400, {"error": "project, kind, data required"})
            project = _safe_project(name)
            if not project or not project.is_dir():
                return _json_response(self, 404, {"error": "project not found"})
            if kind not in ARTIFACT_FILES:
                return _json_response(self, 400, {"error": "unknown kind"})
            _save_artifact(project, kind, data)
            return _json_response(self, 200, {"ok": True, "kind": kind, "data": data})

        if path == "/api/project/storyboard/patch":
            name = body.get("project")
            shot_id = body.get("shot_id")
            patch = body.get("patch") or {}
            if not name or not shot_id:
                return _json_response(self, 400, {"error": "project and shot_id required"})
            project = _safe_project(name)
            if not project:
                return _json_response(self, 400, {"error": "invalid project"})
            sb_path = project / "storyboard.json"
            if not sb_path.exists():
                return _json_response(self, 404, {"error": "storyboard missing"})
            storyboard = json.loads(sb_path.read_text(encoding="utf-8"))
            found = False
            for shot in storyboard.get("shots", []):
                if shot.get("id") == shot_id:
                    shot.update(patch)
                    found = True
                    break
            if not found:
                return _json_response(self, 404, {"error": "shot not found"})
            _save_artifact(project, "storyboard", storyboard)
            return _json_response(self, 200, {"storyboard": storyboard})

        if path == "/api/project/storyboard/reorder":
            name = body.get("project")
            order = body.get("shot_ids") or []
            if not name or not order:
                return _json_response(self, 400, {"error": "project and shot_ids required"})
            project = _safe_project(name)
            if not project:
                return _json_response(self, 400, {"error": "invalid project"})
            sb = _load_artifact(project, "storyboard")
            if not sb:
                return _json_response(self, 404, {"error": "storyboard missing"})
            by_id = {s["id"]: s for s in sb.get("shots") or []}
            shots = []
            for i, sid in enumerate(order, 1):
                if sid not in by_id:
                    return _json_response(self, 400, {"error": f"unknown shot {sid}"})
                shot = dict(by_id[sid])
                shot["index"] = i
                shots.append(shot)
            # append any missing
            for sid, shot in by_id.items():
                if sid not in order:
                    shot = dict(shot)
                    shot["index"] = len(shots) + 1
                    shots.append(shot)
            sb["shots"] = shots
            _save_artifact(project, "storyboard", sb)
            return _json_response(self, 200, {"storyboard": sb})

        if path == "/api/project/ledger/invalidate":
            name = body.get("project")
            shot_id = body.get("shot_id")
            if not name or not shot_id:
                return _json_response(self, 400, {"error": "project and shot_id required"})
            project = _safe_project(name)
            if not project:
                return _json_response(self, 400, {"error": "invalid project"})
            from tools.pipeline.shot_job_manager import ShotJobManager

            ledger_path = project / "shot_jobs.json"
            result = ShotJobManager().execute(
                {
                    "operation": "invalidate_shot",
                    "ledger_path": str(ledger_path),
                    "shot_id": shot_id,
                }
            )
            code = 200 if result.success else 400
            return _json_response(
                self,
                code,
                {"success": result.success, "data": result.data, "error": result.error},
            )

        if path == "/api/project/ledger/sync":
            name = body.get("project")
            if not name:
                return _json_response(self, 400, {"error": "project required"})
            project = _safe_project(name)
            if not project:
                return _json_response(self, 400, {"error": "invalid project"})
            sb = _load_artifact(project, "storyboard")
            if not sb:
                return _json_response(self, 404, {"error": "storyboard missing"})
            from tools.pipeline.shot_job_manager import ShotJobManager

            ledger_path = project / "shot_jobs.json"
            result = ShotJobManager().execute(
                {
                    "operation": "create_from_storyboard",
                    "ledger_path": str(ledger_path),
                    "storyboard": sb,
                    "episode_id": sb.get("episode_id") or "ep01",
                    "concurrency": int(body.get("concurrency") or 2),
                    "max_retries": 2,
                    "default_subgraph_id": "keyframe-i2v-qa",
                }
            )
            code = 200 if result.success else 400
            return _json_response(
                self,
                code,
                {
                    "success": result.success,
                    "ledger": (result.data or {}).get("ledger") if result.success else None,
                    "error": result.error,
                },
            )

        if path == "/api/project/ledger/mark":
            name = body.get("project")
            shot_id = body.get("shot_id")
            status = body.get("status")
            if not name or not shot_id or not status:
                return _json_response(self, 400, {"error": "project, shot_id, status required"})
            project = _safe_project(name)
            if not project:
                return _json_response(self, 400, {"error": "invalid project"})
            from tools.pipeline.shot_job_manager import ShotJobManager

            ledger_path = project / "shot_jobs.json"
            result = ShotJobManager().execute(
                {
                    "operation": "mark",
                    "ledger_path": str(ledger_path),
                    "shot_id": shot_id,
                    "status": status,
                    "clip_path": body.get("clip_path"),
                    "keyframe_path": body.get("keyframe_path"),
                    "error": body.get("error"),
                }
            )
            code = 200 if result.success else 400
            return _json_response(
                self,
                code,
                {"success": result.success, "data": result.data, "error": result.error},
            )

        if path == "/api/project/bible/upsert":
            name = body.get("project")
            entity = body.get("entity")  # character | location | prop
            item = body.get("item") or {}
            if not name or entity not in {"character", "location", "prop"} or not item.get("id"):
                return _json_response(self, 400, {"error": "project, entity, item.id required"})
            project = _safe_project(name)
            if not project:
                return _json_response(self, 400, {"error": "invalid project"})
            bible = _load_artifact(project, "character_bible") or {
                "version": "1.0",
                "characters": [],
                "locations": [],
                "props": [],
            }
            key = {"character": "characters", "location": "locations", "prop": "props"}[entity]
            arr = list(bible.get(key) or [])
            replaced = False
            for i, existing in enumerate(arr):
                if existing.get("id") == item["id"]:
                    arr[i] = {**existing, **item}
                    replaced = True
                    break
            if not replaced:
                arr.append(item)
            bible[key] = arr
            _save_artifact(project, "character_bible", bible)
            return _json_response(self, 200, {"bible": bible})

        if path == "/api/project/generate":
            name = body.get("project")
            if not name:
                return _json_response(self, 400, {"error": "project required"})
            project = _safe_project(name)
            if not project or not project.is_dir():
                return _json_response(self, 404, {"error": "project not found"})
            sb = _load_artifact(project, "storyboard")
            if not sb:
                return _json_response(self, 404, {"error": "storyboard missing"})
            bible = _load_artifact(project, "character_bible")
            limit = int(body.get("limit") or 3)
            result = start_generate(project, sb, bible, limit=limit)
            code = 200 if result.get("started") else 409
            return _json_response(self, code, result)

        if path == "/api/project/delete":
            name = body.get("project") or body.get("name")
            if not name:
                return _json_response(self, 400, {"error": "project required"})
            project = _safe_project(name)
            if not project or not project.is_dir():
                return _json_response(self, 404, {"error": "project not found"})
            shutil.rmtree(project)
            return _json_response(self, 200, {"ok": True, "deleted": name})

        return _json_response(self, 404, {"error": "not found"})


def main() -> None:
    PROJECTS_ROOT.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(
        f"Drama Studio on http://{HOST}:{PORT} (projects={PROJECTS_ROOT}, dist={DIST_DIR.is_dir()})",
        flush=True,
    )
    server.serve_forever()


if __name__ == "__main__":
    main()
