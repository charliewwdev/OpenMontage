# OpenMontage Drama Studio

Self-hostable AI studio for short dramas, viral shorts, and product ads.

The UI borrows patterns from popular short-drama tools:

| Inspiration | How it shows up here |
| --- | --- |
| Six-step workshop | Top flow **Script → Characters → Scenes → Props → Storyboard → Edit** |
| Multi-desk layouts | **Director desk / Canvas / Edit room** |
| Infinite canvas | Node graph of the production chain + Agent command bar |
| Job queue | Left ledger `shot_jobs` status |

The backend reads artifacts under `projects/<name>/` (Scheme F). It does not invent a second orchestrator.

中文版：[README.md](README.md)

## Run (dev)

```bash
# API
python3 studio/server/app.py

# UI
cd studio && npm install && npm run dev
```

Open http://127.0.0.1:5173 — Vite proxies `/api` to port `8787`.

## Run (production, single process)

```bash
cd studio && npm ci && npm run build
HOST=0.0.0.0 PORT=8787 PROJECTS_ROOT=../projects python3 server/app.py
```

## Deploy (Docker one-shot)

Full standalone guide (Demo auth + bundled MinIO): [`docs/SELF_HOSTING.md`](../docs/SELF_HOSTING.md).  
Coolify / hosted notes: [`DEPLOY.md`](DEPLOY.md). Env template: [`.env.example`](.env.example).

```bash
# from repo root
cp studio/.env.example .env
docker compose -f docker-compose.studio.yml up --build
# http://127.0.0.1:8787 → click Demo
```

## Starter prompts

One-line ideas for short drama / viral short / product ad: [`docs/examples.md`](../docs/examples.md).

## API (selected)

- `GET /api/health` · `/api/config`
- `GET /api/projects` · `/api/project/bundle?name=`
- `GET /api/project/artifact?name=&kind=`
- `GET /api/pipeline/short-drama` · `/api/subgraphs/...`
- `POST /api/project/storyboard/patch` · `/api/project/ledger/invalidate`
