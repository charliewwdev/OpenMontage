# Episode Breakdown Director — Short Drama

## Process

1. Build `episodes[]` with stable ids (`ep01`, …) and `scenes[]` (`ep01_sc01`, …).
2. Each scene: purpose, emotional_beat, characters, location_id placeholder.
3. Set `active_episode_id` to the first episode unless user chose otherwise.
4. Keep scene count realistic for budget (prefer 4–8 scenes for a 60–90s vertical ep).

## Output

Schema-valid `episode_breakdown`.
