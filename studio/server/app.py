#!/usr/bin/env python3
"""Drama Studio API + static UI for local / Coolify deployment."""

from __future__ import annotations

import json
import mimetypes
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(os.environ.get("OPENMONTAGE_ROOT", Path(__file__).resolve().parents[2])).resolve()
sys.path.insert(0, str(ROOT))

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


def _json_response(handler: BaseHTTPRequestHandler, code: int, payload: dict) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, PATCH, OPTIONS")
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


def _load_artifact(project: Path, kind: str):
    rel = ARTIFACT_FILES.get(kind)
    if not rel:
        return None
    path = project / rel
    if not path.exists() and kind == "character_bible":
        alt = project / "bible" / "character_bible.json"
        if alt.exists():
            path = alt
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


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
    return {
        "name": name,
        "path": str(project),
        "artifacts": arts,
        "steps": step_status,
        "status": summarize(project),
    }


def _serve_static(handler: BaseHTTPRequestHandler, url_path: str) -> bool:
    if not DIST_DIR.is_dir():
        return False
    rel = url_path.lstrip("/") or "index.html"
    candidate = (DIST_DIR / rel).resolve()
    if not str(candidate).startswith(str(DIST_DIR)):
        return False
    if not candidate.is_file():
        # SPA fallback
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
                },
            )

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
                names = sorted([p.name for p in PROJECTS_ROOT.iterdir() if p.is_dir() and not p.name.startswith(".")])
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

        if path.startswith("/api/"):
            return _json_response(self, 404, {"error": "not found"})

        if _serve_static(self, path):
            return None
        return _json_response(self, 404, {"error": "UI not built; run npm run build in studio/"})

    def do_POST(self) -> None:
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
            sb_path.write_text(json.dumps(storyboard, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            return _json_response(self, 200, {"storyboard": storyboard})

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
