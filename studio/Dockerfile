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

# Minimal OS deps for healthcheck + optional json tools
RUN apt-get update \
  && apt-get install -y --no-install-recommends curl \
  && rm -rf /var/lib/apt/lists/*

# Studio API needs schema validation + YAML pipeline manifests
RUN pip install --no-cache-dir jsonschema pyyaml

# Core framework slices needed by the API
COPY lib ./lib
COPY tools ./tools
COPY schemas ./schemas
COPY pipeline_defs ./pipeline_defs
COPY workflow_defs ./workflow_defs
COPY studio/server ./studio/server
COPY --from=ui /ui/dist ./studio/dist

# Optional demo project baked in (overridable via volume mount on PROJECTS_ROOT)
COPY projects/midnight-sms-ep01 ./projects/midnight-sms-ep01

RUN mkdir -p /data/projects \
  && cp -R ./projects/midnight-sms-ep01 /data/projects/midnight-sms-ep01 \
  && useradd -m -u 10001 studio \
  && chown -R studio:studio /app /data

USER studio
EXPOSE 8787

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD curl -fsS "http://127.0.0.1:${PORT}/api/health" || exit 1

CMD ["python3", "studio/server/app.py"]
