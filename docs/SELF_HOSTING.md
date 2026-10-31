# Self-hosting without a DTok account

The live demo at [openmontage.dtok.io](https://openmontage.dtok.io/) uses DTok account login and DTok-hosted MinIO. **You do not need a DTok account to run Drama Studio yourself.** This page is the standalone path: local demo auth, your own object storage, and your own model endpoints.

Related: [`studio/.env.example`](../studio/.env.example) · [`docker-compose.studio.yml`](../docker-compose.studio.yml) · Coolify/hosted notes in [`studio/DEPLOY.md`](../studio/DEPLOY.md).

---

## What ships in Compose vs what you bring

| Component | In `docker-compose.studio.yml`? | Notes |
|:---|:---|:---|
| Studio UI + API + media worker | Yes | Built from this repo |
| PostgreSQL 16 | Yes | Project / secrets / metadata |
| Redis 7 | Yes | Media job queue |
| S3-compatible object storage | **No — you provide** | MinIO, AWS S3, or any S3 API (`MINIO_*` / `OSS_*` / `S3_*`) |
| Account / login service | **No DTok required** | Use **local demo auth** (built in), or point `API_BASE_URL` at your own compatible account API |
| Text LLM | You provide | Any OpenAI-compatible key (DeepSeek, OpenAI, Qwen, …) |
| Image generation | You provide | **Seedream** via Volcengine Ark (**paid**), **or** your own ComfyUI server |
| Video shots | You provide | **Seedance** via Volcengine Ark (**paid** third-party API) |
| Voice (TTS) | Default local path | **edge-tts** needs no key; optional OpenAI-compatible speech |

Hosted extras (credits / top-up, DTok Google Sign-In, referral) are for the public demo. Self-hosted, you pay model providers directly.

---

## Minimal standalone workflow (no DTok)

### 1. Env for local demo auth + your storage + your keys

```bash
cp studio/.env.example .env
```

Set at least:

```bash
# Public URL of THIS deployment (not openmontage.dtok.io)
STUDIO_PUBLIC_URL=http://localhost:8787

# Auth: local demo session — does NOT call DTok
STUDIO_AUTH_REQUIRED=true
STUDIO_DEMO_ENABLED=true
STUDIO_DEMO_AUTO_ENTER=false
# Optional but recommended outside a throwaway laptop:
# STUDIO_DEMO_SECRET=replace-with-a-long-random-string

# Leave password/Google on DTok unused. Demo login is enough for a private studio.
# If you must hide Google on the login page:
STUDIO_GOOGLE_ENABLED=false

# Do NOT rely on the sample API_BASE_URL for standalone use.
# Password / register / Google still proxy to whatever API_BASE_URL is set
# (shipped default is the DTok account API). With demo auth you never need that path.
# API_BASE_URL=

# Your object storage (replace the dtok MinIO sample values)
MINIO_ENDPOINT=http://127.0.0.1:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=openmontage
MINIO_PREFIX=openmontage
# Or the OSS_* aliases used by dtok-app — same fields.

# Text LLM (pick one family you have a key for)
DEEPSEEK_API_KEY=sk-...
# or OPENAI_API_KEY=... / LLM_PROVIDER=... etc.

# Video shots (paid) — Volcengine Ark Seedance
VOLCENGINE_API_KEY=...   # or ARK_API_KEY

# Images: Seedream (paid, same Ark key) and/or your ComfyUI
# SEEDREAM_MODEL=...
# COMFYUI_SERVER_URL=https://your-comfy-host
```

Postgres / Redis: keep the Compose defaults (`drama-db`, `drama-redis`) unless you already run your own.

### 2. Object storage example (optional local MinIO)

Compose does **not** start MinIO. One common local option:

```bash
docker run -d --name om-minio -p 9000:9000 -p 9001:9001 \
  -e MINIO_ROOT_USER=minioadmin -e MINIO_ROOT_PASSWORD=minioadmin \
  minio/minio server /data --console-address ":9001"
# Create bucket `openmontage` in the console (http://127.0.0.1:9001), then point MINIO_* at it.
```

Any S3-compatible endpoint works the same way. Health: `GET /api/health` reports object-store reachability.

### 3. Start

```bash
docker compose -f docker-compose.studio.yml up --build
# UI: http://localhost:8787
# Health: GET /api/health
```

### 4. Sign in without DTok

1. Open the studio URL.
2. On the auth screen, use **Demo** (one-click), or the demo username/password shown in UI config (`demo` / `demo` by default when prefill is on).
3. That hits `POST /api/auth/demo` and issues a local `omdemo.*` token (`studio/server/demo_auth.py`). **No call to `api-app.dtok.io`.**
4. Configure model keys in **Model settings** (per-account / BYOK) if you did not put them in `.env`.

Password login, register, phone codes, and Google Sign-In still go through `API_BASE_URL` (`studio/server/auth_proxy.py`). Leave those alone for a private self-host, or point `API_BASE_URL` at an account API you control that matches the same routes.

`STUDIO_AUTH_REQUIRED=false` turns off the login gate (browse + mutate without a session). Prefer demo auth when you want a user-scoped secrets/projects boundary without DTok.

---

## Which stages need paid external APIs

| Stage | Runs locally / on your stack | Needs a third-party paid API? |
|:---|:---|:---|
| 1 Script (剧本) | Studio + your LLM endpoint | Only if your chosen LLM is paid (BYOK) |
| 2 Characters (角色) | Studio + storage | **Seedream** (Volcengine Ark, paid) **or** your own **ComfyUI** |
| 3 Scenes (场景) | same as characters | same as characters |
| 4 Props (道具) | same as characters | same as characters |
| 5 Storyboard & shots (分镜) | LLM breakdown locally via your LLM; shot video via provider | **Seedance** via Volcengine Ark — **paid third-party API** (your own key) |
| 6 Voice (配音) | **edge-tts** by default | No key for edge-tts; optional paid OpenAI-compatible speech |
| 7 Edit (剪辑) | FFmpeg export in the studio/worker | No generation API |

Summary: a full “idea → finished clip” path on self-host needs **(a)** an LLM key, **(b)** image path (Seedream **or** ComfyUI), and **(c)** Seedance for video shots unless you only stop at stills/script. TTS can stay on edge-tts.

---

## Auth modes (quick reference)

| Mode | Env | Talks to DTok? |
|:---|:---|:---|
| Local demo (recommended standalone) | `STUDIO_DEMO_ENABLED=true`, use Demo / demo credentials | No |
| Hosted DTok accounts (public demo) | `API_BASE_URL=https://api-app.dtok.io/api/v1`, password/Google | Yes |
| Your own account API | `API_BASE_URL=https://your-api/...` implementing the same `/auth/*` shape | No (your API) |
| Open gate | `STUDIO_AUTH_REQUIRED=false` | No |

Implementation pointers: `studio/server/demo_auth.py`, `studio/server/auth_proxy.py`, `POST /api/auth/demo` in `studio/server/app.py`.

---

## Owner-controlled model endpoints

Configured via env and/or **Model settings** in the UI:

- **Text:** DeepSeek, OpenAI, Claude, Gemini, Qwen, Doubao, Kimi, GLM, MiniMax, OpenRouter, gpuhome / suanqiao token factories, or any OpenAI-compatible base URL.
- **Images:** Volcengine Ark **Seedream**, or `COMFYUI_SERVER_URL` (and related vars) for a GPU you control.
- **Video:** Volcengine Ark **Seedance** (`VOLCENGINE_API_KEY` / `ARK_API_KEY`).
- **Speech:** edge-tts default; optional OpenAI-compatible TTS keys.

There is no requirement to use DTok-billed credits when self-hosting.

---

## Checklist before you call it “fully self-hosted”

- [ ] `STUDIO_PUBLIC_URL` is your host, not `openmontage.dtok.io`
- [ ] Sign-in works via **Demo** (or your own `API_BASE_URL`), without creating a DTok account
- [ ] `MINIO_*` / `OSS_*` point at storage you control (not `minio-api.dtok.io` unless you intend to)
- [ ] LLM key set; image path (Seedream or ComfyUI) set; Seedance key set if you need video shots
- [ ] `GET /api/health` shows Postgres + object storage OK
