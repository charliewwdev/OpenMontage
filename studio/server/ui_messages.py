"""Request-scoped UI locale for user-visible API status / error strings.

The frontend sends ``X-Studio-Locale: zh|en`` (the language picked in the UI).
Only plain status/error text shown to the user is localized here; LLM prompts,
stored project data and messages raised deep inside services stay unchanged.
"""

from __future__ import annotations

from contextvars import ContextVar

SUPPORTED = ("zh", "en")
DEFAULT_LOCALE = "zh"

_current_locale: ContextVar[str] = ContextVar("om_ui_locale", default=DEFAULT_LOCALE)

MESSAGES: dict[str, dict[str, str]] = {
    "entity_qa_force_hint": {
        "zh": "传入 forceEntityQa=true 可强制出片（仍会使用未过检参考图）",
        "en": "Pass forceEntityQa=true to force video generation (reference images that failed QA will still be used).",
    },
    "keys_import_none_in_env": {
        "zh": "进程环境里没有可用的文本大模型 / 火山 Key。请在本页直接粘贴保存即可（运行时动态读取，不必依赖环境变量）。",
        "en": "No text LLM / Volcengine key is available in the process environment. Paste and save keys on this page instead (they are read at runtime; environment variables are not required).",
    },
    "keys_no_llm": {
        "zh": "未配置任何文本大模型 API Key",
        "en": "No text LLM API key configured",
    },
    "keys_no_cursor": {
        "zh": "未配置 CURSOR_API_KEY",
        "en": "CURSOR_API_KEY is not configured",
    },
    "keys_no_volcengine": {
        "zh": "未配置 VOLCENGINE_API_KEY / ARK_API_KEY",
        "en": "VOLCENGINE_API_KEY / ARK_API_KEY is not configured",
    },
    "keys_volcengine_note": {
        "zh": "火山 Key 已写入进程；图片/视频任务会在实际出图出片时校验。",
        "en": "Volcengine key loaded; image/video jobs validate it when they actually run.",
    },
    "keys_no_comfyui": {
        "zh": "未配置 COMFYUI_SERVER_URL（智川云租 GPU 后填写）",
        "en": "COMFYUI_SERVER_URL is not configured (fill it in after renting a GPU on Zhichuan cloud)",
    },
    "jobs_note_error": {
        "zh": "无独立 cron；媒体队列 + 一键全流程为后台任务源。",
        "en": "No separate cron; background jobs come from the media queue and one-click full pipelines.",
    },
    "jobs_note": {
        "zh": "无独立 cron / 定时表；后台任务来自 Redis 媒体队列与项目一键全流程。",
        "en": "No separate cron / schedule; background jobs come from the Redis media queue and project one-click full pipelines.",
    },
    "upload_media_qa_failed": {
        "zh": "文件未通过质量检测：{error}",
        "en": "File failed the quality check: {error}",
    },
    "share_missing_text": {
        "zh": "缺少文案 text",
        "en": "Missing post text",
    },
    "share_browser_failed": {
        "zh": "浏览器发帖失败: {error}",
        "en": "Browser posting failed: {error}",
    },
    "audio_no_dialogue": {
        "zh": "episode has no dialogue text（请用「角色：台词」格式）",
        "en": "Episode has no dialogue text (use the \"Character: line\" format)",
    },
    "video_backend_missing": {
        "zh": "未配置出片后端，或顶部所选后端不可用。请在顶部模型切换选择 ComfyUI / Seedance，并确认 Key 或租机地址。",
        "en": "No video backend configured, or the backend selected at the top is unavailable. Pick ComfyUI / Seedance in the model switcher at the top and check your key or rented GPU URL.",
    },
    "auto_produce_missing_brief": {
        "zh": "请输入一句话想法或粘贴剧本",
        "en": "Enter a one-line idea or paste a script",
    },
}


def normalize_locale(value: str | None) -> str:
    raw = (value or "").strip().lower().replace("_", "-")
    base = raw.split("-", 1)[0]
    return base if base in SUPPORTED else DEFAULT_LOCALE


def set_request_locale(value: str | None) -> str:
    locale = normalize_locale(value)
    _current_locale.set(locale)
    return locale


def get_request_locale() -> str:
    return _current_locale.get()


def ui_msg(key: str, **params: object) -> str:
    entry = MESSAGES[key]
    text = entry.get(get_request_locale()) or entry[DEFAULT_LOCALE]
    return text.format(**params) if params else text
