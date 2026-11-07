# Free GPU / free inference quotas (2026)

Use these when you want Drama Studio generation without renting a ComfyUI box or paying Volcengine. Quotas change; verify on each vendor’s dashboard.

| Provider | What you get for free | Studio wiring | Sign up |
|:---|:---|:---|:---|
| **NVIDIA NIM** (`build.nvidia.com`) | Hosted GPU: **FLUX image works with one key**. Chat models are listed broadly but each must be enabled on its model page (`Get API Key`); cold starts can take >60s or 404 until enabled. Rate-limited free prototype tier. | `NVIDIA_API_KEY` → `STUDIO_IMAGE_BACKEND=nvidia`; optional `LLM_PROVIDER=nvidia` after enabling a chat model | [Get API Key](https://build.nvidia.com/settings) |
| **GroqCloud** | Free plan LLM on Groq LPU (rate limits per model; no card). | `GROQ_API_KEY` → LLM provider `groq` | [console.groq.com](https://console.groq.com/keys) |
| **Cloudflare Workers AI** | **10,000 Neurons / day** on Workers Free (reset 00:00 UTC). Text + some image models (e.g. FLUX schnell). Larger frontier models may require Paid. | `CF_ACCOUNT_ID` + `CF_API_TOKEN` → LLM `cloudflare` | [Workers AI](https://developers.cloudflare.com/workers-ai/) |
| **Google AI Studio (Gemini)** | Free API key for Gemini Flash (not a raw GPU rental; free hosted inference). | `GEMINI_API_KEY` | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) |
| **OpenRouter `:free` models** | Community free model routes (unstable / queue). | `OPENROUTER_API_KEY` + model ending in `:free` | [openrouter.ai/keys](https://openrouter.ai/keys) |
| **Hugging Face ZeroGPU** | ~5 GPU minutes / day on Gradio Spaces (demo Spaces, not Studio API). | Host a Space; optional `HF_TOKEN` for Inference Providers (~$0.10/mo credits). | [ZeroGPU docs](https://huggingface.co/docs/hub/spaces-zerogpu) |
| **Google Colab / Kaggle** | Notebook T4-class GPU sessions (hours/week style quotas). | Run ComfyUI/notebook → expose URL → `COMFYUI_SERVER_URL` | Colab / Kaggle |
| **Modal Starter** | ~$30 / month compute credit (serverless GPU). | Custom OpenAI-compatible or Comfy bridge | [modal.com](https://modal.com) |
| **RunPod / Vast.ai trials** | Occasional new-user credits (not forever-free). | `scripts/provision_comfy_gpu.py` or paste Comfy URL | Vast / RunPod |

## Recommended Drama Studio setup (zero rent)

```bash
# 1) NVIDIA — free FLUX stills + free NIM chat
NVIDIA_API_KEY=nvapi-...          # build.nvidia.com
NVIDIA_IMAGE_MODEL=flux-3-image-klein
STUDIO_IMAGE_BACKEND=nvidia
# Optional: after enabling a chat model on build.nvidia.com
# LLM_PROVIDER=nvidia
# NVIDIA_LLM_MODEL=deepseek-ai/deepseek-v4.1-flash

# 2) Free LLM (more reliable for scripts than cold NIM chat)
GROQ_API_KEY=gsk_...
# or
GEMINI_API_KEY=AIza...

# 3) Optional Cloudflare daily neurons
CF_ACCOUNT_ID=...
CF_API_TOKEN=...                  # Workers AI edit permission
LLM_PROVIDER=cloudflare
CLOUDFLARE_LLM_MODEL=@cf/meta/llama-3.1-8b-instruct
```

Fill keys in UI **模型配置**, or `studio/.env` / Compose env. Do not commit real keys.

## Auto routing notes

- Image `STUDIO_IMAGE_BACKEND=auto` prefers **NVIDIA (free)** over Seedream / Comfy when the NIM key is present.
- Text `LLM_PROVIDER` unset: Studio walks configured providers; put `nvidia` / `groq` / `gemini` ahead of paid token factories if you want free-first.
- Video shots still need **Seedance (paid)** or a **ComfyUI** GPU you control — there is no durable free Seedance-class video quota.

## Quick verify

```bash
# NIM catalog (should list dozens of models)
curl -s -H "Authorization: Bearer $NVIDIA_API_KEY" \
  https://integrate.api.nvidia.com/v1/models | head

# Studio health after compose / local API up
curl -s http://127.0.0.1:8787/api/health
```
