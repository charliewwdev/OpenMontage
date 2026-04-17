# Animation Runtime Selector

Meta-skill that answers: *"for the animated scene I'm about to build, which runtime + Layer 3 skills should I reach for?"*

Read this before authoring any animated Remotion component or HyperFrames composition. It routes you to the right Layer 3 skill so you don't waste time hand-rolling what a plugin already solves.

## When to use this skill

Apply when:
- A stage director (asset, edit, compose) needs to author an animated component
- An agent is about to write Remotion JSX for a scene that involves text reveals, SVG motion, curved camera paths, shape morphs, or multi-stage choreography
- An agent is asked to build a HyperFrames composition
- An agent is uncertain whether to reach for a GSAP plugin vs inline `interpolate()`/`spring()`

## Decision matrix

| Animation need | Recommended runtime | Read first |
|---|---|---|
| Simple fade / slide / scale / spring | Remotion primitives (no plugin) | `.agents/skills/remotion` |
| Two-state spring with physics | Remotion `spring()` | `.agents/skills/remotion` |
| Multi-step sequence with offsets | Remotion `Sequence` + `interpolate()` **or** GSAP timeline | `.agents/skills/remotion` + optionally `.agents/skills/gsap-timeline` |
| Per-word text reveal synced to narration | Remotion `interpolate` driven by word-level transcript (existing `CaptionOverlay` pattern) | `.agents/skills/remotion` |
| Per-character kinetic typography (SplitText style) | GSAP SplitText inside Remotion | `.agents/skills/gsap-plugins` (SplitText), `.agents/skills/gsap-react` |
| SVG shape morph between two paths | GSAP MorphSVG inside Remotion | `.agents/skills/gsap-plugins` (MorphSVG) |
| Curved camera / object motion along a custom path | GSAP MotionPath inside Remotion | `.agents/skills/gsap-plugins` (MotionPath) |
| SVG line drawing / stroke reveal | GSAP DrawSVG | `.agents/skills/gsap-plugins` (DrawSVG) |
| Bespoke bezier / elastic / stutter easing | GSAP CustomEase / EasePack / CustomWiggle | `.agents/skills/gsap-plugins` |
| Layout-to-layout transition (FLIP) | GSAP Flip inside Remotion | `.agents/skills/gsap-plugins` (Flip) |
| Disney's 12 animation principles for UI motion | framer-motion + Lottie | `.agents/skills/framer-motion`, `.agents/skills/lottie-bodymovin` |
| Lottie export from After Effects / Figma | Lottie | `.agents/skills/lottie-bodymovin` |
| Synthetic terminal / CLI demo | Remotion TerminalScene | `.agents/skills/synthetic-screen-recording` |
| Mathematical / scientific visualization | Manim | `.agents/skills/manim-composer`, `.agents/skills/manimce-best-practices` |
| D3 data-driven visualization | D3 | `.agents/skills/d3-viz` |
| Data chart (bar/line/pie/KPI) | Remotion built-in chart components | `remotion-composer/SCENE_TYPES.md` |
| HyperFrames composition (any motion) | HyperFrames + GSAP (mandatory) | `.agents/skills/gsap-core`, `.agents/skills/gsap-timeline` |

## The "keep it simple" bias

Before reaching for GSAP, ask: **does Remotion's primitive API solve this in ≤ 20 lines?**

- Fade/slide/scale/rotate → `interpolate(frame, [inFrame, outFrame], [from, to])`
- Natural "bouncy" motion → `spring({ frame, fps, config: { damping, stiffness } })`
- Word-level caption highlight → iterate transcript, filter by `frame / fps`

If yes, use Remotion primitives. If no, that's your signal to escalate to a GSAP plugin.

GSAP is a powerful escape hatch, not the default. Every plugin adds bundle weight, registration boilerplate, and another skill to read.

## Running GSAP deterministically inside Remotion

Standard GSAP runs on `requestAnimationFrame` — not deterministic, not Remotion-compatible out of the box. Three patterns that ARE Remotion-safe:

```jsx
// Pattern 1: paused timeline, seek by progress
const tl = useRef(gsap.timeline({ paused: true })).current;
useEffect(() => {
  tl.to('.x', { x: 500 }).to('.y', { opacity: 0 });
}, []);
tl.progress(frame / durationInFrames);

// Pattern 2: paused timeline, seek by time
tl.seek(frame / fps);

// Pattern 3: GSAP as value calculator only
const easeFn = gsap.parseEase('power2.out');
const t = frame / durationInFrames;
const easedValue = easeFn(t);
```

For the full breakdown, read `.agents/skills/gsap-react/SKILL.md`.

## Check against the pipeline's stage director

Every pipeline's asset-director has animation-specific guidance. If you're in:
- **animated-explainer** → read `skills/pipelines/explainer/asset-director.md` — it references the text/SVG options for kinetic typography
- **animation** → read `skills/pipelines/animation/asset-director.md` — it references MorphSVG and MotionPath for logo/motion-graphics work
- **cinematic** → read `skills/pipelines/cinematic/asset-director.md` — it references MotionPath for cinematic camera moves

The asset-director tells you *what* to build in the context of this pipeline. This selector tells you *how*.

## Never do

- ❌ Pull GSAP into a scene that needs only fade/slide — use Remotion primitives.
- ❌ Use GSAP with `requestAnimationFrame` inside Remotion — render will be non-deterministic.
- ❌ Skip reading the matching Layer 3 skill when a plugin is indicated — per-plugin prompting guidance matters.
- ❌ Register GSAP plugins inside a component body — register once at module scope or app entry.
