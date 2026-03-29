# Script Director — Talking Head Pipeline

## When to Use

You have a brief and raw talking-head footage. Your job is to transcribe the footage and structure it into a script artifact with timestamped sections.

Unlike the explainer pipeline (which writes a script from scratch), you're extracting and structuring existing speech.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/script.schema.json` | Artifact validation |
| Prior artifacts | `state.artifacts["idea"]["brief"]` | Content context |
| Tools | `transcriber` (WhisperX) | Speech-to-text with timestamps |

## Process

### Step 1: Transcribe

Use the transcriber tool to get word-level timestamps:
- Model: `large-v3` for best quality, `base` for speed
- Enable word-level alignment for precise timing
- Note language detection result

### Step 2: Segment into Sections

Group the transcript into logical sections:
- Detect topic changes by content
- Respect natural pauses (> 1.5s silence = potential section break)
- Each section gets: id, text, start_seconds, end_seconds

### Step 3: Enhance Section Metadata

For each section, add:
- Enhancement cues (where overlays, b-roll, or text cards could go)
- Speaker notes (emphasis, pace changes detected in audio)

### Step 4: Build Script Artifact

Assemble the structured script with:
- Total duration (from transcript)
- All sections with timestamps
- Enhancement cues per section

### Step 5: Self-Evaluate

| Criterion | Question |
|-----------|----------|
| **Transcription accuracy** | Are the words correct? (Spot-check a few sections) |
| **Timestamp accuracy** | Do section boundaries align with actual speech? |
| **Coverage** | Does the script span the full footage duration? |

### Step 6: Submit

Validate the script against the schema and persist via checkpoint.
