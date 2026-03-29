# Asset Director — Talking Head Pipeline

## When to Use

You have a scene plan and script. Your job is to generate the supporting assets for a talking-head video: subtitles, extracted audio, and any overlay graphics.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/asset_manifest.schema.json` | Artifact validation |
| Prior artifacts | Scene plan, Script | What assets to create |
| Tools | `subtitle_gen`, `audio_mixer`, `image_selector` (optional) | Asset generation |

## Process

### Step 1: Generate Subtitles

Use the transcription data from the script stage to create:
- SRT or ASS subtitle file with word-level timing
- Style subtitles per the playbook (font, size, color, position)

### Step 2: Extract and Process Audio

- Extract audio track from raw footage
- Apply noise reduction if needed (via `audio_mixer`)
- Normalize audio levels

### Step 3: Generate Overlays (Optional)

If the scene plan includes overlay scenes:
- Generate text card images
- Generate lower third graphics
- Create any B-roll placeholders

### Step 4: Build Asset Manifest

Document all generated assets with paths, types, and tool references.

### Step 5: Self-Evaluate

| Criterion | Question |
|-----------|----------|
| **Subtitles** | Do subtitles exist and match speech timing? |
| **Audio** | Is audio clean and normalized? |
| **Files** | Do all asset paths point to existing files? |

### Step 6: Submit

Validate the asset_manifest against the schema and persist via checkpoint.
