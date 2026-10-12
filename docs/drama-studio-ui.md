# Drama Studio UI

Deployable product UI for OpenMontage short-drama (not Cursor `.canvas.tsx`).

Design references: 雪风六步工作流、Bomiio 编导台/无限画布/剪辑室、影策自由画布 + Agent。

## Product shell

### 六步导航

`剧本 → 角色 → 场景 → 道具 → 分镜 → 剪辑` — status from project artifacts (`script`, `character_bible`, `storyboard`, `shot_jobs`, …).

### 三台

| Desk | Role |
| --- | --- |
| **编导台** | Script scenes, character bible, locations, props, storyboard grid |
| **画布** | Shot DAG · short-drama main chain · subgraph IR (`workflow_defs/subgraphs`) |
| **剪辑室** | Phone preview + timeline from storyboard durations / ledger colors |

### Agent bar

Surgical NL edits (`仰拍`, `时长 N 秒`) → storyboard patch + ledger invalidate.

## Run / deploy

See [`studio/README.md`](../studio/README.md) and [`studio/DEPLOY.md`](../studio/DEPLOY.md).

Coolify (`https://cicd.dtok.io/`): Dockerfile `studio/Dockerfile`, context repo root, port `8787`, env from `studio/.env.example` (API URL pattern matches dtok-app `https://api-app.dtok.io/api/v1`).

## API

`studio/server/app.py`:

- `GET /api/health`, `/api/config`
- `GET /api/pipeline/short-drama`
- `GET /api/subgraphs`, `/api/subgraphs/:id/graph`
- `GET /api/projects`, `/api/project/bundle`, `/api/project/artifact`
- `GET /api/project/storyboard`, `/api/project/ledger`, `/api/project/status`
- `POST /api/project/storyboard/patch`, `/api/project/ledger/invalidate`, `/api/subgraphs/validate`
- Non-`/api` routes serve `studio/dist` (SPA)
