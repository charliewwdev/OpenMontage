# Ink Theater — hand-drawn "moving art" (creative skill)

> Style id: `ink-sketch` · Engine: `ink-theater/ink-theater.js` · Runtime: HyperFrames (atelier)
> Technique credit: inspired by Ian's `小黑/Xiaohei` MIT skill. Generic, English, motion-first.

**What it is:** a minimalist **black-ink-on-white** world where a deadpan mascot *physically performs* an abstract idea by operating an absurd **low-tech contraption**. Not a fixed catalog of scenes — a generic method + a parametric engine. Runs on the `animation` pipeline in atelier mode; it is NOT its own pipeline.

## The generic method (concept → moving scene)

The "unlock" from research + the Xiaohei composition rules is a 3-step metaphor generator — do this in the agent, not in code:

1. **Abstract concept → one physical ACTION** — stuck, leaking, compounding, sorting, fermenting, pushing, sinking, unraveling.
2. **System → one low-tech OBJECT** — press, funnel, well, jar, conveyor, ladder, bridge, cabinet, boulder, gate, scale.
3. **Mascot PERFORMS the action on the object** — it cranks / pushes / pumps / stamps / fishes-out. *If you can delete the mascot and the metaphor survives, it's decoration — redo it.*

Then stage as beats on one continuous white page with a camera (pan / push).

## Mined archetypes (pick one, invent fresh specifics)

| Archetype | Mascot action | Motion recipe |
|---|---|---|
| **Contraption** | operates a machine (crank/lever/pump) | feed in → crank → machine works (steam/gauge) → output pops |
| **Before/after load-shift** | crushed by chaos → relaxed, one key act | left chaos → orange sweep → right structure assembles |
| **Journey / pitfalls** | walks a path; falls in pits or hits nodes | path draws on → walk → pit swallows / node pops → blue return loop |
| **One → many fan** | splits/cuts one source | source splits → arrows draw to N branches → each branch acts |
| **Push / momentum** | shoves a boulder up, it rolls away | slow strained up (power1) → crest → fast roll (power2.in) |
| **Well / extract** | lowers a bucket into noise, scoops the gem | bucket descends → scoop → pull up the one good bit |

## Color grammar (strict)

- **black** = structure & mascot · **orange** = flow / arrows ONLY · **red** = the problem / warning · **blue** = the good end-state.
- Pure white paper, ≥35% negative space, subject ~40–60%. Deadpan mascot (white-dot eyes), never cute.

## Engine cheat-sheet (`InkTheater`)

- Lines: `inkPath(pts)`, `inkRibbon(pts,{width,taper})` (brush). Boil: `boil(turbEl, tl, {duration})`.
- Motion: `ease.{settle,overshoot,bouncy,soft}` (seek-safe springs) — use overshoot for pops, settle for arrivals, bounce for landings.
- Character: `mascot({x,y,scale})` → `.reachL/.reachR([x,y])` (FABRIK). Follow a moving target via GSAP `onUpdate`.
- Machines: `parts.{crank,gauge,hopper,slot,lever,box}` — compose them.
- Full API + determinism rules: `ink-theater/README.md`.

## ⚠ Non-negotiables

- **Handwriting font: embed the FULL font, not a Google-Fonts subset woff2** (a `css2`-API subset is missing basic-latin → silent serif fallback everywhere). Use the bundled `ink-theater/assets/patrickhand.ttf` (`@font-face … format("truetype")`) on **HTML overlay `<div>`s** for captions/speech-balloons. No Google hot-link (breaks determinism). See `ink-theater/README.md` → "font gotcha".
- Determinism: closed-form springs, seed-stepped boil off the timeline, no `repeat:-1`, seeded PRNG only.
- One paused `gsap.timeline` on `window.__timelines`. Validate with `lint` + `snapshot` (read the contact-sheet) before render.

## Reference builds

- `projects/ink-theater-reel/` — capabilities reel. · `projects/ink-theater-momentum/` — "Momentum" story (handwriting via HTML divs).
