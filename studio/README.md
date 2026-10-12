# OpenMontage Drama Studio

Scheme F dual canvas:

- **编辑流程 (Lab):** short-drama main chain + editable subgraph IR graphs
- **制作中 (Production):** storyboard shot DAG + ledger status + surgical chat edits

## Run

```bash
# API (from repo root)
python3 studio/server/app.py

# UI
cd studio && npm install && npm run dev
```

Open http://127.0.0.1:5173 — Vite proxies `/api` to port 8787.

Production mode reads `projects/<name>/storyboard.json` and `shot_jobs.json`.
