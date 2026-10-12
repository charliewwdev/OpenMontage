# Character Bible Director — Short Drama

## Process

1. Create bible entries for every speaking role + key locations.
2. Generate or assign reference images via `image_selector`; persist with `character_bible_store`.
3. Bind TTS voice ids when available; record provider subject ids when using Soul/reference video.
4. Set `store_path` to project `bible/`.

## Hard rule

No character-bearing shot may proceed in assets without a bible entry + at least one reference image path (or explicit user waiver).

## Output

Schema-valid `character_bible`.
