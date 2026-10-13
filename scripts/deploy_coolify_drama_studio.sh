#!/usr/bin/env bash
# Create or redeploy OpenMontage Drama Studio on Coolify (cicd.dtok.io).
#
# Requires a Coolify API token with WRITE permission:
#   export COOLIFY_TOKEN='...'
# Optional:
#   export COOLIFY_URL='https://cicd.dtok.io'   # or http://66.29.128.32:8000
#   export STUDIO_DOMAIN='https://openmontage.dtok.io'
#   export COOLIFY_APP_UUID='...'  # if set, only trigger deploy (skip create)
#
# Usage:
#   ./scripts/deploy_coolify_drama_studio.sh

set -euo pipefail

COOLIFY_URL="${COOLIFY_URL:-https://cicd.dtok.io}"
COOLIFY_TOKEN="${COOLIFY_TOKEN:?set COOLIFY_TOKEN with write scope}"
COOLIFY_PROJECT_UUID="${COOLIFY_PROJECT_UUID:-fkcockcs4s8os4c8s4go48w4}"
COOLIFY_SERVER_UUID="${COOLIFY_SERVER_UUID:-y0o8w0wwwgco004wsg4k0sg4}"
COOLIFY_ENV_UUID="${COOLIFY_ENV_UUID:-gwsgws48s0gg8ww804wocc08}"
DESTINATION_UUID="${DESTINATION_UUID:-h88ggkc80s8g4s040o080c8s}"
# Prefer git.dtok.io (GitLab). Full push may 413 — use scripts/sync_dtok_git.sh for slim sync.
GIT_REPO="${GIT_REPO:-https://git.dtok.io/dtok-app/OpenMontage.git}"
GIT_BRANCH="${GIT_BRANCH:-main}"
STUDIO_DOMAIN="${STUDIO_DOMAIN:-}"
UA="${COOLIFY_UA:-Mozilla/5.0 OpenMontage-drama-studio}"
APP_NAME="${APP_NAME:-openmontage-drama-studio}"

api() {
  local method="$1" path="$2"
  shift 2
  curl -fsS -X "$method" \
    -H "Authorization: Bearer ${COOLIFY_TOKEN}" \
    -H "User-Agent: ${UA}" \
    -H "Accept: application/json" \
    -H "Content-Type: application/json" \
    "$@" \
    "${COOLIFY_URL}${path}"
}

poll_deploy() {
  local dep_uuid="$1"
  echo "==> Polling deployment ${dep_uuid}"
  local i status
  for i in $(seq 1 80); do
    status=$(api GET "/api/v1/deployments/${dep_uuid}" | python3 -c "import json,sys; print(json.load(sys.stdin).get('status',''))")
    echo "  [$i] $status"
    case "$status" in
      finished)
        echo "OK deployed"
        return 0
        ;;
      failed|error-ing|cancelled)
        echo "Deploy failed: $status" >&2
        return 1
        ;;
    esac
    sleep 15
  done
  echo "Timed out waiting for Coolify" >&2
  return 1
}

echo "==> Coolify ${COOLIFY_URL}"

if [[ -z "${COOLIFY_APP_UUID:-}" ]]; then
  echo "==> Creating public application ${APP_NAME}"
  CREATE_PAYLOAD=$(COOLIFY_PROJECT_UUID="$COOLIFY_PROJECT_UUID" \
    COOLIFY_SERVER_UUID="$COOLIFY_SERVER_UUID" \
    COOLIFY_ENV_UUID="$COOLIFY_ENV_UUID" \
    DESTINATION_UUID="$DESTINATION_UUID" \
    GIT_REPO="$GIT_REPO" \
    GIT_BRANCH="$GIT_BRANCH" \
    APP_NAME="$APP_NAME" \
    STUDIO_DOMAIN="$STUDIO_DOMAIN" \
    python3 - <<'PY'
import json, os
body = {
  "project_uuid": os.environ["COOLIFY_PROJECT_UUID"],
  "server_uuid": os.environ["COOLIFY_SERVER_UUID"],
  "environment_uuid": os.environ["COOLIFY_ENV_UUID"],
  "destination_uuid": os.environ["DESTINATION_UUID"],
  "git_repository": os.environ["GIT_REPO"],
  "git_branch": os.environ["GIT_BRANCH"],
  "build_pack": "dockerfile",
  "ports_exposes": "8787",
  "name": os.environ["APP_NAME"],
  "description": "OpenMontage Drama Studio",
  "dockerfile_location": "/studio/Dockerfile",
  "base_directory": "/",
  "health_check_enabled": True,
  "health_check_path": "/api/health",
  "health_check_port": "8787",
  "health_check_method": "GET",
  "health_check_return_code": 200,
  "is_auto_deploy_enabled": True,
  "is_force_https_enabled": True,
  "is_git_lfs_enabled": False,
  "is_git_submodules_enabled": False,
  "watch_paths": "studio/**,docker-compose.studio.yml,lib/**,tools/pipeline/**,pipeline_defs/short-drama.yaml,workflow_defs/**,projects/midnight-sms-ep01/**",
  "instant_deploy": True,
  "autogenerate_domain": True,
}
domain = os.environ.get("STUDIO_DOMAIN") or ""
if domain:
  body["domains"] = domain
  body["autogenerate_domain"] = False
print(json.dumps(body))
PY
)
  RESP=$(api POST /api/v1/applications/public -d "$CREATE_PAYLOAD")
  echo "$RESP" | python3 -m json.tool | head -80
  COOLIFY_APP_UUID=$(echo "$RESP" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('uuid') or d.get('application_uuid') or '')")
  if [[ -z "$COOLIFY_APP_UUID" ]]; then
    echo "ERROR: create did not return uuid" >&2
    exit 1
  fi
  echo "==> Created app uuid=${COOLIFY_APP_UUID}"

  echo "==> Setting environment variables"
  PUBLIC_URL="${STUDIO_DOMAIN:-https://openmontage.dtok.io}"
  while IFS='=' read -r key val; do
    [[ -z "$key" ]] && continue
    payload=$(KEY="$key" VAL="$val" python3 -c 'import json,os; print(json.dumps({"key":os.environ["KEY"],"value":os.environ["VAL"],"is_preview":False,"is_build_time":False,"is_literal":True,"is_shown_once":False}))')
    api POST "/api/v1/applications/${COOLIFY_APP_UUID}/envs" -d "$payload" >/dev/null || true
    echo "  set $key"
  done <<EOF
HOST=0.0.0.0
PORT=8787
OPENMONTAGE_ROOT=/app
PROJECTS_ROOT=/data/projects
STUDIO_DIST=/app/studio/dist
API_BASE_URL=https://api-app.dtok.io/api/v1
STUDIO_PUBLIC_URL=${PUBLIC_URL}
DEEPSEEK_API_KEY=${DEEPSEEK_API_KEY:-}
DEEPSEEK_BASE_URL=${DEEPSEEK_BASE_URL:-https://api.deepseek.com}
DEEPSEEK_MODEL=${DEEPSEEK_MODEL:-deepseek-chat}
VOLCENGINE_API_KEY=${VOLCENGINE_API_KEY:-${ARK_API_KEY:-}}
ARK_API_KEY=${ARK_API_KEY:-${VOLCENGINE_API_KEY:-}}
EOF

  # instant_deploy already requested; try to discover latest deployment
  sleep 3
else
  echo "==> Using existing app uuid=${COOLIFY_APP_UUID}"
  echo "==> Triggering deploy"
  RESP=$(api POST "/api/v1/deploy?uuid=${COOLIFY_APP_UUID}&force=false")
  echo "$RESP"
  DEP_UUID=$(echo "$RESP" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['deployments'][0]['deployment_uuid'])")
  poll_deploy "$DEP_UUID"
fi

APP=$(api GET "/api/v1/applications/${COOLIFY_APP_UUID}")
echo "$APP" | python3 -c "import json,sys; d=json.load(sys.stdin); print('name:', d.get('name')); print('fqdn:', d.get('fqdn')); print('uuid:', d.get('uuid')); print('auto_deploy:', (d.get('settings') or {}).get('is_auto_deploy_enabled'))"
echo
echo "Save for CI / later redeploys:"
echo "  export COOLIFY_APP_UUID=${COOLIFY_APP_UUID}"
echo "  export COOLIFY_TOKEN=***"
echo "Health: curl -fsS \"\$FQDN/api/health\""
