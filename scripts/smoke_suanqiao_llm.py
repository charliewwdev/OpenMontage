#!/usr/bin/env python3
"""Smoke-test 算桥 / 算家云 OpenAI-compatible Chat Completions.

Usage:
  SUANQIAO_API_KEY=sk-... python3 scripts/smoke_suanqiao_llm.py
  # or with Studio secrets / .env already loaded via settings_store
  python3 scripts/smoke_suanqiao_llm.py
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STUDIO = ROOT / "studio"
sys.path.insert(0, str(STUDIO / "server"))


def _load_dotenv() -> None:
    env_path = STUDIO / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, _, v = s.partition("=")
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v


def _secret(name: str, default: str = "") -> str:
    try:
        from settings_store import get_secret

        return (get_secret(name, default) or "").strip()
    except Exception:
        return (os.environ.get(name) or default or "").strip()


def main() -> int:
    _load_dotenv()
    # Prefer Studio catalog wiring
    from providers.llm_catalog import provider_by_id

    meta = provider_by_id("suanqiao")
    assert meta, "suanqiao missing from LLM_PROVIDERS"
    key = _secret(str(meta["keyEnv"]))
    base = (_secret(str(meta["baseEnv"])) or str(meta["defaultBase"])).rstrip("/")
    model = _secret(str(meta["modelEnv"])) or str(meta["defaultModel"])
    if not key:
        print("FAIL: SUANQIAO_API_KEY 未配置（控制台 https://suanjiayun.com/apiUser/ 创建令牌）")
        return 2

    url = f"{base}/chat/completions"
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": "只输出合法 JSON 对象。"},
            {"role": "user", "content": '返回 {"ok":true,"provider":"suanqiao"}'},
        ],
        "temperature": 0,
        "max_tokens": 64,
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
        },
    )
    print(f"POST {url}")
    print(f"model={model}")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:600]
        print(f"FAIL HTTP {exc.code}: {detail}")
        return 1

    content = (((raw.get("choices") or [{}])[0].get("message") or {}).get("content")) or ""
    usage = raw.get("usage") or {}
    print(f"content={content!r}")
    print(f"usage={usage}")
    # Also exercise Studio llm.resolve_provider path
    os.environ["LLM_PROVIDER"] = "suanqiao"
    os.environ["SUANQIAO_API_KEY"] = key
    os.environ["SUANQIAO_BASE_URL"] = base
    os.environ["SUANQIAO_MODEL"] = model
    from providers.llm import chat_json, resolve_provider

    resolved = resolve_provider()
    print(f"resolve_provider={resolved['id']} modelEnv={resolved.get('modelEnv')}")
    data = chat_json(
        system="只输出合法 JSON。",
        user='返回 {"ping":"pong","via":"studio"}',
        temperature=0,
        max_tokens=64,
    )
    print(f"chat_json={data}")
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
