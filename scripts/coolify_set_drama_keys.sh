#!/usr/bin/env bash
# Upsert Drama Studio keys on the Coolify app (survives redeploys).
#
#   export COOLIFY_TOKEN='...'           # write scope
#   export COOLIFY_APP_UUID='x096iqdmsnez39b4sp6bbaan'
#   # optional exports, else reads studio/.env:
#   export DEEPSEEK_API_KEY='...' GPUHOME_API_KEY='...' CURSOR_API_KEY='...' VOLCENGINE_API_KEY='...'
#   ./scripts/coolify_set_drama_keys.sh

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
COOLIFY_URL="${COOLIFY_URL:-https://cicd.dtok.io}"
COOLIFY_TOKEN="${COOLIFY_TOKEN:?set COOLIFY_TOKEN}"
COOLIFY_APP_UUID="${COOLIFY_APP_UUID:-x096iqdmsnez39b4sp6bbaan}"
UA="${COOLIFY_UA:-Mozilla/5.0 OpenMontage-drama-studio}"
ENV_FILE="${ENV_FILE:-$ROOT/studio/.env}"

export COOLIFY_URL COOLIFY_TOKEN COOLIFY_APP_UUID UA ENV_FILE
export VOLCENGINE_API_KEY="${VOLCENGINE_API_KEY:-${ARK_API_KEY:-}}"
export DEEPSEEK_API_KEY="${DEEPSEEK_API_KEY:-}"
export DEEPSEEK_BASE_URL="${DEEPSEEK_BASE_URL:-https://api.deepseek.com}"
export DEEPSEEK_MODEL="${DEEPSEEK_MODEL:-deepseek-chat}"
export GPUHOME_API_KEY="${GPUHOME_API_KEY:-}"
export GPUHOME_BASE_URL="${GPUHOME_BASE_URL:-https://tokens.gpuhome.cc/v1}"
export GPUHOME_MODEL="${GPUHOME_MODEL:-deepseek-v4-flash}"
export COMFYUI_SERVER_URL="${COMFYUI_SERVER_URL:-}"
export ARK_API_KEY="${ARK_API_KEY:-}"
export CURSOR_API_KEY="${CURSOR_API_KEY:-}"
export CURSOR_API_BASE="${CURSOR_API_BASE:-https://api.cursor.com}"
export CURSOR_MODEL="${CURSOR_MODEL:-auto}"
export LLM_PROVIDER="${LLM_PROVIDER:-}"
export STUDIO_PUBLIC_URL="${STUDIO_PUBLIC_URL:-https://openmontage.dtok.io}"

python3 - <<'PY'
import json, os, urllib.request
from pathlib import Path

env_file = Path(os.environ.get("ENV_FILE") or "")
file_vals = {}
if env_file.is_file():
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k and v:
            file_vals[k] = v

def pick(name: str, default: str = "") -> str:
    return (os.environ.get(name) or file_vals.get(name) or default or "").strip()

base = os.environ["COOLIFY_URL"].rstrip("/")
tok = os.environ["COOLIFY_TOKEN"]
app = os.environ["COOLIFY_APP_UUID"]
ua = os.environ.get("UA", "Mozilla/5.0 OpenMontage-drama-studio")

def api(method, path, data=None):
    body = None if data is None else json.dumps(data).encode()
    req = urllib.request.Request(
        base + path,
        data=body,
        method=method,
        headers={
            "Authorization": f"Bearer {tok}",
            "User-Agent": ua,
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        raw = r.read().decode() or "{}"
        return json.loads(raw)

envs = api("GET", f"/api/v1/applications/{app}/envs")
by_key = {e["key"]: e for e in envs}

volc = pick("VOLCENGINE_API_KEY") or pick("ARK_API_KEY")
llm_provider = pick("LLM_PROVIDER")
if not llm_provider:
    if pick("GPUHOME_API_KEY"):
        llm_provider = "gpuhome"
    elif pick("DEEPSEEK_API_KEY"):
        llm_provider = "deepseek"
    elif pick("CURSOR_API_KEY"):
        llm_provider = "cursor"

pairs = [
    ("GPUHOME_API_KEY", pick("GPUHOME_API_KEY")),
    ("GPUHOME_BASE_URL", pick("GPUHOME_BASE_URL", "https://tokens.gpuhome.cc/v1")),
    ("GPUHOME_MODEL", pick("GPUHOME_MODEL", "deepseek-v4-flash")),
    ("COMFYUI_SERVER_URL", pick("COMFYUI_SERVER_URL")),
    ("DEEPSEEK_API_KEY", pick("DEEPSEEK_API_KEY")),
    ("DEEPSEEK_BASE_URL", pick("DEEPSEEK_BASE_URL", "https://api.deepseek.com")),
    ("DEEPSEEK_MODEL", pick("DEEPSEEK_MODEL", "deepseek-chat")),
    ("CURSOR_API_KEY", pick("CURSOR_API_KEY")),
    ("CURSOR_API_BASE", pick("CURSOR_API_BASE", "https://api.cursor.com")),
    ("CURSOR_MODEL", pick("CURSOR_MODEL", "auto")),
    ("LLM_PROVIDER", llm_provider),
    ("VOLCENGINE_API_KEY", volc),
    ("NVIDIA_API_KEY", pick("NVIDIA_API_KEY")),
    ("NVIDIA_IMAGE_MODEL", pick("NVIDIA_IMAGE_MODEL", "flux.1-schnell")),
    ("ARK_API_KEY", pick("ARK_API_KEY") or volc),
    ("STUDIO_PUBLIC_URL", pick("STUDIO_PUBLIC_URL", "https://openmontage.dtok.io")),
    ("OSS_API_BASE_URL", pick("OSS_API_BASE_URL", "https://minio-api.dtok.io")),
    ("OSS_CONSOLE_USERNAME", pick("OSS_CONSOLE_USERNAME") or pick("MINIO_ACCESS_KEY")),
    ("OSS_CONSOLE_PASSWORD", pick("OSS_CONSOLE_PASSWORD") or pick("MINIO_SECRET_KEY")),
    ("MINIO_BUCKET", pick("MINIO_BUCKET", "dtok-app")),
    ("MINIO_PREFIX", pick("MINIO_PREFIX", "openmontage")),
]

secret_keys = {
    "GPUHOME_API_KEY",
    "DEEPSEEK_API_KEY",
    "CURSOR_API_KEY",
    "VOLCENGINE_API_KEY",
    "NVIDIA_API_KEY",
    "ARK_API_KEY",
    "OSS_CONSOLE_PASSWORD",
    "OSS_CONSOLE_USERNAME",
}

for key, val in pairs:
    if not val and key in secret_keys:
        print(f"skip empty {key}")
        continue
    if not val and key == "LLM_PROVIDER":
        print(f"skip empty {key}")
        continue
    payload = {
        "key": key,
        "value": val,
        "is_preview": False,
        "is_literal": True,
    }
    if key in by_key:
        try:
            api("PATCH", f"/api/v1/applications/{app}/envs", payload)
            print(f"updated {key}")
            continue
        except Exception:
            pass
    try:
        api("POST", f"/api/v1/applications/{app}/envs", payload)
        print(f"created {key}")
    except Exception as exc:
        print(f"failed {key}: {exc}")

dep = api("POST", f"/api/v1/deploy?uuid={app}&force=false")
print("deploy", dep["deployments"][0]["deployment_uuid"])
print("Verify: curl -fsS https://openmontage.dtok.io/api/health")
print("After deploy also run: ./scripts/restore_studio_keys.sh")
PY
