# Compose Director — Explainer Pipeline

## When to Use

You are the Compositor for a generated explainer video. You have `edit_decisions` with the complete edit timeline and an `asset_manifest` with all file paths. Your job is to render the final video: assemble visuals, layer audio, burn subtitles, and encode to the target format.

This is the last technical stage before the video exists as a playable file. Everything converges here.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/render_report.schema.json` | Artifact validation |
| Prior artifacts | `state.artifacts["edit"]["edit_decisions"]`, `state.artifacts["assets"]["asset_manifest"]` | What to render |
| Playbook | Active style playbook | Quality targets |
| Tools | `video_compose`, `audio_mixer` | Rendering capabilities |
| Media profiles | `lib/media_profiles.py` | Output format specs (resolution, codec, bitrate) |

## Process

### Step 1: Choose Render Strategy

Based on the edit decisions, pick the rendering approach:

**FFmpeg pipeline** (simpler videos):
- Static images with Ken Burns
- Audio layering
- Subtitle burn-in
- Best for: diagram-heavy, image-based explainers

**Remotion render** (motion-heavy videos):
- Animated text cards, stat cards
- Complex transitions (morph, zoom)
- Programmatic motion graphics
- Best for: flat-motion-graphics playbook, animation-heavy plans

You can combine both: Remotion for animated segments, FFmpeg for final assembly.

### Step 2: Prepare Render Inputs

For each cut in the edit decisions:
1. Verify the source asset exists at its declared path
2. Check asset dimensions/duration match expectations
3. Prepare transform parameters (scale, position, crop)

For audio:
1. Verify all narration segments exist
2. Verify music track exists
3. Prepare ducking parameters from edit decisions

### Step 3: Determine Output Profile

Read the target platform from the brief artifact. Map to a media profile:

| Platform | Profile | Resolution | Notes |
|----------|---------|-----------|-------|
| YouTube | `youtube_landscape` | 1920x1080 | Default for most explainers |
| TikTok/Reels | `tiktok` | 1080x1920 | Vertical, needs reframing |
| Twitter/X | `twitter_landscape` | 1280x720 | Shorter format |
| LinkedIn | `linkedin` | 1920x1080 | Professional context |

Get the exact encoding parameters via `ffmpeg_output_args(get_profile(name))`.

### Step 4: Render Video

Call the `video_compose` tool with:
```
{
  "operation": "render",
  "edit_decisions": <edit_decisions artifact>,
  "asset_manifest": <asset_manifest artifact>,
  "output_profile": "youtube_landscape",
  "output_path": "renders/output.mp4",
  "options": {
    "subtitle_burn": true,
    "audio_normalize": true,
    "two_pass_encode": true
  }
}
```

If using Remotion for animated segments:
1. Generate Remotion composition data from edit decisions
2. Call `video_compose` with `operation: "remotion_render"` for animated segments
3. Assemble Remotion outputs with remaining segments via FFmpeg

### Step 5: Audio Post-Processing

Call the `audio_mixer` tool to:
1. Layer narration segments in order
2. Mix background music at playbook volume
3. Apply ducking (music dips during narration)
4. Normalize overall audio levels
5. Output the final mixed audio track

The video_compose tool will mux this with the video.

### Step 5b: Generate Subtitles (Mandatory)

Subtitles are mandatory for all explainer content. Generate them from the narration audio — do NOT skip this step.

1. **Transcribe** the full narration using the `transcriber` tool (whisperx):
   ```python
   from tools.analysis.transcriber import Transcriber
   result = Transcriber().execute({
       'input_path': 'projects/<project>/assets/audio/narration_full.mp3',
       'model_size': 'base',
       'language': 'en',
       'output_dir': 'projects/<project>/assets/audio'
   })
   # result.data contains segments with word-level timestamps
   ```

2. **Generate SRT** from the transcription using `subtitle_gen`:
   ```python
   from tools.subtitle.subtitle_gen import SubtitleGen
   result = SubtitleGen().execute({
       'segments': transcription_data['segments'],
       'format': 'srt',
       'output_path': 'projects/<project>/assets/subtitles.srt',
       'max_words_per_cue': 8,
       'max_chars_per_line': 42
   })
   ```

3. **Burn subtitles** into the video using `video_compose`:
   ```python
   from tools.video.video_compose import VideoCompose
   result = VideoCompose().execute({
       'operation': 'burn_subtitles',
       'input_path': 'projects/<project>/renders/output.mp4',
       'output_path': 'projects/<project>/renders/final.mp4',
       'subtitle_path': 'projects/<project>/assets/subtitles.srt',
       'subtitle_style': {
           'font': '<from playbook typography.headings.font or Arial>',
           'font_size': 22,
           'primary_color': '&HFFFFFF',
           'outline_color': '&H000000',
           'outline_width': 2,
           'margin_v': 50,
           'alignment': 2
       }
   })
   ```

**The final deliverable is the subtitled version**, not the pre-subtitle render.

### Step 6: Verify Output

**File verification:**
- [ ] Output file exists at declared path
- [ ] File size is reasonable (not 0 bytes, not suspiciously small)
- [ ] File is a valid container (ffprobe succeeds)

**Content verification:**
- [ ] Duration within ±5% of target
- [ ] Resolution matches selected profile
- [ ] Audio channels present (stereo)
- [ ] No audio clipping or silence gaps > 1s

**Quality check:**
- [ ] Visual: scrub through at 25%, 50%, 75% marks — images display correctly
- [ ] Audio: narration is audible and clear throughout
- [ ] Subtitles: visible and correctly timed

### Step 7: Build Render Report

```json
{
  "version": "1.0",
  "outputs": [
    {
      "path": "renders/output.mp4",
      "format": "mp4",
      "codec": "h264",
      "resolution": "1920x1080",
      "fps": 30,
      "duration_seconds": 62.4,
      "file_size_mb": 45.2,
      "audio_codec": "aac",
      "audio_channels": 2,
      "render_strategy": "ffmpeg",
      "render_time_seconds": 180
    }
  ],
  "render_summary": {
    "total_cuts_rendered": 12,
    "subtitles_burned": true,
    "audio_tracks_mixed": 3,
    "target_duration_seconds": 60,
    "actual_duration_seconds": 62.4
  }
}
```

### Step 8: Self-Evaluate

Score (1-5):

| Criterion | Question |
|-----------|----------|
| **Playability** | Does the video play without errors in a standard player? |
| **Duration accuracy** | Is actual duration within ±5% of target? |
| **Audio quality** | Is narration clear, music balanced, no clipping? |
| **Visual quality** | Are images sharp, transitions smooth, no artifacts? |
| **Subtitle accuracy** | Are subtitles present, readable, and synced? |

If any dimension scores below 3, investigate and re-render.

### Step 9: Submit

Validate the render_report against the schema and persist via checkpoint.

## Common Pitfalls

- **Missing asset files**: Always verify every referenced file exists before starting the render. A missing file mid-render wastes time.
- **Audio sync drift**: Accumulated timing errors across narration segments cause audio-visual desync. Use absolute timestamps, not relative offsets.
- **Subtitle encoding**: Burn subtitles into the video (hardcoded) for maximum compatibility. Don't rely on soft subtitles for social media.
- **Single-pass encode**: Two-pass encoding produces better quality at the same file size. Worth the extra render time.
- **Ignoring media profile**: YouTube and TikTok have very different requirements. Always check the target profile.
