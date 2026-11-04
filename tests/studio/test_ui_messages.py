"""Unit tests for studio/server/ui_messages.py (request-scoped UI locale)."""

from __future__ import annotations

import contextvars
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STUDIO_SERVER = ROOT / "studio" / "server"
if str(STUDIO_SERVER) not in sys.path:
    sys.path.insert(0, str(STUDIO_SERVER))

import ui_messages  # noqa: E402
from ui_messages import MESSAGES, normalize_locale, set_request_locale, ui_msg  # noqa: E402


def _in_fresh_context(fn):
    return contextvars.copy_context().run(fn)


def test_every_message_has_zh_and_en():
    for key, entry in MESSAGES.items():
        assert entry.get("zh"), key
        assert entry.get("en"), key


def test_normalize_locale():
    assert normalize_locale("en") == "en"
    assert normalize_locale("en-US") == "en"
    assert normalize_locale("ZH_cn") == "zh"
    assert normalize_locale("fr") == ui_messages.DEFAULT_LOCALE
    assert normalize_locale(None) == ui_messages.DEFAULT_LOCALE


def test_default_is_chinese():
    assert _in_fresh_context(lambda: ui_msg("keys_no_llm")) == MESSAGES["keys_no_llm"]["zh"]


def test_english_with_params():
    def run():
        set_request_locale("en")
        return ui_msg("upload_media_qa_failed", error="too small")

    assert _in_fresh_context(run) == "File failed the quality check: too small"


def test_frontend_locale_packs_have_same_keys():
    locales = ROOT / "studio" / "config" / "locales"
    zh = json.loads((locales / "zh.json").read_text(encoding="utf-8"))
    en = json.loads((locales / "en.json").read_text(encoding="utf-8"))
    assert set(zh) == set(en)
    assert all(isinstance(v, str) and v for v in en.values())
