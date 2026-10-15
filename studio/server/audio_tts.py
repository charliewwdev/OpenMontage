"""Dialogue TTS + optional BGM helpers (edge-tts primary, OpenAI-compatible fallback)."""

from __future__ import annotations

import asyncio
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from settings_store import get_secret

logger = logging.getLogger("studio.audio_tts")

# Alternate Edge voices so multi-speaker dialogue does not sound like one narrator.
_FEMALE_VOICES = (
    "zh-CN-XiaoxiaoNeural",
    "zh-CN-XiaoyiNeural",
    "zh-CN-XiaohanNeural",
)
_MALE_VOICES = (
    "zh-CN-YunxiNeural",
    "zh-CN-YunjianNeural",
    "zh-CN-YunyangNeural",
)
_NARRATOR_VOICE = "zh-CN-YunyangNeural"


def pick_voice_for_speaker(speaker: str, *, known: dict[str, str] | None = None) -> str:
    """Stable voice assignment per speaker name."""
    name = (speaker or "旁白").strip() or "旁白"
    if known is not None and name in known:
        return known[name]
    if name in {"旁白", "解说", "narrator", "VO"}:
        voice = get_secret("EDGE_TTS_VOICE") or _NARRATOR_VOICE
    else:
        # Heuristic + hash: prefer male/female pools without needing LLM gender labels.
        female_hints = ("女", "姐", "妈", "婆", "妹", "娘", "姨", "玲", "晓", "婷", "芳", "丽", "娟", "敏", "娜", "雪", "倩")
        male_hints = ("男", "哥", "爸", "叔", "爷", "弟", "明", "强", "伟", "军", "磊", "豪", "辰", "默", "昊", "宇", "泽", "轩")
        digest = sum(ord(ch) for ch in name)
        if any(h in name for h in female_hints) and not any(h in name for h in male_hints):
            voice = _FEMALE_VOICES[digest % len(_FEMALE_VOICES)]
        elif any(h in name for h in male_hints) and not any(h in name for h in female_hints):
            voice = _MALE_VOICES[digest % len(_MALE_VOICES)]
        else:
            # Alternate pools by name hash so two unnamed roles still differ.
            pool = _FEMALE_VOICES if digest % 2 == 0 else _MALE_VOICES
            voice = pool[digest % len(pool)]
    if known is not None:
        known[name] = voice
    return voice


async def _edge_tts_save(text: str, out_path: Path, voice: str = "zh-CN-XiaoxiaoNeural") -> None:
    import edge_tts  # type: ignore

    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(str(out_path))


def _edge_tts_cli(text: str, out_path: Path, voice: str = "zh-CN-XiaoxiaoNeural") -> bool:
    """Fallback when the Python package import works but asyncio path fails."""
    try:
        proc = subprocess.run(
            ["edge-tts", "--voice", voice, "--text", text[:3000], "--write-media", str(out_path)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        return proc.returncode == 0 and out_path.is_file() and out_path.stat().st_size > 0
    except Exception as exc:
        logger.warning("edge-tts CLI failed: %s", exc)
        return False


def _openai_compatible_speech(text: str, out_path: Path, *, voice: str | None = None) -> dict | None:
    """Call /audio/speech on any OpenAI-compatible base (not only api.openai.com)."""
    api_key = get_secret("OPENAI_API_KEY") or get_secret("OPENAI_TTS_API_KEY")
    if not api_key:
        return None
    base = (get_secret("OPENAI_TTS_BASE_URL") or get_secret("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
    model = get_secret("OPENAI_TTS_MODEL") or "gpt-4o-mini-tts"
    speech_voice = voice or get_secret("OPENAI_TTS_VOICE") or "alloy"
    import json
    import urllib.error
    import urllib.request

    payload = json.dumps({"model": model, "voice": speech_voice, "input": text[:4000]}).encode("utf-8")
    req = urllib.request.Request(
        f"{base}/audio/speech",
        data=payload,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            out_path.write_bytes(resp.read())
        if out_path.is_file() and out_path.stat().st_size > 0:
            return {"provider": "openai-compatible", "path": str(out_path), "bytes": out_path.stat().st_size, "base": base}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        logger.warning("OpenAI-compatible TTS HTTP %s: %s", exc.code, detail)
    except Exception as exc:
        logger.warning("OpenAI-compatible TTS failed: %s", exc)
    return None


def synthesize_mp3(text: str, out_path: Path, *, voice: str | None = None) -> dict:
    """Single-voice TTS (legacy / narrator). Prefer synthesize_dialogue_mp3 for short drama."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cleaned = (text or "").strip()
    if not cleaned:
        raise RuntimeError("没有可合成的文本")

    voice_id = voice or get_secret("EDGE_TTS_VOICE") or "zh-CN-XiaoxiaoNeural"

    try:
        asyncio.run(_edge_tts_save(cleaned, out_path, voice=voice_id))
        if out_path.is_file() and out_path.stat().st_size > 0:
            return {"provider": "edge-tts", "path": str(out_path), "bytes": out_path.stat().st_size, "voice": voice_id}
    except Exception as exc:
        logger.warning("edge-tts python failed: %s", exc)

    if _edge_tts_cli(cleaned, out_path, voice=voice_id):
        return {"provider": "edge-tts-cli", "path": str(out_path), "bytes": out_path.stat().st_size, "voice": voice_id}

    speech = _openai_compatible_speech(cleaned, out_path)
    if speech:
        return speech

    raise RuntimeError(
        "配音失败：edge-tts 不可用，且 OpenAI 兼容 TTS 未成功。"
        "可配置 OPENAI_API_KEY + OPENAI_BASE_URL（需支持 /audio/speech），或跳过配音。"
    )


def _ffmpeg_concat_mp3(parts: list[Path], out_path: Path, *, gap_ms: int = 280) -> None:
    if not parts:
        raise RuntimeError("没有可拼接的配音片段")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="om-tts-") as tmp:
        tmp_path = Path(tmp)
        normalized: list[Path] = []
        for i, part in enumerate(parts):
            norm = tmp_path / f"{i:03d}.mp3"
            cmd = [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(part),
                "-ar",
                "44100",
                "-ac",
                "1",
                "-c:a",
                "libmp3lame",
                "-q:a",
                "4",
                str(norm),
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True)
            if proc.returncode != 0 or not norm.is_file():
                raise RuntimeError(proc.stderr.strip() or "ffmpeg normalize dialogue failed")
            normalized.append(norm)
            if gap_ms > 0 and i < len(parts) - 1:
                silence = tmp_path / f"{i:03d}_gap.mp3"
                gap_cmd = [
                    "ffmpeg",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-y",
                    "-f",
                    "lavfi",
                    "-i",
                    f"anullsrc=r=44100:cl=mono",
                    "-t",
                    f"{gap_ms / 1000:.3f}",
                    "-c:a",
                    "libmp3lame",
                    "-q:a",
                    "4",
                    str(silence),
                ]
                proc = subprocess.run(gap_cmd, capture_output=True, text=True)
                if proc.returncode == 0 and silence.is_file():
                    normalized.append(silence)

        list_file = tmp_path / "list.txt"
        list_file.write_text("\n".join(f"file '{p.as_posix()}'" for p in normalized) + "\n", encoding="utf-8")
        proc = subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(list_file),
                "-c",
                "copy",
                str(out_path),
            ],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0 or not out_path.is_file():
            raise RuntimeError(proc.stderr.strip() or "ffmpeg concat dialogue failed")


def synthesize_dialogue_mp3(lines: list[dict[str, Any]], out_path: Path) -> dict:
    """Multi-speaker short-drama dialogue (not single-voice narration).

    Each item: {"speaker": "林晓", "text": "你给我站住"} — spoken text only, no 「X说：」.
    """
    cleaned: list[dict[str, str]] = []
    for item in lines or []:
        text = str(item.get("text") or "").strip()
        if len(text) < 2:
            continue
        speaker = str(item.get("speaker") or "对白").strip() or "对白"
        cleaned.append({"speaker": speaker, "text": text[:400]})
    if not cleaned:
        raise RuntimeError("没有可合成的对白台词")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    voice_map: dict[str, str] = {}
    with tempfile.TemporaryDirectory(prefix="om-dialogue-") as tmp:
        tmp_path = Path(tmp)
        parts: list[Path] = []
        voices_used: list[str] = []
        for i, line in enumerate(cleaned):
            voice = pick_voice_for_speaker(line["speaker"], known=voice_map)
            voices_used.append(f"{line['speaker']}={voice}")
            part = tmp_path / f"{i:03d}.mp3"
            # Speak the line only — never prefix with "角色说：" (that becomes narration).
            synthesize_mp3(line["text"], part, voice=voice)
            parts.append(part)
        if len(parts) == 1:
            out_path.write_bytes(parts[0].read_bytes())
        else:
            _ffmpeg_concat_mp3(parts, out_path, gap_ms=320)
    return {
        "provider": "edge-tts-dialogue",
        "path": str(out_path),
        "bytes": out_path.stat().st_size if out_path.is_file() else 0,
        "lines": len(cleaned),
        "voices": voices_used[:12],
        "mode": "dialogue",
    }


def generate_bgm_mp3(out_path: Path, *, duration_sec: float = 60.0, mood: str = "drama") -> dict:
    """Procedural soft drama bed via ffmpeg (no external music API required)."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    dur = max(8.0, min(240.0, float(duration_sec or 60)))
    # Soft low pad + slow pulse — sits under dialogue without sounding like a jingle.
    if mood in {"tense", "suspense", "悬疑"}:
        filter_graph = (
            "sine=f=110:d={d}[a];sine=f=164.8:d={d}[b];sine=f=196:d={d}[c];"
            "[a][b][c]amix=inputs=3:duration=longest,lowpass=f=600,volume=0.11,afade=t=in:st=0:d=1.5,"
            "afade=t=out:st={fade}:d=2"
        ).format(d=dur, fade=max(0.5, dur - 2))
    else:
        filter_graph = (
            "sine=f=130.8:d={d}[a];sine=f=164.8:d={d}[b];sine=f=196:d={d}[c];"
            "anoisesrc=color=pink:d={d},lowpass=f=280,volume=0.04[n];"
            "[a][b][c]amix=inputs=3:duration=longest,lowpass=f=700,volume=0.09[pad];"
            "[pad][n]amix=inputs=2:duration=longest,afade=t=in:st=0:d=2,afade=t=out:st={fade}:d=2.5"
        ).format(d=dur, fade=max(0.5, dur - 2.5))
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-f",
        "lavfi",
        "-i",
        filter_graph,
        "-t",
        str(dur),
        "-ar",
        "44100",
        "-ac",
        "2",
        "-c:a",
        "libmp3lame",
        "-q:a",
        "5",
        str(out_path),
    ]
    # lavfi complex graphs need -filter_complex when multi-label; for single -i string with filters,
    # use -filter_complex form:
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-filter_complex",
        filter_graph,
        "-t",
        str(dur),
        "-ar",
        "44100",
        "-ac",
        "2",
        "-c:a",
        "libmp3lame",
        "-q:a",
        "5",
        str(out_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 or not out_path.is_file() or out_path.stat().st_size <= 0:
        raise RuntimeError(proc.stderr.strip() or "ffmpeg BGM generate failed")
    return {"provider": "ffmpeg-ambient", "path": str(out_path), "bytes": out_path.stat().st_size, "duration": dur}


def mix_video_with_audio(
    video_path: Path,
    audio_path: Path,
    out_path: Path,
    *,
    bgm_path: Path | None = None,
    dialogue_volume: float = 1.0,
    bgm_volume: float = 0.16,
    video_audio_volume: float = 0.35,
    keep_video_audio: bool = False,
) -> None:
    """Mux dialogue (and optional BGM) onto the picture.

    By default replaces Seedance track with dialogue+BGM so multi-speaker dubbing is clear.
    Set keep_video_audio=True to mix original clip audio with dialogue/BGM.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    has_bgm = bool(bgm_path and Path(bgm_path).is_file())
    inputs = ["-i", str(video_path), "-i", str(audio_path)]
    if has_bgm:
        inputs += ["-i", str(bgm_path)]

    if has_bgm and keep_video_audio:
        filter_complex = (
            f"[1:a]volume={dialogue_volume}[dlg];"
            f"[2:a]volume={bgm_volume},aloop=loop=-1:size=2e+09[bg];"
            f"[0:a]volume={video_audio_volume}[orig];"
            f"[dlg][bg][orig]amix=inputs=3:duration=first:dropout_transition=2[aout]"
        )
    elif has_bgm:
        filter_complex = (
            f"[1:a]volume={dialogue_volume}[dlg];"
            f"[2:a]volume={bgm_volume},aloop=loop=-1:size=2e+09[bg];"
            f"[dlg][bg]amix=inputs=2:duration=first:dropout_transition=2[aout]"
        )
    elif keep_video_audio:
        filter_complex = (
            f"[1:a]volume={dialogue_volume}[dlg];"
            f"[0:a]volume={video_audio_volume}[orig];"
            f"[dlg][orig]amix=inputs=2:duration=first:dropout_transition=2[aout]"
        )
    else:
        # Simple replace (legacy path)
        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(video_path),
            "-i",
            str(audio_path),
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-shortest",
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-movflags",
            "+faststart",
            str(out_path),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.strip() or "ffmpeg audio mix failed")
        return

    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        *inputs,
        "-filter_complex",
        filter_complex,
        "-map",
        "0:v:0",
        "-map",
        "[aout]",
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-shortest",
        "-movflags",
        "+faststart",
        str(out_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "ffmpeg audio/BGM mix failed")
