# Ink Theater

A deterministic, seek-safe engine for hand-drawn **"moving art"** — a minimalist black-ink-on-white world where a deadpan mascot physically *performs* an abstract idea by operating absurd low-tech contraptions. Built for OpenMontage's **atelier** path and rendered through **HyperFrames** (HTML/SVG/CSS + one paused GSAP timeline → MP4).

Inspired by Ian's `小黑 / Xiaohei` illustration skill (MIT — credit Ian for the technique); this is an original, generic, English, motion-first engine, not a copy.

## Why it exists

The illustration style is simple enough that **the illustration IS the animation** — no diffusion model needed. Vector shapes + math give you the whole thing: free, deterministic, infinitely editable, and the character genuinely acts out the concept. This engine turns the research findings (`memory: project_ink_atelier_animation`, deep-research on vector/physics/metaphor foundations) into reusable primitives.

## The five capabilities (`ink-theater.js`, global `InkTheater`)

| Module | What it does | Key API |
|---|---|---|
| **ink strokes** | Confident hand-drawn lines — variable-width brush ribbons + wobbled centerlines | `inkPath(pts, opt)`, `inkRibbon(pts, {width,taper,seed})` |
| **boil** | Seek-safe hand-drawn line "boil" — steps a `feTurbulence` seed off the timeline (~9fps), NOT SMIL | `boil(turbEl, tl, {duration,fps})` |
| **spring physics** | Closed-form damped-spring eases (anticipation/overshoot/settle) — pure functions of progress, seek-safe | `springEase({stiffness,damping,mass})`, `ease.{settle,overshoot,bouncy,soft}` |
| **rig / IK** | 2D FABRIK inverse kinematics + a riggable mascot whose arms reach a target | `fabrik(lengths,origin,target)`, `mascot({x,y,scale})` → `.reachL/.reachR([x,y])` |
| **contraption grammar** | Parametric composable machine parts | `parts.{crank,gauge,hopper,slot,lever,box}` |

## Determinism (HyperFrames render contract)

Every frame must be reproducible from time alone. This engine obeys that:

- **Closed-form springs** — `springEase` evaluates an analytic damped-oscillator step response, so any progress `p` maps deterministically (no numeric integration, no accumulated state).
- **Seek-safe boil** — driven by a GSAP stepped-seed tween on the timeline, never SMIL / render-time clocks.
- **IK-follow via `onUpdate`** — pose the arm from a target whose position is set by the timeline; GSAP fires `onUpdate` on seek, so it's pure-function-of-time.
- Seeded PRNG (`rng`) for all "random-looking" wobble — no runtime `Math.random`.
- No `repeat:-1` (finite counts only), animate only transforms/opacity/attrs.

## ⚠ The font gotcha (learned the hard way)

**HyperFrames' rasterizer applies `@font-face` webfonts to HTML elements but NOT to SVG `<text>`.** SVG text silently falls back to a system serif — even static, even with the font "loaded". 

**Always render custom-font captions as HTML overlay `<div>`s** positioned over the SVG scene, never as SVG `<text>`. See `projects/ink-theater-momentum/index.html` for the working pattern:

```html
<div class="stage">
  <svg class="scene">…ink art…</svg>            <!-- shapes only -->
  <div id="cap1" class="cap">handwritten line</div>  <!-- HTML text = webfont works -->
</div>
```

Bundle the font locally (`@font-face url("assets/x.woff2")`) — a Google Fonts hot-link is a render-time network fetch and violates determinism. Prefer a **static** woff2 (e.g. Patrick Hand) — but note even static SVG `<text>` fails; it's the SVG-vs-HTML boundary that matters, not variable-vs-static.

## Usage in a HyperFrames project

1. Copy `ink-theater.js` into the project root; `<script src="ink-theater.js">` after gsap.
2. Build the scene programmatically into a mount `<g>`, keep node refs.
3. Apply `filter="url(#boil)"` to ink groups; call `InkTheater.boil(...)` once.
4. Captions = HTML overlay divs (see gotcha).
5. Register one `gsap.timeline({paused:true})` on `window.__timelines["<id>"]`.

## Ink Puppet — real mocap on a hand-drawn figure (recommended for characters)

The right way to animate a doodle *character* (walk / dance / wave / jump) is **not** hand-tuned math — it is **real motion-capture retargeted onto a stick figure**. An agent should only choose the character and choreograph named moves; it must never hand-tune motion. Two pieces:

- **`mocap/bvh2clip.mjs`** — offline converter: a 3D BVH mocap file → a compact 2D "clip" (per-frame joint tracks, hips-relative pose + root motion, scaled to a fixed figure height). Run once per motion; bundle clips with `clips.js`.
- **`ink-puppet.js`** — runtime: builds the stick figure, plays clips, exposes a **declarative choreography API**:

```js
var p = InkPuppet.create(mount, { cx: 960, ground: 902, boil: "boil" });
p.drawIn(tl, { start: 0.4 });                         // pencil sketches the figure limb-by-limb
InkPuppet.choreograph(tl, p, [                          // then plays named mocap clips — zero hand-tuning
  { clip: "wave_hello" }, { clip: "dab" }, { clip: "jumping" }, { clip: "zombie" }
], { start: 3.7 });
```

Deterministic + seek-safe (pose is a pure function of each segment's local time). **Add a motion** by dropping any BVH through the converter — free CMU mocap has thousands (walk/run/dance/…). This is what Meta's *Animated Drawings* does, but here it stays **vector, white-ink, with a draw-on reveal** (Animated Drawings is raster, humanoid-only, and has no reveal — see the eval notes). Provenance of the bundled example clips: `mocap/NOTE.md`.

## Demos

- `examples/mocap-figure/` — the pencil figure draws itself, then waves / dabs / jumps / walks via **real mocap**.
- `examples/reel.html` — capabilities reel (each primitive, labeled).
- `examples/momentum.html` — "Momentum" story (springs + rig + ink + handwriting).
