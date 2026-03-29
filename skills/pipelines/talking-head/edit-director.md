# Edit Director — Talking Head Pipeline

## When to Use

You have a scene plan and asset manifest. Your job is to assemble the edit decision list for a talking-head video: primarily keeping the full footage with subtitle overlay and optional enhancements.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/edit_decisions.schema.json` | Artifact validation |
| Prior artifacts | Scene plan, Asset manifest, Script | Edit inputs |
| Playbook | Active style playbook | Transition and pacing rules |

## Process

### Step 1: Define Primary Cut

For talking-head, the primary cut is usually the full footage (or trimmed segments). Create cuts that:
- Reference the raw footage as source
- Use timestamps from the script sections
- Apply any trim decisions (cut dead air, false starts)

### Step 2: Configure Subtitles

- Enable subtitles with playbook-compatible styling
- Reference the subtitle asset from the manifest
- Set position (usually bottom-center)

### Step 3: Configure Audio

- Set narration to the raw footage audio
- If background music is desired, configure ducking
- Set music volume per playbook

### Step 4: Plan Enhancements

If the scene plan includes overlays:
- Add overlay cuts for text cards, lower thirds
- Time them to match speech content

### Step 5: Self-Evaluate

| Criterion | Question |
|-----------|----------|
| **Coverage** | Do cuts span the full intended duration? |
| **Subtitles** | Are subtitles enabled and styled? |
| **Audio** | Is audio configuration complete? |

### Step 6: Submit

Validate the edit_decisions against the schema and persist via checkpoint.
