# Compose Director - Localization Dub Pipeline

## When To Use

Render the localized outputs. The quality bar is intelligibility, timing coherence, and clear version labeling across every language package.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/render_report.schema.json` | Artifact validation |
| Prior artifacts | `state.artifacts["edit"]["edit_decisions"]`, `state.artifacts["assets"]["asset_manifest"]` | Locale-specific render instructions |
| Tools | `video_compose`, `audio_mixer`, `video_trimmer`, `audio_enhance` | Final render and audio finishing |
| Playbook | Active style playbook | Subtitle placement and output quality |

## Process

### 1. Render By Locale

Treat each target language as its own deliverable set. Keep names and output directories explicit.

### 2. Expect Timing Adjustments

Allow for:

- subtitle reflow,
- dub-audio duration drift,
- longer CTA holds,
- optional trims or coverage sections.

### 3. Verify Every Locale

Record important findings in:

- `render_report.verification_notes`
- `render_report.warnings`
- `render_report.metadata.locale_notes`

Check:

- intelligibility,
- subtitle fit,
- obvious sync drift,
- version labeling.

### 4. Quality Gate

- each locale output exists,
- the dub and subtitle timing are acceptable,
- labels and filenames are unambiguous,
- warnings are preserved.

## Common Pitfalls

- Rendering all locales as if they were timing-identical.
- Forgetting to re-check subtitle line length after translation.
- Naming outputs in ways that hide the locale or treatment mode.
