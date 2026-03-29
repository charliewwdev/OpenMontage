# OpenMontage Capability Audit

> 2026-03-28 | Code-verified. Every finding traced to specific file + line.

**Core question:** When an agent discovers its capabilities via the registry and reads
the skills/manifests, does it get an accurate picture of what it can and can't do?

**Verdict:** No. The agent receives a mostly-accurate tool inventory but is actively
misled at the skill-to-tool boundary. Skills promise inputs tools don't accept, schemas
reject structures skills tell the agent to produce, and the discovery mechanism omits
the one thing the agent needs most: what inputs each tool takes.

---

## 1. Discovery: What the Agent Learns at Boot

The agent runs:
```python
from tools.tool_registry import registry
registry.discover()
envelope = registry.support_envelope()
```

**What it gets per tool** (via `BaseTool.get_info()`):
- Identity: name, version, tier, capability, provider, stability
- Status: available/unavailable/degraded, dependencies list
- Runtime: execution_mode, determinism, runtime type, resource_profile
- Decision hints: best_for, not_good_for, provider_matrix, fallback_tools
- Skill links: agent_skills, related_skills
- Side effects, resume_support, user_visible_verification

**What it does NOT get:**
| Missing Field | Why It Matters |
|---|---|
| `input_schema` | Agent can't know what parameters a tool accepts without reading source code |
| `output_schema` | Agent can't know what a tool returns |
| `artifact_schema` | Agent can't know what files a tool produces |
| `estimate_cost()` results | Agent can't compare costs without calling each tool individually |

**This is the root cause of most downstream issues.** The agent knows *what tools exist* but not *what they accept or produce*. It must rely on skills for that information — and skills get it wrong in several places.

### Fix

Add to `BaseTool.get_info()`:
```python
"input_schema": self.input_schema,
"output_schema": self.output_schema,
"artifact_schema": self.artifact_schema,
```

This single change would let the agent validate skill instructions against actual tool contracts at runtime.

---

## 2. Skills Tell the Agent to Pass Inputs Tools Don't Accept

These are cases where a stage-director skill instructs the agent to call a tool with
specific parameters, but the tool's `input_schema` and `execute()` don't read them.
The agent follows the skill, the extra fields are silently ignored, and the output
doesn't reflect the agent's intent.

### 2a. tts_selector: voice style, speaker directions, pronunciation

**Skill says** (`skills/pipelines/explainer/asset-director.md` lines 54-62):
> Apply speaker directions from the script (pace, emphasis, emotion).
> Apply the playbook's `audio.voice_style`.
> Include a pronunciation map in the TTS request for technical terms.

**Tool accepts** (`tools/audio/tts_selector.py` input_schema):
`text`, `preferred_provider`, `allowed_providers`, `output_path`

No fields for voice_style, speaker_directions, pace, emphasis, emotion, or pronunciation.
None of the concrete TTS tools (elevenlabs, openai, piper) accept these either — except
elevenlabs_tts which accepts `stability`, `similarity_boost`, `style` (numeric 0-1 floats),
not the semantic concepts the skill describes.

**Agent impact:** Agent is told to express creative direction through tool parameters that
don't exist. The narration will be generated with default voice settings regardless of what
the script specifies.

### 2b. image_selector: negative_prompt, consistency_anchors

**Skill says** (`skills/pipelines/explainer/asset-director.md` lines 68-73):
> Build the prompt: playbook.image_prompt_prefix + scene description + style cues.
> Add negative prompt from playbook.
> Include consistency anchors (same palette, same style across all images).

**Tool accepts** (`tools/graphics/image_selector.py` input_schema):
`prompt`, `preferred_provider`, `allowed_providers`, `output_path`

No `negative_prompt` or `consistency_anchors` field. The selector passes `prompt` through
to whichever provider it selects. Some downstream providers (flux_image) DO accept
`negative_prompt`, but the selector doesn't forward it.

**Agent impact:** Agent must flatten everything into a single `prompt` string. Negative
prompts and consistency anchors are lost unless the agent bypasses the selector and calls
flux_image directly — which contradicts the skill's guidance.

### 2c. video_compose "render" operation: options, output_profile

**Skill says** (`skills/pipelines/explainer/compose-director.md` lines 66-80):
```json
{
  "operation": "render",
  "edit_decisions": {...},
  "asset_manifest": {...},
  "output_profile": "youtube_landscape",
  "options": {
    "subtitle_burn": true,
    "audio_normalize": true,
    "two_pass_encode": true
  }
}
```

**Tool accepts** (`tools/video/video_compose.py` input_schema):
`operation`, `input_path`, `output_path`, `edit_decisions`, `subtitle_path`,
`subtitle_style`, `overlays`, `audio_path`, `profile`, `codec`, `crf`, `preset`

- `asset_manifest`: NOT in input_schema but IS read by `_render()` (line 271). Works but undocumented.
- `output_profile`: Not accepted. The field is `profile` and only used by `_encode()`, not `_render()`.
- `options`: Not accepted at all. `subtitle_burn`, `audio_normalize`, `two_pass_encode` are silently dropped.

**Agent impact:** Agent follows the skill, passes these fields, they vanish. Output won't
match target platform. No subtitle burn, no normalization, no two-pass encode.

### 2d. audio_mixer: skill implies single call, tool requires multiple

**Skill says** (`skills/pipelines/explainer/compose-director.md` lines 87-95):
> Call the audio_mixer tool to:
> 1. Layer narration segments in order
> 2. Mix background music at playbook volume
> 3. Apply ducking (music dips during narration)
> 4. Normalize overall audio levels

**Tool accepts** (`tools/audio/audio_mixer.py`):
Three discrete operations: `mix`, `duck`, `extract`. Each is a separate `execute()` call.
There is no single-call "mix everything together" mode.

**Agent impact:** Agent attempts a single call with all requirements. The tool handles one
operation per call. Agent must orchestrate: mix narration tracks first, then duck with
music, then the compose step muxes audio into video. The skill doesn't explain this
multi-step choreography.

---

## 3. Skills Tell the Agent to Produce Artifacts Schemas Reject

These are cases where a skill shows the agent an example JSON structure for an artifact,
but the corresponding JSON Schema has `additionalProperties: false` and rejects the
skill's fields.

### 3a. edit_decisions: transforms and transitions

**Skill says** (`skills/pipelines/explainer/edit-director.md` lines 38-53):
```json
{
  "id": "cut-1",
  "source": "img-scene-1",
  "in_seconds": 0,
  "out_seconds": 10,
  "layer": "primary",
  "transform": {
    "scale": 1.0,
    "position": "center",
    "animation": "ken-burns-slow-zoom"
  },
  "transition_in": "fade",
  "transition_out": "dissolve",
  "transition_duration": 0.4
}
```

**Schema allows** (`schemas/artifacts/edit_decisions.schema.json` lines 12-24):
```json
{
  "required": ["id", "source", "in_seconds", "out_seconds"],
  "properties": {
    "id": {}, "source": {}, "in_seconds": {}, "out_seconds": {},
    "speed": {}, "reason": {}
  },
  "additionalProperties": false
}
```

**Rejected fields:** `layer`, `transform` (and all sub-fields), `transition_in`,
`transition_out`, `transition_duration`.

**Agent impact:** Agent builds the edit_decisions artifact per skill instructions.
Checkpoint validation rejects it. Agent is stuck between following the skill and
passing schema validation. The schema also means `video_compose._compose()` will
never receive transition/transform data even if it could handle it — which it can't
(it only does hard cuts via concat).

### 3b. edit_decisions: subtitle styling

**Skill says** (edit-director.md lines 62-78):
```json
"subtitles": {
  "enabled": true,
  "style": "word-by-word",
  "font": "Inter",
  "font_size": 48,
  "color": "#FFFFFF",
  "background": "#00000088",
  "position": "bottom-center",
  "max_words_per_line": 8
}
```

**Schema allows** (edit_decisions.schema.json lines 51-58):
```json
"subtitles": {
  "properties": {
    "enabled": { "type": "boolean" },
    "style": { "type": "string" },
    "source": { "type": "string" }
  }
}
```

**Rejected fields:** `font`, `font_size`, `color`, `background`, `position`,
`max_words_per_line`.

**Agent impact:** All subtitle styling information is lost at schema validation.
The compose stage gets `enabled: true` and `style: "word-by-word"` but no font,
color, or positioning data. Subtitle styling must come from video_compose's
`subtitle_style` input instead — but the edit-director skill doesn't mention this path.

### 3c. edit_decisions: narration and SFX audio configuration

**Skill says** (edit-director.md lines 84-110):
```json
"audio": {
  "narration": {
    "segments": [
      { "asset_id": "narration-s1", "start_seconds": 0 }
    ]
  },
  "music": {
    "asset_id": "...",
    "ducking": {
      "enabled": true,
      "threshold_db": -3,
      "reduction_db": -8,
      "attack_ms": 200,
      "release_ms": 500
    }
  },
  "sfx": []
}
```

**Schema allows** (edit_decisions.schema.json lines 59-67):
`music` with `asset_id`, `volume`, `ducking` (boolean only), `fade_in_seconds`, `fade_out_seconds`.

**Rejected:** Entire `audio.narration` section, entire `audio.sfx` section, structured
`ducking` object (schema only accepts boolean). Narration segment timing and SFX
have no home in the validated artifact.

---

## 4. Tools Lie About What They Can Do

### 4a. video_compose._render() claims image-to-video conversion

**Docstring** (`tools/video/video_compose.py` line 267):
> "It orchestrates: image-to-video conversion, concatenation, audio mixing,
> subtitle burn-in, and final encoding to target profile."

**Actual code** (lines 280-302): Resolves asset IDs from asset_manifest to file paths,
then calls `_compose()`. No image-to-video conversion. `_compose()` uses `ffmpeg -ss/-to`
on each source, which fails on still images (PNG/JPG have no temporal dimension to seek into).

**Agent impact:** Agent trusts that the "render" operation handles images. It doesn't.
Explainer pipelines where most cuts are generated images will produce broken output.

### 4b. subtitle_gen declares highlight_style but ignores it

**Input schema** (`tools/subtitle/subtitle_gen.py`): includes `highlight_style` parameter.

**Execute method:** Never reads `highlight_style`. It's a phantom parameter.

**Agent impact:** Low — agent might pass highlight_style expecting highlighted captions
and get plain ones.

### 4c. video_selector declares operation parameter but ignores it

**Input schema** (`tools/video/video_selector.py`): includes `operation` field.

**Execute method:** Reads it but never passes it to the selected provider tool.

**Agent impact:** Low — operation context is lost during delegation but most video
providers only do one thing anyway.

---

## 5. Phantom Tools in Pipeline Manifests

`pipeline_defs/framework-smoke.yaml` references three tools that don't exist:

| Tool Name | Stage | Field |
|---|---|---|
| `idea_explorer_llm` | research | preferred_tools |
| `script_writer_llm` | script | preferred_tools |
| `script_writer_template` | script | fallback_tools |

`registry.discover()` will not find these. If the agent tries to resolve them, it gets
nothing. These appear to be placeholders from an earlier design where LLM capabilities
were modeled as tools.

**Agent impact:** framework-smoke pipeline is broken. Other 10 pipelines are clean —
all their tool references resolve to real tools.

---

## 6. Unused Tools the Agent Doesn't Know to Use

Five tools exist in `tools/` but no pipeline manifest references them:

| Tool | What It Does | Why It's Missing |
|---|---|---|
| `bg_remove` | Background removal (rembg/U2Net) | Useful for compositing, overlays. No skill mentions it. |
| `face_restore` | Face restoration (CodeFormer/GFPGAN) | Useful for low-res faces in talking-head. No skill mentions it. |
| `upscale` | Image/video upscaling (Real-ESRGAN) | Useful for enhancement pass. No skill mentions it. |
| `video_understand` | Vision-language analysis (CLIP/BLIP-2) | Could be used for quality review. No skill mentions it. |
| `image_gen` | Legacy multi-provider image gen | Deprecated, replaced by image_selector. Expected. |

The agent discovers these via `support_envelope()` but has no skill guidance on when or
how to use them. They're invisible capabilities — the agent CAN use them but WON'T
unless it independently decides to.

---

## 7. The Playbook Gap: Declared Knowledge the Agent Can't Apply

Style playbooks (`styles/*.yaml`) define detailed visual contracts:
`image_prompt_prefix`, `negative_prompt`, `consistency_anchors`, `typography`,
`motion.transition_duration_seconds`, `audio.music_mood`, `quality_rules`.

Skills extensively reference these: "apply the playbook's voice_style", "use playbook's
image_prompt_prefix", "set music volume per playbook". **30+ skill references across
all pipelines.**

But:
- Zero tools import `playbook_loader` or read playbook data
- The selector tools (tts_selector, image_selector) have no playbook-aware parameters
- The agent must: load the YAML, extract values, manually inject them into tool calls

This works IF the agent knows to do it. But the tools give no signal that they expect
playbook-derived values. The playbook system is a skill-layer convention that the tool
layer is unaware of. This is architecturally fine for an agent-first system — but the
skills need to be explicit about HOW the agent should bridge this (e.g., "read
`playbook.asset_generation.image_prompt_prefix` and prepend it to the `prompt` field
when calling image_selector"). Currently skills say WHAT to apply but not HOW to
translate playbook values into tool parameters.

---

## 8. Missing Skill: Talking-Head Executive Producer

`pipeline_defs/talking-head.yaml` declares `orchestration.skill: pipelines/talking-head/executive-producer` but the file `skills/pipelines/talking-head/executive-producer.md` does not exist. All other 9 pipelines with orchestration have their EP skill.

**Agent impact:** Agent following the talking-head pipeline reads the manifest, tries to
load the EP skill, gets a file-not-found. Must improvise orchestration without guidance.

---

## Summary: What the Agent Gets Right vs. Wrong

### Accurate (agent can trust these)
- Tool inventory: 44/47 tool references in manifests resolve correctly (3 phantoms in framework-smoke only)
- Tool status: `get_status()` accurately reports availability based on real dependency checks
- Fallback chains: All `fallback_tools` references point to tools that exist
- Tool self-description: 10/12 tools audited have accurate input_schema vs execute() behavior
- Pipeline stage ordering and artifact flow: checkpoint system matches manifests
- Cost estimates: Tools that implement `estimate_cost()` return realistic numbers

### Inaccurate (agent will be misled by these)
| Issue | Count | Root Cause |
|---|---|---|
| Skills pass inputs tools don't accept | 4 cases | Skills written to aspirational API, not actual tool schema |
| Skills produce artifacts schemas reject | 3 cases | Schemas stricter than skills expect (additionalProperties: false) |
| Tool overclaims capability | 1 case | video_compose._render() docstring lies about image handling |
| Discovery omits input/output schemas | All tools | get_info() doesn't include schemas |
| Phantom tools in manifests | 3 tools | framework-smoke has placeholder references |
| Missing EP skill | 1 pipeline | talking-head pipeline incomplete |

### Recommended Fix Priority

| # | Fix | Effort | Effect |
|---|---|---|---|
| 1 | Add input_schema/output_schema to `get_info()` | 3 lines | Agent can self-validate against skills |
| 2 | Align edit_decisions.schema.json with edit-director skills | Medium | Unblocks transitions, subtitle styling, narration config |
| 3 | Add image-to-video loop in video_compose._compose() | Small | Unblocks all image-based pipelines |
| 4 | Add negative_prompt passthrough to image_selector | Small | Enables playbook integration for image gen |
| 5 | Add voice_id/style passthrough to tts_selector | Small | Enables creative direction for narration |
| 6 | Fix compose-director to match video_compose's actual interface | Small | Agent stops passing phantom options |
| 7 | Fix compose-director to document multi-call audio_mixer flow | Small | Agent knows to call mix then duck |
| 8 | Remove phantom tools from framework-smoke.yaml | Trivial | Clean manifest |
| 9 | Create talking-head executive-producer.md | Medium | Completes pipeline |
| 10 | Document playbook-to-tool bridging pattern in skills | Medium | Agent knows HOW to apply playbook values |
