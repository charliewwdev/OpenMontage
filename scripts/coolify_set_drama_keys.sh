#!/usr/bin/env bash
# Upsert DeepSeek / Volcengine keys on the Coolify Drama Studio app.
#
#   export COOLIFY_TOKEN='...'           # write scope
#   export COOLIFY_APP_UUID='x096iqdmsnez39b4sp6bbaan'
#   export DEEPSEEK_API_KEY='...'
#   export VOLCENGINE_API_KEY='...'      # or ARK_API_KEY
#   ./scripts/coolify_set_drama_keys.sh

set -euo pipefail

COOLIFY_URL="${COOLIFY_URL:-https://cicd.dtok.io}"
COOLIFY_TOKEN="${COOLIFY_TOKEN:?set COOLIFY_TOKEN}"
COOLIFY_APP_UUID="${COOLIFY_APP_UUID:-x096iqdmsnez39b4sp6bbaan}"
UA="${COOLIFY_UA:-Mozilla/5.0 OpenMontage-drama-studio}"
export COOLIFY_URL COOLIFY_TOKEN COOLIFY_APP_UUID
export VOLC="${VOLCENGINE_API_KEY:-${ARK_API_KEY:-}}"
export DEEPSEEK_API_KEY="${DEEPSEEK_API_KEY:-}"
export DEEPSEEK_BASE_URL="${DEEPSEEK_BASE_URL:-https://api.deepseek.com}"
export DEEPSEEK_MODEL="${DEEPSEEK_MODEL:-deepseek-chat}"
export ARK_API_KEY="${ARK_API_KEY:-}"
export STUDIO_PUBLIC_URL="${STUDIO_PUBLIC_URL:-https://openmontage.dtok.io}"

python3 - <<'PY'
import json, os, urllib.request

base = os.environ["COOLIFY_URL"].rstrip("/")
tok = os.environ["COOLIFY_TOKEN"]
app = os.environ["COOLIFY_APP_UUID"]
ua = os.environ.get("COOLIFY_UA", "Mozilla/5.0 OpenMontage-drama-studio")

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

pairs = [
    ("DEEPSEEK_API_KEY", os.environ.get("DEEPSEEK_API_KEY") or ""),
    ("DEEPSEEK_BASE_URL", os.environ.get("DEEPSEEK_BASE_URL") or "https://api.deepseek.com"),
    ("DEEPSEEK_MODEL", os.environ.get("DEEPSEEK_MODEL") or "deepseek-chat"),
    ("VOLCENGINE_API_KEY", os.environ.get("VOLC") or ""),
    ("ARK_API_KEY", os.environ.get("ARK_API_KEY") or os.environ.get("VOLC") or ""),
    ("STUDIO_PUBLIC_URL", os.environ.get("STUDIO_PUBLIC_URL") or "https://openmontage.dtok.io"),
]

for key, val in pairs:
    if not val and key in ("DEEPSEEK_API_KEY", "VOLCENGINE_API_KEY", "ARK_API_KEY"):
        print(f"skip empty {key}")
        continue
    payload = {
        "key": key,
        "value": val,
        "is_preview": False,
        "is_literal": True,
    }
    if key in by_key:
        euuid = by_key[key].get("uuid")
        api("PATCH", f"/api/v1/applications/{app}/envs/{euuid}", payload)
        print(f"updated {key}")
    else:
        api("POST", f"/api/v1/applications/{app}/envs", payload)
        print(f"created {key}")

dep = api("POST", f"/api/v1/deploy?uuid={app}&force=false")
print("deploy", dep["deployments"][0]["deployment_uuid"])
print("Verify: curl -fsS https://openmontage.dtok.io/api/health")
PY
