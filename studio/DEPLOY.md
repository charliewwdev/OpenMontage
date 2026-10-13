# Deploy Drama Studio to Coolify (`cicd.dtok.io`)

Product UI learns from short-drama workspaces (六步工作流 + 编导台 / 画布 / 剪辑室) and serves a single container: React SPA + **FastAPI** (`uvicorn`) API.

## Coolify settings

| Field | Value |
| --- | --- |
| Source | This OpenMontage git repo |
| Build Pack | Dockerfile |
| Dockerfile | `studio/Dockerfile` |
| Docker Build Context | `/` (repo root) |
| Port | `8787` |
| Domain | `https://openmontage.dtok.io` (aaPanel → `:8787`) |

## Environment variables

Copy from [`studio/.env.example`](.env.example). Minimum:

```bash
HOST=0.0.0.0
PORT=8787
PROJECTS_ROOT=/data/projects
STUDIO_PUBLIC_URL=https://openmontage.dtok.io
API_BASE_URL=https://api-app.dtok.io/api/v1
# Required for Xuefeng-parity generation (no offline fake scripts):
DEEPSEEK_API_KEY=
VOLCENGINE_API_KEY=   # or ARK_API_KEY — Seedream + Seedance
```

`API_BASE_URL` follows the same public API shape as **dtok-app**. Without `DEEPSEEK_API_KEY` / Volcengine keys, the UI works but script/image/video generation returns clear errors.

> **Domain note:** Drama Studio public host is **`openmontage.dtok.io`**. Do **not** use `studio.dtok.io` (DTok 短剧平台管理后台) or other occupied `*.dtok.io` hosts.

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

## One-shot create + continuous verify

Code is on `origin/main` (`https://github.com/charliewwdev/OpenMontage`).

### 1. Create the Coolify app (needs **write** API token)

In Coolify → Keys & Tokens, create a token with **write** (read-only tokens return `Missing required permissions: write`).

```bash
export COOLIFY_TOKEN='...'          # write scope
export COOLIFY_URL='https://cicd.dtok.io'
# optional custom domain (default openmontage.dtok.io):
# export STUDIO_DOMAIN='https://openmontage.dtok.io'
./scripts/deploy_coolify_drama_studio.sh
```

Or in Coolify UI: New Resource → Public Repository →

| Field | Value |
| --- | --- |
| Repo | `https://github.com/charliewwdev/OpenMontage` |
| Branch | `main` |
| Build Pack | Dockerfile |
| Dockerfile | `/studio/Dockerfile` |
| Base directory | `/` |
| Port | `8787` |
| Health | `/api/health` |
| Auto Deploy | on |
| Watch paths | `studio/**` (+ related paths in script) |

### Keys for Xuefeng-parity generation

```bash
export COOLIFY_TOKEN='...'
export COOLIFY_APP_UUID='x096iqdmsnez39b4sp6bbaan'
export DEEPSEEK_API_KEY='...'
export VOLCENGINE_API_KEY='...'   # or ARK_API_KEY
./scripts/coolify_set_drama_keys.sh
```

### Product target

对齐 **有彩视界在线版** 信息架构与影视工坊正式 UI（片库英雄区、建片场、六步侧栏、风格库弹层）。  
平台导航已铺：创作 Agent / 创作中心 / 有彩画布 / 个人资产 / 灵感广场（能力逐项接入；非其云积分 SaaS）。

### Acceptance checklist (影视工坊 · 在线版对照)

1. 创建片场：片名 / 题材 / 39 风格 / 画幅 / 创作需求 + AI 优化需求  
2. 剧本：分批生成、续写、改写、逐集编辑、定稿 / 批量定稿；同步实体档案  
3. 角色/场景/道具：出图、三视图、批量、重绘、上传、版本切换、软删除  
4. 分镜：定稿拆镜、参考图≤9、Seedance 模型/分辨率、批量、TAKE 评分备注选用  
5. 剪辑：时间线、启用/禁用、入出点、草稿、FFmpeg MP4 预览  
6. 壳层：左侧 01–06 + 计数、片库进度条、确认弹层、灯箱、耗时反馈  

### 2. Wire GitHub Actions (every fix → online)

Repo secrets:

- `COOLIFY_TOKEN` — write token
- `COOLIFY_DRAMA_STUDIO_UUID` — app uuid from step 1
- `COOLIFY_URL` — optional, default `https://cicd.dtok.io`

Workflow: [`.github/workflows/deploy-drama-studio.yml`](../.github/workflows/deploy-drama-studio.yml)  
Push to `main` under `studio/**` (etc.) → Coolify rebuild → open the FQDN to verify.
