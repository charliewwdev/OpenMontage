#!/usr/bin/env bash
# Sync a Coolify-ready slim tree to git.dtok.io (GitLab).
#
# Why slim: full-history HTTPS push hits HTTP 413 (~76MB pack / reverse-proxy
# body limit). Drama Studio Docker build only needs studio + lib/tools/schemas/
# pipeline_defs/workflow_defs — large demo mp4/bvh are omitted.
#
# Usage (from repo root):
#   ./scripts/sync_dtok_git.sh
#   DTOK_GIT_REMOTE=https://git.dtok.io/dtok-app/OpenMontage.git ./scripts/sync_dtok_git.sh
#
# After push, GitLab webhook → Coolify auto-deploys (same pattern as dtok-app).

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REMOTE="${DTOK_GIT_REMOTE:-https://git.dtok.io/dtok-app/OpenMontage.git}"
WORK="${DTOK_SYNC_WORKDIR:-/tmp/om-dtok-slim-sync}"
BRANCH="${DTOK_SYNC_BRANCH:-main}"

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

# main is protected against force-push; temporarily unprotect if needed.
# Prefer: DTOK_GIT_TOKEN (GitLab PAT with api+write_repository) for unprotect/reprotect.
if [[ -n "${DTOK_GIT_TOKEN:-}" ]]; then
  API="https://git.dtok.io/api/v4/projects/dtok-app%2FOpenMontage"
  curl -fsS -X DELETE -H "PRIVATE-TOKEN: ${DTOK_GIT_TOKEN}" \
    "${API}/protected_branches/${BRANCH}" >/dev/null 2>&1 || true
fi

echo "==> Force-pushing slim tree to ${REMOTE} (${BRANCH})"
git -c http.postBuffer=524288000 push -f dtok "HEAD:${BRANCH}"

if [[ -n "${DTOK_GIT_TOKEN:-}" ]]; then
  curl -fsS -X POST -H "PRIVATE-TOKEN: ${DTOK_GIT_TOKEN}" -H 'Content-Type: application/json' \
    -d "{\"name\":\"${BRANCH}\",\"push_access_level\":40,\"merge_access_level\":40,\"allow_force_push\":false}" \
    "${API}/protected_branches" >/dev/null || true
fi

echo "OK synced ${SHA} → ${REMOTE} ${BRANCH}"
echo "Coolify should auto-deploy via GitLab webhook (main)."
