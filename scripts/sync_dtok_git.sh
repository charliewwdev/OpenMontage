#!/usr/bin/env bash
# Sync a Coolify-ready slim tree to git.dtok.io (GitLab), and mirror the full
# local repo HEAD to GitHub main.
#
# Why slim (dtok only): full-history HTTPS push hits HTTP 413 (~76MB pack /
# reverse-proxy body limit). Drama Studio Docker build only needs studio +
# lib/tools/schemas/pipeline_defs/workflow_defs — large demo mp4/bvh are omitted.
#
# GitHub mirror pushes the *full* local commit (not the slim Coolify tree), so
# charliewwdev/OpenMontage keeps normal monorepo history on main.
#
# Usage (from repo root):
#   ./scripts/sync_dtok_git.sh
#   DTOK_GIT_REMOTE=https://git.dtok.io/dtok-app/OpenMontage.git ./scripts/sync_dtok_git.sh
#   GITHUB_MIRROR_SKIP=1 ./scripts/sync_dtok_git.sh          # Coolify only
#   GITHUB_MIRROR_FORCE=1 ./scripts/sync_dtok_git.sh         # force-push main
#   GITHUB_MIRROR_REQUIRED=1 ./scripts/sync_dtok_git.sh      # fail if GitHub push fails
#
# After dtok push, GitLab webhook → Coolify auto-deploys (same pattern as dtok-app).

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REMOTE="${DTOK_GIT_REMOTE:-https://git.dtok.io/dtok-app/OpenMontage.git}"
WORK="${DTOK_SYNC_WORKDIR:-/tmp/om-dtok-slim-sync}"
# Prefer `deploy` — `main` is often protected against force-push on git.dtok.io.
BRANCH="${DTOK_SYNC_BRANCH:-deploy}"
GITHUB_MIRROR_REMOTE="${GITHUB_MIRROR_REMOTE:-}"
GITHUB_MIRROR_BRANCH="${GITHUB_MIRROR_BRANCH:-main}"
GITHUB_MIRROR_SKIP="${GITHUB_MIRROR_SKIP:-0}"
GITHUB_MIRROR_FORCE="${GITHUB_MIRROR_FORCE:-0}"
GITHUB_MIRROR_REQUIRED="${GITHUB_MIRROR_REQUIRED:-0}"
GITHUB_MIRROR_DEFAULT="git@github.com:charliewwdev/OpenMontage.git"

cd "$ROOT"
SHA="$(git rev-parse --short HEAD)"
MSG="$(git log -1 --pretty=%s)"

rm -rf "$WORK"
mkdir -p "$WORK"

git archive HEAD \
  studio lib tools schemas pipeline_defs workflow_defs \
  AGENT_GUIDE.md AGENTS.md CLAUDE.md PROJECT_CONTEXT.md README.md \
  docker-compose.studio.yml scripts/deploy_coolify_drama_studio.sh \
  scripts/coolify_set_drama_keys.sh scripts/sync_dtok_git.sh \
  .gitignore \
  | tar -x -C "$WORK"

# Include uncommitted studio/scripts/config fixes so local WIP can ship without a commit.
rsync -a --delete \
  --exclude node_modules --exclude dist --exclude __pycache__ \
  --exclude '*.mp4' --exclude '*.bvh' --exclude '*.mov' --exclude '*.webm' \
  --exclude npm-debug.log --exclude .DS_Store \
  --exclude '.env' --exclude '.env.*' --exclude '*.env' \
  --exclude '.studio_secrets.json' --exclude '**/.studio_secrets.json' \
  "$ROOT/studio/" "$WORK/studio/"
for rel in scripts/sync_dtok_git.sh scripts/deploy_coolify_drama_studio.sh scripts/coolify_set_drama_keys.sh scripts/baota_set_maintenance.sh docker-compose.studio.yml; do
  [[ -f "$ROOT/$rel" ]] && cp "$ROOT/$rel" "$WORK/$rel"
done
# Ensure edge nginx + maintenance assets ship even if path filters change.
mkdir -p "$WORK/studio/deploy" "$WORK/studio/public"
[[ -f "$ROOT/studio/deploy/nginx-edge.conf" ]] && cp "$ROOT/studio/deploy/nginx-edge.conf" "$WORK/studio/deploy/"
[[ -f "$ROOT/studio/public/maintenance.html" ]] && cp "$ROOT/studio/public/maintenance.html" "$WORK/studio/public/"
# Coolify historically looks for docker-compose.yaml — keep a copy of the studio stack.
cp "$WORK/docker-compose.studio.yml" "$WORK/docker-compose.yaml"

# Not required by studio/Dockerfile; dropping them keeps packs under proxy limits.
find "$WORK" -type f \( -name '*.mp4' -o -name '*.bvh' -o -name '*.mov' -o -name '*.webm' \) -delete

cd "$WORK"
git init -q -b "$BRANCH"
git config user.email "${GIT_AUTHOR_EMAIL:-charlie@dtok.io}"
git config user.name "${GIT_AUTHOR_NAME:-Charlie Wong}"
git add -A
git commit -q -m "$(cat <<EOF
sync: ${SHA} — ${MSG}

Slim Coolify tree from OpenMontage ${SHA} (demo media omitted for git.dtok.io HTTP limits).
EOF
)"

git remote add dtok "$REMOTE"

# Load GitLab PAT from env or local secrets files (never printed).
if [[ -z "${DTOK_GIT_TOKEN:-}" ]]; then
  for cand in \
    "${ROOT}/studio/.env" \
    "${ROOT}/.env" \
    "${HOME}/.config/dtok/gitlab_token" \
    "${HOME}/.config/dtok/DTOK_GIT_TOKEN"
  do
    if [[ -f "$cand" ]]; then
      if [[ "$(basename "$cand")" == "gitlab_token" || "$(basename "$cand")" == "DTOK_GIT_TOKEN" ]]; then
        DTOK_GIT_TOKEN="$(tr -d ' \n\r' < "$cand" || true)"
      else
        DTOK_GIT_TOKEN="$(
          TOKEN_FILE="$cand" python3 - <<'PY'
import os
from pathlib import Path
p = Path(os.environ["TOKEN_FILE"])
for line in p.read_text(errors="ignore").splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    k, _, v = line.partition("=")
    if k.strip() in {"DTOK_GIT_TOKEN", "GITLAB_TOKEN", "GITLAB_PAT"}:
        print(v.strip().strip('"').strip("'"))
        break
PY
        )"
      fi
      [[ -n "${DTOK_GIT_TOKEN:-}" ]] && break
    fi
  done
fi

API="https://git.dtok.io/api/v4/projects/dtok-app%2FOpenMontage"

# deploy/main are often protected against force-push; temporarily unprotect when we have a PAT.
if [[ -n "${DTOK_GIT_TOKEN:-}" ]]; then
  echo "==> Unprotecting ${BRANCH} for force-push (PAT present)"
  curl -fsS -X DELETE -H "PRIVATE-TOKEN: ${DTOK_GIT_TOKEN}" \
    "${API}/protected_branches/${BRANCH}" >/dev/null 2>&1 || true
else
  echo "WARN: DTOK_GIT_TOKEN unset — if ${BRANCH} is protected, push will fail."
  echo "      export DTOK_GIT_TOKEN='glpat-…'  # api + write_repository"
fi

SLIM_SHA="$(git rev-parse HEAD)"

echo "==> Force-pushing slim tree to ${REMOTE} (${BRANCH})"
if ! git -c http.postBuffer=524288000 push -f dtok "HEAD:${BRANCH}"; then
  echo "ERROR: git push to ${REMOTE} ${BRANCH} failed." >&2
  if [[ -z "${DTOK_GIT_TOKEN:-}" ]]; then
    echo "HINT: set DTOK_GIT_TOKEN (GitLab PAT) so this script can unprotect ${BRANCH}." >&2
  fi
  exit 1
fi

if [[ -n "${DTOK_GIT_TOKEN:-}" ]]; then
  curl -fsS -X POST -H "PRIVATE-TOKEN: ${DTOK_GIT_TOKEN}" -H 'Content-Type: application/json' \
    -d "{\"name\":\"${BRANCH}\",\"push_access_level\":40,\"merge_access_level\":40,\"allow_force_push\":false}" \
    "${API}/protected_branches" >/dev/null 2>&1 || true
fi

# Belt-and-suspenders: GitLab project webhook should fire on push to ${BRANCH}.
# Also ping Coolify directly when COOLIFY_GITLAB_WEBHOOK_SECRET is set (same secret as Coolify → Webhooks → GitLab).
if [[ -n "${COOLIFY_GITLAB_WEBHOOK_SECRET:-}" ]]; then
  WH_URL="${COOLIFY_GITLAB_WEBHOOK_URL:-http://66.29.128.32:8000/webhooks/source/gitlab/events/manual}"
  echo "==> Triggering Coolify GitLab webhook (${BRANCH})"
  curl -fsS -X POST "$WH_URL" \
    -H "Content-Type: application/json" \
    -H "X-Gitlab-Token: ${COOLIFY_GITLAB_WEBHOOK_SECRET}" \
    -H "X-Gitlab-Event: Push Hook" \
    -d "$(python3 - <<PY
import json
print(json.dumps({
  "object_kind": "push",
  "event_name": "push",
  "ref": "refs/heads/${BRANCH}",
  "checkout_sha": "${SLIM_SHA}",
  "project": {
    "id": 1,
    "name": "OpenMontage",
    "path_with_namespace": "dtok-app/OpenMontage",
    "git_http_url": "https://git.dtok.io/dtok-app/OpenMontage.git",
    "http_url": "https://git.dtok.io/dtok-app/OpenMontage.git",
    "web_url": "https://git.dtok.io/dtok-app/OpenMontage",
  },
  "repository": {
    "name": "OpenMontage",
    "git_http_url": "https://git.dtok.io/dtok-app/OpenMontage.git",
    "url": "https://git.dtok.io/dtok-app/OpenMontage.git",
    "homepage": "https://git.dtok.io/dtok-app/OpenMontage",
  },
  "commits": [{"id": "${SLIM_SHA}", "message": "sync: ${SHA}", "url": "https://git.dtok.io/dtok-app/OpenMontage/-/commit/${SLIM_SHA}"}],
  "total_commits_count": 1,
}))
PY
)" >/dev/null && echo "OK Coolify webhook accepted" || echo "WARN Coolify webhook call failed (GitLab push hook may still deploy)"
fi

echo "OK synced ${SHA} → ${REMOTE} ${BRANCH}"
echo "Coolify auto-deploys via GitLab webhook on push to ${BRANCH}."

# --- GitHub mirror (full local HEAD → main; never the slim Coolify pack) ---
mirror_github() {
  if [[ "${GITHUB_MIRROR_SKIP}" == "1" ]]; then
    echo "==> GitHub mirror skipped (GITHUB_MIRROR_SKIP=1)"
    return 0
  fi

  local gh_remote="${GITHUB_MIRROR_REMOTE}"
  if [[ -z "${gh_remote}" ]]; then
    if git -C "$ROOT" remote get-url github >/dev/null 2>&1; then
      gh_remote="$(git -C "$ROOT" remote get-url github)"
    elif git -C "$ROOT" remote get-url origin >/dev/null 2>&1; then
      local origin_url
      origin_url="$(git -C "$ROOT" remote get-url origin)"
      case "${origin_url}" in
        *github.com*) gh_remote="${origin_url}" ;;
        *) gh_remote="${GITHUB_MIRROR_DEFAULT}" ;;
      esac
    else
      gh_remote="${GITHUB_MIRROR_DEFAULT}"
    fi
  fi

  # Optional HTTPS PAT: GITHUB_TOKEN → https://x-access-token:…@github.com/...
  if [[ -n "${GITHUB_TOKEN:-}" && "${gh_remote}" == git@github.com:* ]]; then
    local path="${gh_remote#git@github.com:}"
    path="${path%.git}.git"
    gh_remote="https://x-access-token:${GITHUB_TOKEN}@github.com/${path}"
  elif [[ -n "${GITHUB_TOKEN:-}" && "${gh_remote}" == https://github.com/* ]]; then
    local path="${gh_remote#https://github.com/}"
    gh_remote="https://x-access-token:${GITHUB_TOKEN}@github.com/${path}"
  fi

  local full_sha
  full_sha="$(git -C "$ROOT" rev-parse --short HEAD)"
  # Hide token in logs if present
  local push_url="${gh_remote}"
  if [[ "${push_url}" == https://x-access-token:*@github.com/* ]]; then
    push_url="https://github.com/${push_url#*@github.com/}"
  fi
  echo "==> Mirroring full repo ${full_sha} → ${push_url} (${GITHUB_MIRROR_BRANCH})"

  local -a push_args=(-C "$ROOT" push)
  if [[ "${GITHUB_MIRROR_FORCE}" == "1" ]]; then
    push_args+=(-f)
  fi
  push_args+=("${gh_remote}" "HEAD:${GITHUB_MIRROR_BRANCH}")

  if git "${push_args[@]}"; then
    echo "OK mirrored ${full_sha} → GitHub ${GITHUB_MIRROR_BRANCH}"
    echo "NOTE: GitHub gets committed HEAD only; uncommitted WIP still ships on dtok slim deploy."
    return 0
  fi
  echo "WARN GitHub mirror failed (Coolify deploy already pushed to dtok)."
  return 1
}

if ! mirror_github; then
  if [[ "${GITHUB_MIRROR_REQUIRED}" == "1" ]]; then
    echo "ERROR GITHUB_MIRROR_REQUIRED=1 and GitHub push failed"
    exit 1
  fi
fi

# Project state + media blobs dual-write to Postgres (drama-db / drama_pg volume).
# Disk under drama_projects is a cache; avoid Coolify "Remove volumes" on drama_pg.
echo "NOTE: Projects + media + secrets/credits persist in Postgres (drama_pg). Disk is cache."
STUDIO_URL="${STUDIO_URL:-https://openmontage.dtok.io}"

# Edge proxy (宝塔): branded standby instead of white nginx 502 during Coolify swaps.
if [[ -f "$ROOT/studio/.env" ]]; then
  while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line%$'\r'}"
    case "$line" in
      \#*|"") continue ;;
      BT_PANEL_URL=*|BT_PANEL_USER=*|BT_PANEL_PASS=*|SITE_NAME=*|MAINTENANCE_UPSTREAM=*)
        key="${line%%=*}"
        val="${line#*=}"
        val="${val%\"}"; val="${val#\"}"
        val="${val%\'}"; val="${val#\'}"
        export "${key}=${val}"
        ;;
    esac
  done < "$ROOT/studio/.env"
fi
if [[ -n "${BT_PANEL_URL:-}" && -n "${BT_PANEL_USER:-}" && -n "${BT_PANEL_PASS:-}" ]]; then
  echo "==> Installing edge maintenance page on ${SITE_NAME:-openmontage.dtok.io}"
  "$ROOT/scripts/baota_set_maintenance.sh" || echo "WARN baota maintenance install failed"
fi

if [[ -f "$ROOT/studio/.env" && -f "$ROOT/scripts/restore_studio_keys.sh" ]]; then
  echo "==> Waiting for ${STUDIO_URL}/api/health then restoring keys from studio/.env"
  ok=0
  for i in $(seq 1 36); do
    if curl -fsS --max-time 8 "${STUDIO_URL}/api/health" >/dev/null 2>&1; then
      ok=1
      break
    fi
    sleep 5
  done
  if [[ "$ok" -eq 1 ]]; then
    # Extra settle time after health flips during rolling deploy
    sleep 8
    STUDIO_URL="$STUDIO_URL" "$ROOT/scripts/restore_studio_keys.sh" || echo "WARN key restore failed (UI can still paste keys)"
  else
    echo "WARN ${STUDIO_URL} not healthy yet — run: STUDIO_URL=${STUDIO_URL} ./scripts/restore_studio_keys.sh"
  fi
fi
