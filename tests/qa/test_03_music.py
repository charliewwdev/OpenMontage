#!/usr/bin/env python3
"""QA Test 03: Music generation via ElevenLabs."""

import sys, os, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from lib.env_loader import load_env
load_env()

from tools.audio.music_gen import MusicGen

OUT = os.path.join(os.path.dirname(__file__), "output")
os.makedirs(OUT, exist_ok=True)

tool = MusicGen()
print(f"Tool status: {tool.get_status()}")

# Test 1: Upbeat tech background
print("\n--- Test 1: Upbeat tech background ---")
r1 = tool.execute({
    "prompt": "Upbeat electronic background music, 120 BPM, energetic but not overwhelming, suitable for a tech explainer video",
    "duration_seconds": 30,
    "output_path": os.path.join(OUT, "music_upbeat.mp3"),
})
print(f"Success: {r1.success}, Cost: ${r1.cost_usd:.4f}")
if r1.error: print(f"Error: {r1.error}")
if r1.artifacts: print(f"Artifacts: {r1.artifacts}")

# Test 2: Calm ambient
print("\n--- Test 2: Calm ambient ---")
r2 = tool.execute({
    "prompt": "Calm ambient background music, soft piano and strings, 80 BPM, reflective mood, suitable for documentary narration",
    "duration_seconds": 30,
    "output_path": os.path.join(OUT, "music_calm.mp3"),
})
print(f"Success: {r2.success}, Cost: ${r2.cost_usd:.4f}")
if r2.error: print(f"Error: {r2.error}")
if r2.artifacts: print(f"Artifacts: {r2.artifacts}")

# Probe outputs
import subprocess
for name in ["music_upbeat.mp3", "music_calm.mp3"]:
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

print("\n=== MUSIC GEN TEST COMPLETE ===")
