"""Documentation and skill contract tests for Kling official integration."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.graphics.kling_official_image import KlingOfficialImage
from tools.audio.kling_tts import KlingTTS
from tools.avatar.kling_avatar import KlingAvatar
from tools.avatar.kling_lip_sync import KlingLipSync
from tools.video.kling_official_video import KlingOfficialVideo


def read(path: str) -> str:
    return (PROJECT_ROOT / path).read_text(encoding="utf-8")


def test_env_example_documents_kling_official_keys():
    env = read(".env.example")
    assert "KLING_API_KEY=" in env
    assert "KLING_API_BASE_URL=" in env


def test_provider_docs_distinguish_fal_and_official_kling():
    providers = read("docs/PROVIDERS.md")
    assert "Kling Official" in providers
    assert "kling_official_video" in providers
    assert "kling_official_image" in providers
    assert "kling_tts" in providers
    assert "kling_avatar" in providers
    assert "kling_lip_sync" in providers
    assert "fal.ai" in providers
    assert "provider=\"kling_official\"" in providers
    assert "provider=\"kling\"" in providers
    assert "Elements remain an internal Kling Official helper" in providers
    assert "Account Usage is available as a low-frequency diagnostic helper" in providers
    assert "callback_url" in providers
    assert "audio effects and video effects are documented but intentionally not registered" in providers


def test_architecture_env_mapping_includes_kling_official():
    architecture = read("docs/ARCHITECTURE.md")
    assert "`KLING_API_KEY` | kling_official_video, kling_official_image, kling_tts, kling_avatar, kling_lip_sync" in architecture
    assert "`KLING_API_BASE_URL` | kling_official_video, kling_official_image, kling_tts, kling_avatar, kling_lip_sync" in architecture
    assert "Elements and Account" in architecture
    assert "not separate pipeline stages" in architecture
    assert "Kling Official Phase 3 adds provider tools only where OpenMontage already has a" in architecture


def test_ai_video_skill_metadata_and_new_skill_link():
    ai_video = read(".agents/skills/ai-video-gen/SKILL.md")
    index = read("skills/INDEX.md")
    creative = read("skills/creative/video-gen-prompting.md")
    official_skill = PROJECT_ROOT / ".agents/skills/kling-official/SKILL.md"

    assert "KLING_API_KEY" in ai_video
    assert "kling_official_video" in ai_video
    assert "kling_tts" in index
    assert "avatar/lip-sync face selection" in index
    assert ".agents/skills/kling-official/" in creative
    assert official_skill.is_file()
    official_skill_text = official_skill.read_text(encoding="utf-8")
    assert "Omni References" in official_skill_text
    assert "Callback Notes" in official_skill_text
    assert "TTS Parameters" in official_skill_text
    assert "Lip Sync Parameters" in official_skill_text
    assert "Audio Effects And Video Effects" in official_skill_text


def test_provider_agent_skills_reference_kling_official():
    assert "kling-official" in KlingOfficialVideo().agent_skills
    assert "kling-official" in KlingOfficialImage().agent_skills
    assert "kling-official" in KlingTTS().agent_skills
    assert "kling-official" in KlingAvatar().agent_skills
    assert "kling-official" in KlingLipSync().agent_skills


def test_phase3_does_not_register_audio_or_video_effect_tools():
    from tools.tool_registry import registry

    registry.clear()
    registry.discover("tools")
    assert registry.get("kling_audio") is None
    assert registry.get("kling_effects") is None
