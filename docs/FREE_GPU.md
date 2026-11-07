# Free GPU / free inference quotas (2026)

Use these when you want Drama Studio generation without renting a ComfyUI box or paying Volcengine. Quotas change; verify on each vendor’s dashboard.

| Provider | What you get for free | Studio wiring | Sign up |
|:---|:---|:---|:---|
| **Pollinations** | **No API key**: anonymous OpenAI-compatible chat + FLUX-style images (rate-limited). | LLM `pollinations` (always on); image backend `pollinations` (default on; `POLLINATIONS_IMAGE=0` to disable) | [pollinations.ai](https://pollinations.ai/) |
| **NVIDIA NIM** (`build.nvidia.com`) | Hosted GPU: **FLUX image works with one key**. Chat models are listed broadly but each must be enabled on its model page (`Get API Key`); cold starts can take >60s or 404 until enabled. Rate-limited free prototype tier. | `NVIDIA_API_KEY` → `STUDIO_IMAGE_BACKEND=nvidia`; optional `LLM_PROVIDER=nvidia` after enabling a chat model | [Get API Key](https://build.nvidia.com/settings) |
| **GroqCloud** | Free plan LLM on Groq LPU (rate limits per model; no card). | `GROQ_API_KEY` → LLM provider `groq` | [console.groq.com](https://console.groq.com/keys) |
| **Cloudflare Workers AI** | **10,000 Neurons / day** on Workers Free (reset 00:00 UTC). Text + some image models (e.g. FLUX schnell). Larger frontier models may require Paid. | `CF_ACCOUNT_ID` + `CF_API_TOKEN` → LLM `cloudflare` | [Workers AI](https://developers.cloudflare.com/workers-ai/) |
| **Google AI Studio (Gemini)** | Free API key for Gemini Flash (not a raw GPU rental; free hosted inference). | `GEMINI_API_KEY` | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) |
| **OpenRouter `:free` models** | Community free model routes (unstable / queue). | `OPENROUTER_API_KEY` + model ending in `:free` | [openrouter.ai/keys](https://openrouter.ai/keys) |
| **SambaNova Cloud** | Free-tier OpenAI-compatible chat (Llama / Gemma / GPT-OSS, etc.). | `SAMBANOVA_API_KEY` → LLM `sambanova` | [cloud.sambanova.ai](https://cloud.sambanova.ai/) |
| **Cohere Trial** | Trial credits via OpenAI Compatibility endpoint. | `COHERE_API_KEY` → LLM `cohere` | [dashboard.cohere.com](https://dashboard.cohere.com/api-keys) |
| **Mistral La Plateforme** | Free experiment quota (prefer `mistral-small-latest` / Nemo). | `MISTRAL_API_KEY` → LLM `mistral` | [console.mistral.ai](https://console.mistral.ai/api-keys/) |
| **Hugging Face ZeroGPU** | ~5 GPU minutes / day on Gradio Spaces (demo Spaces, not Studio API). | Host a Space; optional `HF_TOKEN` for Inference Providers (~$0.10/mo credits). | [ZeroGPU docs](https://huggingface.co/docs/hub/spaces-zerogpu) |
| **Google Colab / Kaggle** | Notebook T4-class GPU sessions (hours/week style quotas). | Run ComfyUI/notebook → expose URL → `COMFYUI_SERVER_URL` | Colab / Kaggle |
| **Modal Starter** | ~$30 / month compute credit (serverless GPU). | Custom OpenAI-compatible or Comfy bridge | [modal.com](https://modal.com) |
| **RunPod / Vast.ai trials** | Occasional new-user credits (not forever-free). | `scripts/provision_comfy_gpu.py` or paste Comfy URL | Vast / RunPod |

## Recommended Drama Studio setup (zero rent)

```bash
# Defaults (compose + .env.example): free-first auto routing
STUDIO_IMAGE_BACKEND=auto
STUDIO_VIDEO_BACKEND=auto
STUDIO_FREE_FIRST=1
# LLM_PROVIDER=   # empty → nvidia → groq → gemini → cloudflare → openrouter
#                 # → pollinations (no key) → sambanova → cohere → mistral → paid

# Zero-config free fallback (no keys required):
# POLLINATIONS_IMAGE=1
# POLLINATIONS_MODEL=openai-fast
# POLLINATIONS_IMAGE_MODEL=flux

NVIDIA_API_KEY=nvapi-...
NVIDIA_IMAGE_MODEL=flux-3-image-klein
GROQ_API_KEY=gsk_...              # or GEMINI_API_KEY=
CF_ACCOUNT_ID=...
CF_API_TOKEN=...                  # Workers AI: LLM + FLUX images
CF_IMAGE_MODEL=@cf/black-forest-labs/flux-1-schnell
# OPENROUTER_API_KEY=
# SAMBANOVA_API_KEY=
# COHERE_API_KEY=
# MISTRAL_API_KEY=
HF_TOKEN=hf_...
HF_IMAGE_MODEL=black-forest-labs/FLUX.1-schnell
```

Fill keys in UI **模型配置**, or `studio/.env` / Compose env. Do not commit real keys.

## Free GPU for **video** (Drama Studio unblock)

Studio video only runs on **ComfyUI** (`COMFYUI_*_SERVER_URL`) or **Seedance** (paid Volcengine). Hosted “free API” keys (NVIDIA / Groq / Gemini / CF) do **not** replace video. Use one of the channels below to get a reachable Comfy endpoint, then set:

```bash
COMFYUI_SERVER_URL=https://…   # must answer Comfy /system_stats (not a 404 landing page)
STUDIO_VIDEO_BACKEND=auto      # picks reachable Comfy before Seedance
```

| Priority | Channel | Free quota (verify live) | Fit for Studio video | How to wire |
|:---|:---|:---|:---|:---|
| **1** | **Google Colab** free | ~15–30 h/week T4 (dynamic; no guarantee) | Best DIY: run ComfyUI notebook + Cloudflare tunnel | Paste tunnel URL → `COMFYUI_SERVER_URL` |
| **1** | **Kaggle** Notebooks | ~30 h/week GPU (often T4/P100), resets weekly | Same pattern as Colab | Tunnel / ngrok → Comfy URL |
| **2** | **Lightning AI** free | ~5 credits on signup; +~25 after card; ~30 credits ≈ tens of interruptible GPU-hours | Good short Comfy sessions | Expose Comfy port → Studio |
| **2** | **Modal** Starter | **~$30 / month** compute credit | Serverless GPU; write a thin Comfy/OpenAI bridge or keep a worker | Custom URL or job bridge |
| **3** | **Comfy Cloud** ([cloud.comfy.org](https://www.comfy.org/cloud/)) | New accounts: **~5 free GPU runs** (pricing page). Older “400 credits/mo” free tier may be gone — check dashboard | Official RTX Pro 6000; video templates (Wan/Seedance/…); **not** a drop-in for our local Comfy API unless you use their Cloud API / MCP | Trial / paid plans; Studio still expects self-hosted Comfy HTTP by default |
| **3** | **HF ZeroGPU** | 5 min/day free (PRO 40 min) | Gradio Spaces only — **too short / wrong shape** for batch Drama shots | Skip for Studio backlog |
| **4** | **Startup / one-time credits** | Modal / Groq / Nebius / RunPod / Vast / Lambda / Together grants ($1k–$50k, eligibility) | Real GPU hours if you qualify | Vast: `scripts/provision_comfy_gpu.py`; else paste Comfy URL |
| **5** | **NVIDIA NIM free credits** | Prototype credits + rate limits | **Image / LLM**, not MiniMax H3 video path | Keep for stills (`STUDIO_IMAGE_BACKEND=nvidia`) |

### Practical unblock order (production backlog)

1. **Colab or Kaggle** → start ComfyUI with video workflow (MiniMax H3 / Wan) → `cloudflared tunnel` → update live `COMFYUI_SERVER_URL` (shared secrets / Coolify).
2. If sessions die too often → **Modal $30** or **Lightning** credits for a steadier worker.
3. If you only need a few trial clips → **Comfy Cloud** free runs (UI), not the stuck auto-produce queue.
4. Seedance remains the quality/paid path once Volcengine balance is restored (`STUDIO_VIDEO_BACKEND=seedance`).

## Auto routing notes (shipped defaults)

- **`STUDIO_FREE_FIRST=1` (default):** pinned `comfyui` that is unreachable **falls through** to the next usable backend.
- Image `auto`: **NVIDIA → Cloudflare → HF → Seedream → reachable Comfy**.
- LLM with empty `LLM_PROVIDER`: **nvidia → groq → gemini → cloudflare → openrouter → paid**.
- Video `auto`: **reachable Comfy** (Colab/Kaggle/rental) → **Seedance**. Dead Comfy URLs do not win.

## Quick verify

```bash
# NIM catalog (should list dozens of models)
curl -s -H "Authorization: Bearer $NVIDIA_API_KEY" \
  https://integrate.api.nvidia.com/v1/models | head

# Studio health after compose / local API up
curl -s http://127.0.0.1:8787/api/health
```
