# 无 DTok 账号的自托管

线上体验站 [openmontage.dtok.io](https://openmontage.dtok.io/) 使用 DTok 账号登录与 DTok 托管的 MinIO。**自己部署 Drama Studio 不需要 DTok 账号。** 本文说明独立路径：本地 Demo 鉴权、自管对象存储、自管模型端点。

相关文件：[`studio/.env.example`](../studio/.env.example) · [`docker-compose.studio.yml`](../docker-compose.studio.yml) · 托管/Coolify 说明见 [`studio/DEPLOY.md`](../studio/DEPLOY.md)。英文版：[SELF_HOSTING.md](SELF_HOSTING.md)。

---

## Compose 自带 vs 需自备

| 组件 | `docker-compose.studio.yml` 是否包含 | 说明 |
|:---|:---|:---|
| Studio 前端 + API + media worker | 是 | 本仓库构建 |
| PostgreSQL 16 | 是 | 项目 / 密钥 / 元数据 |
| Redis 7 | 是 | 媒体任务队列 |
| MinIO（S3 兼容对象存储） | **是（已内置）** | `drama-minio` + `drama-minio-init`（自动建桶）。托管/外部 S3 时覆盖 `MINIO_*`。 |
| 账号 / 登录服务 | **不需要 DTok** | 用内置 **本地 Demo 鉴权**，或把 `API_BASE_URL` 指到自有兼容账号接口 |
| 文本大模型 | 需自备 | 任意 OpenAI 兼容 Key |
| 出图 | 需自备 | 火山方舟 **Seedream**（**付费**），**或**自有 ComfyUI |
| 分镜出视频 | 需自备 | 火山方舟 **Seedance**（**付费第三方 API**） |
| 配音 TTS | 默认本地路径 | **edge-tts** 无需密钥；可选 OpenAI 兼容语音 |

积分充值、DTok Google 登录、推荐计划等是线上体验站能力。自托管时直接向各模型供应商付费。

---

## 最小独立流程（不经过 DTok）

### 1. 环境变量：本地 Demo + 自管存储 + 自备密钥

```bash
cp studio/.env.example .env
```

至少设置：

```bash
STUDIO_PUBLIC_URL=http://localhost:8787

STUDIO_AUTH_REQUIRED=true
STUDIO_DEMO_ENABLED=true
STUDIO_DEMO_AUTO_ENTER=false
# STUDIO_DEMO_SECRET=换成足够长的随机串

STUDIO_GOOGLE_ENABLED=false

# 独立部署不要依赖示例里的 API_BASE_URL。
# 密码登录 / 注册 / Google 仍会代理到 API_BASE_URL（默认是 DTok 账号接口）。
# 只用 Demo 登录时不需要那条路径。
# API_BASE_URL=

# 对象存储：Compose 默认指向栈内 drama-minio。
# 仅在使用外部 MinIO / S3 时覆盖：
# MINIO_ENDPOINT=https://minio-api.example.com
# MINIO_ACCESS_KEY=...
# MINIO_SECRET_KEY=...
# MINIO_PUBLIC_BASE=https://minio-api.example.com

DEEPSEEK_API_KEY=sk-...
VOLCENGINE_API_KEY=...   # 或 ARK_API_KEY；Seedance（及可选 Seedream）
# COMFYUI_SERVER_URL=https://your-comfy-host
```

Postgres / Redis 可沿用 Compose 默认服务。

### 2. 对象存储

**默认：** `docker compose … up --build` 会启动 `drama-minio` 并创建桶 `openmontage`。控制台：http://localhost:9001（`minioadmin` / `minioadmin`）。容器内 Studio 访问 `http://drama-minio:9000`；浏览器侧用 `MINIO_PUBLIC_BASE`（默认 `http://127.0.0.1:9000`）。

**外部 S3 / 托管 MinIO：** 设置 `MINIO_ENDPOINT`、密钥、桶与 `MINIO_PUBLIC_BASE`（或 `OSS_*`）。栈内 MinIO 可闲置，或在覆盖 compose 中去掉。

健康检查：`GET /api/health` 会报告对象存储可达性。

### 3. 启动

```bash
cp studio/.env.example .env
docker compose -f docker-compose.studio.yml up --build
# http://localhost:8787 → Demo
# GET /api/health
# MinIO 控制台：http://localhost:9001
```

### 4. 不经过 DTok 登录

1. 打开 Studio。
2. 在登录页点 **Demo**（一键），或使用界面预填的 demo 用户名/密码（默认 `demo` / `demo`）。
3. 请求 `POST /api/auth/demo`，签发本地 `omdemo.*` token（`studio/server/demo_auth.py`），**不会访问 `api-app.dtok.io`**。
4. 若未写入 `.env`，再到「模型配置」里按账号填写密钥。

密码登录、注册、短信与 Google 仍走 `API_BASE_URL`（`auth_proxy.py`）。私有自托管可忽略这些入口，或把 `API_BASE_URL` 指到自有兼容接口。

`STUDIO_AUTH_REQUIRED=false` 会关闭登录门禁。需要按用户隔离密钥/项目、又不想接 DTok 时，优先用 Demo 鉴权。

---

## 各阶段是否依赖付费外部 API

| 步骤 | 本地 / 自管栈 | 是否需要付费第三方 API |
|:---|:---|:---|
| 1 剧本 | Studio + 自备 LLM | 仅当你选的 LLM 本身收费（BYOK） |
| 2 角色 | Studio + 存储 | **Seedream**（火山方舟，付费）**或**自有 **ComfyUI** |
| 3 场景 | 同角色 | 同角色 |
| 4 道具 | 同角色 | 同角色 |
| 5 分镜 | 拆镜走自备 LLM；镜头视频走供应商 | **Seedance**（火山方舟，**付费第三方 API**，自备 Key） |
| 6 配音 | 默认 **edge-tts** | edge-tts 无需密钥；可选付费语音接口 |
| 7 剪辑 | Studio/worker 内 FFmpeg | 无生成类 API |

完整「一句话 → 成片」自托管路径通常需要：LLM Key + 出图（Seedream 或 ComfyUI）+ Seedance（要出视频时）。TTS 可继续用 edge-tts。

---

## 鉴权模式速查

| 模式 | 环境变量 | 是否访问 DTok |
|:---|:---|:---|
| 本地 Demo（推荐独立部署） | `STUDIO_DEMO_ENABLED=true`，用 Demo | 否 |
| 线上 DTok 账号（体验站） | `API_BASE_URL=https://api-app.dtok.io/api/v1` + 密码/Google | 是 |
| 自有账号 API | 自建兼容 `/auth/*` 的 `API_BASE_URL` | 否（走你的 API） |
| 开放门禁 | `STUDIO_AUTH_REQUIRED=false` | 否 |

---

## 上线前核对

- [ ] `STUDIO_PUBLIC_URL` 是你的地址，不是 `openmontage.dtok.io`
- [ ] 能用 **Demo**（或自有 `API_BASE_URL`）登录，且未注册 DTok 账号
- [ ] 对象存储正常：默认栈内 MinIO，或自管 `MINIO_*` / `OSS_*`（除非有意使用 dtok MinIO）
- [ ] 已配置 LLM；出图路径（Seedream 或 ComfyUI）；需要视频时已配置 Seedance
- [ ] `GET /api/health` 中 Postgres 与对象存储正常
