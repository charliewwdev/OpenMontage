# Scene Director — Talking Head Pipeline

## When to Use

You have a script (from transcription) and raw footage. Your job is to create a scene plan — mostly simple since talking-head footage is a single continuous shot, but you still need to plan where overlays, text cards, and B-roll might appear.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/scene_plan.schema.json` | Artifact validation |
| Prior artifacts | Script, Brief | Section timing and context |
| Tools | `frame_sampler` (optional) | Extract representative frames |

## Process

### Step 1: Plan Base Scenes

For talking-head, the base is simple: one scene per script section, all type `talking_head`. The raw footage IS the scene.

### Step 2: Plan Enhancement Scenes

Based on script enhancement cues, plan overlay scenes:
- Text cards for key terms or statistics
- Lower thirds for speaker identification
- B-roll suggestions for topic illustrations

### Step 3: Build Scene Plan

Create a scene per section with:
- Type: `talking_head` (primary)
- Timing from script sections
- Required assets: subtitle file, any overlay images

### Step 4: Self-Evaluate

| Criterion | Question |
|-----------|----------|
| **Coverage** | Every script section has a scene? |
| **Enhancement** | Are overlay opportunities identified? |
| **Feasibility** | Can all required assets be generated? |

### Step 5: Submit

Validate the scene_plan against the schema and persist via checkpoint.
