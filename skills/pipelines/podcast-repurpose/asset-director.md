# Asset Director - Podcast Repurpose Pipeline

## When To Use

This stage builds the reusable kit for podcast-derived video assets: subtitles, speaker cards, quote cards, optional topic art, and optional music support.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/asset_manifest.schema.json` | Artifact validation |
| Prior artifacts | `state.artifacts["scene_plan"]["scene_plan"]`, `state.artifacts["script"]["script"]`, `state.artifacts["idea"]["brief"]` | Deliverable plan and transcript truth |
| Tools | `subtitle_gen`, `image_selector`, `diagram_gen`, `music_gen`, `audio_enhance` | Asset generation |
| Playbook | Active style playbook | Brand consistency |

## Process

### 1. Start With Mandatory Assets

Highest priority:

- subtitles for every clip,
- clean audio where needed,
- speaker attribution assets if multiple speakers appear,
- quote-card templates for quote-led outputs.

### 2. Treat Topic Graphics As Optional

Generated graphics should support the batch, not dominate it. Use them only when:

- the topic truly benefits from a clarifying image,
- the episode companion needs chapter separation,
- the budget can support consistent outputs.

### 3. Use Templates, Not Reinvention

Prefer reusable templates for:

- speaker cards,
- quote cards,
- end cards,
- brand containers.

### 4. Store Rich Asset Truth In Metadata

Recommended metadata keys:

- `speaker_assets`
- `subtitle_assets`
- `quote_card_assets`
- `topic_graphics`
- `music_assets`

### 5. Quality Gate

- all clips have subtitle assets,
- speaker identity is visually consistent,
- quote-card text remains mobile-readable,
- optional generated art stays within budget and style constraints.

## Common Pitfalls

- Spending budget on optional art before subtitles and attribution assets are complete.
- Creating inconsistent speaker cards across the same episode.
- Overproducing topic graphics for long-form companion videos.
