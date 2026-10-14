<p align="center">
  <img src="assets/drama-studio-mark.svg" alt="OpenMontage Drama Studio" width="96"/>
</p>

<h1 align="center">OpenMontage</h1>

<p align="center">
  <strong>Drama Studio · 一站式短剧工坊</strong><br/>
  <sub>script → cast → storyboard → shoot → edit</sub>
</p>

<p align="center">
  <a href="https://openmontage.dtok.io/"><img src="https://img.shields.io/badge/Live-openmontage.dtok.io-E11D48?style=flat-square" alt="Live"/></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-AGPLv3-334155?style=flat-square" alt="License"/></a>
  <img src="https://img.shields.io/badge/Stack-React%20%2B%20FastAPI%20%2B%20Postgres-0F172A?style=flat-square" alt="Stack"/>
</p>

<p align="center">
  <a href="#features">Features</a> ·
  <a href="#drama-studio">Drama Studio</a> ·
  <a href="#architecture">Architecture</a> ·
  <a href="#quick-start">Quick Start</a> ·
  <a href="#stack">Stack</a>
</p>

---

Short-drama production studio: write a script, lock characters, board shots, generate video, then edit and export — with cloud persistence so redeploys don’t wipe projects or media.

**Live:** [openmontage.dtok.io](https://openmontage.dtok.io/)

## Features

| | |
|:---|:---|
| **Inspire** | Inspiration wall with media stored locally (Postgres + MinIO) |
| **Drama pipeline** | Script → entities → storyboard → keyframes → shots → edit |
| **Assets & skills** | Personal library, prompts, community skills |
| **Soft auth** | Browse freely; sign in when calling models |
| **Durable state** | Projects / secrets / credits / usage in **PostgreSQL**; blobs in **MinIO** |

## Drama Studio

```text
  Script  →  Entities  →  Storyboard  →  Video  →  Audio  →  Edit
```

Config lives in `studio/config/platform.yaml` (product name, auth, locales, providers).

## Architecture

```text
  React UI  ──▶  FastAPI (studio/server)  ──▶  PostgreSQL
                         │
                         └──▶  MinIO (inspire / media)
```

| Path | Role |
|:---|:---|
| `studio/` | Drama Studio UI + API |
| `pipeline_defs/` · `skills/` | Agentic pipelines & directors |
| `lib/` · `tools/` | Tool registry |

## Quick Start

```bash
# env
cp studio/.env.example studio/.env
# set DATABASE_URL, MinIO (OSS_*), provider keys

# API
cd studio/server && pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8787

# UI
cd studio && npm install && npm run dev
```

Docker:

```bash
docker compose -f docker-compose.studio.yml up --build
```

Health: `GET /api/health`

Agent / pipeline usage: see [`AGENT_GUIDE.md`](AGENT_GUIDE.md).

## Stack

Python · FastAPI · React · PostgreSQL · MinIO · Seedream / Seedance · Docker

## License

AGPL-3.0 — see [`LICENSE`](LICENSE).
