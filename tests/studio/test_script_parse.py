"""Unit tests for studio/server/script_parse.py (pure helpers, no I/O services)."""

from __future__ import annotations

import io
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
STUDIO_SERVER = ROOT / "studio" / "server"
if str(STUDIO_SERVER) not in sys.path:
    sys.path.insert(0, str(STUDIO_SERVER))

from script_parse import (  # noqa: E402
    dialogue_from_episode,
    dialogue_lines_for_episode,
    extract_dialogue_lines,
    extract_text,
    guess_title,
)


def test_guess_title_from_first_nonempty_line():
    text = "\n\n# 复仇开局\n下一行\n"
    assert guess_title(text) == "复仇开局"


def test_guess_title_falls_back_to_filename_stem():
    assert guess_title("   \n\n  ", "my_revenge_ep01.txt") == "my_revenge_ep01"


def test_guess_title_default_when_empty():
    assert guess_title("", "") == "未命名剧本"


def test_extract_text_utf8_txt():
    data = "角色：你好\n".encode("utf-8")
    assert "你好" in extract_text("script.txt", data)


def test_extract_text_gbk_txt():
    data = "角色：你好世界".encode("gbk")
    assert "你好世界" in extract_text("script.txt", data)


def test_extract_text_docx_paragraphs():
    pytest.importorskip("docx")
    from docx import Document

    doc = Document()
    doc.add_paragraph("第一段台词")
    doc.add_paragraph("第二段旁白")
    buf = io.BytesIO()
    doc.save(buf)
    text = extract_text("script.docx", buf.getvalue())
    assert "第一段台词" in text
    assert "第二段旁白" in text


def test_extract_dialogue_speaker_colon_styles():
    content = """
# 第一集
场景：咖啡馆

小美：你终于来了。
Alex: I brought the evidence.
旁白：门外雨声渐大。
"""
    lines = extract_dialogue_lines(content, limit=40)
    speakers = {item["speaker"] for item in lines}
    texts = [item["text"] for item in lines]
    assert "小美" in speakers
    assert "Alex" in speakers
    assert any("终于来了" in t for t in texts)
    assert any("evidence" in t.lower() for t in texts)


def test_extract_dialogue_respects_limit():
    content = "\n".join(f"角色{i}：这是第{i}句足够长的对白内容。" for i in range(20))
    lines = extract_dialogue_lines(content, limit=5)
    assert len(lines) == 5


def test_dialogue_lines_for_episode_prefers_shot_dialogue():
    content = "小美：剧本里的台词会被镜头覆盖。"
    shots = [
        {"shotOrder": 2, "dialogue": "反派：你逃不掉。", "characters": ["反派"]},
        {"shotOrder": 1, "dialogue": "小美：我不怕。", "characters": ["小美"]},
    ]
    lines = dialogue_lines_for_episode(content, shots, limit=10)
    assert len(lines) >= 2
    assert lines[0]["speaker"] == "小美"
    assert "不怕" in lines[0]["text"]
    assert lines[1]["speaker"] == "反派"


def test_dialogue_from_episode_flattens_spoken_text():
    content = "小美：走吧。\n阿强：好。"
    flat = dialogue_from_episode(content, limit=1200)
    assert "走吧" in flat
    assert "好" in flat
    assert "小美说" not in flat
