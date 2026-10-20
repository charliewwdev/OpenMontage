#!/usr/bin/env python3
"""Smoke-test every model listed on 算桥 / 算家云 (api.suanjiayun.com).

- Text / chat models → POST /v1/chat/completions
- Seedream → POST /v1/images/generations
- Seedance → try chat + video task-style endpoints

Usage:
  python3 scripts/smoke_suanqiao_all_models.py
"""

from __future__ import annotations

import concurrent.futures
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SECRETS = ROOT / "studio" / "projects" / ".studio_secrets.json"
OUT = ROOT / "studio" / "projects" / ".suanqiao_model_smoke.json"
BASE = "https://api.suanjiayun.com"


def _key() -> str:
    key = (os.environ.get("SUANQIAO_API_KEY") or "").strip()
    if key:
        return key
    if SECRETS.is_file():
        data = json.loads(SECRETS.read_text(encoding="utf-8") or "{}")
        key = (data.get("SUANQIAO_API_KEY") or "").strip()
    if not key:
        raise SystemExit("SUANQIAO_API_KEY missing")
    return key


def _http(method: str, path: str, key: str, body: dict | None, timeout: int = 120) -> tuple[int, dict | str]:
    url = f"{BASE}{path}"
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                return int(resp.status), json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                return int(resp.status), raw[:500]
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            payload: dict | str = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            payload = raw[:500]
        return int(exc.code), payload
    except Exception as exc:  # noqa: BLE001
        return 0, {"error": str(exc)}


def _err_msg(payload: dict | str) -> str:
    if isinstance(payload, str):
        return payload[:240]
    if not isinstance(payload, dict):
        return str(payload)[:240]
    err = payload.get("error")
    if isinstance(err, dict):
        return str(err.get("message") or err)[:240]
    return str(payload.get("msg") or payload.get("message") or payload)[:240]


def classify(mid: str) -> str:
    low = mid.lower()
    if "seedance" in low:
        return "video"
    if "seedream" in low:
        return "image"
    return "chat"


def test_chat(key: str, mid: str) -> dict:
    t0 = time.time()
    status, payload = _http(
        "POST",
        "/v1/chat/completions",
        key,
        {
            "model": mid,
            "messages": [{"role": "user", "content": "Reply with exactly: OK"}],
            "temperature": 0,
            "max_tokens": 32,
        },
        timeout=180,
    )
    content = ""
    if isinstance(payload, dict):
        content = (((payload.get("choices") or [{}])[0].get("message") or {}).get("content")) or ""
        usage = payload.get("usage") or {}
    else:
        usage = {}
    ok = status == 200 and bool(str(content).strip())
    return {
        "id": mid,
        "kind": "chat",
        "ok": ok,
        "http": status,
        "latency_s": round(time.time() - t0, 2),
        "content": str(content)[:120],
        "usage": usage,
        "error": None if ok else _err_msg(payload),
    }


def test_image(key: str, mid: str) -> dict:
    t0 = time.time()
    status, payload = _http(
        "POST",
        "/v1/images/generations",
        key,
        {
            "model": mid,
            "prompt": "a simple red apple on white background, product photo",
            "size": "1024x1024",
            "n": 1,
        },
        timeout=180,
    )
    url = ""
    if isinstance(payload, dict):
        data = payload.get("data") or []
        if data and isinstance(data[0], dict):
            url = str(data[0].get("url") or data[0].get("b64_json") or "")[:80]
    ok = status == 200 and bool(url)
    return {
        "id": mid,
        "kind": "image",
        "ok": ok,
        "http": status,
        "latency_s": round(time.time() - t0, 2),
        "content": url,
        "usage": {},
        "error": None if ok else _err_msg(payload),
    }


def test_video(key: str, mid: str) -> dict:
    """Seedance is marked task-plugin; probe a few OpenAI-compatible shapes."""
    t0 = time.time()
    attempts: list[dict] = []
    bodies = [
        ("/v1/chat/completions", {"model": mid, "messages": [{"role": "user", "content": "a cat walking"}], "max_tokens": 8}),
        (
            "/v1/videos",
            {"model": mid, "prompt": "a cat walking, 2 seconds"},
        ),
        (
            "/v1/video/generations",
            {"model": mid, "prompt": "a cat walking, 2 seconds"},
        ),
        (
            "/v1/contents/generations/tasks",
            {
                "model": mid,
                "content": [{"type": "text", "text": "a cat walking outdoors, 2s"}],
            },
        ),
    ]
    for path, body in bodies:
        status, payload = _http("POST", path, key, body, timeout=60)
        attempts.append({"path": path, "http": status, "error": _err_msg(payload)})
        if status == 200:
            return {
                "id": mid,
                "kind": "video",
                "ok": True,
                "http": status,
                "latency_s": round(time.time() - t0, 2),
                "content": f"ok via {path}",
                "usage": {},
                "error": None,
                "attempts": attempts,
            }
    return {
        "id": mid,
        "kind": "video",
        "ok": False,
        "http": attempts[-1]["http"] if attempts else 0,
        "latency_s": round(time.time() - t0, 2),
        "content": "",
        "usage": {},
        "error": attempts[-1]["error"] if attempts else "no attempts",
        "attempts": attempts,
    }


def run_one(key: str, mid: str) -> dict:
    kind = classify(mid)
    if kind == "image":
        return test_image(key, mid)
    if kind == "video":
        return test_video(key, mid)
    return test_chat(key, mid)


def main() -> int:
    key = _key()
    status, payload = _http("GET", "/v1/models", key, None, timeout=60)
    if status != 200 or not isinstance(payload, dict):
        print("FAIL list models", status, payload)
        return 1
    models = [m.get("id") for m in (payload.get("data") or []) if isinstance(m, dict) and m.get("id")]
    print(f"models={len(models)} base={BASE}")

    results: list[dict] = []
    # Keep concurrency modest — avoid burning quota / rate limits.
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futs = {pool.submit(run_one, key, mid): mid for mid in models}
        for fut in concurrent.futures.as_completed(futs):
            mid = futs[fut]
            try:
                row = fut.result()
            except Exception as exc:  # noqa: BLE001
                row = {"id": mid, "kind": classify(mid), "ok": False, "http": 0, "error": str(exc)}
            results.append(row)
            mark = "OK" if row.get("ok") else "FAIL"
            print(
                f"[{mark}] {row.get('kind'):5} {row.get('http')} {row.get('latency_s')}s {mid} "
                f"{(row.get('content') or row.get('error') or '')!s}"[:200],
                flush=True,
            )

    results.sort(key=lambda r: (0 if r.get("ok") else 1, r.get("kind") or "", r.get("id") or ""))
    summary = {
        "base": BASE,
        "total": len(results),
        "ok": sum(1 for r in results if r.get("ok")),
        "fail": sum(1 for r in results if not r.get("ok")),
        "by_kind": {},
        "results": results,
    }
    for kind in ("chat", "image", "video"):
        rows = [r for r in results if r.get("kind") == kind]
        summary["by_kind"][kind] = {
            "total": len(rows),
            "ok": sum(1 for r in rows if r.get("ok")),
            "fail": sum(1 for r in rows if not r.get("ok")),
            "failed_ids": [r["id"] for r in rows if not r.get("ok")],
        }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"\nSUMMARY ok={summary['ok']}/{summary['total']} "
        f"chat={summary['by_kind']['chat']} image={summary['by_kind']['image']} video={summary['by_kind']['video']}"
    )
    print(f"wrote {OUT}")
    return 0 if summary["fail"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
