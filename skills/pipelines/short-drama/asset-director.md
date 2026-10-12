# Asset Director — Short Drama

## Process

1. Validate subgraphs with `subgraph_validate`.
2. Fan out storyboard shots into `shot_job_manager` (`create_ledger_from_storyboard`).
3. For each job, run subgraph `keyframe-i2v-qa` via `meta/subgraph-runner`:
   - keyframe (`image_selector`) with bible references
   - route provider (`video-router` subgraph)
   - I2V (`video_selector`)
   - optional `drama_visual_qa`; rework on critical
4. Generate dialogue audio via `tts_selector` / `audio-pack` subgraph; lip_sync only when needed.
5. Write `asset_manifest` + persist ledger.

## Hard rules

- **No naked batch `video_selector`**
- Pause/resume only through ledger
- Announce provider before each paid shot generation

## Output

Schema-valid `asset_manifest` and `shot_job_ledger`.
