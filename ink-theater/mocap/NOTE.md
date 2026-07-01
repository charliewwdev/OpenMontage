# Mocap provenance & licensing

The bundled example BVH clips (`wave_hello`, `jumping`, `dab`, `zombie`) were taken
from Meta's **AnimatedDrawings** example set (`examples/bvh/fair1/`,
github.com/facebookresearch/AnimatedDrawings — code MIT; the repo is archived).
`clips.js` / `clips/*.json` are 2D derivations produced by `bvh2clip.mjs`.

**Before any public or commercial use, verify licensing of the source mocap.**
For unrestricted production use, prefer the **CMU Graphics Lab Motion Capture
Database** (free for any purpose) — thousands of clips incl. walk, run, dance,
wave, jump. Convert any of them with:

```
node bvh2clip.mjs <in.bvh> clips/<name>.json --fps 30
```

Then rebundle `clips.js`. Different skeletons may need the `MAP` (BVH-joint →
rig-joint) in `bvh2clip.mjs` adjusted, and `--axis xy|zy` to pick the projection
plane (frontal vs sagittal).
