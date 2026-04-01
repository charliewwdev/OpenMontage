# Scene Director — Talking Head Pipeline

## When to Use

You have a script (from transcription) and raw footage. Your job is to create a scene plan — mostly simple since talking-head footage is a single continuous shot, but you still need to plan where overlays, text cards, and B-roll might appear.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/scene_plan.schema.json` | Artifact validation |
| Prior artifacts | Script, Brief | Section timing and context |
| Tools | `frame_sampler` (optional) | Extract representative frames |
| Tools | `face_tracker` (optional) | Analyze speaker face position for reframing |
| Tools | `silence_cutter` (optional) | Detect silence for jump cut planning |

## Process

### Step 1: Analyze Footage (if tools available)

**Face tracking** — If `face_tracker` is available, run it on the raw footage:
```
face_tracker.execute({
    "input_path": "<raw_footage>",
    "sample_fps": 5
})
```
This outputs per-frame face bounding boxes. Use this data to:
- Decide if reframing is needed (e.g. speaker is off-center for vertical crop)
- Identify sections where the speaker moves significantly (needs dynamic crop)
- Note face position for auto_reframe in the compose stage

**Silence detection** — If `silence_cutter` is available, run in `mark` mode:
```
silence_cutter.execute({
    "input_path": "<raw_footage>",
    "mode": "mark",
    "silence_threshold_db": -35,
    "min_silence_duration": 0.5
})
```
This outputs silence/speech segment timestamps. Use this to:
- Plan which segments should be jump-cut or sped up
- Identify dead air, false starts, and long pauses
- Estimate the final video duration after cuts
- Present the user with a summary: "Found X seconds of silence across Y segments — recommend removing?"

### Step 2: Plan Base Scenes

For talking-head, the base is simple: one scene per script section, all type `talking_head`. The raw footage IS the scene.

### Step 3: Plan Enhancement Scenes

Based on script enhancement cues, plan overlay scenes:
- Text cards for key terms or statistics
- Lower thirds for speaker identification
- B-roll suggestions for topic illustrations

### Step 4: Plan Reframing & Cuts

If the target platform requires a different aspect ratio (e.g. Instagram Reels = 9:16):
- Note `auto_reframe` should be applied in the compose stage
- Record the target aspect ratio in the scene plan
- If face tracking data shows significant speaker movement, note that dynamic crop is needed

If silence detection found segments to cut:
- Record the recommended cut mode (`remove` or `speed_up`) in the scene plan
- Note padding preferences (default 0.08s to avoid clipping words)

### Step 5: Build Scene Plan

Create a scene per section with:
- Type: `talking_head` (primary)
- Timing from script sections
- Required assets: subtitle file, any overlay images

### Step 6: Self-Evaluate

| Criterion | Question |
|-----------|----------|
| **Coverage** | Every script section has a scene? |
| **Enhancement** | Are overlay opportunities identified? |
| **Feasibility** | Can all required assets be generated? |

### Step 7: Submit

Validate the scene_plan against the schema and persist via checkpoint.
