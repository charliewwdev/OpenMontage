# Compose Director - Animation Pipeline

## When To Use

Render the animation with an emphasis on text sharpness, timing integrity, and consistent output cadence.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/render_report.schema.json` | Artifact validation |
| Prior artifacts | `state.artifacts["edit"]["edit_decisions"]`, `state.artifacts["assets"]["asset_manifest"]` | Timing plan and asset files |
| Tools | `video_compose`, `audio_mixer`, `video_stitch` | Final assembly |
| Playbook | Active style playbook | Render consistency |

## Process

### 1. Preserve Motion Timing

Do not let export settings or careless composition change the perceived timing of holds, stagger, or scene transitions.

### 2. Protect Text And Diagram Sharpness

Animation often fails on export through soft text, muddy thin lines, or cramped mobile framing.

### 3. Verify The First And Last Frames

Ensure:

- the opening frame reads immediately,
- the final frame lands cleanly,
- nothing important is clipped by safe zones.

### 4. Use Render Metadata

Recommended metadata keys:

- `render_fps`
- `sharpness_checks`
- `safe_zone_checks`
- `variant_outputs`

## Common Pitfalls

- Soft or aliased text after rendering.
- Compression choices that damage diagrams.
- Scene cadence changing between preview and final.
