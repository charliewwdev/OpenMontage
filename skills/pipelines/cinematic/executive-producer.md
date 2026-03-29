# Executive Producer — Cinematic Pipeline

## When to Use

You are the **Executive Producer (EP)** for a cinematic video (trailers, brand films, montages, short dramatic edits). You orchestrate the pipeline serially with quality gates focused on **mood, emotional pacing, color consistency, and audio dynamics**.

**No pre-production stages.** Source footage or direction exists. The EP adds cross-stage gates that enforce emotional arc integrity and cinematic polish.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Pipeline | `pipeline_defs/cinematic.yaml` | Stage definitions |
| Skills | All 7 director skills + `meta/reviewer` | Stage execution |
| Schemas | All artifact schemas | Validation |
| Playbook | Active style playbook | Quality constraints |

## Cumulative State

```
EP_STATE:
  pipeline: cinematic
  playbook: <selected>
  target_duration_seconds: <from brief>
  budget_total_usd: <configured>
  budget_spent_usd: 0.0

  # Cinematic-specific
  emotional_arc: null         # from brief: build → reveal → landing
  color_grade_target: null    # mood-driven color palette
  hero_moments: []            # key reveal/climax frames
  music_beat_map: null        # audio-driven pacing reference

  artifacts:
    idea: null
    script: null
    scene_plan: null
    assets: null
    edit: null
    compose: null
    publish: null

  revision_counts: {}
  issues_log: []
```

## Execution Protocol

Same as standard EP: Initialize → Execute stages serially (idea → script → scene_plan → assets → edit → compose → publish) → Final QA.

Each stage: PREPARE → SPAWN DIRECTOR → REVIEW → GATE DECISION (pass / revise / send-back).

## EP-Specific Cross-Stage Checks

### After IDEA stage:
```
CHECK: Emotional arc definition
  - Is the emotional arc explicit (build → reveal → landing)?
  - Is source mode clear (supplied footage vs generated inserts)?
  - Is the target mood defined and achievable?
```

### After SCRIPT stage:
```
CHECK: Beat escalation
  - Does the beat map escalate cleanly toward the reveal?
  - Are dialogue/title cards sparse and purposeful?
  - Is the landing beat distinct from the build?

CHECK: Duration fit
  - Word count aligns with cinematic pacing (slower than explainer — ~120 WPM)
```

### After SCENE_PLAN stage:
```
CHECK: Hero moment definition
  - Are hero frames (climax, reveal) explicitly identified?
  - Is source footage prioritized over generated inserts?
  - Do transitions support mood (not distract)?

CHECK: Visual consistency
  - Is the color/mood system coherent across scenes?
  - Are aspect ratio choices consistent (letterbox if used)?
```

### After ASSETS stage:
```
CHECK: Music/ambience alignment
  - Does the music beat map align with the script beat map?
  - Are generated inserts limited and justified?
  - Budget gate: 90% threshold warning

CHECK: Source selects quality
  - Are source clips properly identified and accessible?
  - Do support assets (generated or stock) match source quality level?
```

### After EDIT stage:
```
CHECK: Emotional pacing
  - Strong moments are not overcut
  - Audio cues reinforce story beats
  - Title-card timing is restrained

CHECK: Timeline completeness
  - Full runtime covered, no gaps
  - All asset references valid
```

### After COMPOSE stage:
```
CHECK: Output validation
  - ffprobe: duration, resolution, codec
  - Color grade applied and consistent
  - Audio dynamics controlled — dialogue intelligible, music balanced
  - Letterbox or frame treatment improves (not harms) the output
```

## Quality Gates Summary

| Gate | After Stage | What's Checked | Fail Action |
|------|-------------|---------------|-------------|
| G1 | idea | Emotional arc, source mode | Revise |
| G2 | script | Beat escalation, duration | Revise |
| G3 | scene_plan | Hero moments, visual consistency | Revise |
| G4 | assets | Music alignment, source quality, budget | Revise |
| G5 | edit | Emotional pacing, timeline | Revise |
| G6 | compose | Output probe, color grade, audio dynamics | Revise or send-back |
| G7 | publish | Metadata, poster frame | Revise |
| FINAL | all | Mood coherence, audio, visual polish | Send-back |

## Execution Limits

| Limit | Value |
|-------|-------|
| Max revisions per stage | 3 |
| Max send-backs per stage pair | 1 |
| Max total send-backs | 3 |
| Max total budget | Configurable (default $2) |
| Max total wall-time | 12 minutes |

## Common Pitfalls

- **Over-grading**: Color grade should enhance mood, not make footage look artificial.
- **Overuse of generated inserts**: Source footage should be primary. Generated content fills gaps, not replaces.
- **Ignoring audio dynamics**: Cinematic videos live and die by their audio. Music/dialogue balance is critical.
- **Rushing the reveal**: The climax moment needs breathing room. Don't let pacing compress it.
