# Asset Director — Explainer Pipeline

## When to Use

You are the Asset Producer for a generated explainer video. You have a `scene_plan` with required assets and a `script` with narration text. Your job is to generate every asset needed: narration audio, images, diagrams, code snippets, and background music. Every file must exist on disk before you finish.

This is where plans become real files. A missing or low-quality asset will torpedo the final video.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/asset_manifest.schema.json` | Artifact validation |
| Prior artifacts | `state.artifacts["scene_plan"]["scene_plan"]`, `state.artifacts["script"]["script"]`, `state.artifacts["idea"]["brief"]` | What to produce |
| Playbook | Active style playbook | Image prompts, diagram style, audio preferences |
| Tools | `tts_selector`, `image_selector`, `video_selector`, `diagram_gen`, `code_snippet`, `music_gen` — selectors auto-discover all available providers from the registry | Generation capabilities |
| Cost tracker | `tools/cost_tracker.py` | Budget governance |

## Process

### Step 1: Inventory Required Assets

Walk every scene in the scene plan. For each `required_assets` entry, create an asset task:

```
Asset Task:
  scene_id: scene-3
  type: diagram
  description: "Mermaid flowchart: query -> encode -> search -> rank -> return"
  source: generate
  tool: diagram_gen
  estimated_cost: $0.00
```

Also create tasks for:
- **Narration audio** — one per script section (use `tts_selector` or a concrete TTS provider)
- **Background music** — one track for the whole video (use `music_gen` or select from library)
- **Sound effects** — per playbook's `sfx_style` (optional, use `music_gen` or stock)

### Step 2: Check Budget

Before generating anything:
1. Sum all estimated costs from the asset tasks
2. Compare against the cost tracker's remaining budget
3. If over budget:
  - Switch expensive tools to cheaper alternatives (use `tts_selector` with `preferred_provider` to route to cheaper TTS; use `image_selector` to route to cheaper image providers)
   - Reduce image count (combine similar scenes)
   - Skip optional assets (SFX, B-roll)
4. Get cost approval via cost tracker before proceeding

### Step 2b: Sample Preview (Prevents Wasted Spend)

Before batch-generating assets, produce one sample of each expensive asset type and present them to the user for approval:

1. **TTS sample**: Generate narration for the first script section only. Play it for the user. Confirm voice, pace, and tone are acceptable before generating the rest.
2. **Image sample**: Generate one image for the most representative scene. Show it to the user. Confirm the style, quality, and prompt approach before batch-generating all images.
3. **Music sample** (if using `music_gen`): Generate one short clip. Confirm mood and energy before committing.

If the user rejects a sample:
- Adjust the parameters (voice, prompt style, provider) and regenerate the sample.
- Do not batch-generate until the sample is approved.
- Max 3 sample iterations per asset type before escalating to the user for a decision.

This step typically costs $0.03–0.08 total and prevents $1–3 of wasted generation.

### Step 3: Generate Narration

For each script section:
1. Extract the narration text
2. Apply speaker directions from the script (pace, emphasis, emotion)
3. Apply the playbook's `audio.voice_style`
4. Generate using `tts_selector` — it auto-routes to the best available TTS provider based on user preference and availability. Check the registry's `best_for` fields to understand each provider's strengths.
5. Verify the audio file exists and duration matches expected timing (±15%)

**Pronunciation guide**: If the script contains technical terms, jargon, or names with non-obvious pronunciation, include a pronunciation map in the TTS request.

### Step 4: Generate Visual Assets

Process asset tasks grouped by tool for efficiency:

**Images (`image_selector`)**:
1. Build the prompt: `playbook.asset_generation.image_prompt_prefix` + scene description + style cues
2. Add negative prompt from playbook
3. Include consistency anchors (same palette, same style across all images)
4. Generate and verify the file exists
5. If the result doesn't match expectations, refine the prompt and regenerate (max 2 retries)

**Diagrams (`diagram_gen`)**:
1. Convert the scene description into valid Mermaid syntax
2. Apply playbook's `asset_generation.diagram_style`
3. Generate SVG/PNG
4. Verify all nodes and edges are present

**Code snippets (`code_snippet`)**:
1. Extract language and code from the scene description
2. Apply syntax highlighting theme from playbook's overlay styles
3. Generate highlighted image or Remotion-compatible data

### Step 5: Generate Music

1. Read playbook's `audio.music_mood` and `audio.music_volume`
2. Check the music decision from `proposal_packet.production_plan.music_source` (set by the Proposal Director)
3. Source the background track in this priority order:
   - **User-selected library track**: If the proposal specified a track from `music_library/`, copy it to `projects/<project>/assets/music/background_music.mp3`
   - **User music library (`music_library/`)**: If the folder exists and has tracks, pick the best match for the playbook's `audio.music_mood`. List candidates by filename and let the EP decide.
   - **Music generation API**: Use `music_gen` (ElevenLabs) or `suno_music` if available. Check status via registry first — if the tool is unavailable or quota-exhausted, skip immediately (do NOT attempt and fail silently).
   - **No music available**: Log this clearly in the asset manifest as `"music_status": "unavailable"` with the reason. Do NOT silently produce a video without music — the EP and user should know.
4. Duration should be at least as long as total video duration. If shorter, it can be looped by the compose stage.
5. Verify the audio file exists at `projects/<project>/assets/music/background_music.mp3`

**Critical:** If music generation fails or is unavailable, report it immediately in the asset manifest — do not defer the problem to the compose stage.

### Step 6: Build Asset Manifest

Assemble all generated assets into the manifest:

```json
{
  "version": "1.0",
  "assets": [
    {
      "id": "narration-s1",
      "type": "audio",
      "subtype": "narration",
      "path": "assets/narration/s1.mp3",
      "source_tool": "tts_selector",
      "scene_id": "scene-1",
      "duration_seconds": 8.2,
      "cost_usd": 0.003
    },
    {
      "id": "img-scene-3",
      "type": "image",
      "path": "assets/images/scene-3-diagram.png",
      "source_tool": "diagram_gen",
      "scene_id": "scene-3",
      "cost_usd": 0.00
    },
    {
      "id": "music-bg",
      "type": "audio",
      "subtype": "music",
      "path": "assets/music/background.mp3",
      "source_tool": "music_gen",
      "duration_seconds": 62,
      "cost_usd": 0.05
    }
  ],
  "total_cost_usd": 0.053,
  "generation_summary": {
    "narration_sections": 5,
    "images_generated": 8,
    "diagrams_generated": 2,
    "music_tracks": 1
  }
}
```

### Step 7: Verify All Assets

**Existence check:**
- [ ] Every asset `path` exists on disk
- [ ] Every narration section has a corresponding audio file
- [ ] Every scene with `required_assets` has all assets generated
- [ ] Background music file exists

**Quality check:**
- [ ] Narration durations within ±15% of expected timing
- [ ] Images match the playbook's style (review consistency anchors)
- [ ] Diagrams are legible and complete
- [ ] Total cost within budget

### Step 8: Self-Evaluate

Score (1-5):

| Criterion | Question |
|-----------|----------|
| **Completeness** | Does every scene have all required assets? |
| **Audio quality** | Does narration sound natural with correct pacing? |
| **Visual consistency** | Do all images look like they belong to the same video? |
| **Budget adherence** | Is total cost within the approved budget? |
| **Playbook fidelity** | Do assets match the playbook's style guide? |

If any dimension scores below 3, fix before proceeding.

### Step 9: Submit

Validate the asset_manifest against the schema and persist via checkpoint.

## Common Pitfalls

- **Generating before checking budget**: Always estimate total cost first. A 60-second video with 15 images can burn $3+ quickly.
- **Inconsistent image style**: Each image_selector call is independent. Without explicit consistency anchors in every prompt, images will drift. Always include the playbook prefix.
- **Ignoring narration timing**: If TTS produces 12s of audio for a 10s section, the edit phase will struggle. Check durations.
- **Missing pronunciation guide**: "PostgreSQL" or "Kubernetes" will be mispronounced without explicit guidance.
- **One retry then give up**: If an image doesn't match, refine the prompt specifically — don't just retry the same prompt.
