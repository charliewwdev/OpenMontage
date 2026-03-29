# Compose Director - Podcast Repurpose Pipeline

## When To Use

Render the podcast-derived outputs with audio fidelity as the top priority. The visuals need to support the speech, not compete with it.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/render_report.schema.json` | Artifact validation |
| Prior artifacts | `state.artifacts["edit"]["edit_decisions"]`, `state.artifacts["assets"]["asset_manifest"]` | Output plans and asset paths |
| Tools | `video_compose`, `audio_mixer` | Rendering and mix control |
| Playbook | Active style playbook | Brand consistency |

## Process

### 1. Render Highest-Value Outputs First

Priority order:

1. short highlight clips
2. quote-led clips
3. optional long-form companion video

This keeps the most publishable assets available first.

### 2. Preserve Audio Quality

- avoid unnecessary re-encoding,
- keep speech intelligible and stable,
- use music sparingly and only when it does not compete,
- verify subtitle sync after render.

### 3. Respect Platform Shapes

- `9:16` for short-form social
- `1:1` for quote-led or feed-safe clips
- `16:9` for long-form YouTube companion output

### 4. Verify Every Deliverable

- correct duration,
- correct aspect ratio,
- readable subtitles,
- accurate speaker attribution,
- stable audio,
- consistent brand treatment.

### 5. Use Render Report Metadata

Recommended metadata keys:

- `deliverable_groups`
- `audio_notes`
- `subtitle_checks`
- `failed_outputs`

## Common Pitfalls

- Letting visual treatments degrade audio quality.
- Rendering the full companion first and delaying the clips that matter most.
- Forgetting that a simple, readable clip beats a technically elaborate but confusing one.
