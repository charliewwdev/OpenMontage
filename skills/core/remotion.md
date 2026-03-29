# Remotion Skill

## When to Use

Use Remotion for advanced video composition from Phase 3 onward — anywhere that requires
React-based scene assembly, parametric templates, animated overlays, transitions, or
data-driven batch rendering. For simple cuts, burns, and encodes, prefer FFmpeg directly.

## Relationship to Remotion Agent Skills

The **installed agent skills** (`.agents/skills/remotion-best-practices/`) teach correct
Remotion API usage — imports, timing, animation constraints, code patterns.
**This file** teaches how OpenMontage uses Remotion — which compositions map to pipeline
stages, how artifacts flow in, and how renders are triggered.

## When to Use Remotion vs FFmpeg

| Use Case | Backend | Why |
|----------|---------|-----|
| Simple cuts, trims, concat | FFmpeg | Instant, no Node dependency |
| Subtitle burn-in | FFmpeg | Proven, fast |
| Face enhance, color grade | FFmpeg | Filter-based, deterministic |
| Multi-layer overlays + transitions | Remotion | React composability |
| Animated diagrams/text cards | Remotion | Frame-by-frame control |
| Data-driven batch videos | Remotion | Zod props + parametric renders |
| Generated explainer pipeline | Remotion | Full scene graph needed |
| Talking-head (video-only cuts) | FFmpeg | No images/animations needed |

**Note:** The `render` operation auto-routes — if any cut contains images,
animations, transitions, or component types (text_card, stat_card, etc.),
it delegates to Remotion automatically. No need to manually select backend.

## Architecture

```
remotion-composer/
├── src/
│   ├── Root.tsx              # Composition registry
│   ├── compositions/         # One file per pipeline type
│   │   ├── Explainer.tsx     # Generated explainer composition
│   │   ├── AnimatedScene.tsx # Individual animated scene
│   │   └── TitleCard.tsx     # Standalone title card
│   ├── components/           # Reusable visual building blocks
│   │   ├── Caption.tsx       # Subtitle/caption renderer
│   │   ├── DiagramOverlay.tsx
│   │   ├── ProgressBar.tsx
│   │   └── TransitionWrapper.tsx
│   └── styles/               # Tailwind + playbook-derived styles
├── public/                   # Static assets (fonts, LUTs)
├── package.json
├── remotion.config.ts
└── tsconfig.json
```

## Pipeline Integration

### How Artifacts Map to Remotion Props

| OpenMontage Artifact | Remotion Prop | Maps To |
|---------------------|---------------|---------|
| `scene_plan.json` → `scenes[]` | `scenes` prop | `<TransitionSeries>` children |
| `scene.type` | Component selector | `talking_head` → `<Video>`, `diagram` → `<DiagramOverlay>`, etc. |
| `scene.start_seconds` / `end_seconds` | `from` / `durationInFrames` | `fps * seconds` conversion |
| `scene.transition_in` / `transition_out` | `<TransitionSeries.Transition>` | `fade`, `slide`, `wipe` |
| `asset_manifest.json` → assets | `assets` prop | `staticFile()` or absolute paths |
| `style_playbook` | `theme` prop | Colors, fonts, animation curves |
| `edit_decisions.json` → cuts | `cuts` prop | `<Series>` with trimmed `<Video>` segments |
| `media_profile` | Composition dimensions | `width`, `height`, `fps` from profile |

### Render Invocation

The orchestrator calls Remotion renders via CLI:

```bash
# Standard render
npx remotion render src/index.ts ExplainerVideo \
  --props='{"scenes": [...], "theme": "clean_professional"}' \
  --output=pipeline/<project>/output/final_output.mp4 \
  --codec=h264

# With specific media profile
npx remotion render src/index.ts ExplainerVideo \
  --width=1080 --height=1920 --fps=30 \
  --props=props.json \
  --output=output.mp4
```

In Python, invoke via `subprocess` from `video_compose.py` when `backend="remotion"`.

### Media Profile Mapping

| OpenMontage Profile | Remotion Config |
|--------------------|-----------------|
| `youtube_landscape` | `width: 1920, height: 1080, fps: 30` |
| `youtube_shorts` | `width: 1080, height: 1920, fps: 30` |
| `tiktok_vertical` | `width: 1080, height: 1920, fps: 30` |
| `instagram_reels` | `width: 1080, height: 1920, fps: 30` |
| `instagram_square` | `width: 1080, height: 1080, fps: 30` |
| `cinematic_wide` | `width: 2560, height: 1080, fps: 24` |

## Key Patterns

### Scene Plan to Composition

Each scene in `scene_plan.json` becomes a child of `<TransitionSeries>`:

```tsx
// Pseudocode — actual component in remotion-composer/src/compositions/Explainer.tsx
const Explainer: React.FC<ExplainerProps> = ({ scenes, theme, assets }) => {
  return (
    <TransitionSeries>
      {scenes.map((scene, i) => (
        <React.Fragment key={scene.id}>
          {scene.transition_in && (
            <TransitionSeries.Transition
              presentation={mapTransition(scene.transition_in)}
              timing={timing({ durationInFrames: 15 })}
            />
          )}
          <TransitionSeries.Sequence durationInFrames={secondsToFrames(scene)}>
            <SceneRenderer scene={scene} theme={theme} assets={assets} />
          </TransitionSeries.Sequence>
        </React.Fragment>
      ))}
    </TransitionSeries>
  );
};
```

### Dynamic Duration with calculateMetadata

When TTS audio determines video length (generated explainers), use `calculateMetadata`:

```tsx
export const ExplainerVideo = {
  component: Explainer,
  calculateMetadata: async ({ props }) => {
    const totalDuration = props.scenes.reduce(
      (sum, s) => sum + (s.end_seconds - s.start_seconds), 0
    );
    return {
      durationInFrames: Math.ceil(totalDuration * props.fps),
      fps: props.fps,
      width: props.width,
      height: props.height,
    };
  },
};
```

### Style Playbook to Theme

Style playbooks (`skills/styles/`) define visual parameters. Map them to Remotion themes:

```tsx
// Derived from the style playbook YAML
const cleanProfessional = {
  background: "#FFFFFF",
  text: "#1A1A1A",
  accent: "#2563EB",
  fontFamily: "Inter",
  headingWeight: 600,
  transitionType: "fade",
  transitionDuration: 15, // frames
  animationEasing: "easeInOutCubic",
};
```

### Audio Layering

Narration + background music + SFX as parallel `<Audio>` components:

```tsx
<AbsoluteFill>
  <Audio src={narrationUrl} />
  <Audio src={musicUrl} volume={0.06} />
  {sfxCues.map(cue => (
    <Sequence key={cue.id} from={secondsToFrames(cue.time)}>
      <Audio src={cue.url} volume={cue.volume} />
    </Sequence>
  ))}
  {/* Visual layers */}
</AbsoluteFill>
```

### Cost Tracking

Remotion renders are CPU-intensive but $0 API cost. Track via cost_tracker:
- `estimate`: based on composition duration × resolution tier
- `reserve`: 0 (no API spend)
- `reconcile`: wall-clock render time for benchmarking

## Critical Constraints

- **No CSS animations or transitions** — they don't render correctly. Use `useCurrentFrame()` + `interpolate()` for all motion.
- **No Tailwind animation classes** — `animate-*` classes break frame-based rendering. Static Tailwind utilities are fine.
- **Always clamp interpolate()** — use `extrapolateLeft: 'clamp', extrapolateRight: 'clamp'` to prevent values shooting past endpoints.
- **Node.js 18+ required** — listed as optional in minimum system, required in recommended.
- **Render in series, not parallel** — unless the machine has enough RAM. Each render spawns a Chromium instance.

## Quality Checklist

- [ ] Composition duration matches sum of scene durations minus transition overlaps
- [ ] All `staticFile()` references resolve to existing assets
- [ ] Transitions don't cut off content (account for overlap in timing)
- [ ] Audio layers are in sync with visual scenes
- [ ] Theme colors match the active style playbook
- [ ] Output resolution and FPS match the target media profile
- [ ] Render completes without Chromium timeout errors
- [ ] Final output plays correctly on target platform
