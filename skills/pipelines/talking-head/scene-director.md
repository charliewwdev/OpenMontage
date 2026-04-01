# Scene Director — Talking Head Pipeline

## When to Use

You have a script (from transcription) and raw footage. Your job is to **watch the footage, understand the content, and propose a creative enhancement plan** — then build a scene plan that transforms raw talking-head footage into an engaging, visually rich video.

You are not just a processor. You are a creative director. Your job is to figure out what the speaker is saying and propose visual enhancements that make the content more engaging and easier to understand.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/scene_plan.schema.json` | Artifact validation |
| Prior artifacts | Script, Brief | Section timing and context |
| Tools | `frame_sampler` (optional) | Extract representative frames |
| Tools | `face_tracker` (optional) | Analyze speaker face position for reframing |
| Tools | `silence_cutter` (optional) | Detect silence for jump cut planning |

## Process

### Step 1: Watch & Listen — Understand the Content

**This is the most important step. Do not skip it.**

Read the full transcript carefully. Understand:
- What is the speaker's **main topic**?
- What are the **key concepts** they explain?
- Where do they use **numbers, statistics, or data**?
- Where do they **compare things** (A vs B, before/after, old vs new)?
- Where do they **list items** (3 tips, 5 steps, etc.)?
- Where do they introduce **technical terms** or jargon?
- Where are the **section transitions** (topic changes)?
- What is the **emotional arc** (excitement, serious, humorous)?

If `frame_sampler` is available, extract 5-8 representative frames to see the speaker's setup, background, lighting, and gestures.

### Step 2: Propose Creative Overlays

Based on your content analysis, propose **on-screen graphics** that will appear alongside the speaker at key moments. These are Remotion components that get composited on top of or next to the talking-head footage.

**Available overlay types:**

| Overlay Type | Remotion Component | Best For |
|-------------|-------------------|----------|
| **Key term definition** | `text_card` | When the speaker introduces a technical term — show the term + short definition |
| **Statistic/number** | `stat_card` | When the speaker mentions a number or percentage — animate it on screen |
| **Comparison** | `comparison` | When the speaker compares two things (A vs B) — show side-by-side |
| **Data chart** | `bar_chart` / `pie_chart` / `line_chart` | When the speaker references data or rankings |
| **KPI dashboard** | `kpi_grid` | When multiple numbers are mentioned together |
| **Progress indicator** | `progress_bar` | When the speaker describes a process or percentage |
| **Section title** | `hero_title` | At major topic transitions — show the new section title |
| **Callout/quote** | `callout` | When the speaker makes a key point worth emphasizing |
| **Lower third** | `text_card` | Speaker identification at the start |

**Overlay planning rules:**
- **Don't over-overlay.** 3-6 overlays per minute of final video is the sweet spot. More than that is distracting.
- **Time overlays to speech.** Each overlay should appear when the speaker says the relevant words, not before or after.
- **Keep overlays brief.** 3-5 seconds each. They support the speaker, not compete with them.
- **Vary the types.** Don't use 5 text_cards in a row — mix in charts, comparisons, callouts.
- **Use overlays at natural pauses.** When the speaker pauses for emphasis, that's a good overlay moment.
- **Match the vibe.** Professional talk = clean stat cards and charts. Casual talk = callouts and bold key terms.

### Step 3: Present Your Plan to the User

**MANDATORY: Present your enhancement plan before proceeding.**

Format your proposal clearly:

```
## Enhancement Plan for [Video Title/Topic]

**Content Summary:** [1-2 sentences about what the speaker covers]

**Proposed Overlays:**

| Time | Type | Content | Why |
|------|------|---------|-----|
| 0:05 | lower_third | "Speaker Name — Title" | Speaker intro |
| 0:22 | text_card | "Agentic AI: software that acts autonomously" | Key term definition |
| 0:45 | comparison | Traditional Software vs Agentic Software | Speaker is comparing the two |
| 1:10 | stat_card | "73% of developers..." | Statistic mentioned |
| 1:35 | bar_chart | [Framework popularity data] | Speaker references rankings |
| 2:00 | callout | "The key insight is..." | Speaker's main takeaway |

**Enhancement Chain:**
- Silence removal: ~X seconds of dead air detected
- Speed: 1.25x (user requested)
- Face + eye enhancement
- Animated captions (bottom of frame)
- Background music: [recommendation]

**Estimated final duration:** ~Xs (from Xs raw)
```

Wait for user approval before proceeding. The user may:
- Approve as-is
- Add/remove overlays
- Change overlay content
- Adjust the enhancement plan

### Step 4: Analyze Footage (if tools available)

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
- **Determine overlay safe zones** — where to place graphics without occluding the face

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

### Step 5: Plan Base Scenes

For talking-head, the base is simple: one scene per script section, all type `talking_head`. The raw footage IS the scene.

### Step 6: Build Overlay Scenes

For each approved overlay from Step 3, create an overlay scene entry:
```json
{
  "id": "overlay_1",
  "type": "overlay",
  "overlay_type": "text_card",
  "start_seconds": 22.0,
  "duration_seconds": 4.0,
  "content": {
    "text": "Agentic AI",
    "subtext": "Software that acts autonomously toward goals",
    "backgroundColor": "#0F172A",
    "accentColor": "#22D3EE"
  },
  "position": "lower_third"
}
```

**Overlay position options:**
- `lower_third` — bottom 30% of frame (safest, doesn't occlude face)
- `upper_third` — top 30% of frame (good for titles)
- `side_panel` — left or right 40% (for charts/comparisons, speaker shifts to other side)
- `full_overlay` — brief full-screen graphic (1-2s max, for dramatic emphasis)

### Step 7: Plan Reframing & Cuts

If the target platform requires a different aspect ratio (e.g. Instagram Reels = 9:16):
- Note `auto_reframe` should be applied in the compose stage
- Record the target aspect ratio in the scene plan
- If face tracking data shows significant speaker movement, note that dynamic crop is needed

If silence detection found segments to cut:
- Record the recommended cut mode (`remove` or `speed_up`) in the scene plan
- Note padding preferences (default 0.08s to avoid clipping words)

### Step 8: Build Scene Plan

Assemble the full scene plan with:
- Base scenes (one per script section, type `talking_head`)
- Overlay scenes (from Step 6, type `overlay`)
- Enhancement chain decisions (silence cut mode, speed factor, reframe target)
- Music recommendation
- Estimated final duration

### Step 9: Self-Evaluate

| Criterion | Question |
|-----------|----------|
| **Content understanding** | Did I actually understand what the speaker is talking about? |
| **Overlay relevance** | Does every overlay directly relate to what's being said at that moment? |
| **Overlay density** | Am I in the 3-6 per minute range? Not too sparse, not too cluttered? |
| **Overlay variety** | Am I using different types, not just text_cards? |
| **Timing** | Are overlays timed to the speaker's words, not arbitrary moments? |
| **Coverage** | Every script section has a scene? |
| **Feasibility** | Can all overlays be rendered with available Remotion components? |
| **User approved** | Did the user approve the enhancement plan? |

### Step 10: Submit

Validate the scene_plan against the schema and persist via checkpoint.
