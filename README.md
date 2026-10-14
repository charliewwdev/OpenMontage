<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/monty-dark.svg">
    <img src="assets/monty-light.svg" alt="OpenMontage" width="160">
  </picture>
</p>

<h1 align="center">OpenMontage</h1>

<p align="center">
  <strong>Drama Studio · 一站式短剧工坊</strong><br/>
  <sub>Agentic video production · script → cast → storyboard → shoot → edit</sub>
</p>

<p align="center">
  <a href="https://openmontage.dtok.io/" target="_blank" rel="noopener noreferrer">
    <img src="https://img.shields.io/badge/Live_Demo-openmontage.dtok.io-EC4899?style=for-the-badge&logo=vercel&logoColor=white" alt="Live Demo">
  </a>
  <a href="https://github.com/charliewwdev/OpenMontage" target="_blank" rel="noopener noreferrer">
    <img src="https://img.shields.io/badge/GitHub-charliewwdev%2FOpenMontage-181717?style=for-the-badge&logo=github&logoColor=white" alt="GitHub">
  </a>
  <a href="LICENSE">
    <img src="https://img.shields.io/badge/License-AGPLv3-blue?style=for-the-badge" alt="License">
  </a>
</p>

<p align="center">
  <a href="#-features">Features</a> ·
  <a href="#-drama-studio">Drama Studio</a> ·
  <a href="#-architecture">Architecture</a> ·
  <a href="#-quick-start">Quick Start</a> ·
  <a href="#-stack">Stack</a>
</p>

---

## Why this repo

This is **Charlie’s OpenMontage line** — a production Drama Studio built on agentic video pipelines:

- **Browse-first product** — explore Inspire / Skills / Assets without login; auth only when you call models
- **Short-drama workflow** — script, entities, storyboard, video, audio, edit in one studio
- **Cloud-ready** — Postgres for all mutable state, MinIO for media, Coolify / Docker deploy
- **Bring your own keys** — Seedream / Seedance / LLM providers, soft credits, usage ledger

Live: **[openmontage.dtok.io](https://openmontage.dtok.io/)**

---

## ✨ Features

| | |
|:---|:---|
| **Inspire wall** | Localized inspiration media (Postgres metadata + MinIO blobs) — no broken external pin CDN |
| **Drama pipeline** | Script → character bible → storyboard → keyframes → Seedance shots → edit / export |
| **Asset library** | Personal uploads + AI assets, prompts library, community skills |
| **Soft auth** | DTok login / Google / Demo; mutations & generation gated, browsing open |
| **Durable state** | Projects, secrets, credits, usage, config → **PostgreSQL**; images/video → **MinIO** |
| **Agent skills** | Pipeline directors + Layer-3 provider skills for better generation quality |

---

## 🎬 Drama Studio

```text
  Script  →  Entities  →  Storyboard  →  Video  →  Audio  →  Edit
     │           │            │            │         │         │
     └───────────┴────────────┴────────────┴─────────┴─────────┘
                         Drama Studio UI
                    (React + FastAPI + PG/MinIO)
```

**Product defaults** (see `studio/config/platform.yaml`):

- Brand: OpenMontage Drama Studio  
- Tagline: 自带密钥 · 一站式短剧工坊  
- Default nav: Inspire · locales: `zh` / `en`

---

## 🏗 Architecture

```text
┌──────────────────┐     ┌─────────────────┐     ┌──────────────────┐
│  Drama Studio UI │────▶│  FastAPI server │────▶│  PostgreSQL      │
│  (Vite / React)  │     │  studio/server  │     │  projects·kv·meta│
└──────────────────┘     └────────┬────────┘     └──────────────────┘
                                  │
                                  ▼
                         ┌─────────────────┐
                         │  MinIO (S3)     │
                         │  inspire·media  │
                         └─────────────────┘
```

| Layer | Role |
|:---|:---|
| `studio/` | Product UI + API (Drama Studio) |
| `pipeline_defs/` · `skills/` | Agentic production pipelines & directors |
| `lib/` · `tools/` | Tool registry for agents |
| Postgres | Source of truth for projects & `studio_kv` |
| MinIO | Binary media (`openmontage/` prefix) |

---

## 🚀 Quick Start

### Drama Studio (local)

```bash
# 1) Env
cp studio/.env.example studio/.env
# fill DATABASE_URL / MinIO (OSS_*) / provider keys

# 2) API
cd studio/server && pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8787

# 3) UI
cd studio && npm install && npm run dev
```

### Docker / Coolify

```bash
docker compose -f docker-compose.studio.yml up --build
# or sync slim tree → git.dtok.io deploy branch (see scripts/sync_dtok_git.sh)
```

Public health: `GET /api/health` → Postgres + object store status.

### Agent pipelines (CLI / coding agent)

OpenMontage remains an **instruction-driven** system: the agent reads pipeline manifests + stage director skills, then drives tools. Start from [`AGENT_GUIDE.md`](AGENT_GUIDE.md).

---

## 🛠 Stack

<p align="left">
  <img src="https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python"/>
  <img src="https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI"/>
  <img src="https://img.shields.io/badge/React-61DAFB?style=flat-square&logo=react&logoColor=black" alt="React"/>
  <img src="https://img.shields.io/badge/PostgreSQL-4169E1?style=flat-square&logo=postgresql&logoColor=white" alt="PostgreSQL"/>
  <img src="https://img.shields.io/badge/MinIO-C72E49?style=flat-square&logo=minio&logoColor=white" alt="MinIO"/>
  <img src="https://img.shields.io/badge/Seedream-EC4899?style=flat-square" alt="Seedream"/>
  <img src="https://img.shields.io/badge/Seedance-7C3AED?style=flat-square" alt="Seedance"/>
  <img src="https://img.shields.io/badge/Docker-2496ED?style=flat-square&logo=docker&logoColor=white" alt="Docker"/>
</p>

---

## 📁 Layout

```text
OpenMontage/
├── studio/                 # Drama Studio (UI + FastAPI)
│   ├── src/                # React app
│   ├── server/             # API, PG, MinIO, providers
│   └── config/             # platform.yaml, locales
├── pipeline_defs/          # Production pipelines
├── skills/                 # Agent / stage director skills
├── lib/ · tools/           # Tooling
├── docker-compose.studio.yml
└── AGENT_GUIDE.md          # Agent contract
```

---

## 🔗 Links

| | |
|:---|:---|
| 🎬 Live Studio | [openmontage.dtok.io](https://openmontage.dtok.io/) |
| 👤 Author | [github.com/charliewwdev](https://github.com/charliewwdev) |
| 🖥️ OpenCLI | [opencli.ai](https://opencli.ai/) |
| 📖 Agent Guide | [AGENT_GUIDE.md](AGENT_GUIDE.md) |

---

## License

AGPL-3.0 — see [`LICENSE`](LICENSE).

---

<p align="center">
  <sub>Built by <a href="https://github.com/charliewwdev" target="_blank" rel="noopener noreferrer">Charlie</a> · DTok · <a href="https://openmontage.dtok.io/" target="_blank" rel="noopener noreferrer">Drama Studio</a></sub>
</p>
