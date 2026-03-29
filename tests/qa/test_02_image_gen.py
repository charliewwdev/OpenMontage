#!/usr/bin/env python3
"""QA Test 02: Image generation via OpenAI (DALL-E 3) and fal.ai (FLUX)."""

import sys, os, json, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from lib.env_loader import load_env
load_env()

from tools.graphics.image_gen import ImageGen

OUT = os.path.join(os.path.dirname(__file__), "output")
os.makedirs(OUT, exist_ok=True)

tool = ImageGen()
print(f"Tool status: {tool.get_status()}")

# Test 1: DALL-E — professional diagram
print("\n--- Test 1: DALL-E professional diagram ---")
r1 = tool.execute({
    "prompt": "A clean, professional infographic showing the 5 stages of a video production pipeline: Idea, Script, Assets, Edit, Publish. Flat design, blue and amber color scheme, white background, no text.",
    "width": 1280,
    "height": 720,
    "provider": "openai",
    "output_path": os.path.join(OUT, "img_dalle_diagram.png"),
})
print(f"Success: {r1.success}, Cost: ${r1.cost_usd:.4f}")
if r1.error: print(f"Error: {r1.error}")
if r1.artifacts: print(f"Artifacts: {r1.artifacts}")

# Test 2: DALL-E — cinematic scene
print("\n--- Test 2: DALL-E cinematic scene ---")
r2 = tool.execute({
    "prompt": "A futuristic control room with holographic displays showing data visualizations, cinematic lighting, wide angle, film grain, warm tones",
    "width": 1280,
    "height": 720,
    "provider": "openai",
    "output_path": os.path.join(OUT, "img_dalle_cinematic.png"),
})
print(f"Success: {r2.success}, Cost: ${r2.cost_usd:.4f}")
if r2.error: print(f"Error: {r2.error}")
if r2.artifacts: print(f"Artifacts: {r2.artifacts}")

# Test 3: FLUX via fal.ai — abstract tech
print("\n--- Test 3: FLUX abstract tech ---")
r3 = tool.execute({
    "prompt": "Abstract visualization of neural network connections, glowing nodes and edges, dark background, neon blue and purple, high detail, 8k render",
    "width": 1280,
    "height": 720,
    "provider": "flux",
    "output_path": os.path.join(OUT, "img_flux_abstract.png"),
})
print(f"Success: {r3.success}, Cost: ${r3.cost_usd:.4f}")
if r3.error: print(f"Error: {r3.error}")
if r3.artifacts: print(f"Artifacts: {r3.artifacts}")

# Test 4: FLUX — character/mascot
print("\n--- Test 4: FLUX character illustration ---")
r4 = tool.execute({
    "prompt": "Friendly robot mascot character, simple geometric design, holding a film clapboard, isometric view, clean white background, flat illustration style",
    "width": 1024,
    "height": 1024,
    "provider": "flux",
    "output_path": os.path.join(OUT, "img_flux_mascot.png"),
})
print(f"Success: {r4.success}, Cost: ${r4.cost_usd:.4f}")
if r4.error: print(f"Error: {r4.error}")
if r4.artifacts: print(f"Artifacts: {r4.artifacts}")

# Probe outputs
import subprocess
for name in ["img_dalle_diagram.png", "img_dalle_cinematic.png", "img_flux_abstract.png", "img_flux_mascot.png"]:
    path = os.path.join(OUT, name)
    if os.path.exists(path):
        probe = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", path],
            capture_output=True, text=True
        )
        info = json.loads(probe.stdout)
        stream = info.get("streams", [{}])[0]
        print(f"\n[{name}] {stream.get('width', '?')}x{stream.get('height', '?')}, "
              f"Format: {stream.get('codec_name', '?')}, "
              f"Size: {os.path.getsize(path)} bytes")
    else:
        print(f"\n[{name}] FILE NOT FOUND")

print("\n=== IMAGE GEN TEST COMPLETE ===")
