# Asset Director - Documentary Montage Pipeline

## When To Use

The shot list exists. You now have to actually go out and find the
clips that fill each slot. This is a two-step operation:

1. **Build the corpus** — fan the scene director's queries out across
   Pexels / Archive.org / NASA / Wikimedia / Unsplash and download/embed the candidates.
2. **Pick per slot** — run CLIP retrieval against the corpus with each
   slot description and choose one winner per slot.

The output is an `asset_manifest` mapping every slot to exactly one
clip with full provenance.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/asset_manifest.schema.json` | Artifact validation |
| Prior artifact | `state.artifacts["scene_plan"]["scene_plan"]` | Slot descriptions + queries + preferred_sources |
| Prior artifact | `state.artifacts["idea"]["brief"]` | `era_mix`, `sources_allowed`, `music_plan` |
| Tool | `corpus_builder` | Populates the retrieval index |
| Tool | `clip_search` | Ranks clips against slot descriptions |
| Tool (optional) | `music_gen`, user's `music_library/` | Score bed |

## Mental Model

The corpus is NOT a stock library. It is a search index the agent
builds on demand. You do not scroll through it — you query it.

Three rules that follow from that:

1. **Build before picking.** Never call `clip_search.rank_for_slot`
   on a corpus that doesn't contain candidates for that slot's query
   family. The ranking will return junk and you'll waste the slot.
2. **Grow, don't replace.** The corpus is append-only. If a slot's
   retrieval is weak, add more queries and rebuild — don't start over.
3. **Pick per slot, not per clip.** Every clip only belongs to one
   slot in the final edit. Use `exclude_ids` to prevent double-use.

## Process

### 1. Resolve The Corpus Directory

Decide where the corpus lives. Convention:

```
projects/<project-name>/corpus/
```

The same `corpus_dir` is passed to every `corpus_builder` and
`clip_search` call. The corpus is reusable across re-runs — if the
scene director adds slots later, you can grow the same corpus instead
of rebuilding from scratch.

### 2. Fan Out The Queries Into `corpus_builder`

Read `scene_plan.metadata.slots[]`. Collect every `queries[]` array
across every slot. De-duplicate. Group by `preferred_sources`.

Call `corpus_builder.execute(...)` with one fan-out per source set:

```python
# Example shape. The agent constructs this from the shot list.
corpus_builder.execute({
    "corpus_dir": "projects/<name>/corpus",
    "queries": [
        {"query": "raindrop on asphalt slow motion", "kind": "video", "per_source": 8},
        {"query": "wet city street night neon",       "kind": "video", "per_source": 8},
        {"query": "taxi heavy rain yellow",           "kind": "video", "per_source": 6},
        # ... one entry per unique slot query
    ],
    "sources": ["pexels", "archive_org", "wikimedia"],   # from preferred_sources union
    "filters": {
        "min_duration": 3,
        "max_duration": 40,
        "orientation": "landscape",
        "min_width": 1280,
    },
    "max_new_clips": 150,          # enlarge the search space
    "thumbs_per_video": 5,
})
```

**Rules for the fan-out:**

- If the brief pins a source and `corpus_builder.source_provider_menu`
  says that source is unavailable, STOP and surface it. Do not silently
  drop to the remaining sources.
- Budget the corpus for 8-12x the slot count. A 15-slot montage wants
  ~150 candidates so retrieval has real choices.
- `per_source` of 4-8 per query is usually enough. Pushing to 20+
  mostly adds noise.
- If `era_mix = "vintage"`, run a separate fan-out restricted to
  `["archive_org"]` with period-appropriate queries. Prelinger search
  is slow — don't interleave it with the modern Pexels batch.
- If any slot has `nasa` in `preferred_sources`, run ONE small
  `nasa`-only batch. NASA is slow and its results are niche.
- `unsplash` is image-only. Use it as a support source, not the
  backbone of a motion-led documentary cut.

### 3. Sanity-Check The Corpus Before Retrieval

Before spending tokens on slot picks, call `clip_search` with
`operation=stats`:

```python
clip_search.execute({
    "operation": "stats",
    "corpus_dir": "projects/<name>/corpus",
})
```

Look at `rows`, `per_source`, `per_kind`, `mean_motion_score`. You're
checking for three failure modes:

- `rows < 50` — corpus is too small. Grow it.
- `per_source` heavily skewed (e.g. 98% pexels, 2% archive_org) on a
  vintage brief — run a targeted archive_org fan-out.
- `mean_motion_score < 1.0` — corpus is full of static clips and will
  make for a slideshow. Rerun with different queries, or apply
  `motion_min` at rank time.

### 4. Rank Candidates Per Slot

For each slot in `scene_plan.metadata.slots[]`, call `clip_search`
with `operation=rank_for_slot`:

```python
clip_search.execute({
    "operation": "rank_for_slot",
    "corpus_dir": "projects/<name>/corpus",
    "query_text": slot["description"],      # NOT slot["queries"] — the description is richer
    "k": 30 if slot.get("hero") else 12,
    "tag_weight": 0.3,
    "motion_min": 1.5,
    "kind": "video",
    "exclude_ids": already_picked_ids,      # global accumulator
})
```

Key points:

- Use the slot **description**, not the queries. The description is
  the rich noun-and-adjective string the scene director wrote. CLIP
  ranks it better than short search phrases.
- `tag_weight=0.3` blends visual embedding (70%) with source-tag
  embedding (30%). Raise to 0.5 when Pexels URL tags are strong and
  the visual channel is noisy. Lower to 0.15 for Prelinger where tags
  are long prose.
- Always pass `exclude_ids` with every clip already locked to a slot,
  so the same key-in-door clip doesn't win two slots.

### 5. Pick With Judgement, Not By Score

The top result is not always the right pick. Look at the top 3-5 and
judge each one against:

- **Era fit.** Does a 2022 4K Pexels shot belong in an elegiac list
  montage about home? Maybe. Maybe not.
- **Motion fit.** The tone table from the scene director tells you
  how long the hold will be. If the clip has a 4.0s hold target and
  the clip is 2s long with a fast whip pan, it won't stretch.
- **Compositional carry.** Will this clip work NEXT to the clips
  picked for the adjacent slots? You don't know yet — but if slot_02
  is a wide rooftop-in-rain and the top hit for slot_03 is also a
  wide rooftop-in-rain, pick the #2 instead.
- **Emotional register.** CLIP will happily match "empty city
  sidewalk at night" to a bright neon Vegas cutaway. The neon shot is
  WRONG for an elegiac brief. Score 0.42 does not override tone.

**Acceptable-score rules of thumb (CLIP ViT-B/32 cosine):**

- `>= 0.30` — strong match, usually usable.
- `0.22-0.30` — plausible, needs human judgement.
- `< 0.22` — the corpus doesn't contain what you need. Grow it,
  don't force a pick.

### 6. Grow The Corpus When Retrieval Is Weak

If a slot's top score is below 0.22, do NOT pick the best-of-a-bad-
bunch. Instead:

1. Rewrite the slot's queries — maybe too abstract, maybe wrong
   vocabulary for the era.
2. Run another `corpus_builder.execute(...)` pass with just the new
   queries for that one slot. The builder skips clips already in the
   index, so this is cheap.
3. Re-rank.

Two growth passes per slot is plenty. If three passes can't find a
score above 0.22, tell the idea director the slot is unfilmable from
open corpora and recommend either dropping the slot or letting the
user supply the footage.

### 7. Diversify Adjacent Picks

Once you have one candidate per slot, you have a list of clip_ids in
timeline order. Visually-redundant adjacent shots kill the edit. Run
`clip_search.diversify` across the list:

```python
clip_search.execute({
    "operation": "diversify",
    "corpus_dir": "projects/<name>/corpus",
    "candidate_ids": picked_ids_in_timeline_order,
    "n": len(picked_ids_in_timeline_order),
    "diversity": 0.5,
})
```

If `diversify` drops a clip, it's telling you two of your picks are
visually identical. Re-rank the slot whose clip got dropped with
`exclude_ids` including the surviving twin.

### 8. Handle The Music Plan

Read `brief.music_plan`. Execute exactly the plan the idea director
recorded — do not invent a new source here:

- **`source=library`**: Verify the file at `music_plan.path` exists.
  Record it in the asset manifest as `type=music`, `subtype=library`.
- **`source=user`**: Same, with `subtype=provided`.
- **`source=generated`**: Call the named music tool with the seed
  prompt from the brief. Sample first, batch only after confirming
  mood. Record provider and cost.
- **`source=none`**: Do not generate silence. Do not swap in a track
  because the edit feels thin. If the user approved "no music", run
  with no music.

**Never switch music source at this stage.** That's a Decision
Communication Contract violation — changing music mode is a major
production change and needs user approval at proposal time.

### 9. Record The Asset Manifest

Emit one asset per slot using the canonical schema. Documentary-
montage-specific fields live in `metadata`:

```json
{
  "version": "1.0",
  "assets": [
    {
      "id": "asset_slot_01",
      "type": "video",
      "path": "projects/<name>/corpus/clips/pexels_12345/video.mp4",
      "source_tool": "corpus_builder",
      "scene_id": "slot_01",
      "duration_seconds": 7.2,
      "resolution": "1920x1080",
      "format": "mp4",
      "provider": "pexels",
      "license": "Pexels License (free, no attribution required)",
      "original_url": "https://www.pexels.com/video/12345",
      "subtype": "stock",
      "generation_summary": "Retrieved via CLIP rank for slot 'raindrop on asphalt slow motion...'. Score 0.38."
    },
    {
      "id": "asset_music_bed",
      "type": "music",
      "path": "music_library/dawn_04.mp3",
      "source_tool": "music_library",
      "scene_id": "global",
      "subtype": "library",
      "license": "user-provided"
    }
  ],
  "metadata": {
    "pipeline": "documentary-montage",
    "corpus_dir": "projects/<name>/corpus",
    "corpus_stats": { "rows": 157, "per_source": {"pexels": 98, "archive_org": 52, "nasa": 7} },
    "rejected_picks": [
      {
        "slot_id": "slot_03",
        "clip_id": "pexels_99921",
        "score": 0.41,
        "reason": "wrong era — 2022 4K kitchen, brief is vintage"
      }
    ]
  }
}
```

The `rejected_picks` log matters. The edit director reads it when a
pick feels wrong and needs to reach for the #2 option.

### 10. Quality Gate

- Every slot in the scene plan has exactly one asset mapped to it.
- Every picked clip has `score >= 0.22` in the rejected-picks log
  (or a logged "user-approved override" note).
- No clip_id appears as the primary pick for two slots.
- `diversify` ran clean on the final list (no dropped picks, or all
  dropped picks were re-filled).
- `corpus_stats` shows at least 8x the slot count in rows.
- Music asset exists OR `music_plan.source = "none"` with explicit
  acknowledgement.
- For vintage briefs, at least 60% of picks come from `archive_org`.
- All file paths resolve.

## Common Pitfalls

- **Running `clip_search.rank_for_slot` against an empty corpus.**
  You will get an empty `results` list or a cryptic shape error.
  Always call `stats` after a build, before ranking.
- **Picking by score alone.** Score is an input to judgement, not the
  judgement. An elegiac piece full of top-scored Pexels HD sunshine
  will feel wrong regardless of scores.
- **Forgetting `exclude_ids`.** Without it, the same amazing clip
  wins every slot and the montage becomes a slideshow of one image.
- **Quiet music substitution.** User said "none", agent generated
  anyway because "the edit felt thin". This is a major change and
  needs approval — see `skills/pipelines/documentary-montage/executive-producer.md`
  cross-stage rules.
- **Growing the corpus unboundedly.** Two growth passes per weak slot
  is the limit. Beyond that, the footage probably doesn't exist in
  the open corpora and the slot needs to change.
- **Using slot queries as the rank text.** Queries are search phrases
  for stock APIs; descriptions are semantic text for CLIP. They are
  different. Rank on descriptions.
- **Losing provenance.** Every clip must carry `provider`,
  `original_url`, and `license` in the manifest. These are the
  non-negotiables for any downstream publishing step.

## Retrieval Recipes

A few retrieval moves that come up often:

### "Find N variants of this one clip I love"

```python
clip_search.execute({
    "operation": "find_similar_set",
    "corpus_dir": "projects/<name>/corpus",
    "seed_clip_id": "pexels_12345",
    "n": 5,
    "diversity": 0.4,
    "candidate_pool": 40,
})
```

Used when a slot wants "five more shots like this one" — e.g. a
catalogue of doorways all filmed in the same register.

### "I have 20 candidates, trim to 8 non-redundant picks"

```python
clip_search.execute({
    "operation": "diversify",
    "corpus_dir": "projects/<name>/corpus",
    "candidate_ids": [...],
    "n": 8,
    "diversity": 0.5,
})
```

### "Look up one clip's full metadata"

```python
clip_search.execute({
    "operation": "get",
    "corpus_dir": "projects/<name>/corpus",
    "clip_id": "archive_org_Prelinger_HomeMovies_0042",
})
```

Used when the edit director wants to confirm the provider/URL before
locking the cut.
