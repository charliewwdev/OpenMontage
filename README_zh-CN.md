<p align="center">
  <img src="assets/drama-studio-mark.svg" alt="OpenMontage Drama Studio" width="72"/>
</p>

<h1 align="center">OpenMontage Drama Studio</h1>

<p align="center">
  <strong>一句话灵感 → 短剧、爆款短视频、带货广告片</strong><br/>
  剧本 → 角色 → 场景 → 道具 → 分镜出片 → 配音 → 剪辑，一站式、可自部署的 AI 短剧工坊
</p>

<p align="center">
  <a href="https://openmontage.dtok.io/"><img src="https://img.shields.io/badge/在线体验-openmontage.dtok.io-E11D48?style=flat-square" alt="在线体验"/></a>
  <a href="https://github.com/charliewwdev/OpenMontage/stargazers"><img src="https://img.shields.io/github/stars/charliewwdev/OpenMontage?style=flat-square" alt="GitHub stars"/></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-AGPLv3-334155?style=flat-square" alt="License: AGPL-3.0"/></a>
  <a href="https://github.com/charliewwdev/OpenMontage/releases"><img src="https://img.shields.io/github/v/release/charliewwdev/OpenMontage?style=flat-square" alt="Release"/></a>
  <img src="https://img.shields.io/badge/Stack-React%20%2B%20FastAPI%20%2B%20Postgres-0F172A?style=flat-square" alt="Stack"/>
  <img src="https://img.shields.io/badge/Docker-Compose-2496ED?style=flat-square&logo=docker&logoColor=white" alt="Docker Compose"/>
</p>

<p align="center">⭐ 觉得有用就点个 Star，让更多人看到</p>

<p align="center"><a href="README.md">English</a> · <b>简体中文</b></p>

<!--
  演示 GIF 占位（发布前补上）
  录 20–30 秒：输入一句话 → 走完七步 → 播放导出的成片。
  存为 docs/demo.gif（< 10 MB），或把 MP4 上传到 GitHub issue / release，然后把这段注释替换为：
  <p align="center"><img src="docs/demo.gif" alt="一句话出片" width="720"/></p>
-->

---

## 项目简介

OpenMontage Drama Studio 是面向短剧 / 短视频制作的 **产品化工坊**。一句话描述需求（例如「10 集复仇爽剧，9:16，前 3 秒强钩子」），系统先生成剧本，再按七步生产线推进；每一步都可编辑，角色、场景、道具会作为参考图带入镜头生成，所以可以只重做某个角色或某个镜头，不必从头再来。

- **自带密钥（BYOK）**：文本、出图、出视频模型都在「模型配置」里按账号配置，密钥按账号隔离保存。
- **先逛逛**：灵感、技能、资产页面无需登录即可浏览；调用大模型与写入项目时再鉴权。
- **逐步或一键**：可以自己一步步走，也可以让创作 Agent「一键全流程」在后台跑通，之后任意一步仍可单独重跑或换版本。

| | |
|:---|:---|
| 产品地址 | [openmontage.dtok.io](https://openmontage.dtok.io/) |
| 典型路径 | 先逛逛 → 登录创作 → 配密钥 → 七步成片 |
| 状态持久化 | 项目 / 密钥 / 积分 / 用量 → **PostgreSQL**；图片视频 → **MinIO / S3**；媒体任务队列 → **Redis** |
| 主要模型 | 文本 LLM（OpenAI 兼容等多家）· Seedream 出图 · Seedance 出视频 |

---

## 七步工坊

| 步骤 | 功能 |
|:---|:---|
| 1 剧本 | 题材、画幅、视觉风格、梗概 / 素材；生成、续写、重写、定稿 |
| 2 角色 | Seedream（或自有 GPU 上的 ComfyUI）造型出图、版本回看、三视图、参考重绘、本地上传 |
| 3 场景 | 空间与光线设定、场景原画 |
| 4 道具 | 关键道具与材质细节 |
| 5 分镜 | 大模型拆镜；Seedance 参考角色 / 场景 / 道具生成镜头视频 |
| 6 配音 | 旁白与对白 TTS（默认 edge-tts，可回退到 OpenAI 兼容语音接口），导出时混入音轨 |
| 7 剪辑 | 时间线编排与成片导出 |

当前界面中，1–4 步各有独立标签页，5–7 步合并在「**工作台**」里按片段完成；「无限画布」用节点图展示同样的七步并按进度着色。

## 能做什么

- **短剧**：爽剧 / 短剧 / 正剧项目模板，也可以上传已有剧本。
- **爆款短视频**：「爆款内容广场」内置抖音、TikTok、小红书、Reels、Shorts、B 站的节拍结构与平台套路（钩子、节奏、CTA），可一键带入创作。这些是根据常见信息流套路整理的结构模板，不是实时热榜抓取。
- **广告 / 带货视频**：内置「带货转化」电商短视频模板（痛点演示 → 产品特写 → 利益点字幕 → 催单 CTA）、Reels 软植入套路，以及 Skill 市场里的商业营销 / 电商视觉类技能；同样走七步工坊，没有单独的广告编辑器。

---

## 平台模块一览

左侧导航对应整站能力。

### 爆款内容广场

面向 TikTok、抖音、小红书、Reels、Shorts、B 站等社媒的爆款视频打造工作流；选平台套路后复制提示词或一键带入创作，下方参考墙可学习画面与提示词。

![爆款内容广场](docs/screenshots/01-inspire.png)

### 创作中心

文本 / 视觉 / 音频 / 视频 / 工坊 / 画布入口汇总；一句话描述需求后跳转到对应工具。

![创作中心](docs/screenshots/02-tools.png)

### 创作 Agent

一句话建项：题材、集数、画幅、示例钩子；调用已配置 LLM 生成首批剧本，并显示运行检查（文本 / Seedream / Seedance）。

![创作 Agent](docs/screenshots/03-agent.png)

### 影视工坊

项目库与创作入口（爽剧 / 短剧 / 正剧 / 上传剧本），进入后走七步生产线。

![影视工坊](docs/screenshots/04-workshop.png)

剧本工作台：

![剧本](docs/screenshots/05-workshop-script.png)

角色造型：

![角色](docs/screenshots/06-workshop-character.png)

分镜导演台：

![分镜](docs/screenshots/07-workshop-storyboard.png)

### 个人资产

素材库 + 提示词库：上传 / AI 生成筛选，按角色·场景·道具·分镜·成片等分类；可批量管理并带入创作。

![个人资产](docs/screenshots/08-assets.png)

### Skill 专家

官方 / 用户分享技能市场：分集剧本、分镜提示词、角色造型、场景设计、导演工作流等；可投稿与安装到 Agent。

![Skill 专家](docs/screenshots/09-skills.png)

### 无限画布

把当前项目生产线可视化为可拖拽节点图（剧本 → 角色 / 场景 / 道具 → 分镜 → 配音 → 剪辑），按进度着色，点击进入对应工坊步骤。

![无限画布](docs/screenshots/10-canvas.png)

### 模型配置

管理文本与媒体供应商：OpenAI / DeepSeek / Claude / Gemini / 通义 / 豆包 / Kimi / 智谱 / MiniMax / OpenRouter 等；启用后立即用于剧本与分镜；可检测连通，热加载无需重启。

![模型配置](docs/screenshots/11-keys.png)

### 其他模块

| 模块 | 功能 |
|:---|:---|
| **作品频道** | 汇总导出成片，按项目浏览 |
| **创作挑战** | 挑战任务与积分激励 |
| **资源导航** | 外部工具与学习资源入口 |
| **用量统计** | 请求 / token / 费用趋势（侧栏显示今日花费） |
| **任务队列** | 出图 / 出视频任务状态 |
| **帮助中心** | 使用说明与 FAQ |
| **积分充值** | 软积分余额与套餐 |
| **推荐计划** | 邀请码与推荐奖励 |

---

## 端到端工作流

```text
灵感 / Agent 一句话
        ↓
   创建项目（题材 · 画幅）
        ↓
 剧本定稿 → 角色 / 场景 / 道具出图
        ↓
 分镜拆解 → Seedance 出视频 → 配音 → 剪辑导出
        ↓
   作品频道 / 个人资产
```

---

## 架构

```text
  React UI (studio/src)
       │
       ▼
  FastAPI (studio/server) ──▶ PostgreSQL  (projects · studio_kv · meta)
       │            └──────▶ Redis       (媒体任务队列)
       └──▶ MinIO / S3     (inspire · media blobs)
```

| 目录 | 说明 |
|:---|:---|
| `studio/` | Drama Studio 前端 + API |
| `studio/config/platform.yaml` | 导航、工坊步骤、工具、文案配置 |
| `pipeline_defs/` · `skills/` | Agent 流水线与导演技能 |
| `lib/` · `tools/` | 工具注册表 |
| `docs/screenshots/` | 本文截图 |

---

## 自部署须知

| | `docker-compose.studio.yml` 是否包含 |
|:---|:---|
| Studio 应用（前端 + API）与媒体 worker | ✅ 从本仓库构建 |
| PostgreSQL 16 | ✅ 已内置 |
| Redis 7（媒体任务队列） | ✅ 已内置 |
| S3 兼容对象存储（MinIO / S3） | ❌ **需自备**：endpoint、access key、secret、bucket（`OSS_*` / `MINIO_*` / `S3_*`） |
| 文本大模型密钥 | ❌ **需自备**：DeepSeek、OpenAI、Claude、Gemini、通义、豆包、Kimi、智谱、MiniMax、OpenRouter 或其他 OpenAI 兼容接口 |
| 出图 + 出视频 | ❌ **需自备**：火山方舟 Key，用于 **Seedream**（出图）和 **Seedance**（出视频），二者均为**付费第三方 API**；出图也可改用自有 ComfyUI |
| 配音 TTS | 默认 edge-tts（无需密钥）；可选 OpenAI 兼容语音接口 |

另外：

- `studio/.env.example` 里的默认值指向线上实例（`openmontage.dtok.io`、其 MinIO 地址，以及 `API_BASE_URL` 中的 DTok 账号接口），自部署时请换成自己的。默认登录会代理到 `API_BASE_URL` 的账号接口，相关开关见同文件中的 `STUDIO_AUTH_REQUIRED` 与 Demo 用户配置。
- 线上实例有积分充值页面；自部署时直接向各模型供应商付费。

## 快速开始

Docker（Compose 读取仓库根目录的 `.env`）：

```bash
cp studio/.env.example .env
# 填写 DATABASE_URL（或保留内置 drama-db 默认值）、S3/MinIO 配置、各供应商密钥
docker compose -f docker-compose.studio.yml up --build
# 打开 http://localhost:8787 · 健康检查：GET /api/health（Postgres + 对象存储状态）
```

本地开发：

```bash
cp studio/.env.example studio/.env
# 填写 DATABASE_URL、MinIO(OSS_*)、各供应商密钥，并导出到当前 shell

cd studio/server && pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8787

cd studio && npm install && npm run dev   # http://127.0.0.1:5173，/api 代理到 8787
```

Agent / CLI 管线说明见 [`AGENT_GUIDE.md`](AGENT_GUIDE.md)。

---

## 技术栈

Python · FastAPI · React · PostgreSQL · Redis · MinIO / S3 · Seedream · Seedance · edge-tts · FFmpeg · Docker / Coolify

---

## 关于名字

OpenMontage Drama Studio 是 [@charliewwdev](https://github.com/charliewwdev) 独立开发的产品。早期基于 AGPL-3.0 的 [calesthio/OpenMontage](https://github.com/calesthio/OpenMontage) 代码起步，现已重构为独立的短剧工坊，**与上游项目无隶属关系，也未获其背书**。仓库保留了上游的 git 历史，因此贡献者列表中会出现上游作者。

## 许可证与署名

采用 **GNU AGPL-3.0** 许可，见 [`LICENSE`](LICENSE)。

本项目是 [calesthio/OpenMontage](https://github.com/calesthio/OpenMontage) 的修改版本：原始代码版权归其各自作者所有，修改部分由 @charliewwdev 完成（具体改动与时间见 git 历史）。如果你把修改后的版本作为网络服务提供，AGPL-3.0 第 13 条要求向用户提供对应源码。
