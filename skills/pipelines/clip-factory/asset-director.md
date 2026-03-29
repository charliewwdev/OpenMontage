# Asset Director - Clip Factory Pipeline

## When To Use

This stage builds the shared visual and audio kit for the entire clip batch. The key is reuse, not bespoke design per clip.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/asset_manifest.schema.json` | Artifact validation |
| Prior artifacts | `state.artifacts["scene_plan"]["scene_plan"]`, `state.artifacts["script"]["script"]`, `state.artifacts["idea"]["brief"]` | Clip plans and rankings |
| Tools | `subtitle_gen`, `audio_enhance` | Batch-ready subtitles and audio cleanup |
| Playbook | Active style playbook | Subtitle and overlay consistency |

## Process

### 1. Build Shared Assets First

Prefer reusable assets over per-clip reinvention:

- one subtitle style system,
- one hook text treatment,
- one lower-third treatment,
- one watermark / brand frame,
- one CTA / end-tag treatment if needed.

### 2. Generate Per-Clip Subtitles

Each approved clip needs its own subtitle asset, timed from clip start rather than source start. This timestamp rebasing is critical.

Store clip-relative timing details in `asset_manifest.metadata.subtitle_map`.

### 3. Normalize Audio Consistently

Use `audio_enhance` across the clip set so the batch feels like one series:

- similar loudness,
- similar noise floor,
- similar vocal clarity.

### 4. Keep Hook Assets Lightweight

Most hook overlays should be text-first and template-based. Do not spend time or budget generating bespoke art unless the batch truly benefits.

### 5. Use Metadata For Batch Structure

Recommended metadata keys:

- `shared_assets`
- `subtitle_map`
- `audio_profile`
- `clip_asset_index`
- `style_tokens`

### 6. Quality Gate

- every clip has subtitles,
- every clip has a clean audio asset or verified source audio path,
- shared assets are referenced consistently,
- the asset count stays practical for the batch size.

## Common Pitfalls

- Forgetting to rebase subtitle timing per clip.
- Overdesigning hook assets so the batch becomes inconsistent.
- Normalizing some clips and not others.
- Treating a 10-clip batch like 10 unrelated projects.
