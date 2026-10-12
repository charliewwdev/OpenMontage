# Deploy Drama Studio to Coolify (`cicd.dtok.io`)

Product UI learns from short-drama workspaces (六步工作流 + 编导台 / 画布 / 剪辑室) and serves a single container: React SPA + Python API.

## Coolify settings

| Field | Value |
| --- | --- |
| Source | This OpenMontage git repo |
| Build Pack | Dockerfile |
| Dockerfile | `studio/Dockerfile` |
| Docker Build Context | `/` (repo root) |
| Port | `8787` |
| Domain | e.g. `drama.dtok.io` (Coolify TLS) |

## Environment variables

Copy from [`studio/.env.example`](.env.example). Minimum:

```bash
HOST=0.0.0.0
PORT=8787
PROJECTS_ROOT=/data/projects
STUDIO_PUBLIC_URL=https://drama.dtok.io
API_BASE_URL=https://api-app.dtok.io/api/v1
```

`API_BASE_URL` follows the same public API shape as **dtok-app** (`AppConstants.apiBaseUrl = https://api-app.dtok.io/api/v1`). Generation keys (`FAL_KEY`, `OPENAI_API_KEY`, …) mirror the root [`.env.example`](../.env.example).

## Persistent projects volume

In Coolify → Storages, mount a volume:

- Container path: `/data/projects`
- Holds short-drama project folders (`script.json`, `character_bible.json`, `storyboard.json`, `shot_jobs.json`, …)

The image ships with `midnight-sms-ep01` as a demo; mounting an empty volume hides it unless you copy data in.

## Local Docker

```bash
# from repo root
docker compose -f docker-compose.studio.yml up --build
# open http://127.0.0.1:8787
curl -s http://127.0.0.1:8787/api/health
```

## Local without Docker

```bash
cd studio && npm ci && npm run build
PROJECTS_ROOT=../projects python3 server/app.py
# or: npm run start (serves dist + API)
```

Dev (hot UI):

```bash
python3 studio/server/app.py   # :8787
cd studio && npm run dev       # :5173 proxies /api
```

## Health

`GET /api/health` → `{ "ok": true, ... }` (Coolify healthcheck uses this).
