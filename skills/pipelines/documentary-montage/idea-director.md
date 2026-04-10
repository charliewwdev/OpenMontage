# Idea Director - Documentary Montage Pipeline

## When To Use

You are turning a user prompt into the brief artifact that every
downstream stage will read. For this pipeline, the brief is the
thematic core: what the montage is ABOUT, what it should feel like,
and how long it should run.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/brief.schema.json` | Artifact validation |
| User input | Conversation history | The raw ask |
| Meta | `skills/meta/reviewer.md` | Self-review pass |

## Process

### 1. Extract The Thematic Question

A documentary montage answers a question the user could not put into
a sentence. Your job is to name that question in ONE line.

Good thematic questions:

- "What does it feel like to come home?"
- "How did the 20th century think about the future?"
- "What happens in a city at 4am?"
- "What do all the footprints on Earth look like?"

Bad thematic questions (too abstract or too concrete):

- "A video about cities" (too abstract — no feeling)
- "A montage with 8 specific shots of the moon" (too concrete — that's
  a shot list, not a theme)

### 2. Fix The Tone

Choose ONE emotional register. Write it down. Everything downstream
keys off this.

Common registers for this pipeline:

- **elegiac** — long holds, muted color, slow cuts (loss, memory, home)
- **urgent** — short cuts, hard sync, motion-heavy (crisis, cities, now)
- **reverent** — stately, symmetrical, patient (nature, ritual, scale)
- **wry** — ironic juxtaposition, cut on absurdity (consumer culture,
  politics, mid-century optimism)
- **dreamlike** — slow dissolves, repeated motifs, non-linear (childhood,
  grief, memory)

### 3. Pick A Duration And A Shape

Duration matters because it caps the number of beats.

| Duration | Beats | Use |
|----------|-------|-----|
| 30-45s | 8-12 cuts | Social/Instagram/reel — one feeling, no arc |
| 60-90s | 15-25 cuts | Standard short — mini arc with a turn |
| 2-3 min | 30-50 cuts | Proper essay montage — 3-act arc possible |

Shape options:

- **single-image expansion** — one idea, held from many angles (good
  for elegiac pieces under 60s)
- **before/after** — first half establishes, second half turns (good
  for wry or urgent registers)
- **three-act** — setup → turn → release (the Adam Curtis move, needs
  >90s)
- **list/catalogue** — "everyone who..." structure, no arc, just
  accumulation (good for reverent or elegiac)

### 4. Note Music Intent

Documentary montage is inseparable from its music bed. Decide now:

- user-provided track (put path in `music_plan.source_path`),
- music library pick (list what's in `music_library/`),
- generated (name the tool and prompt seed),
- or none (silence).

**Warn the user if no music source is available.** Do not silently
defer this — it becomes an expensive surprise at the asset stage.

### 5. Record The Brief

Minimum fields the brief must carry:

```json
{
  "topic": "A minute in the rain",
  "thematic_question": "What does rain show you about a city?",
  "tone": "elegiac",
  "duration_seconds": 90,
  "shape": "list",
  "sources_allowed": ["pexels", "archive_org", "nasa"],
  "generated_clips_allowed": false,
  "narration": "none",
  "music_plan": { "source": "library", "path": "music_library/dawn_04.mp3" },
  "era_mix": "any",
  "target_platform": "social_short"
}
```

`era_mix` is a documentary-specific field: "modern" biases toward
Pexels, "vintage" biases toward Archive.org Prelinger, "any" leaves it
open for the scene director to decide per slot.

### 6. Quality Gate

- Thematic question is ONE sentence.
- Tone is ONE register from the fixed list.
- Duration and shape are concrete numbers / enum values.
- Music source is named OR the brief explicitly says "no music".
- Sources list is non-empty and at least one requested source is
  `available` per `corpus_builder.source_provider_menu` surfaced in
  preflight.

## Common Pitfalls

- Stating multiple themes ("it's about cities AND technology AND loss").
  Pick one. The others become downstream associations.
- Jumping to shot lists. The brief is about MEANING. Shots come next.
- Ignoring duration. A 45s piece with 50 cuts is nausea. A 3-minute
  piece with 12 cuts is a slideshow.
- Forgetting to ask about music. The user usually has an opinion.
