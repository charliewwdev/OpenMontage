"""Regression tests for uploaded script parsing and dialogue extraction."""

from io import BytesIO

import pytest

from studio.server.script_parse import (
    dialogue_from_episode,
    dialogue_lines_for_episode,
    extract_dialogue_lines,
    extract_text,
    guess_title,
)


def test_guess_title_prefers_first_nonempty_line() -> None:
    assert guess_title("\n# My story\nSecond line", "fallback.txt") == "My story"
    assert guess_title(" \n\n", "fallback.txt") == "fallback"


def test_extract_text_decodes_utf8_and_gbk() -> None:
    assert extract_text("script.txt", "Hello, 世界".encode()) == "Hello, 世界"
    assert extract_text("script.txt", "你好，世界".encode("gbk")) == "你好，世界"


def test_extract_text_reads_docx() -> None:
    docx = pytest.importorskip("docx")
    document = docx.Document()
    document.add_paragraph("First scene")
    document.add_paragraph("Second scene")
    data = BytesIO()
    document.save(data)

    assert extract_text("script.docx", data.getvalue()) == "First scene\n\nSecond scene"


def test_extract_dialogue_lines_handles_speakers_and_limit() -> None:
    content = "小明：你好！\nAlice: Hello there\nBob: See you later"
    assert extract_dialogue_lines(content, limit=2) == [
        {"speaker": "小明", "text": "你好！"},
        {"speaker": "Alice", "text": "Hello there"},
    ]


def test_episode_helpers_prefer_ordered_shots_and_flatten_speech() -> None:
    shots = [
        {"shotOrder": 2, "dialogue": "Bob: Goodbye"},
        {"shotOrder": 1, "dialogue": "Alice: Hello"},
    ]
    assert dialogue_lines_for_episode("Narration", shots, limit=1) == [
        {"speaker": "Alice", "text": "Hello"}
    ]
    assert (
        dialogue_from_episode("Alice: Hello\nBob: Goodbye", limit=13)
        == "Hello。Goodbye"
    )
