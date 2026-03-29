# Idea Director - Cinematic Pipeline

## When To Use

Use this pipeline for trailers, brand films, dramatic montages, or mood-led short videos where rhythm, atmosphere, and emotional escalation matter more than direct explanation.

Do not use this pipeline just because the user said "make it look cinematic." If the project is really a screen demo, explainer, or repurposing job, route it there instead.

## Reference Inputs

- `docs/cinematic-best-practices.md`
- `skills/creative/cinematic.md`
- `skills/creative/storytelling.md`

## Process

### 1. Classify The Source Reality

Capture the source mode:

- `footage_only`
- `footage_plus_stills`
- `still_led`
- `generated_support`
- `mixed_montage`

Do not assume stock, generated b-roll, or music exists unless the user has provided it or the environment can actually make it.

### 2. Define The Emotional Arc

Choose the arc in plain language:

- tension -> reveal
- wonder -> scale
- intimacy -> payoff
- urgency -> resolution
- mystery -> CTA

The brief should tell later stages what the video is trying to make the viewer feel, not just what it is about.

### 3. Pick The Delivery Shape

Common output shapes:

- `teaser`
- `trailer`
- `hero_brand_film`
- `mood_cut`
- `social_cutdown`

Store longer planning detail in `brief.metadata`.

Recommended metadata keys:

- `source_mode`
- `delivery_shape`
- `emotional_arc`
- `anchor_assets`
- `music_strategy`
- `generated_support_level`
- `aspect_ratio_plan`
- `rights_constraints`

### 4. Reality Check The Treatment

If the user has weak source media and no generation path, say so. A cinematic result still needs enough visual or audio material to carry mood.

### 5. Quality Gate

- the source truth is explicit,
- the emotional arc is specific,
- the output shape fits the available assets,
- the treatment is cinematic for a reason, not by label only.

## Common Pitfalls

- Calling something cinematic when it is really just a normal edit with black bars.
- Assuming generated inserts are available without checking tools.
- Planning a trailer shape with no reveal or payoff.
