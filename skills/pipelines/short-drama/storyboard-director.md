# Storyboard Director — Short Drama

## Process

1. Expand active episode scenes into shots (`ep01_sc01_sh01`, …).
2. Every shot: `shot_intent`, `duration_sec`, `shot_language`, `keyframe_prompt`, `video_prompt`.
3. Attach `character_ids` / `location_id` resolving to bible.
4. Copy pipeline `subgraph_refs` into storyboard.
5. Read `creative/drama-shot-routing.md` for intent → routing hints (do not hardcode provider in storyboard unless user locked one).

## Output

Schema-valid `storyboard`.
