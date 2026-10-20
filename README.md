<p align="center">
  <img src="assets/drama-studio-mark.svg" alt="OpenMontage" width="72"/>
</p>

<h1 align="center">OpenMontage</h1>

<p align="center">
  <strong>Drama Studio · 一站式短剧工坊</strong><br/>
  <sub>从一句话灵感到可拍成片 · script → cast → storyboard → shoot → edit</sub>
</p>

<p align="center">
  <a href="https://openmontage.dtok.io/"><img src="https://img.shields.io/badge/Live-openmontage.dtok.io-E11D48?style=flat-square" alt="Live"/></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-AGPLv3-334155?style=flat-square" alt="License"/></a>
  <img src="https://img.shields.io/badge/Stack-React%20%2B%20FastAPI%20%2B%20Postgres-0F172A?style=flat-square" alt="Stack"/>
</p>

---

## 项目简介

OpenMontage Drama Studio 是面向短剧 / 短视频制作的 **产品化工坊**：左侧按模块浏览，影视工坊内按七步生产线推进。浏览灵感、技能、资产无需登录；调用大模型与写入项目时再鉴权。

| | |
|:---|:---|
| 产品地址 | [openmontage.dtok.io](https://openmontage.dtok.io/) |
| 典型路径 | 先逛逛 → 登录创作 → 配密钥 → 六步成片 |
| 状态持久化 | 项目 / 密钥 / 积分 / 用量 → **PostgreSQL**；图片视频 → **MinIO** |
| 主要模型 | 文本 LLM（OpenAI 兼容等多家）· Seedream 出图 · Seedance 出视频 |

---

## 平台模块一览

左侧导航对应整站能力。下表说明每个模块做什么，并附线上截图。

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

**工坊内七步：**

| 步骤 | 功能 |
|:---|:---|
| 1 剧本 | 题材、画幅、视觉风格、梗概 / 素材；生成、续写、重写、定稿 |
| 2 角色 | Seedream 造型出图、版本回看、三视图、参考重绘、本地上传 |
| 3 场景 | 空间与光线设定、场景原画 |
| 4 道具 | 关键道具与材质细节 |
| 5 分镜 | DeepSeek 拆镜；Seedance 生成镜头视频（参考角色 / 场景 / 道具） |
| 6 配音 | 旁白与对白 TTS，剪辑时可混入音轨 |
| 7 剪辑 | 时间线编排与成片导出 |

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

管理文本与媒体供应商：OpenAI / DeepSeek / Claude / Gemini / 通义 / 豆包等；启用后立即用于剧本与分镜；可检测连通。

![模型配置](docs/screenshots/11-keys.png)

### 其他模块

| 模块 | 功能 |
|:---|:---|
| **作品频道** | 汇总导出成片，按项目浏览 |
| **创作挑战** | 挑战任务与积分激励 |
| **资源导航** | 外部工具与学习资源入口 |
| **用量统计** | 请求 / token / 费用趋势（侧栏显示今日花费） |
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
       │
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

## 快速开始

```bash
cp studio/.env.example studio/.env
# 填写 DATABASE_URL、MinIO(OSS_*)、各供应商密钥

cd studio/server && pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8787

cd studio && npm install && npm run dev
```

Docker：

```bash
docker compose -f docker-compose.studio.yml up --build
```

健康检查：`GET /api/health`（Postgres + 对象存储状态）。

Agent / CLI 管线说明见 [`AGENT_GUIDE.md`](AGENT_GUIDE.md)。

---

## 技术栈

Python · FastAPI · React · PostgreSQL · MinIO · Seedream · Seedance · Docker / Coolify

---

## License

AGPL-3.0 — 见 [`LICENSE`](LICENSE)。
