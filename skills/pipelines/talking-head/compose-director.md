# Compose Director — Talking Head Pipeline

## When to Use

You have edit decisions and an asset manifest. Your job is to render the final talking-head video: apply the enhancement chain, burn subtitles, mix audio, and encode to the target profile.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/render_report.schema.json` | Artifact validation |
| Prior artifacts | Edit decisions, Asset manifest | Render inputs |
| Tools | `video_compose`, `audio_mixer` | Rendering |
| Media profiles | `lib/media_profiles.py` | Output format |

## Process

### Step 1: Run Enhancement Chain

Apply video enhancements in order:
1. **Face enhancement** (if face_enhance tool available) — sharpen faces
2. **Color grading** (if color_grade tool available) — apply a profile
3. **Audio enhancement** (if audio_enhance tool available) — noise reduction, normalization

Each step is optional — check tool availability first.

### Step 2: Burn Subtitles

Use `video_compose` with `burn_subtitles` operation:
- Input: enhanced video (or raw if no enhancements)
- Subtitle file from asset manifest
- Style from playbook

### Step 3: Mix Audio

Use `audio_mixer` to:
- Layer original audio with any background music
- Apply ducking if music is present
- Normalize final levels

### Step 4: Final Encode

Use `video_compose` with `encode` operation:
- Apply target media profile (youtube_landscape, tiktok, etc.)
- Two-pass encoding for quality

### Step 5: Verify Output

- Check file exists and is playable
- Verify duration matches expectations
- Check audio is present

### Step 6: Build Render Report

Document output: path, format, resolution, duration, file size.

### Step 7: Self-Evaluate

| Criterion | Question |
|-----------|----------|
| **Playability** | Does the video play without errors? |
| **Quality** | Are enhancements applied correctly? |
| **Audio** | Is speech clear with balanced levels? |
| **Subtitles** | Are subtitles visible and synced? |

### Step 8: Submit

Validate the render_report against the schema and persist via checkpoint.
