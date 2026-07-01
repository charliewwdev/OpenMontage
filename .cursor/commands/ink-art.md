# /ink-art — hand-drawn ink doodle animation

A character that draws itself then walks/dances/waves, or a deadpan contraption explainer. Vector, deterministic, rendered via HyperFrames to MP4.

Read `skills/creative/ink-theater.md` and `ink-theater/README.md`, then build what the user asks:

- **Ink Theater** engine (`ink-theater/ink-theater.js`): variable-width ink strokes, seek-safe boil, closed-form spring eases, FABRIK IK, contraption grammar.
- For a **character that walks / dances / waves / jumps**, use the **Ink Puppet** mocap system: `InkPuppet.create` → `p.drawIn` (self-drawing reveal) → `InkPuppet.choreograph([{clip:'wave_hello'},{clip:'dab'},…])`. **Never hand-tune motion**; add moves via `ink-theater/mocap/bvh2clip.mjs`.
- Captions = **HTML overlay `<div>`s** (HyperFrames doesn't apply webfonts to SVG `<text>`).
- Validate (`npx hyperframes lint` + `snapshot`) before rendering.
