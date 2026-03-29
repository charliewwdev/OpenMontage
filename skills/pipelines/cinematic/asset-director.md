# Asset Director - Cinematic Pipeline

## When To Use

This stage prepares the usable media for the final cinematic edit: source selects, title-card assets, optional support inserts, music, ambience, and subtitle assets when needed.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/asset_manifest.schema.json` | Artifact validation |
| Prior artifacts | `state.artifacts["scene_plan"]["scene_plan"]`, `state.artifacts["script"]["script"]`, `state.artifacts["idea"]["brief"]` | Scene intent and beat plan |
| Tools | `subtitle_gen`, `audio_enhance`, `image_selector`, `video_selector`, `music_gen` — selectors auto-discover all available providers from the registry | Optional support asset creation |
| Playbook | Active style playbook | Brand and typography consistency |

## Process

### 1. Prioritize Source Selects

Start with:

- source footage selects,
- stills,
- title-card backgrounds,
- any approved provided music or ambient beds.

These are the primary materials. Everything else is support.

### 1b. Sample Preview (Prevents Wasted Spend)

Before batch-generating support assets, produce one sample of each expensive generated type and show the user:

1. **Generated insert sample** (if using `image_selector` or `video_selector`): Generate one representative visual. Confirm it complements the source footage before batching.
2. **Music sample** (if using `music_gen`): Generate a short clip. Confirm mood and energy match the beat plan.

If rejected, adjust parameters and retry (max 3 iterations). Do not batch until approved.

### 2. Generate Support Assets Only Where Needed

Optional generated assets should fill clear gaps:

- missing transitional b-roll,
- concept-led inserts,
- texture or atmosphere cards,
- simple textural motion backgrounds.

### 3. Prepare A Real Audio Plan

Store:

- chosen music track or prompt,
- ambience layers,
- impact or transition sounds,
- subtitle assets if dialogue or narration is present.

### 4. Use Metadata For Rights And Intent

Recommended metadata keys:

- `source_selects`
- `music_plan`
- `ambience_plan`
- `title_assets`
- `generated_support_assets`
- `rights_notes`

### 5. Quality Gate

- source and support assets are clearly distinguished,
- generated inserts are limited and purposeful,
- audio plan matches the beat map,
- every referenced file exists.

## Common Pitfalls

- Generating extra shots before proving the source edit works.
- Treating music as a single loop instead of a beat-aware element.
- Forgetting rights or provenance notes for supplied assets.
