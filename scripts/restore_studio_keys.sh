#!/usr/bin/env bash
# Push local studio/.env LLM / Volc keys to a running Drama Studio (survives ephemeral volumes).
# Never prints secret values.
#
#   STUDIO_URL=https://openmontage.dtok.io ./scripts/restore_studio_keys.sh
#   ENV_FILE=studio/.env ./scripts/restore_studio_keys.sh

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STUDIO_URL="${STUDIO_URL:-https://openmontage.dtok.io}"
ENV_FILE="${ENV_FILE:-$ROOT/studio/.env}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "skip restore: no $ENV_FILE"
  exit 0
fi

export STUDIO_URL ENV_FILE
python3 <<'PY'
import json, os, urllib.error, urllib.request
from pathlib import Path

env_file = Path(os.environ["ENV_FILE"])
base = os.environ["STUDIO_URL"].rstrip("/")
vals = {}
for line in env_file.read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    k, _, v = line.partition("=")
    k, v = k.strip(), v.strip().strip('"').strip("'")
    if k and v:
        vals[k] = v

wanted = [
    "LLM_PROVIDER",
    "GPUHOME_API_KEY", "GPUHOME_BASE_URL", "GPUHOME_MODEL",
    "COMFYUI_SERVER_URL", "COMFYUI_IMAGE_SERVER_URL", "COMFYUI_VIDEO_SERVER_URL",
    "CURSOR_API_KEY", "CURSOR_API_BASE", "CURSOR_MODEL",
    "DEEPSEEK_API_KEY", "DEEPSEEK_BASE_URL", "DEEPSEEK_MODEL",
    "OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_MODEL",
    "ANTHROPIC_API_KEY", "ANTHROPIC_BASE_URL", "ANTHROPIC_MODEL",
    "GEMINI_API_KEY", "GEMINI_BASE_URL", "GEMINI_MODEL",
    "DASHSCOPE_API_KEY", "DASHSCOPE_BASE_URL", "QWEN_MODEL",
    "MOONSHOT_API_KEY", "MOONSHOT_BASE_URL", "MOONSHOT_MODEL",
    "VOLCENGINE_API_KEY", "ARK_API_KEY", "ARK_API_BASE", "VOLCENGINE_API_BASE",
    "ARK_PLAN", "AGENT_PLAN_TIER", "SEEDREAM_MODEL", "SEEDANCE_MODEL",
]
payload = {k: vals[k] for k in wanted if vals.get(k)}
if not payload:
    print("skip restore: no usable keys in env file")
    raise SystemExit(0)
if not payload.get("LLM_PROVIDER"):
    if "GPUHOME_API_KEY" in payload:
        payload["LLM_PROVIDER"] = "gpuhome"
    elif "DEEPSEEK_API_KEY" in payload:
        payload["LLM_PROVIDER"] = "deepseek"
    elif "CURSOR_API_KEY" in payload:
        payload["LLM_PROVIDER"] = "cursor"

ops = (
    os.environ.get("STUDIO_OPS_TOKEN")
    or os.environ.get("STUDIO_DEMO_SECRET")
    or vals.get("STUDIO_OPS_TOKEN")
    or vals.get("STUDIO_DEMO_SECRET")
    or "openmontage-demo-local"
).strip()
req = urllib.request.Request(
    f"{base}/api/settings/keys",
    data=json.dumps(payload).encode("utf-8"),
    method="POST",
    headers={
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-Studio-Ops-Token": ops,
    },
)
try:
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8") or "{}")
except urllib.error.URLError as exc:
    print(f"WARN restore keys failed: {exc}")
    raise SystemExit(1)

keys = data.get("keys") or {}
print(
    "OK restored keys →",
    base,
    "| backend=",
    keys.get("llmBackend"),
    "| cursor=",
    bool((keys.get("cursor") or {}).get("configured")),
    "| llmReady=",
    keys.get("llmReady"),
    "| uploaded=",
    ",".join(sorted(payload.keys())),
)
PY
