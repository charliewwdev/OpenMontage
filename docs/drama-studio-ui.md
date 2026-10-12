# Drama Studio UI

Product UI for OpenMontage short-drama (not Cursor `.canvas.tsx`).

## Modes

### 编辑流程 (Lab)

- Top swimlane: main-chain stages from `short-drama` manifest
- Drill-down: subgraph IR graphs (`workflow_defs/subgraphs`)
- Palette conceptually = agents/tools/controls (v1 lists presets)
- NL graph edits: prefer Cursor EP + IR patch; Studio chat hints the workflow

### 制作中 (Production)

- Shot DAG from `projects/<name>/storyboard.json`
- Status colors from `shot_jobs.json` ledger
- Inspector: shot fields + Rerun (invalidate ledger job)
- Chat: surgical edits (`仰拍`, `时长 N 秒`) → storyboard patch + ledger invalidate

## Run

See [`studio/README.md`](../studio/README.md).

## API

`studio/server/app.py` on `:8787`:

- `GET /api/pipeline/short-drama`
- `GET /api/subgraphs`, `GET /api/subgraphs/:id/graph`
- `GET /api/projects`, `/api/project/storyboard`, `/api/project/ledger`, `/api/project/status`
- `POST /api/project/storyboard/patch`, `/api/project/ledger/invalidate`, `/api/subgraphs/validate`
