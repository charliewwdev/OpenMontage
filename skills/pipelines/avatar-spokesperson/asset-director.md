# Asset Director - Avatar Spokesperson Pipeline

## When To Use

This stage prepares the actual spokesperson ingredients: narration, avatar or lip-sync footage, subtitle assets, branded backgrounds, and the minimal support graphics needed to complete the cut.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/asset_manifest.schema.json` | Artifact validation |
| Prior artifacts | `state.artifacts["scene_plan"]["scene_plan"]`, `state.artifacts["script"]["script"]`, `state.artifacts["idea"]["brief"]` | Presenter plan and narration needs |
| Tools | `talking_head`, `lip_sync`, `tts_selector`, `subtitle_gen`, `image_selector`, `audio_enhance` — selectors auto-discover all available providers from the registry | Avatar, narration, and support asset options |
| Playbook | Active style playbook | Background, type, and subtitle rules |

## Process

### 1. Lock The Avatar Generation Path

Use one primary path and record it clearly:

- `talking_head` from still image plus audio,
- `lip_sync` from existing presenter plate plus new audio,
- externally supplied avatar render if created outside the current runtime.

Do not hide a blocked avatar path. Record it.

### 1b. Sample Preview (Prevents Wasted Spend)

Before batch-generating assets, produce one sample of each expensive type and show the user:

1. **TTS sample** (if generating narration): Generate one section. Confirm voice, pace, and persona before batching the rest.
2. **Avatar sample** (if using `talking_head`): Generate a short test clip. Confirm the avatar quality is acceptable before committing to full generation.

If rejected, adjust parameters and retry (max 3 iterations). Do not batch until approved.

### 2. Resolve Narration Before Support Graphics

Spokesperson videos depend on speech. Determine whether narration is:

- supplied,
- TTS-generated,
- already embedded in a presenter plate.

If narration is missing and no TTS tool is available, mark the project blocked instead of pretending the stage succeeded.

### 3. Build The Minimal Support Kit

Prepare only what the scene plan actually needs:

- subtitle files,
- one lower-third system,
- CTA card,
- background or plate assets,
- optional still or product support images.

### 4. Use Metadata For Capability Truth

Recommended metadata keys:

- `avatar_generation_path`
- `narration_assets`
- `subtitle_assets`
- `background_assets`
- `scene_asset_index`
- `blocked_assets`

### 5. Quality Gate

- the avatar path is explicit,
- narration and avatar assets align,
- support graphics stay minimal,
- every referenced file exists.

## No-Avatar Path

When the EP has triggered a narration-over-graphics pivot (neither `talking_head` nor `lip_sync` available), skip avatar generation entirely and produce a graphics-driven asset kit instead:

### What to produce:
1. **Narration audio** — via `tts_selector` (mandatory; block the project if no TTS is available either).
2. **Scene visuals** — via `image_selector` or `video_selector`. One primary visual per scene that reinforces the spoken point (diagram, illustration, product shot, or stock footage).
3. **Subtitle files** — same as standard path.
4. **Text cards** — key-point overlays, stat cards, CTA end card.
5. **Backgrounds** — consistent family matching the playbook.

### What to skip:
- No `talking_head` or `lip_sync` calls.
- No presenter framing metadata.
- `avatar_generation_path` should be set to `"none — narration-over-graphics pivot"`.

### Metadata for this path:
- `avatar_generation_path`: `"narration_over_graphics"`
- `pivot_reason`: why the no-avatar path was chosen
- All other metadata keys remain the same.

## Common Pitfalls

- Building decorative assets before the narration path is solved.
- Mixing multiple avatar-generation strategies in one simple spokesperson video.
- Marking the stage complete when the core presenter asset is still hypothetical.
- (No-avatar path) Generating filler visuals with no connection to the narration — every image must reinforce the spoken point.
