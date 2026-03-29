# Asset Director - Screen Demo Pipeline

## When To Use

This stage produces the minimal but high-leverage assets that make a screen demo easier to follow: subtitles, audio cleanup, reusable overlays, masks, and optional light-weight support cards.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/asset_manifest.schema.json` | Artifact validation |
| Prior artifacts | `state.artifacts["scene_plan"]["scene_plan"]`, `state.artifacts["script"]["script"]`, `state.artifacts["idea"]["brief"]` | What to produce |
| Tools | `subtitle_gen`, `audio_enhance`, `tts_selector`, `image_selector`, `diagram_gen` — selectors auto-discover all available providers from the registry | Generation capabilities |
| Playbook | Active style playbook | Typography and overlay styling |

## Process

### 1. Prioritize Utility Over Decoration

Screen demos do not need a large asset pile. They need the right few assets:

- mandatory: subtitles
- usually mandatory: cleaned primary audio
- usually helpful: reusable highlight box, arrow, step label, blur mask kit
- optional: one intro card, one outro card, sparse diagram overlays
- optional only if preflight allows it: generated narration for silent recordings

### 2. Generate Subtitles First

Rules:

- high contrast over unknown UI backgrounds,
- never cover the text the viewer needs to read,
- prefer phrase-level chunks unless word-by-word highlighting materially helps,
- prepare position override notes in `asset_manifest.metadata.subtitle_zones`.

### 3. Build A Reusable Overlay Kit

Do not generate bespoke assets for every click. Build a small shared kit:

- `highlight_box_primary`
- `arrow_primary`
- `step_label_primary`
- `keystroke_badge_primary`
- `blur_mask_template`

These should be reusable across scenes, with timing and placement handled downstream.

### 4. Clean Or Generate Audio Pragmatically

Goals:

- remove distracting keyboard and room noise,
- normalize speech,
- preserve timing,
- do not over-process into robotic audio.

If the recording is silent:

- only generate narration if TTS passed preflight,
- otherwise keep the asset plan text-led and note the limitation in metadata.

### 5. Only Generate Supplementary Visuals When They Earn It

Use `image_selector` or `diagram_gen` only for:

- a short opening card,
- a step transition card,
- a simple diagram that clarifies a hidden process,
- an outro card.

Do not create decorative artwork for a workflow the screen already explains.

### 6. Build The Asset Manifest Cleanly

Every asset must have a valid schema type and `scene_id`.

Use `asset_manifest.metadata` for details like:

- `subtitle_zones`
- `overlay_kit`
- `audio_settings`
- `narration_mode`
- `sensitive_regions`

### 7. Quality Gate

**Existence check:**
- [ ] Subtitle file exists at declared path and parses without errors
- [ ] Cleaned audio file exists and has the expected duration
- [ ] Reusable overlay kit exists and covers planned callout types
- [ ] All supplementary visuals exist at declared paths

**Timing check:**
- [ ] Subtitle timestamps align with script section timestamps
- [ ] If narration was generated, timing matches section duration closely enough for editing

**Quality check:**
- [ ] Subtitles are readable at output resolution
- [ ] Cleaned audio has no remaining distracting noise
- [ ] Callout colors have sufficient contrast
- [ ] Blur masks fully cover the sensitive content

## Common Pitfalls

- Generating too many one-off overlay files instead of a reusable kit.
- Using subtitles that sit directly on top of terminal output or bottom navigation.
- Assuming silent recordings will magically gain narration without checking TTS.
- Spending image generation budget on visuals the raw screen already provides.
