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
from platform_config import default_genre, public_platform_payload, seedance_models  # noqa: E402
from providers import provider_status  # noqa: E402
from settings_store import load_and_apply, public_status, save_secrets  # noqa: E402
from store import ProjectStore  # noqa: E402

PROJECTS_ROOT = Path(os.environ.get("PROJECTS_ROOT", str(ROOT / "projects"))).resolve()
DIST_DIR = Path(os.environ.get("STUDIO_DIST", str(Path(__file__).resolve().parents[1] / "dist"))).resolve()
HOST = os.environ.get("HOST", os.environ.get("STUDIO_HOST", "0.0.0.0"))
PORT = int(os.environ.get("PORT", os.environ.get("STUDIO_API_PORT", "8787")))
SKILLS_ROOT = Path(__file__).resolve().parents[1] / "skills"

STORE = ProjectStore(PROJECTS_ROOT)
load_and_apply(PROJECTS_ROOT)
SEEDANCE_MODELS = seedance_models()

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
        "keys": public_status(),
    }


@app.get("/api/settings/keys")
def get_keys() -> dict[str, Any]:
    return {"keys": public_status(), "capabilities": _providers_payload()}


@app.post("/api/settings/keys")
async def post_keys(request: Request) -> dict[str, Any]:
    body = await request.json()
    status = save_secrets(PROJECTS_ROOT, body if isinstance(body, dict) else {})
    return {"ok": True, "keys": status, "capabilities": _providers_payload()}


@app.post("/api/settings/keys/import-env")
def import_keys_from_env() -> dict[str, Any]:
    """Copy process env (Coolify / Docker) into the secrets file if values exist."""
    payload: dict[str, str] = {}
    for key in (
        "DEEPSEEK_API_KEY",
        "DEEPSEEK_BASE_URL",
        "DEEPSEEK_MODEL",
        "VOLCENGINE_API_KEY",
        "ARK_API_KEY",
        "SEEDREAM_MODEL",
        "SEEDANCE_MODEL",
    ):
        val = (os.environ.get(key) or "").strip()
        if val:
            payload[key] = val
    if not payload.get("DEEPSEEK_API_KEY") and not payload.get("VOLCENGINE_API_KEY") and not payload.get("ARK_API_KEY"):
        return {
            "ok": False,
            "imported": [],
            "keys": public_status(),
            "capabilities": _providers_payload(),
            "error": "服务器环境变量里没有可用的 DeepSeek / 火山 Key，无法自动导入。请在本页粘贴，或写入 Coolify 环境变量后重启。",
        }
    status = save_secrets(PROJECTS_ROOT, payload)
    return {
        "ok": True,
        "imported": sorted(payload.keys()),
        "keys": status,
        "capabilities": _providers_payload(),
    }


@app.post("/api/settings/keys/test")
async def test_keys() -> dict[str, Any]:
    results: dict[str, Any] = {"deepseek": None, "volcengine": None}
    if provider_status().get("deepseek"):
        try:
            from providers.deepseek import chat_json

            data = chat_json(
                system="只输出 JSON。",
                user='返回 {"ok": true}',
                temperature=0,
                max_tokens=32,
            )
            results["deepseek"] = {"ok": True, "sample": data}
        except Exception as exc:
            results["deepseek"] = {"ok": False, "error": str(exc)}
    else:
        results["deepseek"] = {"ok": False, "error": "未配置 DEEPSEEK_API_KEY"}
    results["volcengine"] = {
        "ok": bool(provider_status().get("volcengine")),
        "error": None if provider_status().get("volcengine") else "未配置 VOLCENGINE_API_KEY / ARK_API_KEY",
        "note": "火山 Key 已写入进程；图片/视频任务会在实际出图出片时校验。",
    }
    return {"results": results, "keys": public_status()}


@app.get("/api/platform/assets")
def platform_assets() -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for project in STORE.list_items():
        pid = project["id"]
        root = STORE._dir(pid)
        media = root / "media"
        if not media.is_dir():
            continue
        for path in sorted(media.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp", ".mp4", ".svg", ".wav", ".mp3"}:
                continue
            rel = path.relative_to(root).as_posix()
            items.append(
                {
                    "projectId": pid,
                    "projectTitle": project.get("title") or pid,
                    "path": rel,
                    "url": f"/api/media/{pid}/{rel}",
                    "kind": "video" if path.suffix.lower() == ".mp4" else "audio" if path.suffix.lower() in {".wav", ".mp3"} else "image",
                    "size": path.stat().st_size,
                    "updatedAt": path.stat().st_mtime,
                }
            )
    items.sort(key=lambda x: x["updatedAt"], reverse=True)
    return {"assets": items[:500], "total": len(items)}


@app.get("/api/platform/skills")
def platform_skills() -> dict[str, Any]:
    skills = []
    if SKILLS_ROOT.is_dir():
        for skill_dir in sorted(SKILLS_ROOT.iterdir()):
            md = skill_dir / "SKILL.md"
            if not md.is_file():
                continue
            text = md.read_text(encoding="utf-8")
            title = skill_dir.name
            summary = ""
            for line in text.splitlines():
                if line.startswith("# "):
                    title = line[2:].strip() or title
                elif line.strip() and not line.startswith("---") and not line.startswith("#"):
                    summary = line.strip()
                    break
            skills.append(
                {
                    "id": skill_dir.name,
                    "title": title,
                    "summary": summary[:180],
                    "path": str(md.relative_to(SKILLS_ROOT.parent)),
                    "content": text,
                }
            )
    return {"skills": skills}


@app.get("/api/platform/exports")
def platform_exports() -> dict[str, Any]:
    exports = []
    for project in STORE.list_items():
        pid = project["id"]
        bundle = STORE.bundle(pid) or {}
        root = STORE._dir(pid)
        for edit in bundle.get("edits") or []:
            output_path = edit.get("outputPath") or ""
            output_url = edit.get("outputUrl") or ""
            if not output_url and not output_path:
                continue
            filename = Path(output_path).name if output_path else (output_url.rsplit("/", 1)[-1] or "export.mp4")
            if not output_url and output_path:
                # Prefer media API path when relative under project root
                try:
                    rel = Path(output_path)
                    if not rel.is_absolute():
                        output_url = f"/api/media/{pid}/{rel.as_posix()}"
                    elif Path(output_path).is_relative_to(root):
                        output_url = f"/api/media/{pid}/{Path(output_path).relative_to(root).as_posix()}"
                except Exception:
                    output_url = output_path
            exports.append(
                {
                    "projectId": pid,
                    "projectTitle": (bundle.get("project") or {}).get("title") or pid,
                    "episodeId": edit.get("episodeId"),
                    "filename": filename,
                    "url": output_url,
                    "outputUrl": output_url,
                    "outputPath": output_path,
                    "updatedAt": edit.get("updatedAt"),
                }
            )
        # Also scan media/exports folder for orphaned mp4s
        media = root / "media"
        if media.is_dir():
            for path in sorted(media.rglob("*.mp4")):
                rel = path.relative_to(root).as_posix()
                url = f"/api/media/{pid}/{rel}"
                if any(e.get("url") == url for e in exports):
                    continue
                exports.append(
                    {
                        "projectId": pid,
                        "projectTitle": project.get("title") or pid,
                        "episodeId": None,
                        "filename": path.name,
                        "url": url,
                        "outputUrl": url,
                        "outputPath": rel,
                        "updatedAt": path.stat().st_mtime,
                    }
                )
    exports.sort(key=lambda x: x.get("updatedAt") or "", reverse=True)
    return {"exports": exports, "items": exports}


@app.get("/api/config")
def config() -> dict[str, Any]:
    payload = public_platform_payload()
    payload["styles"] = load_styles()
    payload["capabilities"] = _providers_payload()
    return payload


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
        genre=body.get("genre") or default_genre(),
        visual_style=body.get("visualStyle") or body.get("visual_style") or "",
        ratio=body.get("ratio") or body.get("aspect_ratio") or None,
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
            model=body.get("model") or (SEEDANCE_MODELS[0]["id"] if SEEDANCE_MODELS else ""),
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
                        model=body.get("model") or (SEEDANCE_MODELS[0]["id"] if SEEDANCE_MODELS else ""),
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
