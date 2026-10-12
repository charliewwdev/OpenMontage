#!/usr/bin/env python3
"""OpenMontage Drama Studio — Xuefeng-parity API + static UI."""

from __future__ import annotations

import base64
import json
import mimetypes
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

ROOT = Path(os.environ.get("OPENMONTAGE_ROOT", Path(__file__).resolve().parents[2])).resolve()
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from drama_service import (  # noqa: E402
    continue_script,
    ensure_edit_draft,
    export_edit_mp4,
    generate_entity_image,
    generate_script,
    generate_storyboard,
    load_styles,
    optimize_brief,
    patch_episode,
    patch_project,
    patch_shot,
    patch_take,
    poll_shot,
    rewrite_script,
    save_edit,
    select_entity_image,
    select_take,
    set_episode_status,
    soft_delete_entity,
    start_shot_video,
    upload_entity_image,
    upsert_entity,
)
from export_mp4 import ffmpeg_available  # noqa: E402
from providers import provider_status  # noqa: E402
from providers.seedance import SEEDANCE_MODELS  # noqa: E402
from store import ProjectStore  # noqa: E402

PROJECTS_ROOT = Path(os.environ.get("PROJECTS_ROOT", str(ROOT / "projects"))).resolve()
DIST_DIR = Path(os.environ.get("STUDIO_DIST", str(Path(__file__).resolve().parents[1] / "dist"))).resolve()
HOST = os.environ.get("HOST", os.environ.get("STUDIO_HOST", "0.0.0.0"))
PORT = int(os.environ.get("PORT", os.environ.get("STUDIO_API_PORT", "8787")))

STORE = ProjectStore(PROJECTS_ROOT)

GENRES = [
    "都市情感",
    "豪门霸总",
    "婚姻家庭",
    "赘婿逆袭",
    "重生复仇",
    "穿越逆袭",
    "战神归来",
    "神医高手",
    "商战职场",
    "古装权谋",
    "悬疑犯罪",
    "奇幻冒险",
]


def _json(handler: BaseHTTPRequestHandler, code: int, payload: dict | list) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, PATCH, PUT, DELETE, OPTIONS")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _read_json(handler: BaseHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length") or 0)
    if length <= 0:
        return {}
    return json.loads(handler.rfile.read(length))


def _read_raw(handler: BaseHTTPRequestHandler) -> bytes:
    length = int(handler.headers.get("Content-Length") or 0)
    return handler.rfile.read(length) if length > 0 else b""


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
    handler.send_header("Content-Length", str(data.__len__()))
    handler.send_header("Cache-Control", "no-cache" if candidate.name == "index.html" else "public, max-age=3600")
    handler.end_headers()
    handler.wfile.write(data)
    return True


def _err(handler: BaseHTTPRequestHandler, code: int, message: str) -> None:
    return _json(handler, code, {"error": message})


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def do_OPTIONS(self) -> None:
        _json(self, 204, {})

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        if path == "/api/health":
            return _json(
                self,
                200,
                {
                    "ok": True,
                    "service": "openmontage-drama-studio",
                    "root": str(ROOT),
                    "projects_root": str(PROJECTS_ROOT),
                    "dist": DIST_DIR.is_dir(),
                    "ffmpeg": ffmpeg_available(),
                    "providers": provider_status(),
                },
            )

        if path == "/api/config":
            return _json(
                self,
                200,
                {
                    "product": "OpenMontage Drama Studio",
                    "public_url": os.environ.get("STUDIO_PUBLIC_URL", ""),
                    "genres": GENRES,
                    "styles": load_styles(),
                    "seedanceModels": SEEDANCE_MODELS,
                    "ratios": [
                        {"value": "9:16", "label": "竖屏", "description": "短剧与移动端"},
                        {"value": "16:9", "label": "横屏", "description": "电影与桌面端"},
                        {"value": "1:1", "label": "方屏", "description": "社媒"},
                    ],
                    "capabilities": {
                        **provider_status(),
                        "ffmpeg": ffmpeg_available(),
                        "configured": sum(1 for v in provider_status().values() if v),
                        "total": 3,
                        "mode": "online" if any(provider_status().values()) else "offline-bootstrap",
                    },
                    "six_steps": [
                        {"id": "script", "label": "剧本"},
                        {"id": "character", "label": "角色"},
                        {"id": "scene", "label": "场景"},
                        {"id": "prop", "label": "道具"},
                        {"id": "storyboard", "label": "分镜"},
                        {"id": "edit", "label": "剪辑"},
                    ],
                },
            )

        if path == "/api/projects":
            return _json(self, 200, {"projects": STORE.list_items()})

        # /api/projects/:id
        if path.startswith("/api/projects/") and path.count("/") == 3:
            pid = unquote(path.split("/")[3])
            bundle = STORE.bundle(pid)
            if not bundle:
                return _err(self, 404, "project not found")
            return _json(self, 200, bundle)

        if path.startswith("/api/media/"):
            parts = path.split("/")
            if len(parts) < 5:
                return _err(self, 400, "bad media path")
            name = unquote(parts[3])
            rel = unquote("/".join(parts[4:]))
            project = STORE._dir(name)
            if not project or not project.is_dir():
                return _err(self, 404, "project not found")
            if ".." in rel.split("/"):
                return _err(self, 400, "invalid path")
            file_path = (project / rel).resolve()
            if not str(file_path).startswith(str(project)) or not file_path.is_file():
                return _err(self, 404, "file not found")
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

        # GET shot poll: /api/projects/:id/shots/:shotId
        if "/shots/" in path and path.startswith("/api/projects/"):
            parts = [unquote(p) for p in path.strip("/").split("/")]
            # api projects pid shots shotId
            if len(parts) >= 5 and parts[3] == "shots":
                try:
                    shot = poll_shot(STORE, parts[2], parts[4])
                    return _json(self, 200, shot)
                except FileNotFoundError as exc:
                    return _err(self, 404, str(exc))

        if path.startswith("/api/"):
            return _err(self, 404, "not found")
        if _serve_static(self, path):
            return None
        return _err(self, 404, "UI not built; run npm run build in studio/")

    def do_DELETE(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)
        if path.startswith("/api/projects/") and path.count("/") == 3:
            pid = unquote(path.split("/")[3])
            if not STORE.delete(pid):
                return _err(self, 404, "project not found")
            return _json(self, 200, {"ok": True, "deleted": pid})
        if path.startswith("/api/projects/") and path.endswith("/entities"):
            pid = unquote(path.split("/")[3])
            eid = (qs.get("entityId") or [None])[0]
            if not eid:
                return _err(self, 400, "entityId required")
            try:
                state = soft_delete_entity(STORE, pid, eid)
                return _json(self, 200, STORE.bundle(pid) or state)
            except FileNotFoundError as exc:
                return _err(self, 404, str(exc))
        return _err(self, 404, "not found")

    def do_PATCH(self) -> None:
        return self._write("PATCH")

    def do_POST(self) -> None:
        return self._write("POST")

    def do_PUT(self) -> None:
        return self._write("PUT")

    def _write(self, method: str) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        body = _read_json(self)

        try:
            # Create project
            if path == "/api/projects" and method == "POST":
                title = (body.get("title") or "").strip()
                if not title:
                    return _err(self, 400, "title required")
                state = STORE.create_project(
                    title=title,
                    brief=body.get("brief") or body.get("source_text") or "",
                    genre=body.get("genre") or GENRES[0],
                    visual_style=body.get("visualStyle") or body.get("visual_style") or "",
                    ratio=body.get("ratio") or body.get("aspect_ratio") or "9:16",
                    name=body.get("name"),
                )
                return _json(self, 201, STORE.bundle(state["project"]["id"]))

            # script brief optimize (global)
            if path == "/api/script-brief" and method == "POST":
                return _json(self, 200, optimize_brief(STORE, body))

            if not path.startswith("/api/projects/"):
                return _err(self, 404, "not found")

            parts = [unquote(p) for p in path.strip("/").split("/")]
            # api, projects, pid, ...
            if len(parts) < 3:
                return _err(self, 404, "not found")
            pid = parts[2]
            action = parts[3] if len(parts) > 3 else ""

            if action == "" and method == "PATCH":
                if not STORE.load(pid):
                    return _err(self, 404, "project not found")
                patch_project(STORE, pid, body)
                return _json(self, 200, STORE.bundle(pid))

            if action == "script-brief" and method == "POST":
                return _json(self, 200, optimize_brief(STORE, body))

            if action == "script" and method == "POST":
                op = body.get("action") or "generate"
                if op == "generate":
                    state = generate_script(
                        STORE, pid, body.get("episodeCount") or body.get("count") or 1, body.get("plannedEpisodes")
                    )
                elif op == "continue":
                    state = continue_script(
                        STORE,
                        pid,
                        body.get("episodeCount") or 1,
                        body.get("instruction") or "",
                        body.get("brief") or "",
                        bool(body.get("asFinale")),
                    )
                elif op == "rewrite":
                    state = rewrite_script(
                        STORE,
                        pid,
                        body.get("startEpisode") or body.get("start") or 1,
                        body.get("episodeCount") or 1,
                        body.get("instruction") or "",
                    )
                else:
                    return _err(self, 400, "unknown script action")
                return _json(self, 200, STORE.bundle(pid))

            if action == "episodes" and method == "PATCH":
                if body.get("episodeId"):
                    ep = patch_episode(STORE, pid, body["episodeId"], body)
                    return _json(self, 200, ep)
                if body.get("status") and body.get("episodeIds"):
                    set_episode_status(STORE, pid, body["episodeIds"], body["status"])
                    return _json(self, 200, STORE.bundle(pid))
                return _err(self, 400, "episodeId or episodeIds+status required")

            if action == "entities":
                if method == "POST":
                    if body.get("action") == "generate":
                        ver = generate_entity_image(
                            STORE,
                            pid,
                            body.get("entityId") or body.get("id"),
                            three_view=bool(body.get("threeView")),
                            redraw=bool(body.get("redraw")),
                        )
                        return _json(self, 200, {"image": ver, "bundle": STORE.bundle(pid)})
                    if body.get("action") == "batch":
                        ids = body.get("entityIds") or []
                        results = []
                        for eid in ids:
                            try:
                                results.append(
                                    generate_entity_image(
                                        STORE, pid, eid, three_view=bool(body.get("threeView"))
                                    )
                                )
                            except Exception as exc:
                                results.append({"entityId": eid, "error": str(exc)})
                        return _json(self, 200, {"results": results, "bundle": STORE.bundle(pid)})
                    if body.get("action") == "select":
                        select_entity_image(STORE, pid, body["entityId"], body["imageId"])
                        return _json(self, 200, STORE.bundle(pid))
                    if body.get("action") == "upload":
                        raw_b64 = body.get("dataUrl") or ""
                        if "," in raw_b64:
                            header, b64 = raw_b64.split(",", 1)
                            ext = "png"
                            if "jpeg" in header or "jpg" in header:
                                ext = "jpg"
                            elif "webp" in header:
                                ext = "webp"
                        else:
                            b64 = raw_b64
                            ext = body.get("ext") or "png"
                        ver = upload_entity_image(STORE, pid, body["entityId"], base64.b64decode(b64), ext)
                        return _json(self, 200, {"image": ver, "bundle": STORE.bundle(pid)})
                    ent = upsert_entity(STORE, pid, body)
                    return _json(self, 200, {"entity": ent, "bundle": STORE.bundle(pid)})
                if method == "PATCH":
                    ent = upsert_entity(STORE, pid, {**body, "id": body.get("entityId") or body.get("id")})
                    return _json(self, 200, {"entity": ent, "bundle": STORE.bundle(pid)})

            if action == "storyboard" and method == "POST":
                op = body.get("action") or "generate"
                if op == "generate":
                    shots = generate_storyboard(STORE, pid, body["episodeId"])
                    return _json(self, 200, {"shots": shots, "bundle": STORE.bundle(pid)})
                if op == "patch":
                    shot = patch_shot(STORE, pid, body["shotId"], body.get("patch") or body)
                    return _json(self, 200, {"shot": shot, "bundle": STORE.bundle(pid)})
                if op == "video":
                    shot = start_shot_video(
                        STORE,
                        pid,
                        body["shotId"],
                        model=body.get("model") or SEEDANCE_MODELS[0]["id"],
                        resolution=body.get("resolution") or "720p",
                    )
                    return _json(self, 200, {"shot": shot, "bundle": STORE.bundle(pid)})
                if op == "batch-video":
                    ids = body.get("shotIds") or []
                    started = []
                    for sid in ids:
                        try:
                            started.append(
                                start_shot_video(
                                    STORE,
                                    pid,
                                    sid,
                                    model=body.get("model") or SEEDANCE_MODELS[0]["id"],
                                    resolution=body.get("resolution") or "720p",
                                )
                            )
                        except Exception as exc:
                            started.append({"shotId": sid, "error": str(exc)})
                    return _json(self, 200, {"started": started, "bundle": STORE.bundle(pid)})
                if op == "select-take":
                    select_take(STORE, pid, body["shotId"], body["videoId"])
                    return _json(self, 200, STORE.bundle(pid))
                if op == "patch-take":
                    ver = patch_take(STORE, pid, body["shotId"], body["videoId"], body)
                    return _json(self, 200, {"video": ver, "bundle": STORE.bundle(pid)})
                return _err(self, 400, "unknown storyboard action")

            if action == "edits" and method == "POST":
                op = body.get("action") or "ensure"
                episode_id = body.get("episodeId")
                if not episode_id:
                    return _err(self, 400, "episodeId required")
                if op == "ensure":
                    edit = ensure_edit_draft(STORE, pid, episode_id)
                    return _json(self, 200, {"edit": edit, "bundle": STORE.bundle(pid)})
                if op == "save":
                    edit = save_edit(STORE, pid, episode_id, body.get("clips") or [])
                    return _json(self, 200, {"edit": edit, "bundle": STORE.bundle(pid)})
                if op == "export":
                    result = export_edit_mp4(STORE, pid, episode_id)
                    return _json(self, 200, {**result, "bundle": STORE.bundle(pid)})
                return _err(self, 400, "unknown edit action")

            # legacy aliases used by older UI bits
            if action == "generate" and method == "POST":
                # no-op redirect message
                return _err(self, 400, "use /api/projects/:id/storyboard with action=batch-video")

            return _err(self, 404, "not found")
        except FileNotFoundError as exc:
            return _err(self, 404, str(exc))
        except ValueError as exc:
            return _err(self, 400, str(exc))
        except Exception as exc:
            return _err(self, 500, str(exc))


def main() -> None:
    PROJECTS_ROOT.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(
        f"Drama Studio on http://{HOST}:{PORT} (projects={PROJECTS_ROOT}, dist={DIST_DIR.is_dir()}, ffmpeg={ffmpeg_available()})",
        flush=True,
    )
    server.serve_forever()


if __name__ == "__main__":
    main()
