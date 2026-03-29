#!/usr/bin/env python3
"""QA Test 01: TTS voice generation via ElevenLabs."""

import sys, os, json, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from lib.env_loader import load_env
load_env()

from tools.audio.elevenlabs_tts import ElevenLabsTTS

OUT = os.path.join(os.path.dirname(__file__), "output")
os.makedirs(OUT, exist_ok=True)

tool = ElevenLabsTTS()
print(f"Tool status: {tool.get_status()}")

# Test 1: Short narration
print("\n--- Test 1: Short narration ---")
r1 = tool.execute({
    "text": "Welcome to OpenMontage. Let's build something amazing together.",
    "output_path": os.path.join(OUT, "tts_short.mp3"),
})
print(f"Success: {r1.success}, Cost: ${r1.cost_usd:.4f}, Duration: {r1.duration_seconds:.2f}s")
if r1.error: print(f"Error: {r1.error}")
if r1.artifacts: print(f"Artifacts: {r1.artifacts}")

# Test 2: Longer paragraph with technical content
print("\n--- Test 2: Technical narration ---")
r2 = tool.execute({
    "text": (
        "Quantum computing leverages quantum mechanical phenomena like superposition and entanglement "
        "to process information in fundamentally different ways than classical computers. "
        "While a classical bit can be either zero or one, a quantum bit, or qubit, can exist in "
        "a superposition of both states simultaneously. This allows quantum computers to explore "
        "many possible solutions at once, making them exceptionally powerful for certain types of problems."
    ),
    "output_path": os.path.join(OUT, "tts_technical.mp3"),
})
print(f"Success: {r2.success}, Cost: ${r2.cost_usd:.4f}, Duration: {r2.duration_seconds:.2f}s")
if r2.error: print(f"Error: {r2.error}")
if r2.artifacts: print(f"Artifacts: {r2.artifacts}")

# Test 3: Emotional / storytelling narration
print("\n--- Test 3: Storytelling narration ---")
r3 = tool.execute({
    "text": (
        "Picture this. You wake up one morning, check your phone, and discover that overnight, "
        "your side project went viral. Thousands of people are using it. Messages are flooding in. "
        "This isn't a dream. This is what happens when you build something people actually need."
    ),
    "output_path": os.path.join(OUT, "tts_story.mp3"),
})
print(f"Success: {r3.success}, Cost: ${r3.cost_usd:.4f}, Duration: {r3.duration_seconds:.2f}s")
if r3.error: print(f"Error: {r3.error}")
if r3.artifacts: print(f"Artifacts: {r3.artifacts}")

# Probe outputs with ffprobe
import subprocess
for name in ["tts_short.mp3", "tts_technical.mp3", "tts_story.mp3"]:
    path = os.path.join(OUT, name)
    if os.path.exists(path):
        probe = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", path],
            capture_output=True, text=True
        )
        info = json.loads(probe.stdout)
        fmt = info.get("format", {})
        streams = info.get("streams", [{}])
        audio = streams[0] if streams else {}
        print(f"\n[{name}] Duration: {fmt.get('duration', '?')}s, "
              f"Sample rate: {audio.get('sample_rate', '?')}Hz, "
              f"Channels: {audio.get('channels', '?')}, "
              f"Codec: {audio.get('codec_name', '?')}, "
              f"Size: {os.path.getsize(path)} bytes")
    else:
        print(f"\n[{name}] FILE NOT FOUND")

print("\n=== TTS TEST COMPLETE ===")
