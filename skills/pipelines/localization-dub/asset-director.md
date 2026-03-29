# Asset Director - Localization Dub Pipeline

## When To Use

This stage produces the localized asset kit: translated subtitle files, dubbed audio, optional lip-sync renders, and any language-specific replacements needed for the final outputs.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/asset_manifest.schema.json` | Artifact validation |
| Prior artifacts | `state.artifacts["scene_plan"]["scene_plan"]`, `state.artifacts["script"]["script"]`, `state.artifacts["idea"]["brief"]` | Language plan and transcript package |
| Tools | `tts_selector`, `subtitle_gen`, `lip_sync`, `audio_enhance` — `tts_selector` auto-discovers all available TTS providers from the registry | Dubbed audio, subtitle, and optional lip-sync production |
| Playbook | Active style playbook | Subtitle and replacement-text rules |

## Process

### 1. Produce Subtitle Assets First

Create the subtitle or caption package for each language. This gives a reviewable fallback even if dubbed-audio generation or lip sync is blocked.

### 2. Generate Dubbed Audio Per Language

Use the approved translated script package, not raw machine output. Record which voice or synthesis path was used for each language.

### 3. Treat Lip Sync As Optional

Only generate lip-sync assets for scenes and languages that actually need it. If the tool path is blocked, record that and keep the dub-audio path alive.

### 4. Use Metadata For Localization Truth

Recommended metadata keys:

- `subtitle_assets_by_language`
- `dub_audio_assets_by_language`
- `lip_sync_assets_by_language`
- `voice_map`
- `pronunciation_warnings`
- `blocked_assets`

### 5. Quality Gate

- subtitle assets exist,
- dubbed audio assets exist for planned dub outputs,
- lip-sync remains explicitly optional,
- every referenced file exists.

## Common Pitfalls

- Generating dubbed audio before finalizing translation review.
- Treating lip sync as mandatory for every language.
- Failing to record which language asset maps to which voice and subtitle set.
