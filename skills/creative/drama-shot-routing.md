# Drama Shot Routing

## When to Use

During short-drama storyboard and assets stages, and when editing the `video-router` subgraph.

## Intent → Generation Bias

| shot_intent | Prefer | Notes |
|-------------|--------|-------|
| dialogue | Providers with native audio / lip_sync | Keep face stable; bible refs required |
| action | High-motion I2V (Seedance / Kling / Runway) | Shorter clips; stronger motion verbs |
| camera_move | Providers with camera_direction controls | Encode move in prompt + shot_language |
| effect | VFX-capable models; allow one rework | Isolate effect shots |
| establishing | Wider FOV, slower push | Location bible refs |
| reaction | Close-up, subtle motion | Identity lock critical |
| insert | Detail cutaway; still→gentle move OK | Often cheaper model |
| montage | Batch with shared grade language | Parallel ledger jobs |

## Hard Rules

1. Character-bearing shots: attach bible reference images before I2V.
2. Prefer keyframe → I2V over pure T2V for identity.
3. On failure: follow `fallback-escalate` subgraph (do not invent ad-hoc provider swaps silently).
4. Announce provider + model before paid calls.
