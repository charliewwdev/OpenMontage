#!/usr/bin/env python3
"""OpenMontage Drama Studio — FastAPI backend + static UI."""

from __future__ import annotations

import base64
import mimetypes
import os
import sys
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(os.environ.get("OPENMONTAGE_ROOT", Path(__file__).resolve().parents[2])).resolve()
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from drama_service import (  # noqa: E402
    add_shot,
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
    soft_delete_shot,
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

app = FastAPI(title="OpenMontage Drama Studio", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


def _http_error(status: int, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail=message)


@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail
    if isinstance(detail, dict):
        return JSONResponse(status_code=exc.status_code, content=detail)
    return JSONResponse(status_code=exc.status_code, content={"error": str(detail)})


@app.exception_handler(FileNotFoundError)
async def not_found_handler(_: Request, exc: FileNotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"error": str(exc)})


@app.exception_handler(ValueError)
async def bad_request_handler(_: Request, exc: ValueError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"error": str(exc)})


@app.exception_handler(Exception)
async def unhandled_handler(_: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=500, content={"error": str(exc)})


def _providers_payload() -> dict[str, Any]:
    status = provider_status()
    configured = sum(1 for v in status.values() if v)
    return {
        **status,
        "ffmpeg": ffmpeg_available(),
        "configured": configured,
        "total": 3,
        "mode": "online" if any(status.values()) else "offline-bootstrap",
    }


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "service": "openmontage-drama-studio",
        "framework": "fastapi",
        "root": str(ROOT),
        "projects_root": str(PROJECTS_ROOT),
        "dist": DIST_DIR.is_dir(),
        "ffmpeg": ffmpeg_available(),
        "providers": provider_status(),
    }


@app.get("/api/config")
def config() -> dict[str, Any]:
    return {
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
        "capabilities": _providers_payload(),
        "six_steps": [
            {"id": "script", "label": "剧本"},
            {"id": "character", "label": "角色"},
            {"id": "scene", "label": "场景"},
            {"id": "prop", "label": "道具"},
            {"id": "storyboard", "label": "分镜"},
            {"id": "edit", "label": "剪辑"},
        ],
    }


@app.get("/api/projects")
def list_projects() -> dict[str, Any]:
    return {"projects": STORE.list_items()}


@app.post("/api/projects", status_code=201)
async def create_project(request: Request) -> dict[str, Any]:
    body = await request.json()
    title = (body.get("title") or "").strip()
    if not title:
        raise _http_error(400, "title required")
    state = STORE.create_project(
        title=title,
        brief=body.get("brief") or body.get("source_text") or "",
        genre=body.get("genre") or GENRES[0],
        visual_style=body.get("visualStyle") or body.get("visual_style") or "",
        ratio=body.get("ratio") or body.get("aspect_ratio") or "9:16",
        name=body.get("name"),
    )
    return STORE.bundle(state["project"]["id"])


@app.get("/api/projects/{project_id}")
def get_project(project_id: str) -> dict[str, Any]:
    bundle = STORE.bundle(unquote(project_id))
    if not bundle:
        raise _http_error(404, "project not found")
    return bundle


@app.patch("/api/projects/{project_id}")
async def update_project(project_id: str, request: Request) -> dict[str, Any]:
    pid = unquote(project_id)
    if not STORE.load(pid):
        raise _http_error(404, "project not found")
    body = await request.json()
    patch_project(STORE, pid, body)
    return STORE.bundle(pid)


@app.delete("/api/projects/{project_id}")
def delete_project(project_id: str) -> dict[str, Any]:
    pid = unquote(project_id)
    if not STORE.delete(pid):
        raise _http_error(404, "project not found")
    return {"ok": True, "deleted": pid}


@app.post("/api/script-brief")
async def script_brief_global(request: Request) -> dict[str, Any]:
    body = await request.json()
    return optimize_brief(STORE, body)


@app.post("/api/projects/{project_id}/script-brief")
async def script_brief_project(project_id: str, request: Request) -> dict[str, Any]:
    body = await request.json()
    return optimize_brief(STORE, body)


@app.post("/api/projects/{project_id}/script")
async def script_actions(project_id: str, request: Request) -> dict[str, Any]:
    pid = unquote(project_id)
    body = await request.json()
    op = body.get("action") or "generate"
    if op == "generate":
        generate_script(
            STORE,
            pid,
            body.get("episodeCount") or body.get("count") or 1,
            body.get("plannedEpisodes"),
        )
    elif op == "continue":
        continue_script(
            STORE,
            pid,
            body.get("episodeCount") or 1,
            body.get("instruction") or "",
            body.get("brief") or "",
            bool(body.get("asFinale")),
        )
    elif op == "rewrite":
        rewrite_script(
            STORE,
            pid,
            body.get("startEpisode") or body.get("start") or 1,
            body.get("episodeCount") or 1,
            body.get("instruction") or "",
        )
    else:
        raise _http_error(400, "unknown script action")
    return STORE.bundle(pid)


@app.patch("/api/projects/{project_id}/episodes")
async def episode_actions(project_id: str, request: Request) -> dict[str, Any]:
    pid = unquote(project_id)
    body = await request.json()
    if body.get("episodeId"):
        return patch_episode(STORE, pid, body["episodeId"], body)
    if body.get("status") and body.get("episodeIds"):
        set_episode_status(STORE, pid, body["episodeIds"], body["status"])
        return STORE.bundle(pid)
    raise _http_error(400, "episodeId or episodeIds+status required")


@app.post("/api/projects/{project_id}/entities")
async def entities_post(project_id: str, request: Request) -> dict[str, Any]:
    pid = unquote(project_id)
    body = await request.json()
    action = body.get("action")
    if action == "generate":
        ver = generate_entity_image(
            STORE,
            pid,
            body.get("entityId") or body.get("id"),
            three_view=bool(body.get("threeView")),
            redraw=bool(body.get("redraw")),
        )
        return {"image": ver, "bundle": STORE.bundle(pid)}
    if action == "batch":
        ids = body.get("entityIds") or []
        results = []
        for eid in ids:
            try:
                results.append(generate_entity_image(STORE, pid, eid, three_view=bool(body.get("threeView"))))
            except Exception as exc:
                results.append({"entityId": eid, "error": str(exc)})
        return {"results": results, "bundle": STORE.bundle(pid)}
    if action == "select":
        select_entity_image(STORE, pid, body["entityId"], body["imageId"])
        return STORE.bundle(pid)
    if action == "upload":
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
        return {"image": ver, "bundle": STORE.bundle(pid)}
    ent = upsert_entity(STORE, pid, body)
    return {"entity": ent, "bundle": STORE.bundle(pid)}


@app.patch("/api/projects/{project_id}/entities")
async def entities_patch(project_id: str, request: Request) -> dict[str, Any]:
    pid = unquote(project_id)
    body = await request.json()
    ent = upsert_entity(STORE, pid, {**body, "id": body.get("entityId") or body.get("id")})
    return {"entity": ent, "bundle": STORE.bundle(pid)}


@app.delete("/api/projects/{project_id}/entities")
def entities_delete(project_id: str, entityId: str | None = Query(default=None)) -> dict[str, Any]:
    pid = unquote(project_id)
    if not entityId:
        raise _http_error(400, "entityId required")
    state = soft_delete_entity(STORE, pid, entityId)
    return STORE.bundle(pid) or state


@app.post("/api/projects/{project_id}/storyboard")
async def storyboard_actions(project_id: str, request: Request) -> dict[str, Any]:
    pid = unquote(project_id)
    body = await request.json()
    op = body.get("action") or "generate"
    if op == "generate":
        shots = generate_storyboard(STORE, pid, body["episodeId"])
        return {"shots": shots, "bundle": STORE.bundle(pid)}
    if op == "add":
        shot = add_shot(STORE, pid, body["episodeId"])
        return {"shot": shot, "bundle": STORE.bundle(pid)}
    if op == "delete":
        soft_delete_shot(STORE, pid, body["shotId"])
        return STORE.bundle(pid)
    if op == "patch":
        shot = patch_shot(STORE, pid, body["shotId"], body.get("patch") or body)
        return {"shot": shot, "bundle": STORE.bundle(pid)}
    if op == "video":
        shot = start_shot_video(
            STORE,
            pid,
            body["shotId"],
            model=body.get("model") or SEEDANCE_MODELS[0]["id"],
            resolution=body.get("resolution") or "720p",
        )
        return {"shot": shot, "bundle": STORE.bundle(pid)}
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
        return {"started": started, "bundle": STORE.bundle(pid)}
    if op == "select-take":
        select_take(STORE, pid, body["shotId"], body["videoId"])
        return STORE.bundle(pid)
    if op == "patch-take":
        ver = patch_take(STORE, pid, body["shotId"], body["videoId"], body)
        return {"video": ver, "bundle": STORE.bundle(pid)}
    raise _http_error(400, "unknown storyboard action")


@app.post("/api/projects/{project_id}/edits")
async def edit_actions(project_id: str, request: Request) -> dict[str, Any]:
    pid = unquote(project_id)
    body = await request.json()
    op = body.get("action") or "ensure"
    episode_id = body.get("episodeId")
    if not episode_id:
        raise _http_error(400, "episodeId required")
    if op == "ensure":
        edit = ensure_edit_draft(STORE, pid, episode_id)
        return {"edit": edit, "bundle": STORE.bundle(pid)}
    if op == "save":
        edit = save_edit(STORE, pid, episode_id, body.get("clips") or [])
        return {"edit": edit, "bundle": STORE.bundle(pid)}
    if op == "export":
        result = export_edit_mp4(STORE, pid, episode_id)
        return {**result, "bundle": STORE.bundle(pid)}
    raise _http_error(400, "unknown edit action")


@app.get("/api/projects/{project_id}/shots/{shot_id}")
def get_shot(project_id: str, shot_id: str) -> dict[str, Any]:
    return poll_shot(STORE, unquote(project_id), unquote(shot_id))


@app.get("/api/media/{project_id}/{media_path:path}")
def media_file(project_id: str, media_path: str) -> FileResponse:
    name = unquote(project_id)
    rel = unquote(media_path)
    project = STORE._dir(name)
    if not project or not project.is_dir():
        raise _http_error(404, "project not found")
    if ".." in Path(rel).parts:
        raise _http_error(400, "invalid path")
    file_path = (project / rel).resolve()
    if not str(file_path).startswith(str(project.resolve())) or not file_path.is_file():
        raise _http_error(404, "file not found")
    ctype = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
    if file_path.suffix.lower() == ".svg":
        ctype = "image/svg+xml"
    return FileResponse(file_path, media_type=ctype, headers={"Cache-Control": "public, max-age=60"})


@app.post("/api/projects/{project_id}/generate")
async def legacy_generate(project_id: str) -> None:
    raise _http_error(400, "use /api/projects/:id/storyboard with action=batch-video")


def _mount_ui() -> None:
    if not DIST_DIR.is_dir():
        return

    assets = DIST_DIR / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets)), name="assets")

    index = DIST_DIR / "index.html"

    @app.get("/")
    async def spa_index() -> FileResponse:
        if not index.is_file():
            raise _http_error(404, "UI not built; run npm run build in studio/")
        return FileResponse(index, headers={"Cache-Control": "no-cache"})

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str) -> FileResponse:
        if full_path.startswith("api/"):
            raise _http_error(404, "not found")
        candidate = (DIST_DIR / full_path).resolve()
        if str(candidate).startswith(str(DIST_DIR.resolve())) and candidate.is_file():
            return FileResponse(candidate)
        if not index.is_file():
            raise _http_error(404, "UI not built; run npm run build in studio/")
        return FileResponse(index, headers={"Cache-Control": "no-cache"})


_mount_ui()


def main() -> None:
    import uvicorn

    PROJECTS_ROOT.mkdir(parents=True, exist_ok=True)
    print(
        f"Drama Studio (FastAPI) on http://{HOST}:{PORT} "
        f"(projects={PROJECTS_ROOT}, dist={DIST_DIR.is_dir()}, ffmpeg={ffmpeg_available()})",
        flush=True,
    )
    uvicorn.run(
        "app:app",
        host=HOST,
        port=PORT,
        factory=False,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    # When launched as `python3 studio/server/app.py`, module name is `__main__`.
    import uvicorn

    PROJECTS_ROOT.mkdir(parents=True, exist_ok=True)
    print(
        f"Drama Studio (FastAPI) on http://{HOST}:{PORT} "
        f"(projects={PROJECTS_ROOT}, dist={DIST_DIR.is_dir()}, ffmpeg={ffmpeg_available()})",
        flush=True,
    )
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")
