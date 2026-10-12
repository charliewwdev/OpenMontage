#!/usr/bin/env bash
# Upsert DeepSeek / Volcengine keys on the Coolify Drama Studio app.
#
#   export COOLIFY_TOKEN='...'           # write scope
#   export COOLIFY_APP_UUID='x096iqdmsnez39b4sp6bbaan'  # or your uuid
#   export DEEPSEEK_API_KEY='...'
#   export VOLCENGINE_API_KEY='...'      # or ARK_API_KEY
#   ./scripts/coolify_set_drama_keys.sh

set -euo pipefail

COOLIFY_URL="${COOLIFY_URL:-https://cicd.dtok.io}"
COOLIFY_TOKEN="${COOLIFY_TOKEN:?set COOLIFY_TOKEN}"
COOLIFY_APP_UUID="${COOLIFY_APP_UUID:?set COOLIFY_APP_UUID}"
UA="${COOLIFY_UA:-Mozilla/5.0 OpenMontage-drama-studio}"

VOLC="${VOLCENGINE_API_KEY:-${ARK_API_KEY:-}}"

upsert() {
  local key="$1" val="$2"
  [[ -z "$val" ]] && { echo "skip empty $key"; return 0; }
  local payload
  payload=$(KEY="$key" VAL="$val" python3 -c 'import json,os; print(json.dumps({"key":os.environ["KEY"],"value":os.environ["VAL"],"is_preview":False,"is_build_time":False,"is_literal":True,"is_shown_once":False}))')
  # try update then create
  if ! curl -fsS -X PATCH \
      -H "Authorization: Bearer ${COOLIFY_TOKEN}" \
      -H "User-Agent: ${UA}" \
      -H "Accept: application/json" \
      -H "Content-Type: application/json" \
      -d "$payload" \
      "${COOLIFY_URL}/api/v1/applications/${COOLIFY_APP_UUID}/envs" >/dev/null 2>&1; then
    curl -fsS -X POST \
      -H "Authorization: Bearer ${COOLIFY_TOKEN}" \
      -H "User-Agent: ${UA}" \
      -H "Accept: application/json" \
      -H "Content-Type: application/json" \
      -d "$payload" \
      "${COOLIFY_URL}/api/v1/applications/${COOLIFY_APP_UUID}/envs" >/dev/null
  fi
  echo "set $key"
}

upsert DEEPSEEK_API_KEY "${DEEPSEEK_API_KEY:-}"
upsert DEEPSEEK_BASE_URL "${DEEPSEEK_BASE_URL:-https://api.deepseek.com}"
upsert DEEPSEEK_MODEL "${DEEPSEEK_MODEL:-deepseek-chat}"
upsert VOLCENGINE_API_KEY "$VOLC"
upsert ARK_API_KEY "${ARK_API_KEY:-$VOLC}"
upsert STUDIO_PUBLIC_URL "${STUDIO_PUBLIC_URL:-https://openmontage.dtok.io}"

echo "==> Trigger redeploy"
RESP=$(curl -fsS -X POST \
  -H "Authorization: Bearer ${COOLIFY_TOKEN}" \
  -H "User-Agent: ${UA}" \
  -H "Accept: application/json" \
  "${COOLIFY_URL}/api/v1/deploy?uuid=${COOLIFY_APP_UUID}&force=false")
echo "$RESP"
echo "Done. Verify: curl -fsS https://openmontage.dtok.io/api/health"
