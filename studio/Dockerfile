# OpenMontage Drama Studio — Coolify / Docker image
# Build context MUST be the OpenMontage repo root:
#   docker build -f studio/Dockerfile -t openmontage-drama-studio .

FROM node:22-alpine AS ui
WORKDIR /ui
COPY studio/package.json studio/package-lock.json ./
RUN npm ci
COPY studio/ ./
RUN npm run build

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=8787 \
    OPENMONTAGE_ROOT=/app \
    PROJECTS_ROOT=/data/projects \
    STUDIO_DIST=/app/studio/dist

WORKDIR /app

# Healthcheck + FFmpeg (成片导出) + CJK fonts for board drawtext
RUN apt-get update \
  && apt-get install -y --no-install-recommends curl ffmpeg fonts-noto-cjk \
  && rm -rf /var/lib/apt/lists/*

# Studio API: FastAPI + schema validation + YAML pipeline manifests
COPY studio/server/requirements.txt /tmp/studio-requirements.txt
RUN pip install --no-cache-dir jsonschema pyyaml -r /tmp/studio-requirements.txt \
  && rm -f /tmp/studio-requirements.txt

# Core framework slices needed by the API
COPY lib ./lib
COPY tools ./tools
COPY schemas ./schemas
COPY pipeline_defs ./pipeline_defs
COPY workflow_defs ./workflow_defs
COPY studio/server ./studio/server
COPY studio/skills ./studio/skills
COPY studio/config ./studio/config
COPY --from=ui /ui/dist ./studio/dist

# Seed project lives in-repo (projects/ is gitignored for agent corpora)
COPY studio/seed/welcome-ep01 ./studio/seed/welcome-ep01

RUN mkdir -p /data/projects \
  && cp -R ./studio/seed/welcome-ep01 /data/projects/welcome-ep01 \
  && useradd -m -u 10001 studio \
  && chown -R studio:studio /app /data

USER studio
EXPOSE 8787
ENV PYTHONPATH=/app/studio/server:/app

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD curl -fsS "http://127.0.0.1:${PORT}/api/health" || exit 1

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8787", "--app-dir", "/app/studio/server"]
