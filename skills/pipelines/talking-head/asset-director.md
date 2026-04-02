# Asset Director — Talking Head Pipeline

## When to Use

You have a scene plan and script. Your job is to generate the supporting assets for a talking-head video: subtitles, extracted audio, overlay graphics (charts, text cards, stat reveals), and any supplementary visuals.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/asset_manifest.schema.json` | Artifact validation |
| Prior artifacts | Scene plan, Script | What assets to create |
| Tools | `subtitle_gen`, `audio_mixer` | Subtitle and audio generation |
| Tools | `image_selector` (optional) | Stock images for overlays |
| Tools | `pixabay_music` (optional) | Royalty-free background music |

## Process

### Step 1: Generate Subtitles

Use the transcription data from the script stage to create:
- SRT or ASS subtitle file with word-level timing
- Style subtitles per the playbook (font, size, color, position)

If the scene plan includes a `corrections` dict, pass it to `subtitle_gen`:
```
subtitle_gen.execute({
    "segments": <transcript_segments>,
    "corrections": {"cloud": "Claude"},
    "max_words_per_line": 5,
    "output_path": "<project>/assets/subtitles/subtitles.srt"
})
```

### Step 2: Extract and Process Audio

- Extract audio track from raw footage
- Apply noise reduction if needed (via `audio_mixer`)
- Normalize audio levels

### Step 3: Source Background Music

If the scene plan includes background music:

1. **Check local pixabay music library** — look for downloaded MP3s matching the mood
2. **Use `pixabay_music` tool** — search by mood/genre keywords from the scene plan
3. **Run `audio_energy` analysis** on the selected track to find optimal start offset (skip quiet intros)

Record the music path, offset, and whether looping is needed in the asset manifest.

### Step 4: Generate Overlay Assets

If the scene plan includes overlay scenes (from the scene-director's Watch & Propose step), generate the assets for each.

**For Remotion-rendered overlays** (charts, comparisons, KPI grids, stat cards):

Create a composition JSON snippet for each overlay. These will be rendered by the compose-director. Each overlay needs:

```json
{
  "overlay_id": "overlay_1",
  "remotion_cut": {
    "id": "term-agentic-ai",
    "type": "callout",
    "text": "Agentic AI: software that acts autonomously toward goals",
    "in_seconds": 0,
    "out_seconds": 4,
    "backgroundColor": "#0F172A",
    "accentColor": "#22D3EE",
    "icon": "💡"
  },
  "overlay_timestamp": 22.0,
  "position": "lower_third"
}
```

**Overlay type → Remotion cut mapping:**

| Scene Plan Overlay | Remotion `type` | Required Props |
|-------------------|-----------------|----------------|
| Key term definition | `callout` | `text`, `icon` (optional) |
| Statistic/number | `stat_card` | `stat` (the number), `text` (label) |
| Comparison | `comparison` | `leftLabel`, `rightLabel`, `leftValue`, `rightValue` |
| Data chart | `bar_chart` | `chartData` (array of `{label, value}`) |
| Pie chart | `pie_chart` | `chartData` (array of `{label, value}`) |
| Line chart | `line_chart` | `chartSeries` (array of `{name, data: number[]}`) |
| KPI dashboard | `kpi_grid` | `chartData` (array of `{label, value}`) — keep numbers small with suffix (e.g. "2.4M") |
| Progress indicator | `progress_bar` | `progress` (0-100), `text` |
| Section title | `hero_title` | `text`, `subtitle` (optional) |
| Callout/quote | `callout` | `text`, `icon` |
| Lower third | `text_card` | `text` |

**Remotion AnimatedBackground:**

The Explainer composition now includes an `AnimatedBackground` component that renders an animated gradient mesh, floating orbs, and a subtle grid pattern. This provides a far more professional look than flat solid colors.

- Scene backgrounds should use `backgroundColor: "#0F172A"` which auto-converts to transparent, letting the animated gradient show through.
- Do NOT use flat solid colors for backgrounds -- always let the AnimatedBackground render behind overlays.
- When compositing green screen footage, render the AnimatedBackground as the replacement background (see compose-director Step 3c).

**Component constraints:**

| Component | Min Width | 720px Portrait? | Value Type |
|-----------|-----------|-----------------|------------|
| comparison | 900px | NO -> use 2x stat_card | string |
| kpi_grid | 720px | YES | numeric ONLY (no "15+") |
| bar_chart | 500px | YES | numeric |
| stat_card | 300px | YES | string OK |
| callout | 400px | YES | string |
| hero_title | 400px | YES | string |
| line_chart | 500px | YES | numeric |
| progress_bar | 600px | YES | numeric |
| stat_reveal | 300px | YES | string OK |

Key rules:
- `comparison` requires 900px+ width. In 720px portrait frames, substitute with two sequential `stat_card` components instead.
- `kpi_grid` values MUST be purely numeric (e.g., `4.8`, `73`, `2400`). Formatted strings like `"15+"`, `"$4.8B"`, or `"2.4M"` will cause rendering errors. Use `stat_card` for string-formatted numbers instead.
- Always check the target frame width before choosing a component. Portrait (720px) excludes `comparison`.

**Dark theme for all overlays** -- use dark backgrounds (`#0F172A`, `#1E293B`) with light text. This ensures overlays are legible when composited on top of talking-head footage. The `#0F172A` backgroundColor is treated as transparent by the AnimatedBackground system, so overlays will show the animated gradient behind them.

**For simple text overlays** (if Remotion is overkill):

Generate PNG images using FFmpeg or PIL, stored at `<project>/assets/overlays/overlay_<id>.png`.

### Step 5: Build Asset Manifest

Document all generated assets with paths, types, and tool references:

```json
{
  "subtitles": {
    "path": "assets/subtitles/subtitles.srt",
    "format": "srt",
    "word_count": 208
  },
  "music": {
    "path": "assets/audio/bg_music.mp3",
    "offset_seconds": 3.5,
    "needs_loop": true
  },
  "overlays": [
    {
      "overlay_id": "overlay_1",
      "type": "callout",
      "timestamp": 22.0,
      "duration": 4.0,
      "remotion_cut": { ... },
      "position": "lower_third"
    }
  ],
  "transcript_segments": "assets/audio/transcript.json"
}
```

### Step 6: Self-Evaluate

| Criterion | Question |
|-----------|----------|
| **Subtitles** | Do subtitles exist and match speech timing? |
| **Audio** | Is audio clean and normalized? |
| **Music** | Was audio_energy run on the music to find optimal offset? |
| **Overlays** | Does every overlay from the scene plan have a generated asset? |
| **Overlay content** | Is the data in overlays accurate to what the speaker actually says? |
| **Files** | Do all asset paths point to existing files? |

### Step 7: Submit

Validate the asset_manifest against the schema and persist via checkpoint.
