# OpenMontage Drama Studio

可部署的 AI 短剧制片台。界面吸收行业产品优点：

| 借鉴 | 落地 |
| --- | --- |
| 雪风六步 | 顶部 **剧本 → 角色 → 场景 → 道具 → 分镜 → 剪辑** |
| Bomiio 三台 | **编导台 / 画布 / 剪辑室** |
| 影策 / Dream Canvas | 无限画布节点（主链 · 镜头 DAG · 子图 IR）+ Agent 指令条 |
| 任务队列 | 左侧 ledger `shot_jobs` 状态 |

后端读 `projects/<name>/` 产物（Scheme F），不另起编排器。

## Run (dev)

```bash
# API
python3 studio/server/app.py

# UI
cd studio && npm install && npm run dev
```

http://127.0.0.1:5173 — Vite 将 `/api` 代理到 `8787`。

## Run (production single process)

```bash
cd studio && npm ci && npm run build
HOST=0.0.0.0 PORT=8787 PROJECTS_ROOT=../projects python3 server/app.py
```

## Deploy (Coolify / cicd.dtok.io)

见 [`DEPLOY.md`](DEPLOY.md)。环境变量模板：[`/.env.example`](.env.example)。

```bash
docker compose -f ../docker-compose.studio.yml up --build
```

## API

- `GET /api/health` · `/api/config`
- `GET /api/projects` · `/api/project/bundle?name=`
- `GET /api/project/artifact?name=&kind=`
- `GET /api/pipeline/short-drama` · `/api/subgraphs/...`
- `POST /api/project/storyboard/patch` · `/api/project/ledger/invalidate`
