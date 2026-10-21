#!/usr/bin/env python3
"""OpenMontage Drama Studio — FastAPI backend + static UI."""

from __future__ import annotations

import base64
import json
import mimetypes
import os
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.websockets import WebSocketState

ROOT = Path(os.environ.get("OPENMONTAGE_ROOT", Path(__file__).resolve().parents[2])).resolve()
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from drama_service import (  # noqa: E402
    EntityQaBlockedError,
    add_shot,
    bind_episode_refs,
    continue_script,
    effective_segment_video_prompt,
    ensure_edit_draft,
    export_edit_mp4,
    fill_entity_stills,
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
    preview_entity_prompt,
    recheck_entity_qa,
    recheck_video_qa,
    rewrite_script,
    save_edit,
    select_entity_image,
    select_take,
    set_episode_status,
    soft_delete_entity,
    soft_delete_shot,
    cancel_shot_video,
    migrate_episode_segments,
    revise_segment,
    start_segment_video,
    start_shot_video,
    punch_entity_image_alpha,
    upload_entity_image,
    upsert_entity,
)
import auth_proxy  # noqa: E402
import demo_auth  # noqa: E402
from export_mp4 import ffmpeg_available  # noqa: E402
from platform_config import (  # noqa: E402
    default_genre,
    demo_auth_config,
    load_platform_config,
    public_platform_payload,
    seedance_models,
)
import asset_library as assetlib  # noqa: E402
from pinterest_feed import fetch_pins, fetch_remote_image  # noqa: E402
import inspire_store  # noqa: E402
from providers import provider_status  # noqa: E402
from settings_store import load_and_apply, public_status, save_secrets  # noqa: E402
from store import ProjectStore, ensure_seed_projects  # noqa: E402
from usage_store import init_usage, query_usage, seed_demo_if_empty  # noqa: E402
from credits_store import (  # noqa: E402
    complete_challenge,
    init_credits,
    load_credits,
    record_referral,
)
from script_parse import dialogue_from_episode, dialogue_lines_for_episode, extract_text, guess_title  # noqa: E402
from audio_tts import generate_bgm_mp3, synthesize_dialogue_mp3, synthesize_mp3  # noqa: E402
from auth_context import current_user_id, set_current_user  # noqa: E402
from auto_produce import (  # noqa: E402
    cancel_auto_produce,
    ensure_auto_produce_worker,
    get_job as get_auto_produce_job,
    start_auto_produce,
)

PROJECTS_ROOT = Path(os.environ.get("PROJECTS_ROOT", str(ROOT / "projects"))).resolve()
DIST_DIR = Path(os.environ.get("STUDIO_DIST", str(Path(__file__).resolve().parents[1] / "dist"))).resolve()
HOST = os.environ.get("HOST", os.environ.get("STUDIO_HOST", "0.0.0.0"))
PORT = int(os.environ.get("PORT", os.environ.get("STUDIO_API_PORT", "8787")))
SKILLS_ROOT = Path(__file__).resolve().parents[1] / "skills"
SEED_ROOT = Path(__file__).resolve().parents[1] / "seed"
COMMUNITY_SKILLS = PROJECTS_ROOT / ".community_skills.json"
PUBLIC_URL = (os.environ.get("STUDIO_PUBLIC_URL") or "").rstrip("/")
CORS_ORIGINS = [
    o.strip()
    for o in (os.environ.get("STUDIO_CORS_ORIGINS") or PUBLIC_URL or "*").split(",")
    if o.strip()
]
AUTH_PUBLIC_PREFIXES = (
    "/api/health",
    "/api/config",
    "/api/auth/",
    "/api/media/",  # <img>/<video>/<audio> cannot send Bearer
    "/assets/",
    "/favicon",
    "/maintenance",
)
# Browse without login (mutations on these prefixes still require auth).
AUTH_PUBLIC_GET_PREFIXES = (
    "/api/inspire/",
    "/api/portrait-match/",  # templates + sample assets; create/generate still need login
    "/api/platform/skills",
    "/api/platform/assets",
    "/api/platform/prompts",
    "/api/platform/exports",
    "/api/projects",
    "/api/settings/keys",  # public status only; POST still gated for anon writes
    "/api/settings/usage",  # browse usage charts anonymously
    "/api/settings/credits",  # browse credit packages; mutations still gated
)
AUTH_PUBLIC_EXACT = {
    "/",
    "/api/config",
    "/api/health",
    "/index.html",
    "/maintenance.html",
    "/favicon.svg",
    "/favicon.ico",
    # Anonymous referral capture from ?ref= (no login yet).
    "/api/settings/credits/referral",
}
OPS_TOKEN_HEADER = "x-studio-ops-token"


def _ops_token_expected() -> str:
    return (
        (os.environ.get("STUDIO_OPS_TOKEN") or "").strip()
        or (os.environ.get("STUDIO_DEMO_SECRET") or "").strip()
        or "openmontage-demo-local"
    )


def _ops_token_ok(request: Request) -> bool:
    got = (request.headers.get(OPS_TOKEN_HEADER) or request.headers.get("X-Studio-Ops-Token") or "").strip()
    expected = _ops_token_expected()
    return bool(got and expected and got == expected)

# Postgres: schema → merge ALL disk history into PG first → then hydrate caches.
# Order matters: never switch readers to PG-primary before disk→PG merge finishes.
try:
    import pg_backend as _pg_backend

    if _pg_backend.enabled():
        ok = _pg_backend.init_schema()
        if ok:
            # 1) Disk → PG (merge, never drop disk-only history)
            migrated = _pg_backend.migrate_disk_projects_to_pg(PROJECTS_ROOT)
            media_up = _pg_backend.migrate_disk_media_to_pg(PROJECTS_ROOT)
            kv_migrated = _pg_backend.migrate_disk_state_to_pg(PROJECTS_ROOT)
            # 2) PG → disk cache for ffmpeg / local tooling
            hydrated = _pg_backend.hydrate_projects_to_disk(PROJECTS_ROOT)
            media_down = _pg_backend.hydrate_media_to_disk(PROJECTS_ROOT)
            try:
                from platform_config import load_platform_config as _lpc

                _lpc.cache_clear()
            except Exception:
                pass
            try:
                import object_store as _oss

                oss_ping = _oss.ping()
                print(f"[studio] object store {oss_ping}", flush=True)
                if oss_ping.get("ok"):
                    moved = _pg_backend.offload_blobs_to_minio(limit=500)
                    print(f"[studio] minio offload {moved}", flush=True)
            except Exception as _oss_exc:
                print(f"[studio] object store skipped: {_oss_exc}", flush=True)
            print(
                f"[studio] postgres ready projects_hydrated={len(hydrated)} "
                f"projects_migrated={len(migrated)} media_up={media_up} media_down={media_down} "
                f"kv_migrated={kv_migrated}",
                flush=True,
            )
        else:
            print("[studio] postgres configured but schema init failed", flush=True)
except Exception as _pg_exc:
    print(f"[studio] postgres bootstrap skipped: {_pg_exc}", flush=True)

STORE = ProjectStore(PROJECTS_ROOT)


def _auto_produce_sweep_loop() -> None:
    import time

    # First pass soon after boot so version updates resume running jobs quickly.
    time.sleep(3)
    try:
        from auto_produce import resume_after_boot, sweep_auto_produce

        resume_after_boot(STORE)
        sweep_auto_produce(STORE)
    except Exception:
        pass

    while True:
        time.sleep(30)
        try:
            from auto_produce import sweep_auto_produce

            sweep_auto_produce(STORE)
        except Exception:
            pass


threading.Thread(target=_auto_produce_sweep_loop, name="auto-produce-sweep", daemon=True).start()
ensure_seed_projects(PROJECTS_ROOT, SEED_ROOT)
load_and_apply(PROJECTS_ROOT)
init_usage(PROJECTS_ROOT)
init_credits(PROJECTS_ROOT)
seed_demo_if_empty(PROJECTS_ROOT)
SEEDANCE_MODELS = seedance_models()


app = FastAPI(title="OpenMontage Drama Studio", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS if CORS_ORIGINS != ["*"] else ["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


def _bearer_token(request: Request) -> str:
    auth = request.headers.get("authorization") or request.headers.get("Authorization") or ""
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return ""


def _resolve_user(token: str) -> dict[str, Any] | None:
    if not token:
        return None
    if demo_auth.is_demo_token(token):
        status, result = demo_auth.demo_me(token)
        if status == 200 and isinstance(result.get("data"), dict):
            return result["data"]
        return None
    status, result = auth_proxy.me(token)
    if status == 200 and isinstance(result.get("data"), dict):
        data = result["data"]
        return {
            "id": data.get("id") or data.get("userId"),
            "userId": data.get("userId") or data.get("id"),
            "username": data.get("username") or data.get("nickname") or "user",
            "avatar": data.get("avatar") or "",
        }
    return None


def _path_is_public(path: str, method: str = "GET") -> bool:
    if path in AUTH_PUBLIC_EXACT:
        return True
    if not path.startswith("/api/"):
        return True
    if any(path.startswith(p) for p in AUTH_PUBLIC_PREFIXES):
        return True
    m = (method or "GET").upper()
    if m in {"GET", "HEAD"} and any(path.startswith(p) for p in AUTH_PUBLIC_GET_PREFIXES):
        return True
    return False


class AuthContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        set_current_user(None)
        path = request.url.path or "/"
        method = request.method.upper()
        token = _bearer_token(request)
        user = _resolve_user(token) if token else None
        if user:
            set_current_user(user)
        auth_required = os.environ.get("STUDIO_AUTH_REQUIRED", "true").strip().lower() not in (
            "0",
            "false",
            "no",
            "off",
        )
        ops_bootstrap = method == "POST" and _ops_token_ok(request) and path in {
            "/api/settings/keys",
            "/api/ops/migrate-disk-to-pg",
        }
        if (
            auth_required
            and path.startswith("/api/")
            and not _path_is_public(path, method)
            and method not in {"OPTIONS", "HEAD"}
            and not user
            and not ops_bootstrap
        ):
            return JSONResponse(status_code=401, content={"error": "login required"})
        try:
            return await call_next(request)
        finally:
            set_current_user(None)


app.add_middleware(AuthContextMiddleware)


def _http_error(status: int, message: str | dict[str, Any]) -> HTTPException:
    return HTTPException(status_code=status, detail=message)


def _entity_qa_blocked_http(exc: EntityQaBlockedError) -> HTTPException:
    return _http_error(
        409,
        {
            "error": str(exc),
            "code": "entity_qa_blocked",
            "blockers": exc.blockers,
            "forceHint": "传入 forceEntityQa=true 可强制出片（仍会使用未过检参考图）",
        },
    )


def _force_entity_qa(body: dict[str, Any]) -> bool:
    return bool(
        body.get("forceEntityQa")
        or body.get("force")
        or body.get("forcePass")
        or body.get("bypassEntityQa")
    )


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
    bools = {k: v for k, v in status.items() if isinstance(v, bool)}
    configured = sum(1 for v in bools.values() if v)
    return {
        **status,
        "ffmpeg": ffmpeg_available(),
        "configured": configured,
        "total": 4,
        "mode": "online" if any(bools.values()) else "offline-bootstrap",
    }


def _object_store_status() -> dict[str, Any]:
    try:
        import object_store as _oss

        return _oss.ping()
    except Exception as exc:
        return {"enabled": False, "error": str(exc)[:120]}


@app.get("/api/health")
def health() -> dict[str, Any]:
    pg_status: dict[str, Any] = {"enabled": False}
    try:
        import pg_backend as _pg_backend

        pg_status = _pg_backend.ping()
    except Exception as exc:
        pg_status = {"enabled": False, "error": str(exc)[:120]}
    queue: dict[str, Any] = {}
    try:
        from job_queue import queue_stats

        queue = queue_stats()
    except Exception as exc:  # noqa: BLE001
        queue = {"error": str(exc)[:120]}
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
        "postgres": pg_status,
        "objectStore": _object_store_status(),
        "mediaQueue": queue,
        "uvicornWorkers": int(os.environ.get("UVICORN_WORKERS") or "1"),
    }


@app.get("/api/settings/keys")
def get_keys(probe: int = 0) -> dict[str, Any]:
    """Public key status. Pass ?probe=1 to live-ping ComfyUI (slower; use before generate)."""
    if not probe:
        return {"keys": public_status(), "capabilities": _providers_payload()}
    # Live probe path: reuse /keys/test Comfy branch so UI gets reachable:true when egress works.
    keys_payload = public_status()
    from settings_store import get_secret

    if get_secret("COMFYUI_SERVER_URL") or get_secret("COMFYUI_IMAGE_SERVER_URL"):
        try:
            from providers.comfyui import list_checkpoints, ping, public_status as comfy_public

            info = ping()
            ckpts = list_checkpoints()
            probed = comfy_public(probe=True)
            keys_payload["comfyui"] = {
                **probed,
                "reachable": True,
                "checkpoints": ckpts[:20] or probed.get("checkpoints") or [],
                "checkpoint": get_secret("COMFYUI_CHECKPOINT")
                or (ckpts[0] if ckpts else "")
                or probed.get("checkpoint")
                or "",
                "deviceName": info.get("deviceName") or probed.get("deviceName") or "",
                "error": "",
                "probedAt": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as exc:  # noqa: BLE001
            comfy = dict(keys_payload.get("comfyui") or {})
            comfy["reachable"] = False
            comfy["error"] = str(exc)[:240]
            keys_payload["comfyui"] = comfy
    return {"keys": keys_payload, "capabilities": _providers_payload()}


@app.post("/api/settings/keys")
async def post_keys(request: Request) -> dict[str, Any]:
    body = await request.json()
    payload = body if isinstance(body, dict) else {}
    # Coolify/ops restore writes shared secrets so all users can fall back before BYOK.
    if _ops_token_ok(request) and not current_user_id():
        status = save_secrets(PROJECTS_ROOT, payload, user_id="")
    else:
        status = save_secrets(PROJECTS_ROOT, payload)
    return {"ok": True, "keys": status, "capabilities": _providers_payload()}


@app.post("/api/settings/keys/import-env")
def import_keys_from_env() -> dict[str, Any]:
    """Optional ops helper: copy process env into secrets store once."""
    from providers.llm_catalog import all_secret_envs

    payload: dict[str, str] = {}
    for key in all_secret_envs():
        val = (os.environ.get(key) or "").strip()
        if val:
            payload[key] = val
    has_llm = any(k.endswith("_API_KEY") and k not in {"VOLCENGINE_API_KEY", "ARK_API_KEY"} for k in payload)
    has_volc = bool(payload.get("VOLCENGINE_API_KEY") or payload.get("ARK_API_KEY"))
    if not has_llm and not has_volc:
        return {
            "ok": False,
            "imported": [],
            "keys": public_status(),
            "capabilities": _providers_payload(),
            "error": "进程环境里没有可用的文本大模型 / 火山 Key。请在本页直接粘贴保存即可（运行时动态读取，不必依赖环境变量）。",
        }
    status = save_secrets(PROJECTS_ROOT, payload)
    return {
        "ok": True,
        "imported": sorted(payload.keys()),
        "keys": status,
        "capabilities": _providers_payload(),
    }


@app.get("/api/ops/stats")
def ops_stats(request: Request) -> dict[str, Any]:
    """Ops: user / project / queue counts (requires ops token)."""
    if not _ops_token_ok(request):
        raise HTTPException(status_code=403, detail="ops token required")
    owners: dict[str, int] = {}
    for p in STORE.list_items():
        oid = str(p.get("ownerId") or "").strip() or "(none)"
        owners[oid] = owners.get(oid, 0) + 1
    kv_users: set[str] = set()
    kv_keys: list[str] = []
    try:
        import pg_backend as _pg

        if _pg.enabled():
            kv_keys = _pg.list_kv_keys()
            for key in kv_keys:
                # secrets:.users/{uid}/secrets.json → ['secrets:.users', '{uid}', 'secrets.json']
                # credits:user:{uid}
                if key.startswith("secrets:.users/"):
                    parts = key.split("/")
                    if len(parts) >= 2 and parts[1]:
                        kv_users.add(parts[1])
                elif key.startswith("credits:user:"):
                    uid = key.split("credits:user:", 1)[-1].strip()
                    if uid:
                        kv_users.add(uid)
    except Exception as exc:  # noqa: BLE001
        kv_keys = []
        kv_err = str(exc)[:120]
    else:
        kv_err = None
    from job_queue import queue_stats

    return {
        "ok": True,
        "projects": sum(owners.values()),
        "owners": owners,
        "ownerCount": len(owners),
        "kvUserCount": len(kv_users),
        "kvUsers": sorted(kv_users),
        "kvKeyCount": len(kv_keys),
        "kvError": kv_err,
        "mediaQueue": queue_stats(),
        "providers": provider_status(),
    }


@app.post("/api/ops/migrate-disk-to-pg")
def ops_migrate_disk_to_pg(request: Request) -> dict[str, Any]:
    """Merge all disk secrets/credits/usage/projects/media into Postgres (ops token)."""
    if not _ops_token_ok(request):
        raise HTTPException(status_code=403, detail="ops token required")
    try:
        import pg_backend as _pg
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"pg backend unavailable: {exc}") from exc
    if not _pg.enabled():
        raise HTTPException(status_code=503, detail="DATABASE_URL not configured")
    if not _pg.init_schema():
        raise HTTPException(status_code=503, detail="schema init failed")
    projects = _pg.migrate_disk_projects_to_pg(PROJECTS_ROOT)
    media = _pg.migrate_disk_media_to_pg(PROJECTS_ROOT)
    kv = _pg.migrate_disk_state_to_pg(PROJECTS_ROOT)
    return {
        "ok": True,
        "projects": projects,
        "media": media,
        "kv": kv,
    }



@app.post("/api/settings/keys/test")
async def test_keys() -> dict[str, Any]:
    results: dict[str, Any] = {
        "llm": None,
        "deepseek": None,
        "cursor": None,
        "volcengine": None,
        "comfyui": None,
    }
    status = provider_status()
    if status.get("llmReady") or status.get("deepseek"):
        try:
            from providers.llm import chat_json

            data = chat_json(
                system="只输出 JSON。",
                user='返回 {"ok": true}',
                temperature=0,
                max_tokens=32,
                retries=1,
            )
            sample = {"ok": True, "sample": data, "backend": status.get("llmBackend")}
            results["llm"] = sample
            results["deepseek"] = sample  # legacy UI field
        except Exception as exc:  # noqa: BLE001
            err = {"ok": False, "error": str(exc)}
            results["llm"] = err
            results["deepseek"] = err
    else:
        err = {"ok": False, "error": "未配置任何文本大模型 API Key"}
        results["llm"] = err
        results["deepseek"] = err
    from settings_store import get_secret

    results["cursor"] = {
        "ok": bool(status.get("cursor")),
        "error": None if status.get("cursor") else "未配置 CURSOR_API_KEY",
        "model": get_secret("CURSOR_MODEL", "auto") or "auto",
    }

    results["volcengine"] = {
        "ok": bool(status.get("volcengine")),
        "error": None if status.get("volcengine") else "未配置 VOLCENGINE_API_KEY / ARK_API_KEY",
        "note": "火山 Key 已写入进程；图片/视频任务会在实际出图出片时校验。",
    }

    if get_secret("COMFYUI_SERVER_URL") or get_secret("COMFYUI_IMAGE_SERVER_URL"):
        try:
            from providers.comfyui import list_checkpoints, ping, public_status as comfy_public

            info = ping()
            ckpts = list_checkpoints()
            probed = comfy_public(probe=True)
            results["comfyui"] = {
                "ok": True,
                **info,
                "checkpoints": ckpts[:20],
                "checkpointCount": len(ckpts),
                "videoModels": probed.get("videoModels") or [],
                "videoReady": bool(probed.get("videoReady")),
                "imageBackend": status.get("imageBackend"),
                "videoBackend": status.get("videoBackend"),
            }
            # Merge live probe into keys payload so UI can show checkpoints / H3 video.
            keys_payload = public_status()
            keys_payload["comfyui"] = {
                **probed,
                "reachable": True,
                "checkpoints": ckpts[:20] or probed.get("checkpoints") or [],
                "checkpoint": get_secret("COMFYUI_CHECKPOINT")
                or (ckpts[0] if ckpts else "")
                or probed.get("checkpoint")
                or "",
                "deviceName": info.get("deviceName") or probed.get("deviceName") or "",
                "error": "",
            }
            keys_payload["videoBackend"] = status.get("videoBackend")
            return {"results": results, "keys": keys_payload}
        except Exception as exc:  # noqa: BLE001
            results["comfyui"] = {"ok": False, "error": str(exc)}
    else:
        results["comfyui"] = {
            "ok": False,
            "error": "未配置 COMFYUI_SERVER_URL（智川云租 GPU 后填写）",
        }
    return {"results": results, "keys": public_status()}


@app.get("/api/settings/usage")
def get_usage(
    range: str = Query("7d"),
    provider: str = Query(""),
    model: str = Query(""),
    kind: str = Query("all"),
    status: str = Query("all"),
    date_from: str = Query(""),
    date_to: str = Query(""),
    log_limit: int = Query(20, ge=1, le=500),
    log_offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    return query_usage(
        range_key=range,
        date_from=date_from,
        date_to=date_to,
        provider=provider,
        model=model,
        kind=kind,
        status=status,
        log_limit=log_limit,
        log_offset=log_offset,
    )


def _parse_out_fraction(detail: str) -> tuple[int, int] | None:
    """Parse『出片 10/64』style counters from step detail."""
    import re

    m = re.search(r"(\d+)\s*/\s*(\d+)", str(detail or ""))
    if not m:
        return None
    done, total = int(m.group(1)), int(m.group(2))
    if total <= 0:
        return None
    return done, total


def _jobs_progress(shots: dict[str, Any], steps: list[dict[str, Any]], detail: str) -> dict[str, Any]:
    total_shots = int(shots.get("total") or 0)
    done_shots = int(shots.get("completed") or 0)
    frac = _parse_out_fraction(detail)
    if frac:
        done_shots = max(done_shots, frac[0])
        total_shots = max(total_shots, frac[1])
    shot_pct = round(100.0 * done_shots / total_shots, 1) if total_shots else 0.0
    step_done = sum(1 for s in steps if s.get("status") in {"done", "skipped"})
    step_total = len(steps) or 1
    step_pct = round(100.0 * step_done / step_total, 1)
    # Blend: pipeline stage weight + in-stage shot progress when on videos.
    on_videos = any(s.get("id") == "videos" and s.get("status") == "running" for s in steps)
    overall = step_pct
    if on_videos and total_shots:
        # videos is one of N steps; fill that slice with shot progress.
        slice_w = 100.0 / step_total
        overall = round(step_done * slice_w + (shot_pct / 100.0) * slice_w, 1)
    return {
        "shotDone": done_shots,
        "shotTotal": total_shots,
        "shotPct": min(100.0, shot_pct),
        "stepDone": step_done,
        "stepTotal": step_total,
        "stepPct": min(100.0, step_pct),
        "overallPct": min(100.0, overall),
    }


def _build_jobs_payload() -> dict[str, Any]:
    """Background media queue + per-project auto-produce jobs (no cron; event-driven)."""
    from job_queue import queue_stats

    queue = queue_stats()
    active_statuses = {"running", "queued", "paused", "failed"}
    auto_jobs: list[dict[str, Any]] = []
    try:
        for item in STORE.list_items():
            job = item.get("autoProduce")
            if not isinstance(job, dict) or not job.get("id"):
                continue
            status = str(job.get("status") or "")
            if status not in active_statuses and status != "done":
                continue
            steps_raw = job.get("steps") or []
            step_detail = ""
            for step in steps_raw:
                if step.get("id") == job.get("step"):
                    step_detail = str(step.get("detail") or "")
                    break
            logs = job.get("logs") or []
            last_log = ""
            if logs:
                last = logs[-1] if isinstance(logs[-1], dict) else {}
                last_log = str(last.get("text") or "")[:160]
            steps = [
                {
                    "id": s.get("id"),
                    "label": s.get("label"),
                    "status": s.get("status"),
                    "detail": s.get("detail") or "",
                }
                for s in steps_raw
            ]
            shots = (item.get("progress") or {}).get("shots") or {}
            detail = step_detail or str(job.get("detail") or "")
            auto_jobs.append(
                {
                    "projectId": item.get("id"),
                    "title": item.get("title") or item.get("id"),
                    "jobId": job.get("id"),
                    "status": status,
                    "step": job.get("step") or "",
                    "detail": detail,
                    "error": job.get("error"),
                    "updatedAt": job.get("updatedAt") or item.get("updatedAt"),
                    "startedAt": job.get("startedAt"),
                    "lastLog": last_log,
                    "steps": steps,
                    "shotProgress": shots,
                    "progress": _jobs_progress(shots, steps, detail),
                }
            )
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "error": str(exc)[:160],
            "mediaQueue": queue,
            "autoProduce": [],
            "note": "无独立 cron；媒体队列 + 一键全流程为后台任务源。",
            "polledAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
    rank = {"running": 0, "queued": 1, "paused": 2, "failed": 3, "done": 4}
    auto_jobs.sort(
        key=lambda j: (rank.get(str(j.get("status")), 9), str(j.get("updatedAt") or "")),
        reverse=False,
    )
    trimmed: list[dict[str, Any]] = []
    done_kept = 0
    for j in auto_jobs:
        if j.get("status") == "done":
            if done_kept >= 8:
                continue
            done_kept += 1
        trimmed.append(j)
    pending = int(queue.get("redisPending") or (queue.get("pool") or {}).get("pending") or 0)
    processing = int(queue.get("redisProcessing") or 0)
    queue_cap = max(pending + processing, 1)
    return {
        "ok": True,
        "mediaQueue": {
            **queue,
            "progress": {
                "pending": pending,
                "processing": processing,
                "loadPct": min(100.0, round(100.0 * (pending + processing) / max(queue_cap, 8), 1)),
            },
        },
        "autoProduce": trimmed,
        "note": "无独立 cron / 定时表；后台任务来自 Redis 媒体队列与项目一键全流程。",
        "polledAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


@app.get("/api/settings/jobs")
def get_jobs() -> dict[str, Any]:
    return _build_jobs_payload()


@app.post("/api/settings/jobs/purge-satisfied-stills")
def purge_satisfied_stills() -> dict[str, Any]:
    """Drop queued entity_image jobs that already have a QA-passed still (no quality drop)."""
    if not current_user_id():
        raise _http_error(401, "login required")
    from job_queue import purge_satisfied_entity_image_jobs, queue_stats

    result = purge_satisfied_entity_image_jobs()
    return {**result, "mediaQueue": queue_stats(), "jobs": _build_jobs_payload()}


@app.post("/api/settings/jobs/purge-project")
async def purge_project_jobs(request: Request) -> dict[str, Any]:
    """Drop queued media jobs for one project (free GPU after pausing auto-produce)."""
    if not current_user_id():
        raise _http_error(401, "login required")
    try:
        body = await request.json()
    except Exception:
        body = {}
    if not isinstance(body, dict):
        body = {}
    pid = str(body.get("projectId") or "").strip()
    if not pid:
        raise _http_error(400, "projectId required")
    _assert_project_access(pid, write=True)
    from job_queue import purge_project_media_jobs, queue_stats

    result = purge_project_media_jobs(
        pid,
        video=body.get("video", True) is not False,
        image=bool(body.get("image")),
    )
    return {**result, "mediaQueue": queue_stats(), "jobs": _build_jobs_payload()}


@app.websocket("/api/settings/jobs/ws")
async def jobs_websocket(websocket: WebSocket) -> None:
    """Push jobs snapshots over WebSocket (~2s). Auth via ?token= (browser WS can't set Bearer)."""
    import asyncio

    token = (websocket.query_params.get("token") or "").strip()
    if not token:
        auth = websocket.headers.get("authorization") or websocket.headers.get("Authorization") or ""
        if auth.lower().startswith("bearer "):
            token = auth[7:].strip()
    user = _resolve_user(token) if token else None
    auth_required = os.environ.get("STUDIO_AUTH_REQUIRED", "true").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )
    if auth_required and not user:
        await websocket.close(code=4401, reason="login required")
        return

    await websocket.accept()
    interval = max(1.0, min(10.0, float(os.environ.get("STUDIO_JOBS_WS_INTERVAL") or "2")))
    set_current_user(user)
    try:
        payload = _build_jobs_payload()
        await websocket.send_json({"type": "snapshot", "data": payload})
        while True:
            try:
                msg = await asyncio.wait_for(websocket.receive_text(), timeout=interval)
            except asyncio.TimeoutError:
                msg = ""
            if websocket.client_state != WebSocketState.CONNECTED:
                break
            if msg:
                try:
                    body = json.loads(msg)
                except Exception:
                    body = {}
                if isinstance(body, dict) and body.get("type") == "ping":
                    await websocket.send_json({"type": "pong", "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")})
                    continue
                if isinstance(body, dict) and body.get("type") == "refresh":
                    pass  # fall through to snapshot
            set_current_user(user)
            payload = _build_jobs_payload()
            await websocket.send_json({"type": "snapshot", "data": payload})
    except WebSocketDisconnect:
        return
    except Exception:
        try:
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.close(code=1011)
        except Exception:
            pass
    finally:
        set_current_user(None)


@app.get("/api/platform/assets")
def platform_assets(

    offset: int = Query(0, ge=0),
    limit: int = Query(60, ge=1, le=200),
    kind: str = Query("all"),
    source: str = Query("all"),
    category: str = Query("all"),
    q: str = Query(""),
    sort: str = Query("latest"),
    health: str = Query("healthy"),
) -> dict[str, Any]:
    pool = assetlib.collect_assets(STORE, PROJECTS_ROOT)
    broken_count = sum(1 for x in pool if x.get("broken"))
    items = assetlib.filter_assets(
        pool, kind=kind, source=source, category=category, q=q, sort=sort, health=health
    )
    total = len(items)
    page = items[offset : offset + limit]
    next_offset = offset + limit if offset + limit < total else None
    return {
        "assets": page,
        "total": total,
        "offset": offset,
        "limit": limit,
        "nextOffset": next_offset,
        "hasMore": next_offset is not None,
        "brokenCount": broken_count,
        "categories": [{"id": i, "label": l} for i, l in assetlib.ASSET_CATEGORIES],
    }


@app.post("/api/platform/assets/upload")
async def platform_assets_upload(request: Request) -> dict[str, Any]:
    """Upload personal reference media into the shared library (有彩-style 个人素材)."""
    body = await request.json()
    data_url = str(body.get("dataUrl") or "")
    filename = str(body.get("filename") or "upload.bin")
    category = str(body.get("category") or "").strip()
    if "," not in data_url:
        raise _http_error(400, "dataUrl required")
    header, b64 = data_url.split(",", 1)
    try:
        raw = base64.b64decode(b64)
    except Exception as exc:  # noqa: BLE001
        raise _http_error(400, f"invalid dataUrl: {exc}") from exc
    if not raw:
        raise _http_error(400, "empty file")
    if len(raw) > 40 * 1024 * 1024:
        raise _http_error(400, "file too large (max 40MB)")
    allowed = assetlib.upload_exts()
    ext = Path(filename).suffix.lower()
    if ext not in allowed:
        mime = ""
        if ";base64" in header and ":" in header:
            mime = header.split(":", 1)[1].split(";", 1)[0].strip().lower()
        ext = {
            "image/png": ".png",
            "image/jpeg": ".jpg",
            "image/webp": ".webp",
            "image/gif": ".gif",
            "image/svg+xml": ".svg",
            "video/mp4": ".mp4",
            "video/webm": ".webm",
            "audio/wav": ".wav",
            "audio/mpeg": ".mp3",
            "application/pdf": ".pdf",
            "text/plain": ".txt",
            "text/markdown": ".md",
        }.get(mime, "")
    if ext not in allowed:
        raise _http_error(400, "unsupported file type")
    root = assetlib.ensure_library_root(PROJECTS_ROOT)
    name = f"{int(time.time())}-{uuid.uuid4().hex[:8]}{ext}"
    dest = root / "media" / "uploads" / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(raw)
    kind = assetlib.asset_kind(ext)
    if kind in {"image", "video", "audio"}:
        from media_qa import MediaQAError, assert_media_ok

        try:
            assert_media_ok(dest, kind=kind, unlink_on_fail=True)
        except MediaQAError as exc:
            raise _http_error(400, f"文件未通过质量检测：{exc}") from exc
    rel = dest.relative_to(root).as_posix()
    cat = category or assetlib.guess_category(rel, kind)
    lib = assetlib.library_id()
    try:
        STORE.persist_media(lib, rel, data=raw)
        # Keep library project row alive so hydrate restores _library on redeploy.
        lib_state = STORE.load(lib)
        if lib_state:
            STORE.save(lib_state)
    except Exception:
        pass
    return {
        "ok": True,
        "asset": {
            "id": f"{lib}:{rel}",
            "projectId": lib,
            "projectTitle": "个人素材库",
            "path": rel,
            "name": name,
            "url": f"/api/media/{lib}/{rel}",
            "kind": kind,
            "category": cat,
            "source": "upload",
            "size": dest.stat().st_size,
            "updatedAt": dest.stat().st_mtime,
            "uploaded": True,
        },
    }


@app.delete("/api/platform/assets")
async def platform_assets_delete(request: Request) -> dict[str, Any]:
    body = await request.json()
    items = body.get("items") if isinstance(body.get("items"), list) else [body]
    deleted = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        ok = assetlib.delete_asset(
            PROJECTS_ROOT,
            STORE,
            str(item.get("projectId") or ""),
            str(item.get("path") or ""),
        )
        if ok:
            deleted += 1
    return {"ok": True, "deleted": deleted}


@app.get("/api/platform/prompts")
def platform_prompts(
    category: str = Query("all"),
    q: str = Query(""),
    sort: str = Query("latest"),
) -> dict[str, Any]:
    items = assetlib.list_prompts(PROJECTS_ROOT, category=category, q=q, sort=sort)
    return {
        "prompts": items,
        "total": len(items),
        "categories": [{"id": i, "label": l} for i, l in assetlib.PROMPT_CATEGORIES],
    }


@app.post("/api/platform/prompts")
async def platform_prompts_upsert(request: Request) -> dict[str, Any]:
    body = await request.json()
    try:
        item = assetlib.upsert_prompt(PROJECTS_ROOT, body if isinstance(body, dict) else {})
    except ValueError as exc:
        raise _http_error(400, str(exc)) from exc
    return {"ok": True, "prompt": item}


@app.delete("/api/platform/prompts/{prompt_id}")
def platform_prompts_delete(prompt_id: str) -> dict[str, Any]:
    ok = assetlib.delete_prompt(PROJECTS_ROOT, unquote(prompt_id))
    if not ok:
        raise _http_error(404, "prompt not found")
    return {"ok": True, "deleted": prompt_id}


def _parse_skill_md(text: str, fallback_id: str) -> dict[str, Any]:
    """Parse SKILL.md with optional YAML frontmatter."""
    title = fallback_id
    summary = ""
    meta: dict[str, Any] = {}
    body = text
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            fm = parts[1]
            body = parts[2].lstrip("\n")
            for raw in fm.splitlines():
                line = raw.strip()
                if not line or ":" not in line:
                    continue
                key, val = line.split(":", 1)
                meta[key.strip()] = val.strip().strip("\"'")
    for line in body.splitlines():
        if line.startswith("# "):
            title = line[2:].strip() or title
            break
    for line in body.splitlines():
        s = line.strip()
        if not s or s.startswith("#") or s.startswith("```") or s.startswith("-"):
            continue
        summary = s
        break
    if meta.get("description") and not summary:
        summary = str(meta["description"])
    if meta.get("name") and title == fallback_id:
        title = str(meta["name"])
    return {"title": title, "summary": summary[:220], "content": text, "meta": meta}


def _skill_experience_payload(skill_id: str) -> dict[str, Any]:
    try:
        from skill_runtime import experience_summary

        return experience_summary(skill_id, PROJECTS_ROOT)
    except Exception as exc:  # noqa: BLE001
        return {"skillId": skill_id, "error": str(exc)[:120], "topFailures": [], "patchCount": 0}


@app.get("/api/platform/skills")
def platform_skills() -> dict[str, Any]:
    cfg = load_platform_config()
    catalog = {str(item.get("id") or ""): item for item in (cfg.get("skillCatalog") or []) if isinstance(item, dict)}
    local: dict[str, dict[str, Any]] = {}
    if SKILLS_ROOT.is_dir():
        for skill_dir in sorted(SKILLS_ROOT.iterdir()):
            md = skill_dir / "SKILL.md"
            if not md.is_file():
                continue
            text = md.read_text(encoding="utf-8")
            parsed = _parse_skill_md(text, skill_dir.name)
            local[skill_dir.name] = {
                "id": skill_dir.name,
                "title": parsed["title"],
                "summary": parsed["summary"],
                "path": str(md.relative_to(SKILLS_ROOT.parent)),
                "content": parsed["content"],
                "builtin": True,
            }
    skills: list[dict[str, Any]] = []
    seen: set[str] = set()
    # Prefer catalog order for official store layout.
    for sid, meta in catalog.items():
        if not sid:
            continue
        base = local.get(sid) or {
            "id": sid,
            "title": sid,
            "summary": "",
            "path": "",
            "content": "",
            "builtin": False,
        }
        prompt = str(meta.get("prompt") or "").strip()
        content = base.get("content") or (
            f"# {meta.get('title') or sid}\n\n{meta.get('summary') or ''}\n\n{prompt}".strip()
        )
        exp = _skill_experience_payload(sid) if sid == "drama-entity-still" or (SKILLS_ROOT / sid).is_dir() else {}
        workshop = meta.get("workshop") if isinstance(meta.get("workshop"), dict) else {}
        skills.append(
            {
                **base,
                "title": meta.get("title") or base.get("title") or sid,
                "summary": meta.get("summary") or base.get("summary") or "",
                "source": meta.get("source") or "official",
                "category": meta.get("category") or "other",
                "tags": list(meta.get("tags") or []),
                "accent": meta.get("accent") or "#7c6cff",
                "prompt": prompt,
                "content": content,
                "slash": f"/{sid}",
                "workshop": workshop,
                "experience": {
                    "patchCount": exp.get("patchCount") or 0,
                    "learnedCount": exp.get("learnedCount") or 0,
                    "totalHits": exp.get("totalHits") or 0,
                    "topFailures": exp.get("topFailures") or [],
                },
            }
        )
        seen.add(sid)
    for sid, item in local.items():
        if sid in seen:
            continue
        exp = _skill_experience_payload(sid)
        skills.append(
            {
                **item,
                "source": "official",
                "category": "film",
                "tags": ["短剧漫剧"],
                "accent": "#7c6cff",
                "prompt": "",
                "slash": f"/{sid}",
                "experience": {
                    "patchCount": exp.get("patchCount") or 0,
                    "learnedCount": exp.get("learnedCount") or 0,
                    "totalHits": exp.get("totalHits") or 0,
                    "topFailures": exp.get("topFailures") or [],
                },
            }
        )
    # Merge community posts (Postgres + disk cache)
    try:
        import community_skills as _cskills

        for item in _cskills.load_community_skills(PROJECTS_ROOT):
            if not isinstance(item, dict) or not item.get("id"):
                continue
            if item["id"] in seen:
                continue
            skills.append(
                {
                    "id": item["id"],
                    "title": item.get("title") or item["id"],
                    "summary": item.get("summary") or "",
                    "path": "",
                    "content": item.get("content") or item.get("prompt") or "",
                    "builtin": False,
                    "source": "community",
                    "category": item.get("category") or "other",
                    "tags": list(item.get("tags") or ["用户分享"]),
                    "accent": item.get("accent") or "#fb923c",
                    "prompt": item.get("prompt") or "",
                    "slash": f"/{item['id']}",
                }
            )
            seen.add(item["id"])
    except Exception:
        pass
    return {
        "skills": skills,
        "sources": cfg.get("skillSources") or [],
        "categories": cfg.get("skillCategories") or [],
        "tags": cfg.get("skillTags") or [],
    }


@app.get("/api/platform/skills/{skill_id}/experience")
def platform_skill_experience(skill_id: str) -> dict[str, Any]:
    sid = unquote(skill_id).strip()
    if not sid or "/" in sid or "\\" in sid:
        raise _http_error(400, "invalid skill id")
    return {"ok": True, **_skill_experience_payload(sid)}


@app.post("/api/platform/skills/community")
async def post_community_skill(request: Request) -> dict[str, Any]:
    body = await request.json()
    title = str(body.get("title") or "").strip()
    summary = str(body.get("summary") or "").strip()
    prompt = str(body.get("prompt") or body.get("content") or "").strip()
    if not title or not prompt:
        raise _http_error(400, "title and prompt required")
    sid = str(body.get("id") or "").strip() or f"community-{uuid.uuid4().hex[:8]}"
    item = {
        "id": sid,
        "title": title[:80],
        "summary": summary[:220] or title[:80],
        "prompt": prompt[:8000],
        "content": prompt[:8000],
        "category": str(body.get("category") or "other"),
        "tags": list(body.get("tags") or ["用户分享"])[:8],
        "accent": str(body.get("accent") or "#fb923c"),
        "source": "community",
        "createdAt": int(time.time()),
    }
    import community_skills as _cskills

    existing = [x for x in _cskills.load_community_skills(PROJECTS_ROOT) if x.get("id") != sid]
    existing.insert(0, item)
    _cskills.save_community_skills(PROJECTS_ROOT, existing)
    return {"ok": True, "skill": item}


@app.get("/api/settings/credits")
def get_credits() -> dict[str, Any]:
    return {"credits": load_credits()}


@app.post("/api/settings/credits/challenge")
async def post_challenge_complete(request: Request) -> dict[str, Any]:
    body = await request.json()
    cid = str(body.get("id") or "").strip()
    if not cid:
        raise _http_error(400, "id required")
    prize = body.get("prizePoints")
    if prize is None:
        # parse "+50" style
        raw = str(body.get("prize") or "")
        digits = "".join(ch for ch in raw if ch.isdigit())
        prize = int(digits or 0)
    return complete_challenge(cid, int(prize or 0), title=str(body.get("title") or ""))


@app.post("/api/settings/credits/referral")
async def post_referral(request: Request) -> dict[str, Any]:
    body = await request.json()
    return {"ok": True, "credits": record_referral(str(body.get("ref") or ""))}


@app.get("/api/platform/exports")
def platform_exports() -> dict[str, Any]:
    """List successful final exports only (成片) — not shot clips or failed/missing outputs."""
    exports = []
    for project in STORE.list_items():
        pid = project["id"]
        bundle = STORE.bundle(pid) or {}
        root = STORE._dir(pid)
        for edit in bundle.get("edits") or []:
            output_path = str(edit.get("outputPath") or "").strip()
            output_url = str(edit.get("outputUrl") or "").strip()
            if not output_url and not output_path:
                continue
            # Require a real media file — skip cleared/failed/stale export refs.
            rel_for_check = output_path
            if not rel_for_check and output_url.startswith(f"/api/media/{pid}/"):
                rel_for_check = output_url[len(f"/api/media/{pid}/") :]
            if rel_for_check and not STORE._media_exists(pid, rel_for_check.replace("\\", "/")):
                continue
            if not rel_for_check:
                continue
            filename = Path(output_path).name if output_path else (output_url.rsplit("/", 1)[-1] or "export.mp4")
            if not output_url and output_path:
                try:
                    rel = Path(output_path)
                    if not rel.is_absolute():
                        output_url = f"/api/media/{pid}/{rel.as_posix()}"
                    elif root and Path(output_path).is_relative_to(root):
                        output_url = f"/api/media/{pid}/{Path(output_path).relative_to(root).as_posix()}"
                except Exception:
                    output_url = output_path
            if not output_url:
                continue
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
        # Orphaned finals only under media/exports (never shot clips in media/videos).
        export_dir = root / "media" / "exports" if root else None
        if export_dir and export_dir.is_dir():
            for path in sorted(export_dir.glob("*.mp4")):
                if not path.is_file() or path.stat().st_size <= 0:
                    continue
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
    def _export_sort_key(item: dict[str, Any]) -> float:
        raw = item.get("updatedAt")
        if raw is None or raw == "":
            return 0.0
        if isinstance(raw, (int, float)):
            return float(raw)
        text = str(raw).strip()
        try:
            return float(text)
        except ValueError:
            pass
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return 0.0

    exports.sort(key=_export_sort_key, reverse=True)
    return {"exports": exports, "items": exports}


@app.get("/api/config")
def config() -> dict[str, Any]:
    payload = public_platform_payload()
    payload["styles"] = load_styles()
    payload["capabilities"] = _providers_payload()
    return payload


def _auth_json(status: int, body: dict[str, Any]) -> JSONResponse:
    return JSONResponse(status_code=status, content=body)


@app.get("/api/auth/captcha")
def auth_captcha() -> JSONResponse:
    status, body = auth_proxy.get_captcha()
    return _auth_json(status, body)


@app.get("/api/auth/social-providers")
def auth_social_providers() -> JSONResponse:
    status, body = auth_proxy.social_providers()
    return _auth_json(status, body)


@app.post("/api/auth/social/{provider}")
async def auth_social_login(provider: str, request: Request) -> JSONResponse:
    body = await request.json()
    status, result = auth_proxy.social_login(provider, body if isinstance(body, dict) else {})
    return _auth_json(status, result)


@app.post("/api/auth/login")
async def auth_login(request: Request) -> JSONResponse:
    body = await request.json()
    status, result = auth_proxy.login(body if isinstance(body, dict) else {})
    return _auth_json(status, result)


@app.post("/api/auth/demo")
def auth_demo() -> JSONResponse:
    demo_cfg = demo_auth_config()
    if not demo_cfg.get("enabled"):
        return _auth_json(403, {"ok": False, "error": "demo login disabled"})
    ensure_seed_projects(PROJECTS_ROOT, SEED_ROOT)
    ttl = max(1, int(demo_cfg.get("ttlDays") or 7)) * 24 * 3600
    issued = demo_auth.issue_demo_token(
        user_id=str(demo_cfg.get("userId") or "demo"),
        username=str(demo_cfg.get("displayName") or demo_cfg.get("username") or "Demo"),
        ttl_seconds=ttl,
    )
    return _auth_json(200, {"ok": True, "data": issued, "msg": "ok"})


@app.post("/api/auth/register")
async def auth_register(request: Request) -> JSONResponse:
    body = await request.json()
    status, result = auth_proxy.register(body if isinstance(body, dict) else {})
    return _auth_json(status, result)


@app.post("/api/auth/phone-login")
async def auth_phone_login(request: Request) -> JSONResponse:
    body = await request.json()
    status, result = auth_proxy.phone_login(body if isinstance(body, dict) else {})
    return _auth_json(status, result)


@app.post("/api/auth/send-code")
async def auth_send_code(request: Request) -> JSONResponse:
    body = await request.json()
    status, result = auth_proxy.send_code(body if isinstance(body, dict) else {})
    return _auth_json(status, result)


@app.get("/api/auth/me")
def auth_me(request: Request) -> JSONResponse:
    token = _bearer_token(request)
    if not token:
        return _auth_json(401, {"ok": False, "error": "missing token"})
    if demo_auth.is_demo_token(token):
        status, result = demo_auth.demo_me(token)
        return _auth_json(status, result)
    status, result = auth_proxy.me(token)
    return _auth_json(status, result)


@app.post("/api/auth/logout")
def auth_logout(request: Request) -> JSONResponse:
    token = _bearer_token(request)
    if not token:
        return _auth_json(200, {"ok": True, "data": None})
    if demo_auth.is_demo_token(token):
        status, result = demo_auth.demo_logout(token)
        return _auth_json(status, result)
    status, result = auth_proxy.logout(token)
    return _auth_json(status, result)


@app.post("/api/auth/refresh-token")
def auth_refresh(request: Request) -> JSONResponse:
    token = _bearer_token(request)
    if not token:
        return _auth_json(401, {"ok": False, "error": "missing token"})
    if demo_auth.is_demo_token(token):
        demo_cfg = demo_auth_config()
        status, result = demo_auth.demo_refresh(
            token,
            user_id=str(demo_cfg.get("userId") or "demo"),
            username=str(demo_cfg.get("displayName") or demo_cfg.get("username") or "Demo"),
        )
        return _auth_json(status, result)
    status, result = auth_proxy.refresh_token(token)
    return _auth_json(status, result)


@app.get("/api/inspire/pins")
def inspire_pins(
    limit: int = Query(48, ge=1, le=120),
    offset: int = Query(0, ge=0),
    refresh: bool = Query(False),
    category: str = Query("all"),
    q: str = Query(""),
    mediaType: str = Query("all"),
) -> dict[str, Any]:
    return fetch_pins(
        limit=limit,
        force=refresh,
        category=category,
        offset=offset,
        q=q,
        media_type=mediaType,
    )


@app.get("/api/inspire/media/{item_id}")
def inspire_media(item_id: str) -> Response:
    """Serve inspiration bytes from Postgres / local store (no external CDN)."""
    iid = (item_id or "").strip()
    if not iid or "/" in iid or ".." in iid:
        raise _http_error(400, "invalid id")
    hit = inspire_store.load_blob(iid)
    if not hit:
        raise _http_error(404, "not found")
    blob, ctype = hit
    return Response(
        content=blob,
        media_type=ctype or "image/jpeg",
        headers={"Cache-Control": "public, max-age=604800"},
    )


@app.get("/api/inspire/img")
def inspire_img(u: str = Query("")) -> Response:
    """Legacy: ingest remote once into local store, then serve local bytes."""
    url = (u or "").strip()
    if not url:
        raise _http_error(400, "u required")
    if not url.startswith("https://"):
        raise _http_error(400, "only https remote urls can be ingested")
    iid = inspire_store.item_id_for_url(url)
    hit = inspire_store.load_blob(iid)
    if not hit:
        try:
            blob, ctype = fetch_remote_image(url)
            inspire_store.upsert_local(
                iid,
                blob,
                content_type=ctype or "image/jpeg",
                origin_hash=iid,
                meta={"ingestedVia": "legacy-img"},
            )
            hit = (blob, ctype or "image/jpeg")
        except Exception as exc:
            raise _http_error(502, f"image ingest failed: {exc}") from exc
    blob, ctype = hit
    return Response(
        content=blob,
        media_type=ctype or "image/jpeg",
        headers={"Cache-Control": "public, max-age=604800"},
    )


@app.get("/api/portrait-match/templates")
def portrait_match_templates() -> dict[str, Any]:
    from portrait_match import MATCH_MODES, QUALITY_DIAGNOSIS, list_templates

    return {
        "templates": list_templates(),
        "matchModes": MATCH_MODES,
        "qualityDiagnosis": QUALITY_DIAGNOSIS,
    }


@app.get("/api/portrait-match/assets/{asset_path:path}")
def portrait_match_asset(asset_path: str) -> FileResponse:
    from portrait_match import assets_root

    root = assets_root().resolve()
    target = (root / asset_path).resolve()
    if not str(target).startswith(str(root)) or not target.is_file():
        raise _http_error(404, "asset not found")
    return FileResponse(target)


@app.post("/api/portrait-match/projects", status_code=201)
async def portrait_match_create(request: Request) -> dict[str, Any]:
    from portrait_match import create_from_template

    body = await request.json()
    try:
        bundle = create_from_template(
            STORE,
            template_id=str(body.get("templateId") or body.get("template") or ""),
            title=(body.get("title") or None),
            owner_id=current_user_id() or None,
            include_sample=body.get("includeSample", True) is not False,
            match_mode=str(body.get("matchMode") or body.get("mode") or "gen-likeness"),
        )
    except (ValueError, FileNotFoundError, RuntimeError) as exc:
        raise _http_error(400, str(exc)) from exc
    return {"bundle": bundle, "project": (bundle or {}).get("project")}


@app.post("/api/projects/{project_id}/portrait-match/generate")
async def portrait_match_generate(project_id: str, request: Request) -> dict[str, Any]:
    from portrait_match import start_all_idlock

    body = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {}
    try:
        return start_all_idlock(
            STORE,
            project_id,
            model=str(body.get("model") or ""),
            resolution=str(body.get("resolution") or "1080p"),
            only_missing=body.get("onlyMissing", True) is not False,
            # refreshFrames: pull Douyin-original keyframes into project and regen all shots
            refresh_frames=body.get("refreshFrames") is True or body.get("alignDouyin") is True,
        )
    except (FileNotFoundError, RuntimeError) as exc:
        raise _http_error(400, str(exc)) from exc


@app.post("/api/projects/{project_id}/portrait-match/refresh-frames")
def portrait_match_refresh_frames(project_id: str) -> dict[str, Any]:
    """Replace idlock frames with Douyin-original extracts (invalidate videos)."""
    from portrait_match import refresh_idlock_frames_from_assets

    try:
        return refresh_idlock_frames_from_assets(STORE, project_id, invalidate_videos=True)
    except (FileNotFoundError, RuntimeError) as exc:
        raise _http_error(400, str(exc)) from exc


@app.get("/api/projects/{project_id}/portrait-match/quality")
def portrait_match_quality(project_id: str) -> dict[str, Any]:
    """角色 / 场景 / 提示词是否达标。"""
    from portrait_match import portrait_workshop_quality_report

    return portrait_workshop_quality_report(STORE, project_id)


@app.post("/api/projects/{project_id}/portrait-match/prepare-assets")
def portrait_match_prepare_assets(project_id: str) -> dict[str, Any]:
    """Enqueue drama-entity-still for character + scene; refresh structured prompts."""
    from portrait_match import enqueue_portrait_entity_stills, ensure_portrait_workshop_assets, portrait_workshop_quality_report

    ensure_portrait_workshop_assets(STORE, project_id)
    stills = enqueue_portrait_entity_stills(STORE, project_id)
    return {
        "entityStills": stills,
        "quality": portrait_workshop_quality_report(STORE, project_id),
        "bundle": STORE.bundle(project_id),
    }


@app.post("/api/projects/{project_id}/portrait-match/assemble")
def portrait_match_assemble(project_id: str) -> dict[str, Any]:
    from portrait_match import assemble_portrait

    try:
        return assemble_portrait(STORE, project_id)
    except (FileNotFoundError, RuntimeError) as exc:
        raise _http_error(400, str(exc)) from exc


@app.get("/api/projects")
def list_projects() -> dict[str, Any]:
    items = STORE.list_items()
    uid = current_user_id()
    if uid:
        return {"projects": items}
    # Anonymous browse: seed + public + demo showcase (read-only; generate needs login).
    demo_on = True
    try:
        from platform_config import load_platform_config

        demo_cfg = ((load_platform_config() or {}).get("auth") or {}).get("demo") or {}
        demo_on = bool(demo_cfg.get("enabled", True))
    except Exception:
        demo_on = True
    public = []
    for p in items:
        pid = str(p.get("id") or "")
        if p.get("hidden") or pid.startswith("_") or pid.startswith("."):
            continue
        owner = str(p.get("ownerId") or "").strip()
        if (
            p.get("public")
            or p.get("seed")
            or pid.startswith("welcome")
            or (demo_on and owner in {"", "demo"})
        ):
            public.append(p)
    return {"projects": public}


@app.post("/api/projects/parse-script")
async def parse_script_upload(file: UploadFile = File(...)) -> dict[str, Any]:
    raw = await file.read()
    if not raw:
        raise _http_error(400, "empty file")
    if len(raw) > 8 * 1024 * 1024:
        raise _http_error(400, "file too large (max 8MB)")
    try:
        text = extract_text(file.filename or "script.txt", raw)
    except RuntimeError as exc:
        raise _http_error(400, str(exc)) from exc
    text = (text or "").strip()
    if not text:
        raise _http_error(400, "no text extracted")
    return {
        "ok": True,
        "filename": file.filename,
        "title": guess_title(text, file.filename or ""),
        "text": text[:100000],
        "chars": len(text),
    }


@app.post("/api/projects/{project_id}/audio")
async def project_audio(project_id: str, request: Request) -> dict[str, Any]:
    pid = unquote(project_id)
    body = await request.json()
    action = str(body.get("action") or "generate")
    state = _assert_project_access(pid, write=action != "list")
    episode_id = str(body.get("episodeId") or "").strip()
    if action == "list":
        return {"audios": state.get("audios") or []}
    if not episode_id:
        raise _http_error(400, "episodeId required")
    episode = next((e for e in (state.get("episodes") or []) if e.get("id") == episode_id), None)
    if not episode:
        raise _http_error(404, "episode not found")
    ep_shots = [
        s
        for s in (state.get("shots") or [])
        if s.get("episodeId") == episode_id and not s.get("deletedAt")
    ]
    lines = dialogue_lines_for_episode(
        episode.get("content") or episode.get("script") or "",
        ep_shots,
    )
    # Optional raw text override still goes through multi-voice if it looks like speaker lines
    override = str(body.get("text") or "").strip()
    if override and not lines:
        lines = dialogue_lines_for_episode(override)
    if not lines:
        raise _http_error(400, "episode has no dialogue text（请用「角色：台词」格式）")
    rel = f"media/audio/{episode_id}.mp3"
    out = STORE._dir(pid) / rel
    try:
        meta = synthesize_dialogue_mp3(lines, out)
    except RuntimeError as exc:
        # Fallback single-voice if concat/ffmpeg path fails
        try:
            flat = "。".join(x["text"] for x in lines)[:2000]
            meta = synthesize_mp3(flat, out)
            meta["mode"] = "narration-fallback"
        except RuntimeError as exc2:
            raise _http_error(400, str(exc2)) from exc2
    STORE.persist_media(pid, rel)

    # Soft drama BGM bed for export mix
    bgm_rel = f"media/audio/{episode_id}-bgm.mp3"
    bgm_meta = None
    try:
        # Rough length: ~2.2s per line + padding
        dur = max(24.0, min(180.0, len(lines) * 2.4 + 8))
        bgm_meta = generate_bgm_mp3(STORE._dir(pid) / bgm_rel, duration_sec=dur, mood="drama")
        STORE.persist_media(pid, bgm_rel)
    except Exception:
        bgm_rel = ""

    preview = " / ".join(f"{x['speaker']}：{x['text'][:40]}" for x in lines[:8])
    item = {
        "id": episode_id,
        "episodeId": episode_id,
        "kind": "dialogue",
        "path": rel,
        "url": f"/api/media/{pid}/{rel}",
        "text": preview[:2000],
        "lines": len(lines),
        "mode": meta.get("mode") or "dialogue",
        "voices": meta.get("voices") or [],
        "provider": meta.get("provider"),
        "bytes": meta.get("bytes"),
        "updatedAt": int(time.time()),
    }
    audios = [a for a in (state.get("audios") or []) if a.get("episodeId") != episode_id]
    audios.append(item)
    if bgm_rel and bgm_meta:
        audios.append(
            {
                "id": f"{episode_id}-bgm",
                "episodeId": episode_id,
                "kind": "bgm",
                "path": bgm_rel,
                "url": f"/api/media/{pid}/{bgm_rel}",
                "provider": bgm_meta.get("provider"),
                "bytes": bgm_meta.get("bytes"),
                "updatedAt": int(time.time()),
            }
        )
    state["audios"] = audios
    STORE.save(state)
    return {"ok": True, "audio": item, "bgm": bgm_rel or None, "bundle": STORE.bundle(pid)}


def _assert_project_access(project_id: str, *, write: bool = False) -> dict[str, Any]:
    state = STORE.load(project_id)
    if not state:
        raise _http_error(404, "project not found")
    uid = current_user_id()
    owner = str((state.get("project") or {}).get("ownerId") or "").strip()
    is_seed = project_id.startswith("welcome") or bool((state.get("project") or {}).get("seed"))
    is_public = bool((state.get("project") or {}).get("public")) or is_seed or owner in {"", "demo"}
    # Anonymous may browse public / demo showcase projects; mutations always need login.
    if write and not uid:
        raise _http_error(401, "login required")
    if not uid and not is_public:
        raise _http_error(401, "login required")
    if uid and uid != "demo" and owner and owner != uid:
        raise _http_error(403, "forbidden")
    if write and uid and uid != "demo" and is_seed and not owner:
        raise _http_error(403, "seed project is read-only; create your own project")
    return state


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
        owner_id=current_user_id() or None,
    )
    return STORE.bundle(state["project"]["id"])


@app.get("/api/projects/{project_id}")
def get_project(project_id: str) -> dict[str, Any]:
    pid = unquote(project_id)
    _assert_project_access(pid)
    # Portrait-match: backfill empty 角色/场景 + normalize false「质检未过」on load.
    try:
        from portrait_match import ensure_portrait_workshop_assets

        fixed = ensure_portrait_workshop_assets(STORE, pid)
        if fixed:
            return fixed
    except Exception:
        pass
    bundle = STORE.bundle(pid)
    if not bundle:
        raise _http_error(404, "project not found")
    return bundle


@app.patch("/api/projects/{project_id}")
async def update_project(project_id: str, request: Request) -> dict[str, Any]:
    pid = unquote(project_id)
    _assert_project_access(pid, write=True)
    body = await request.json()
    patch_project(STORE, pid, body)
    return STORE.bundle(pid)


@app.delete("/api/projects/{project_id}")
def delete_project(project_id: str) -> dict[str, Any]:
    pid = unquote(project_id)
    _assert_project_access(pid, write=True)
    if not STORE.delete(pid):
        raise _http_error(404, "project not found")
    return {"ok": True, "deleted": pid}


@app.post("/api/script-brief")
async def script_brief_global(request: Request) -> dict[str, Any]:
    body = await request.json()
    return optimize_brief(STORE, body)


@app.post("/api/projects/{project_id}/script-brief")
async def script_brief_project(project_id: str, request: Request) -> dict[str, Any]:
    pid = unquote(project_id)
    _assert_project_access(pid, write=True)
    body = await request.json()
    return optimize_brief(STORE, body)


@app.post("/api/projects/{project_id}/script")
async def script_actions(project_id: str, request: Request) -> dict[str, Any]:
    pid = unquote(project_id)
    _assert_project_access(pid, write=True)
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
    bundle = STORE.bundle(pid) or {}
    return {**bundle, "skillId": "drama-script"}


@app.patch("/api/projects/{project_id}/episodes")
async def episode_actions(project_id: str, request: Request) -> dict[str, Any]:
    pid = unquote(project_id)
    _assert_project_access(pid, write=True)
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
    _assert_project_access(pid, write=True)
    body = await request.json()
    action = body.get("action")
    if action == "generate":
        # Default async: enqueue on bounded media pool so HTTP stays responsive.
        # User-initiated generate must force=True — otherwise purge_satisfied drops
        # the job when a prior still already has qaPass (「生成新版本」出现排队即消失).
        wait = bool(body.get("wait"))
        redraw = bool(body.get("redraw"))
        force = bool(body.get("force")) if "force" in body else True
        ver = generate_entity_image(
            STORE,
            pid,
            body.get("entityId") or body.get("id"),
            three_view=bool(body.get("threeView")),
            redraw=redraw,
            force=force or redraw,
            wait=wait,
        )
        return {"image": ver, "async": not wait, "bundle": STORE.bundle(pid)}
    if action == "preview-prompt":
        return preview_entity_prompt(
            STORE,
            pid,
            body.get("entityId") or body.get("id"),
            three_view=bool(body.get("threeView")),
        )
    if action == "recheck-qa":
        # Vision recheck + optional regen are heavy — enqueue unless wait=true.
        wait = bool(body.get("wait"))
        if not wait:
            from job_queue import enqueue

            stub = enqueue(
                "entity_recheck_qa",
                {
                    "projectId": pid,
                    "entityIds": body.get("entityIds"),
                    "clearSoftPass": body.get("clearSoftPass", True) is not False,
                    "regenerateFailed": bool(body.get("regenerateFailed")),
                },
            )
            return {**stub, "async": True, "bundle": STORE.bundle(pid)}
        summary = recheck_entity_qa(
            STORE,
            pid,
            entity_ids=body.get("entityIds"),
            clear_soft_pass=body.get("clearSoftPass", True) is not False,
            regenerate_failed=bool(body.get("regenerateFailed")),
        )
        return {**summary, "bundle": STORE.bundle(pid)}
    if action == "batch":
        ids = body.get("entityIds") or []
        wait = bool(body.get("wait"))
        results = []
        for eid in ids:
            try:
                results.append(
                    generate_entity_image(
                        STORE,
                        pid,
                        eid,
                        three_view=bool(body.get("threeView")),
                        wait=wait,
                    )
                )
            except Exception as exc:
                results.append({"entityId": eid, "error": str(exc)})
        return {"results": results, "async": not wait, "bundle": STORE.bundle(pid)}
    if action in {"fill-stills", "fill", "补图"}:
        # Coordinator + Comfy/QA run on the shared media queue (HTTP returns immediately).
        wait = bool(body.get("wait"))
        if not wait:
            from job_queue import enqueue

            stub = enqueue(
                "fill_entity_stills",
                {
                    "projectId": pid,
                    "episodeId": body.get("episodeId"),
                    "segmentOrder": body.get("segmentOrder"),
                    "kinds": body.get("kinds") or ["character", "scene"],
                    "entityIds": body.get("entityIds"),
                    "onlyMissing": body.get("onlyMissing", True) is not False,
                    "forceRefreshKinds": body.get("forceRefreshKinds") or [],
                },
            )
            return {**stub, "async": True, "bundle": STORE.bundle(pid)}
        summary = fill_entity_stills(
            STORE,
            pid,
            episode_id=body.get("episodeId"),
            segment_order=int(body["segmentOrder"]) if body.get("segmentOrder") is not None else None,
            kinds=body.get("kinds") or ["character", "scene"],
            entity_ids=body.get("entityIds"),
            only_missing=body.get("onlyMissing", True) is not False,
            force_refresh_kinds=body.get("forceRefreshKinds") or [],
        )
        return {**summary, "bundle": STORE.bundle(pid)}
    if action == "job-stats":
        from job_queue import queue_stats

        return {"queue": queue_stats(), "bundle": STORE.bundle(pid)}
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
    if action in {"punch-alpha", "cutout", "抠透明底"}:
        return punch_entity_image_alpha(
            STORE,
            pid,
            body.get("entityId") or body.get("id"),
            image_id=body.get("imageId"),
        )
    ent = upsert_entity(STORE, pid, body)
    return {"entity": ent, "bundle": STORE.bundle(pid)}


@app.patch("/api/projects/{project_id}/entities")
async def entities_patch(project_id: str, request: Request) -> dict[str, Any]:
    pid = unquote(project_id)
    _assert_project_access(pid, write=True)
    body = await request.json()
    ent = upsert_entity(STORE, pid, {**body, "id": body.get("entityId") or body.get("id")})
    return {"entity": ent, "bundle": STORE.bundle(pid)}


@app.delete("/api/projects/{project_id}/entities")
def entities_delete(project_id: str, entityId: str | None = Query(default=None)) -> dict[str, Any]:
    pid = unquote(project_id)
    _assert_project_access(pid, write=True)
    if not entityId:
        raise _http_error(400, "entityId required")
    state = soft_delete_entity(STORE, pid, entityId)
    return STORE.bundle(pid) or state


@app.post("/api/projects/{project_id}/storyboard")
async def storyboard_actions(project_id: str, request: Request) -> dict[str, Any]:
    pid = unquote(project_id)
    _assert_project_access(pid, write=True)
    body = await request.json()
    op = body.get("action") or "generate"
    if op == "generate":
        shots = generate_storyboard(STORE, pid, body["episodeId"])
        return {"skillId": "drama-shot-prompt", "shots": shots, "bundle": STORE.bundle(pid)}
    if op == "migrate-segments":
        shots = migrate_episode_segments(STORE, pid, body["episodeId"])
        return {"shots": shots, "bundle": STORE.bundle(pid)}
    if op == "bind-refs":
        shots = bind_episode_refs(STORE, pid, body["episodeId"])
        return {"shots": shots, "bundle": STORE.bundle(pid)}
    if op == "effective-prompt":
        return effective_segment_video_prompt(
            STORE,
            pid,
            episode_id=body["episodeId"],
            segment_order=int(body["segmentOrder"]),
        )
    if op == "check-consistency":
        from drama_service import _now
        from prompt_consistency import check_shot_prompt, entity_name_set, repair_shot_prompt

        state = STORE.load(pid)
        if not state:
            raise _http_error(404, "project not found")
        names = entity_name_set(state.get("entities") or [])
        episode_id = body.get("episodeId")
        rows = []
        changed = False
        for s in state.get("shots") or []:
            if s.get("deletedAt"):
                continue
            if episode_id and s.get("episodeId") != episode_id:
                continue
            if body.get("repair"):
                fixed = repair_shot_prompt(s, entity_names=names)
                if fixed.get("repaired"):
                    s["prompt"] = fixed["prompt"]
                    s["updatedAt"] = _now()
                    changed = True
                report = fixed
            else:
                report = check_shot_prompt(s, entity_names=names)
            s["promptConsistency"] = {"ok": bool(report.get("ok")), "issues": report.get("issues") or []}
            if not report.get("ok") or report.get("repaired"):
                rows.append(
                    {
                        "shotId": s.get("id"),
                        "segmentOrder": s.get("segmentOrder"),
                        "dialogue": (s.get("dialogue") or "")[:80],
                        "ok": bool(report.get("ok")),
                        "issues": report.get("issues"),
                        "repaired": bool(report.get("repaired")),
                    }
                )
        if changed:
            STORE.save(state)
        return {
            "ok": all(r.get("ok") for r in rows) if rows else True,
            "fail": sum(1 for r in rows if not r.get("ok")),
            "results": rows,
            "bundle": STORE.bundle(pid) if changed else None,
        }
    if op == "recheck-video-qa":
        summary = recheck_video_qa(
            STORE,
            pid,
            shot_ids=body.get("shotIds"),
        )
        return {**summary, "bundle": STORE.bundle(pid)}
    if op == "add":
        shot = add_shot(STORE, pid, body["episodeId"])
        return {"shot": shot, "bundle": STORE.bundle(pid)}
    if op == "delete":
        soft_delete_shot(STORE, pid, body["shotId"])
        return STORE.bundle(pid)
    if op == "patch":
        shot = patch_shot(STORE, pid, body["shotId"], body.get("patch") or body)
        return {"shot": shot, "bundle": STORE.bundle(pid)}
    if op == "cancel-video":
        shot = cancel_shot_video(STORE, pid, body["shotId"])
        return {"shot": shot, "bundle": STORE.bundle(pid)}
    def _storyboard_video_model() -> str:
        from providers.media import resolve_video_model, video_backend

        backend = video_backend()
        if backend == "none":
            raise _http_error(
                400,
                "未配置出片后端，或顶部所选后端不可用。请在顶部模型切换选择 ComfyUI / Seedance，并确认 Key 或租机地址。",
            )
        return resolve_video_model(str(body.get("model") or ""))

    force_qa = _force_entity_qa(body)
    skip_refs = bool(body.get("skipRefs") or body.get("textOnly"))
    if op == "video":
        try:
            shot = start_shot_video(
                STORE,
                pid,
                body["shotId"],
                model=_storyboard_video_model(),
                resolution=body.get("resolution") or "720p",
                skip_refs=skip_refs,
                force_entity_qa=force_qa,
            )
        except EntityQaBlockedError as exc:
            raise _entity_qa_blocked_http(exc) from exc
        return {"shot": shot, "bundle": STORE.bundle(pid)}
    if op == "video-segment":
        try:
            shot = start_segment_video(
                STORE,
                pid,
                body["episodeId"],
                int(body["segmentOrder"]),
                model=_storyboard_video_model(),
                resolution=body.get("resolution") or "720p",
                skip_refs=skip_refs,
                force_entity_qa=force_qa,
            )
        except EntityQaBlockedError as exc:
            raise _entity_qa_blocked_http(exc) from exc
        return {"shot": shot, "bundle": STORE.bundle(pid)}
    if op == "revise-segment":
        try:
            shot = revise_segment(
                STORE,
                pid,
                body["episodeId"],
                int(body["segmentOrder"]),
                instruction=str(body.get("instruction") or body.get("note") or ""),
                model=_storyboard_video_model(),
                resolution=body.get("resolution") or "720p",
                skip_refs=skip_refs,
                start_video=body.get("startVideo", True) is not False,
                force_entity_qa=force_qa,
            )
        except EntityQaBlockedError as exc:
            raise _entity_qa_blocked_http(exc) from exc
        return {"shot": shot, "bundle": STORE.bundle(pid)}
    if op == "batch-video":
        # Prefer segment-level generation when segmentOrders are provided.
        seg_orders = body.get("segmentOrders") or []
        episode_id = body.get("episodeId")
        started = []
        vid_model = _storyboard_video_model()
        if seg_orders and episode_id:
            for so in seg_orders:
                try:
                    started.append(
                        start_segment_video(
                            STORE,
                            pid,
                            episode_id,
                            int(so),
                            model=vid_model,
                            resolution=body.get("resolution") or "720p",
                            skip_refs=skip_refs,
                            force_entity_qa=force_qa,
                        )
                    )
                except EntityQaBlockedError as exc:
                    started.append(
                        {
                            "segmentOrder": so,
                            "error": str(exc),
                            "code": "entity_qa_blocked",
                            "blockers": exc.blockers,
                        }
                    )
                except Exception as exc:
                    started.append({"segmentOrder": so, "error": str(exc)})
            return {"started": started, "bundle": STORE.bundle(pid)}
        ids = body.get("shotIds") or []
        for sid in ids:
            try:
                started.append(
                    start_shot_video(
                        STORE,
                        pid,
                        sid,
                        model=vid_model,
                        resolution=body.get("resolution") or "720p",
                        skip_refs=skip_refs,
                        force_entity_qa=force_qa,
                    )
                )
            except EntityQaBlockedError as exc:
                started.append(
                    {
                        "shotId": sid,
                        "error": str(exc),
                        "code": "entity_qa_blocked",
                        "blockers": exc.blockers,
                    }
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
    if op == "sync-video":
        from drama_service import sync_shot_video

        shot = sync_shot_video(STORE, pid, body["shotId"])
        return {"shot": shot, "bundle": STORE.bundle(pid)}
    raise _http_error(400, "unknown storyboard action")


@app.post("/api/projects/{project_id}/edits")
async def edit_actions(project_id: str, request: Request) -> dict[str, Any]:
    pid = unquote(project_id)
    _assert_project_access(pid, write=True)
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
    pid = unquote(project_id)
    _assert_project_access(pid)
    return poll_shot(STORE, pid, unquote(shot_id))


@app.get("/api/media/{project_id}/{media_path:path}")
def media_file(project_id: str, media_path: str) -> FileResponse:
    name = unquote(project_id)
    rel = unquote(media_path)
    if ".." in Path(rel).parts:
        raise _http_error(400, "invalid path")
    # Hydrate from Postgres when the volume was wiped after redeploy.
    file_path = STORE.ensure_media(name, rel)
    project = STORE._dir(name)
    if not project:
        raise _http_error(404, "project not found")
    if not file_path or not file_path.is_file():
        raise _http_error(404, "file not found")
    resolved = file_path.resolve()
    if not str(resolved).startswith(str(project.resolve())):
        raise _http_error(400, "invalid path")
    ctype = mimetypes.guess_type(str(resolved))[0] or "application/octet-stream"
    if resolved.suffix.lower() == ".svg":
        ctype = "image/svg+xml"
    return FileResponse(resolved, media_type=ctype, headers={"Cache-Control": "public, max-age=60"})


@app.post("/api/projects/{project_id}/generate")
async def legacy_generate(project_id: str) -> None:
    raise _http_error(400, "use /api/projects/:id/storyboard with action=batch-video")


@app.post("/api/auto-produce", status_code=201)
async def auto_produce_create(request: Request) -> dict[str, Any]:
    """Create a project from one sentence / pasted script and start the full pipeline."""
    body = await request.json()
    brief = str(body.get("brief") or body.get("prompt") or body.get("script") or "").strip()
    if not brief:
        raise _http_error(400, "请输入一句话想法或粘贴剧本")
    title = str(body.get("title") or "").strip() or brief[:24] or "一键短剧"
    state = STORE.create_project(
        title=title,
        brief=brief,
        genre=body.get("genre") or default_genre(),
        visual_style=body.get("visualStyle") or body.get("visual_style") or "",
        ratio=body.get("ratio") or body.get("aspect_ratio") or None,
        name=body.get("name"),
        owner_id=current_user_id() or None,
    )
    pid = state["project"]["id"]
    try:
        job = start_auto_produce(STORE, pid, body)
    except RuntimeError as exc:
        raise _http_error(400, str(exc)) from exc
    return {"projectId": pid, "job": job, "bundle": STORE.bundle(pid)}


@app.post("/api/projects/{project_id}/auto-produce")
async def auto_produce_start(project_id: str, request: Request) -> dict[str, Any]:
    pid = unquote(project_id)
    _assert_project_access(pid, write=True)
    try:
        body = await request.json()
    except Exception:
        body = {}
    if not isinstance(body, dict):
        body = {}
    action = str(body.get("action") or "").strip().lower()
    if action in {"cancel", "pause", "stop"}:
        try:
            job = cancel_auto_produce(
                STORE,
                pid,
                reason=str(body.get("reason") or "已暂停：先修好定妆再出片"),
            )
        except FileNotFoundError as exc:
            raise _http_error(404, str(exc)) from exc
        return {"projectId": pid, "job": job, "bundle": STORE.bundle(pid)}
    # Allow updating brief/title before run
    patch: dict[str, Any] = {}
    if body.get("brief") or body.get("prompt") or body.get("script"):
        patch["brief"] = str(body.get("brief") or body.get("prompt") or body.get("script") or "").strip()
    if body.get("title"):
        patch["title"] = str(body.get("title")).strip()
    if body.get("genre"):
        patch["genre"] = body.get("genre")
    if body.get("visualStyle") or body.get("visual_style"):
        patch["visualStyle"] = body.get("visualStyle") or body.get("visual_style")
    if body.get("ratio") or body.get("aspect_ratio"):
        patch["ratio"] = body.get("ratio") or body.get("aspect_ratio")
    if patch:
        patch_project(STORE, pid, patch)
    try:
        job = start_auto_produce(STORE, pid, body)
    except RuntimeError as exc:
        raise _http_error(400, str(exc)) from exc
    return {"projectId": pid, "job": job, "bundle": STORE.bundle(pid)}


@app.get("/api/projects/{project_id}/auto-produce")
def auto_produce_status(project_id: str) -> dict[str, Any]:
    pid = unquote(project_id)
    _assert_project_access(pid)
    job = ensure_auto_produce_worker(STORE, pid) or get_auto_produce_job(STORE, pid)
    if not job:
        return {"projectId": pid, "job": None}
    return {"projectId": pid, "job": job, "bundle": STORE.bundle(pid)}


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
