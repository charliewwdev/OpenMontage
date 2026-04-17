# Idea Director - Screen Demo Pipeline

## When To Use

Use this pipeline whenever the deliverable is a screen-recording-style demo. There are **two production modes** — pick one in the brief:

| Mode | Source material | Pick when |
|---|---|---|
| **`real_capture`** | An actual screen recording (MP4) captured via `screen_recorder`, `cap_recorder`, or `playwright-recording` | Real app UI, live behavior, browser flows, IDE plugins, user asked for their own screen |
| **`synthetic_terminal`** | None — nothing is captured. You author a `terminal_scene` cut for Remotion | CLI / terminal / install flow / make targets / git clone / API key config — anything scriptable where every command and output is predictable |

**Decision question:** *"Can I predict every command and its output before shooting?"* If yes → synthetic. If no → real capture.

**Record the mode in `brief.metadata.production_mode`.** The asset-director reads this field to choose between capture+overlay assets vs a `steps` list paced with narration.

For `synthetic_terminal`, also read `.agents/skills/synthetic-screen-recording/SKILL.md` before proceeding — it encodes the pacing rule that killed an earlier showcase render (commands burned through in 40% of scene time, then terminal froze for the remaining 60%).

Your job at this stage is to turn the user's request into a clear procedural video plan. The main deliverable is a schema-valid `brief`, with pipeline-specific detail stored in `brief.metadata`.

## Operating Principles

Screen-demo best practices are consistent:

- prioritize procedure over theory,
- keep scope to one workflow or one outcome,
- map narration to visible action,
- plan attention guidance with restraint,
- optimize for legibility before style.

Reference docs:
- `docs/screen-demo-best-practices.md`
- `skills/creative/screen-recording.md`

## Process

### 1. Inspect The Source

Use the available analysis tools before writing the brief:

- `frame_sampler` for representative frames and dense samples around likely key moments
- `scene_detect` for window switches, page changes, and major layout changes
- `transcriber` to determine whether the recording has narration, system audio only, or silence

Identify:

- software and surfaces shown,
- the single workflow being taught,
- critical interactions: click, type, scroll, submit, result,
- moments that obviously need zoom or highlight support,
- dead time: installs, builds, loading, repetitive typing,
- whether `9:16` is even feasible without losing meaning.

### 2. Classify The Demo

Choose one dominant archetype:

- `tutorial`: step-by-step task completion
- `feature_showcase`: show what a feature does
- `troubleshooting`: reproduce and fix a problem
- `walkthrough`: explain a multi-step flow across tools
- `comparison`: compare two approaches or outcomes

If the footage mixes several archetypes, pick the one that should drive pacing and packaging.

### 3. Set Deliverable Intent

Screen demos should stay narrow and outcome-led:

- `30-60s`: quick tip or feature reveal
- `60-120s`: focused product walkthrough or bug fix
- `120-300s`: chaptered tutorial

Default to the shortest duration that still teaches the task cleanly. Do not preserve raw duration unless the user explicitly wants training footage with minimal compression.

### 4. Choose A Viable Output Shape

Plan the platform around readability, not trend pressure:

- use `youtube` or `linkedin` for dense desktop UI,
- use `instagram` or `tiktok` only if the active area can survive a narrow crop,
- prefer `1:1` or `16:9` when the interface has multiple panels or code windows.

### 5. Build The Brief

Use the schema fields for the concise creative contract and store the richer production detail in `metadata`.

Recommended `metadata` keys:

- `source_path`
- `source_duration_seconds`
- `source_resolution`
- `has_voiceover`
- `software_shown`
- `demo_archetype`
- `critical_moments`
- `dead_time_segments`
- `recommended_aspect_ratios`
- `notes_for_scene_planner`

The brief should answer:

- what the viewer will learn,
- who this is for,
- what proof/result the video should land on,
- what the must-show actions are,
- which crop directions are safe.

### 6. Quality Gate

Before checkpointing, verify:

- the workflow is narrow enough for the chosen duration,
- the "aha" result is clearly identified,
- the target platform matches the UI density,
- the brief names the actual software rather than describing it vaguely,
- the metadata gives downstream stages enough production truth.

## Common Pitfalls

- Treating a 7-minute recording as a 7-minute deliverable by default.
- Choosing `9:16` for a dense desktop capture just because the user asked for Shorts.
- Writing a concept-heavy brief when the user really needs task completion.
- Failing to note silence; if there is no voiceover, downstream stages must know immediately.
