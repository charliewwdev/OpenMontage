#!/usr/bin/env python3
"""Lightweight Drama Studio API (stdlib) over projects/ + workflow_defs/."""

from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from lib.drama_status import summarize  # noqa: E402
from lib.pipeline_loader import get_stage_order, load_pipeline  # noqa: E402
from lib.subgraph_validate import validate_subgraph, validate_subgraph_file  # noqa: E402


def _json_response(handler: BaseHTTPRequestHandler, code: int, payload: dict) -> None:
    body = json.dumps(payload).encode()
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json")
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


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:  # quieter
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def do_OPTIONS(self) -> None:
        _json_response(self, 204, {})

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        if path == "/api/health":
            return _json_response(self, 200, {"ok": True})

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
            for p in sorted(root.glob("*.workflow.json")):
                doc = json.loads(p.read_text())
                items.append({"id": doc.get("id"), "path": str(p.relative_to(ROOT)), "title": doc.get("title")})
            return _json_response(self, 200, {"subgraphs": items})

        if path.startswith("/api/subgraphs/") and path.endswith("/graph"):
            subgraph_id = path.split("/")[3]
            path_file = ROOT / "workflow_defs" / "subgraphs" / f"{subgraph_id}.workflow.json"
            if not path_file.exists():
                return _json_response(self, 404, {"error": "subgraph not found"})
            doc = json.loads(path_file.read_text())
            return _json_response(self, 200, {"document": doc, "validation": validate_subgraph_file(path_file)})

        if path == "/api/projects":
            projects = ROOT / "projects"
            names = []
            if projects.is_dir():
                names = sorted([p.name for p in projects.iterdir() if p.is_dir()])
            return _json_response(self, 200, {"projects": names})

        if path == "/api/project/status":
            name = (qs.get("name") or [None])[0]
            if not name:
                return _json_response(self, 400, {"error": "name required"})
            return _json_response(self, 200, summarize(ROOT / "projects" / name))

        if path == "/api/project/storyboard":
            name = (qs.get("name") or [None])[0]
            if not name:
                return _json_response(self, 400, {"error": "name required"})
            sb = ROOT / "projects" / name / "storyboard.json"
            if not sb.exists():
                return _json_response(self, 404, {"error": "storyboard.json not found"})
            return _json_response(self, 200, {"storyboard": json.loads(sb.read_text())})

        if path == "/api/project/ledger":
            name = (qs.get("name") or [None])[0]
            if not name:
                return _json_response(self, 400, {"error": "name required"})
            lp = ROOT / "projects" / name / "shot_jobs.json"
            if not lp.exists():
                return _json_response(self, 404, {"error": "shot_jobs.json not found"})
            return _json_response(self, 200, {"ledger": json.loads(lp.read_text())})

        return _json_response(self, 404, {"error": "not found"})

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
            from tools.pipeline.shot_job_manager import ShotJobManager

            ledger_path = ROOT / "projects" / name / "shot_jobs.json"
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
            sb_path = ROOT / "projects" / name / "storyboard.json"
            if not sb_path.exists():
                return _json_response(self, 404, {"error": "storyboard missing"})
            storyboard = json.loads(sb_path.read_text())
            found = False
            for shot in storyboard.get("shots", []):
                if shot.get("id") == shot_id:
                    shot.update(patch)
                    found = True
                    break
            if not found:
                return _json_response(self, 404, {"error": "shot not found"})
            sb_path.write_text(json.dumps(storyboard, indent=2))
            return _json_response(self, 200, {"storyboard": storyboard})

        return _json_response(self, 404, {"error": "not found"})


def main() -> None:
    port = 8787
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Drama Studio API on http://127.0.0.1:{port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
