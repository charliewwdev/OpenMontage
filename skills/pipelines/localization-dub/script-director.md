# Script Director - Localization Dub Pipeline

## When To Use

Turn the approved localization brief into a transcript-backed, reviewable script package for every target language. This stage should create text truth before any dubbing audio is generated.

## Reference Inputs

- `docs/localization-dubbing-best-practices.md`
- `skills/creative/storytelling.md`

## Process

### 1. Build Source Transcript Truth

Start with the source transcript and fix obvious errors in:

- names,
- terminology,
- speaker allocation,
- numbers,
- CTA phrasing.

### 2. Produce Reviewable Target Copy

For each target language, generate text that can be reviewed before synthesis. Record where terms should remain unchanged.

### 3. Preserve Structure Where Practical

Keep section timing and sequence aligned to the source unless the translation clearly needs a different pacing strategy.

### 4. Use Metadata For Localization Control

Recommended metadata keys:

- `source_transcript_status`
- `target_language_sections`
- `glossary_terms`
- `protected_terms`
- `pronunciation_notes`
- `review_status_by_language`

### 5. Quality Gate

- the source transcript is strong enough to trust,
- target-language copy exists for every planned deliverable,
- glossary terms are preserved,
- the script package can be reviewed before audio generation.

## Common Pitfalls

- Generating audio from an unreviewed transcript.
- Letting product names drift across languages.
- Treating translation text as final timing without acknowledging length drift.
