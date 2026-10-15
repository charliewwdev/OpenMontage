"""Mainstream LLM provider catalog for Drama Studio keys / routing."""

from __future__ import annotations

from typing import Any

# kind: openai = OpenAI-compatible /chat/completions
#       anthropic = Anthropic Messages API
#       gemini = Google Generative Language API
#       cursor = Cursor Cloud Agents
LLM_PROVIDERS: list[dict[str, Any]] = [
    {
        "id": "gpuhome",
        "label": "智川云 Token",
        "kind": "openai",
        "keyEnv": "GPUHOME_API_KEY",
        "baseEnv": "GPUHOME_BASE_URL",
        "modelEnv": "GPUHOME_MODEL",
        "defaultBase": "https://tokens.gpuhome.cc/v1",
        "defaultModel": "deepseek-v4-flash",
        "docs": "https://tokens.gpuhome.cc/pricing",
        "placeholder": "sk-...",
        "hint": "余额需从 gpuhome.cc 转到 Token 工厂；下方可选模型广场全部模型。",
        # Synced from GET https://tokens.gpuhome.cc/v1/models (2026-10-14)
        "models": [
            {"id": "deepseek-v4-flash", "label": "DeepSeek V4 Flash（默认·快）"},
            {"id": "deepseek-v4-pro", "label": "DeepSeek V4 Pro（强）"},
            {"id": "deepseek-flash", "label": "DeepSeek Flash"},
            {"id": "qwen3.8-max", "label": "通义千问 Qwen3.8 Max"},
            {"id": "qwen3.8-27b", "label": "通义千问 Qwen3.8 27B"},
            {"id": "glm-5.3", "label": "智谱 GLM-5.3"},
            {"id": "glm-5.3-flash", "label": "智谱 GLM-5.3 Flash"},
            {"id": "glm-5.2", "label": "智谱 GLM-5.2"},
            {"id": "kimi-k3", "label": "Kimi K3"},
            {"id": "kimi-k2.7-code", "label": "Kimi K2.7 Code"},
            {"id": "minimax-m3", "label": "MiniMax M3"},
            {"id": "mimo-v2.5-pro", "label": "MiMo V2.5 Pro"},
        ],
    },
    {
        "id": "deepseek",
        "label": "DeepSeek",
        "kind": "openai",
        "keyEnv": "DEEPSEEK_API_KEY",
        "baseEnv": "DEEPSEEK_BASE_URL",
        "modelEnv": "DEEPSEEK_MODEL",
        "defaultBase": "https://api.deepseek.com",
        "defaultModel": "deepseek-chat",
        "docs": "https://platform.deepseek.com/api-docs/",
        "placeholder": "sk-...",
    },
    {
        "id": "openai",
        "label": "OpenAI",
        "kind": "openai",
        "keyEnv": "OPENAI_API_KEY",
        "baseEnv": "OPENAI_BASE_URL",
        "modelEnv": "OPENAI_MODEL",
        "defaultBase": "https://api.openai.com/v1",
        "defaultModel": "gpt-4o",
        "docs": "https://platform.openai.com/api-keys",
        "placeholder": "sk-...",
    },
    {
        "id": "anthropic",
        "label": "Anthropic Claude",
        "kind": "anthropic",
        "keyEnv": "ANTHROPIC_API_KEY",
        "baseEnv": "ANTHROPIC_BASE_URL",
        "modelEnv": "ANTHROPIC_MODEL",
        "defaultBase": "https://api.anthropic.com",
        "defaultModel": "claude-sonnet-4-5",
        "docs": "https://console.anthropic.com/settings/keys",
        "placeholder": "sk-ant-...",
    },
    {
        "id": "gemini",
        "label": "Google Gemini",
        "kind": "gemini",
        "keyEnv": "GEMINI_API_KEY",
        "baseEnv": "GEMINI_BASE_URL",
        "modelEnv": "GEMINI_MODEL",
        "defaultBase": "https://generativelanguage.googleapis.com/v1beta",
        "defaultModel": "gemini-2.0-flash",
        "docs": "https://aistudio.google.com/apikey",
        "placeholder": "AIza...",
    },
    {
        "id": "grok",
        "label": "xAI Grok",
        "kind": "openai",
        "keyEnv": "XAI_API_KEY",
        "baseEnv": "XAI_BASE_URL",
        "modelEnv": "XAI_MODEL",
        "defaultBase": "https://api.x.ai/v1",
        "defaultModel": "grok-2-latest",
        "docs": "https://console.x.ai/",
        "placeholder": "xai-...",
    },
    {
        "id": "moonshot",
        "label": "Moonshot Kimi",
        "kind": "openai",
        "keyEnv": "MOONSHOT_API_KEY",
        "baseEnv": "MOONSHOT_BASE_URL",
        "modelEnv": "MOONSHOT_MODEL",
        "defaultBase": "https://api.moonshot.cn/v1",
        "defaultModel": "moonshot-v1-128k",
        "docs": "https://platform.moonshot.cn/console/api-keys",
        "placeholder": "sk-...",
    },
    {
        "id": "qwen",
        "label": "通义千问 Qwen",
        "kind": "openai",
        "keyEnv": "DASHSCOPE_API_KEY",
        "baseEnv": "DASHSCOPE_BASE_URL",
        "modelEnv": "QWEN_MODEL",
        "defaultBase": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "defaultModel": "qwen-plus",
        "docs": "https://bailian.console.aliyun.com/",
        "placeholder": "sk-...",
    },
    {
        "id": "minimax",
        "label": "MiniMax",
        "kind": "openai",
        "keyEnv": "MINIMAX_API_KEY",
        "baseEnv": "MINIMAX_BASE_URL",
        "modelEnv": "MINIMAX_MODEL",
        "defaultBase": "https://api.minimax.chat/v1",
        "defaultModel": "MiniMax-Text-01",
        "docs": "https://platform.minimaxi.com/",
        "placeholder": "eyJ...",
    },
    {
        "id": "zhipu",
        "label": "智谱 GLM",
        "kind": "openai",
        "keyEnv": "ZHIPU_API_KEY",
        "baseEnv": "ZHIPU_BASE_URL",
        "modelEnv": "ZHIPU_MODEL",
        "defaultBase": "https://open.bigmodel.cn/api/paas/v4",
        "defaultModel": "glm-4-plus",
        "docs": "https://open.bigmodel.cn/usercenter/apikeys",
        "placeholder": "...",
    },
    {
        "id": "doubao",
        "label": "豆包 Doubao",
        "kind": "openai",
        "keyEnv": "DOUBAO_API_KEY",
        "baseEnv": "DOUBAO_BASE_URL",
        "modelEnv": "DOUBAO_MODEL",
        "defaultBase": "https://ark.cn-beijing.volces.com/api/v3",
        "defaultModel": "doubao-seed-1-6-250615",
        "docs": "https://console.volcengine.com/ark",
        "placeholder": "...",
    },
    {
        "id": "openrouter",
        "label": "OpenRouter",
        "kind": "openai",
        "keyEnv": "OPENROUTER_API_KEY",
        "baseEnv": "OPENROUTER_BASE_URL",
        "modelEnv": "OPENROUTER_MODEL",
        "defaultBase": "https://openrouter.ai/api/v1",
        "defaultModel": "openai/gpt-4o-mini",
        "docs": "https://openrouter.ai/keys",
        "placeholder": "sk-or-...",
    },
    {
        "id": "mistral",
        "label": "Mistral",
        "kind": "openai",
        "keyEnv": "MISTRAL_API_KEY",
        "baseEnv": "MISTRAL_BASE_URL",
        "modelEnv": "MISTRAL_MODEL",
        "defaultBase": "https://api.mistral.ai/v1",
        "defaultModel": "mistral-large-latest",
        "docs": "https://console.mistral.ai/api-keys/",
        "placeholder": "...",
    },
    {
        "id": "cursor",
        "label": "Cursor Auto",
        "kind": "cursor",
        "keyEnv": "CURSOR_API_KEY",
        "baseEnv": "CURSOR_API_BASE",
        "modelEnv": "CURSOR_MODEL",
        "defaultBase": "https://api.cursor.com",
        "defaultModel": "auto",
        "docs": "https://cursor.com/dashboard?tab=integrations",
        "placeholder": "crsr_...",
    },
    {
        "id": "custom",
        "label": "自定义 OpenAI 兼容",
        "kind": "openai",
        "keyEnv": "CUSTOM_LLM_API_KEY",
        "baseEnv": "CUSTOM_LLM_BASE_URL",
        "modelEnv": "CUSTOM_LLM_MODEL",
        "defaultBase": "https://api.openai.com/v1",
        "defaultModel": "gpt-4o-mini",
        "docs": "",
        "placeholder": "sk-...",
    },
]


def provider_by_id(pid: str) -> dict[str, Any] | None:
    for item in LLM_PROVIDERS:
        if item["id"] == pid:
            return item
    return None


def all_secret_envs() -> tuple[str, ...]:
    keys = ["LLM_PROVIDER"]
    for item in LLM_PROVIDERS:
        for field in ("keyEnv", "baseEnv", "modelEnv"):
            env = item.get(field)
            if env and env not in keys:
                keys.append(env)
    # Image / video stay separate; ComfyUI points at rented GPU (e.g. gpuhome market)
    keys.extend(
        [
            "VOLCENGINE_API_KEY",
            "ARK_API_KEY",
            "ARK_API_BASE",
            "VOLCENGINE_API_BASE",
            "ARK_PLAN",
            "AGENT_PLAN_TIER",
            "SEEDREAM_MODEL",
            "SEEDANCE_MODEL",
            "COMFYUI_SERVER_URL",
            "COMFYUI_IMAGE_SERVER_URL",
            "COMFYUI_VIDEO_SERVER_URL",
            "COMFYUI_CHECKPOINT",
        ]
    )
    return tuple(keys)
