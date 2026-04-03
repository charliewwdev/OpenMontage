# Scene Director - Cinematic Pipeline

## When To Use

You are deciding how each cinematic beat will look and transition. This is where mood becomes a visual plan.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/scene_plan.schema.json` | Artifact validation |
| Prior artifacts | `state.artifacts["script"]["script"]`, `state.artifacts["proposal"]["proposal_packet"]` | Beat map and source truth |
| Tools | `frame_sampler`, `scene_detect` | Source inspection and reframing checks |
| Playbook | Active style playbook | Color and typography consistency |

## Process

### 1. Make Hero Frames Explicit

Every cinematic piece needs a few memorable frames. Define them directly:

- opening image,
- reveal image,
- final image,
- any title-card hero moments.

### 2. Keep Source-Led Scenes Primary

If source footage exists, let it carry the piece. Generated inserts or text cards should support transitions, emphasis, or missing coverage, not dominate the timeline.

### 3. Limit Transition Vocabulary

Choose a small set:

- hard cut,
- fade to black,
- slow dissolve,
- restrained push or punch-in.

Too many transition types kill the mood.

### 4. Use Metadata For Visual Rules

Recommended metadata keys:

- `hero_frames`
- `transition_rules`
- `aspect_ratio_rules`
- `title_card_rules`
- `support_insert_rules`

### 5. Quality Gate

- every beat has a scene treatment,
- hero frames are identifiable,
- support inserts are justified,
- the visual language stays consistent across the piece.

## Common Pitfalls

- Using title cards as filler.
- Treating generated inserts like the primary story without saying so.
- Planning flashy transitions for every beat.
