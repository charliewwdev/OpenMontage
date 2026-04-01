# Compose Director — Talking Head Pipeline

## When to Use

You have edit decisions and an asset manifest. Your job is to render the final talking-head video: apply the enhancement chain, burn subtitles, mix audio, and encode to the target profile.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/render_report.schema.json` | Artifact validation |
| Prior artifacts | Edit decisions, Asset manifest | Render inputs |
| Tools | `video_compose`, `audio_mixer` | Rendering |
| Media profiles | `lib/media_profiles.py` | Output format |

## Process

### Step 1: Run Enhancement Chain

Apply video enhancements in this exact order. **Attempt every step** if the tool is available — do not skip steps without a reason.

1. **Face enhancement** — apply `talking_head_standard` preset
2. **Eye enhancement** — under-eye dark circle removal + eye brightening
3. **Color grading** — apply a profile
4. **Audio enhancement** — noise reduction, normalization

**Eye enhancement** — always attempt this after face_enhance. It makes a visible difference on webcam/phone footage:
```
eye_enhance.execute({
    "input_path": "<face_enhanced_video>",
    "output_path": "<project>/assets/video/eye_enhanced.mp4",
    "operations": ["dark_circles", "brighten_eyes"],
    "dark_circle_intensity": 0.4,       # 0-1, subtle is better
    "eye_brighten_intensity": 0.3,
})
```
**Important:** Keep intensities low (0.2-0.5). Over-processing makes eyes look unnatural. If the tool fails (e.g. MediaPipe not installed), log the fallback and continue with the face_enhanced video.

### Step 1b: Speed Adjustment (if requested)

If the user wants the video sped up or slowed down, use `video_trimmer`:
```
video_trimmer.execute({
    "operation": "speed",
    "input_path": "<enhanced_video>",
    "output_path": "<project>/assets/video/speed_adjusted.mp4",
    "speed_factor": 1.25    # 0.5x (slow), 1.25x, 1.5x, 2x (fast)
})
```

Common speed factors:
| Factor | Use Case |
|--------|----------|
| `0.5` | Slow-mo for dramatic effect |
| `1.0` | Normal (no change) |
| `1.25` | Slightly faster — tighter pacing without sounding unnatural |
| `1.5` | Noticeably faster — good for recaps or condensed content |
| `2.0` | Double speed — time-lapse effect |

Apply speed AFTER enhancements, BEFORE reframing.

### Step 2: Auto-Reframe (if target platform requires it)

If the target platform requires a different aspect ratio (e.g. Instagram Reels = 9:16), use `auto_reframe`:

```
auto_reframe.execute({
    "input_path": "<enhanced_video>",
    "output_path": "<project>/renders/reframed.mp4",
    "target_aspect": "portrait",       # 9:16 for Reels/TikTok/Shorts
    "smoothing_window": 15,            # smooth camera pan
    "face_padding": 0.4,              # 40% padding around face
})
```

**Aspect ratio presets:**
| Preset | Ratio | Platform |
|--------|-------|----------|
| `portrait` | 9:16 | Instagram Reels, TikTok, YouTube Shorts |
| `square` | 1:1 | Instagram Feed |
| `landscape` | 16:9 | YouTube, LinkedIn |
| `vertical_4_5` | 4:5 | Instagram portrait post |

The tool automatically runs face detection and keeps the speaker centered. If MediaPipe is not installed, falls back to center-crop.

**Important:** Run auto_reframe AFTER face_enhance and color_grade but BEFORE burning subtitles. Subtitles need to be positioned for the final aspect ratio.

### Step 2b: Build ASR Corrections Dictionary

Before burning captions, scan the transcript for likely ASR misrecognitions. Common issues:
- Product/brand names: "cloud" → "Claude", "co-pilot" → "Copilot", "remotion" → "Remotion"
- Technical terms: "pythonic" misheard as "pathonic", "API" as "a pie"
- Speaker's name or company name
- Domain-specific jargon

Build a corrections dict:
```python
corrections = {
    "cloud": "Claude",
    "co pilot": "Copilot",
    "open montage": "OpenMontage",
}
```

Pass this dict to both `subtitle_gen` (if generating SRT) and `remotion_caption_burn` (if using Remotion captions). Even if you find zero corrections needed, explicitly pass an empty dict `{}` to confirm you checked.

### Step 3: Burn Subtitles

**Preferred: Remotion captions** (if `remotion_caption_burn` tool available):
```
remotion_caption_burn.execute({
    "input_path": "<reframed_or_enhanced_video>",
    "output_path": "<project>/assets/video/captioned.mp4",
    "segments": <transcript_segments_from_asset_manifest>,
    "corrections": {"cloud": "Claude", "co-pilot": "Copilot"},
    "words_per_page": 4,
    "font_size": 52,
    "highlight_color": "#22D3EE",
})
```
Remotion renders animated word-by-word captions at the bottom of the frame with active word highlighting. Captions are positioned away from the face.

**Fallback: FFmpeg subtitles** (if Remotion unavailable):
Use `video_compose` with `burn_subtitles` operation:
- Input: reframed video (or enhanced video if no reframe needed)
- Subtitle file from asset manifest

**CRITICAL: Caption positioning for 9:16 vertical video.**
Captions MUST be in the lower 20% of the frame. On a 1920-high frame, that means `MarginV=160` or higher. The default FFmpeg subtitle position is center — this WILL occlude the face. You MUST override it.

FFmpeg subtitle style string for vertical talking-head:
```
"FontName=Arial,FontSize=22,Bold=1,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,Outline=2,Shadow=0,MarginV=160,Alignment=2"
```

**Never** use the default subtitle position. **Never** position subtitles in the center or upper half of the frame. If you see captions on the face during visual QA, the video must be re-rendered with corrected positioning.

### Step 3b: Burn Overlay Graphics (if scene plan includes overlays)

If the scene plan includes overlay scenes (text_cards, stat_cards, charts, comparisons, callouts), render them onto the video.

**How overlay compositing works:**
1. Each overlay is a short Remotion composition (3-5 seconds) rendered as a transparent video clip or composited directly
2. Use `video_compose` with `picture_in_picture` or `overlay` operation to place each overlay at the correct timestamp
3. Respect the overlay's `position` field from the scene plan:
   - `lower_third` → bottom 30% of frame
   - `upper_third` → top 30% of frame
   - `side_panel` → left or right 40%
   - `full_overlay` → centered, brief (1-2s)

**For Remotion-based overlays:** Create a composition JSON with the overlay cuts, render to a transparent clip, then composite onto the talking-head video using FFmpeg.

**For simple text overlays:** Use FFmpeg's drawtext filter directly:
```
ffmpeg -i captioned.mp4 -vf "drawtext=text='Key Term':fontsize=48:fontcolor=white:borderw=3:bordercolor=black:x=(w-text_w)/2:y=h*0.75:enable='between(t,22,26)'" -c:a copy output.mp4
```

**Important:** Time each overlay to match the scene plan timestamps. After speed adjustment, recalculate overlay timestamps: `adjusted_time = original_time / speed_factor`.

### Step 3c: Build Showcase Cards (if multi-clip reel)

If the output is a reel with showcase clips, use `showcase_card` for each:
```
showcase_card.execute({
    "input_path": "<showcase_video>",
    "output_path": "<project>/assets/video/sc_<name>.mp4",
    "title": "VIDEO TITLE",
    "subtitle": "Description | Style | Cost: $0.15",
    "background_color": "0x0A0F1A",
})
```
This creates letterboxed 9:16 cards with typography.

### Step 4: Assemble Multi-Clip (if applicable)

If the output has multiple segments (e.g. talking head + showcase clips), use `video_stitch`:
```
video_stitch.execute({
    "operation": "stitch",
    "clips": ["intro.mp4", "showcase1.mp4", ..., "outro.mp4"],
    "output_path": "<project>/renders/assembled.mp4",
    "transition": "crossfade",         # or "fade" for fade-through-black
    "transition_duration": 0.5,
})
```
**Transition guidance:**
- `crossfade` (fade): smooth blend between talking head and showcase
- `fade` (fade-through-black): brief dip to black between showcase clips
- Mix transition types: use `crossfade` for talk→showcase, `fade` between showcases

### Step 5: Mix Audio

Use `audio_mixer` to layer background music:

**For multi-clip reels** — use `segmented_music` to play music only during talking head sections:
```
audio_mixer.execute({
    "operation": "segmented_music",
    "video_path": "<assembled_video>",
    "music_path": "<bg_music>",
    "music_volume": 0.20,
    "segments": [
        {"start": 0, "end": 17.0},       # intro speech
        {"start": 167.0, "end": 175.0}    # outro speech
    ],
    "fade_duration": 0.5,
    "output_path": "<project>/renders/final.mp4",
})
```

**For single talking-head videos** — use `duck` or `full_mix`:
- Layer original audio with background music
- Apply ducking if music is present
- Normalize final levels

### Step 6: Final Encode — MANDATORY

**Do not skip this step.** Without a final encode, the output will be oversized and may not play correctly on the target platform.

Use `video_compose` with `encode` operation:
- Apply target media profile (youtube_landscape, tiktok, instagram_reels, etc.)
- Two-pass encoding for quality

**Target file sizes:**
| Platform | Max Duration | Target Size |
|----------|-------------|-------------|
| Instagram Reels | 90s | < 50 MB |
| TikTok | 10 min | < 100 MB |
| YouTube Shorts | 60s | < 40 MB |
| YouTube | unlimited | < 25 MB/min |

If the output exceeds the target, re-encode with a lower bitrate. A 66-second Instagram Reel at 76 MB is unacceptable — it should be under 30 MB.

```
video_compose.execute({
    "operation": "encode",
    "input_path": "<mixed_video>",
    "output_path": "<project>/renders/final.mp4",
    "media_profile": "instagram_reels",
    "video_bitrate": "4M",
    "audio_bitrate": "192k",
})
```

### Step 7: Visual QA

Use `visual_qa` to verify the output before declaring success:
```
visual_qa.execute({
    "operation": "review",
    "input_path": "<final_video>",
    "timestamps": [3.0, 10.0, 25.0, 50.0, 100.0, 170.0],
})
```
Then **read each extracted frame** to verify:
- Captions are visible and positioned at the bottom (not on the face)
- Face enhancement is applied (skin looks smooth, not over-processed)
- Transitions are clean (no artifacts at transition points)
- Showcase cards have readable typography

Also run probe validation:
```
visual_qa.execute({
    "operation": "probe",
    "input_path": "<final_video>",
    "expected": {
        "width": 1080, "height": 1920,
        "has_audio": true,
        "pixel_format": "yuv420p"
    },
})
```

And check audio levels:
```
visual_qa.execute({
    "operation": "audio_levels",
    "input_path": "<final_video>",
    "timestamps": [5.0, 50.0, 170.0],
})
```
Verify: speech sections have higher volume than showcase sections (confirms music placement).

### Step 8: Build Render Report

Document output: path, format, resolution, duration, file size, QA results.

### Step 9: Self-Evaluate

| Criterion | Question |
|-----------|----------|
| **Playability** | Does the video play without errors? |
| **Quality** | Are enhancements applied correctly? |
| **Framing** | If reframed — is the face centered? No important content cropped? |
| **Audio** | Is speech clear with balanced levels? Music only during intended segments? |
| **Subtitles** | Are captions visible at the bottom? Not occluding the face? Word highlighting working? |
| **Transitions** | Are transitions clean? Correct type (crossfade vs fadeblack)? |
| **Showcase** | Are showcase cards properly letterboxed with readable typography? |

### Step 10: Submit

Validate the render_report against the schema and persist via checkpoint.
