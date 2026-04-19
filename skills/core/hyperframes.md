# HyperFrames Skill (Layer 2)

This is the **OpenMontage-specific** guide to HyperFrames. It explains when
OpenMontage pipelines should choose HyperFrames over Remotion, how OpenMontage
artifacts map to HyperFrames project files, and how the compose stage drives
the HyperFrames CLI.

For raw HyperFrames knowledge (authoring contract, `data-*` attributes, GSAP
timeline rules, CLI flags, registry blocks, website-to-video), read the Layer 3
skills:

- `.agents/skills/hyperframes/` — composition authoring contract + GSAP rules
- `.agents/skills/hyperframes-cli/` — init, lint, validate, preview, render
- `.agents/skills/hyperframes-registry/` — `hyperframes add` + block wiring
- `.agents/skills/website-to-hyperframes/` — capture-to-video workflow

This file teaches the bridge between the two.

---

## When OpenMontage should pick HyperFrames (vs Remotion vs FFmpeg)

OpenMontage separates two concepts:

- **`renderer_family`** — the creative grammar (`explainer-data`,
  `cinematic-trailer`, `product-reveal`, etc.). Chosen at proposal.
- **`render_runtime`** — the technical engine that realizes that grammar
  (`remotion`, `hyperframes`, `ffmpeg`). Also chosen at proposal.

Both are locked in `proposal_packet.schema.json` and carried through
`edit_decisions` unchanged unless a `render_runtime_selection` decision is
logged in `decision_log`. Silent runtime swaps are a contract violation.

### Decision matrix

| Scenario | Prefer | Why |
|----------|--------|-----|
| Existing explainer, React scene component stack (text_card, stat_card, chart scenes, caption overlay, TalkingHead, CinematicRenderer) | **Remotion** | These compositions already exist in `remotion-composer/`. Reusing them is free; replicating them in HTML is not. |
| Word-level caption burn / karaoke captions | **Remotion** | `remotion_caption_burn` is Remotion-specific and is NOT at parity on HyperFrames day 1. |
| Avatar / lip-sync presenter | **Remotion** | `TalkingHead` composition lives in Remotion. No HyperFrames equivalent yet. |
| Kinetic typography, heavy text motion, GSAP-native animation | **HyperFrames** | HTML/GSAP is the natural medium. Expressing this as Remotion `interpolate()` calls is slow and fragile. |
| Product promo / launch reel / marketing title card | **HyperFrames** | CSS/GSAP composition grammar matches how designers already think about these. Templates (`kinetic-type`, `product-promo`, `swiss-grid`) give a strong starting point. |
| Website-to-video / UI-driven composition | **HyperFrames** | The `website-to-hyperframes` workflow exists for exactly this. |
| Registry block needed (data chart, grain overlay, shimmer sweep, shader transition) | **HyperFrames** | The registry is HyperFrames-only. Remotion does not have `hyperframes add`. |
| Synthetic UI / fake terminal / fake browser demo | Either — depends on existing coverage | OpenMontage already ships Remotion `TerminalScene` (see `synthetic-screen-recording` Layer 3). For UI chrome beyond terminal, HyperFrames HTML is easier. |
| Pure concat / trim of source clips, no composition | **FFmpeg** | Neither Remotion nor HyperFrames add value here. |
| Remotion is not installed on this machine | **HyperFrames** (if available) or **FFmpeg** | Do not silently fall back. Tell the user before downgrading. |

### Hard rule: present both runtimes when both are available

The decision matrix above is input for the conversation with the user, NOT
a license to silently pick a "default." When both Remotion and HyperFrames
are available on the machine, the proposal stage MUST:

1. Present both to the user with brief-specific pros/cons.
2. Recommend one with rationale tied to `delivery_promise` and
   `visual_approach`.
3. Wait for approval.
4. Log both in `options_considered` of a `render_runtime_selection`
   decision.

See `AGENT_GUIDE.md` → "Present Both Composition Runtimes (HARD RULE)" for
the full contract and `skills/meta/reviewer.md` for the CRITICAL-finding
enforcement.

### Hard rule: motion-required deliverables

If the brief's `delivery_promise.motion_required` is `true` (sci-fi trailer,
cinematic teaser, hype edit, any brief whose promise depends on real motion),
then the runtime chosen at proposal is a **commitment**, not a hint. Compose
MUST NOT downgrade to FFmpeg Ken Burns. If the chosen runtime fails (Remotion
not installed, `npx hyperframes doctor` reports a blocker), surface the blocker
per `AGENT_GUIDE.md` > "Escalate Blockers Explicitly" and wait for user
approval before switching runtime.

---

## What stays Remotion-only (Phase 1)

Do **not** attempt to port these to HyperFrames on day 1. They require
dedicated parity work:

- `remotion_caption_burn` (word-by-word burned captions)
- `TalkingHead` composition (avatar/lip-sync presenter)
- Existing documentary-montage end-tag overlay stack (relies on specific
  Remotion components)
- Anything that assumes assets are staged under `remotion-composer/public/`
  and consumed by existing React scene components

For these, keep `render_runtime = "remotion"` and proceed as today.

---

## Project workspace layout

HyperFrames needs its own project workspace. Do **not** reuse
`remotion-composer/public/` — that's Remotion's shared staging directory and
mixing runtimes there causes cross-project collisions.

```
projects/<project-name>/
├── artifacts/
├── assets/
│   ├── images/
│   ├── video/
│   ├── audio/
│   └── music/
├── hyperframes/                ← HyperFrames runtime workspace (when selected)
│   ├── index.html              ← root composition
│   ├── compositions/           ← sub-compositions and registry blocks
│   │   └── components/         ← registry components (grain overlays, etc.)
│   ├── assets/                 ← symlink or copy of project assets
│   ├── hyperframes.json        ← CLI config (registry URL, install paths)
│   ├── DESIGN.md               ← playbook-derived visual brief (optional)
│   └── narration.wav           ← TTS output, when applicable
└── renders/
    └── final.mp4
```

The workspace is generated at compose time by `hyperframes_compose` from
`edit_decisions` + `asset_manifest` + the active playbook. It's regenerable
and gitignored along with the rest of `projects/`.

### Why a dedicated workspace per project

- HyperFrames resolves `data-composition-src`, `src=`, and registry blocks
  relative to the project root. A shared workspace breaks this.
- `npx hyperframes lint | validate | render` all operate on a project
  directory. They don't take an abstract composition ID the way Remotion does.
- Assets live next to the HTML that references them, matching the
  `website-to-hyperframes` reference workflow.

---

## Artifact → HyperFrames mapping

When `render_runtime = "hyperframes"`, the compose stage translates
OpenMontage artifacts into HyperFrames project files:

| OpenMontage artifact field | HyperFrames target |
|---|---|
| `edit_decisions.cuts[]` (sequence of scenes) | `index.html` timeline, one `<div data-composition-id data-composition-src>` per cut |
| `edit_decisions.cuts[i].in_seconds / out_seconds` | `data-start` / `data-duration` on the clip element |
| `edit_decisions.cuts[i].type` (scene kind) | Registry block installed via `hyperframes add`, OR a hand-authored sub-composition template |
| `asset_manifest.assets[]` paths | Copied or symlinked into `projects/<p>/hyperframes/assets/` and referenced with relative `src=` |
| `audio.narration.segments[]` | `<audio>` element with matching `data-start` / `data-duration` |
| `audio.music` | Second `<audio>` element, lower `data-volume` |
| `subtitles` (enabled + source) | Either a registry `captions` block or hand-authored per-word spans — NOT `remotion_caption_burn` |
| Selected playbook (`flat-motion-graphics`, `clean-professional`, etc.) | `:root` CSS custom properties + `DESIGN.md`. See `lib/hyperframes_style_bridge.py`. |
| `renderer_family` | Controls which top-level HTML template is used and which registry blocks are pre-installed |

The concrete rendering is: `hyperframes_compose` writes files into the
workspace, runs `lint → validate → render`, and returns a `render_report`
with the path to the generated MP4. See `tools/video/hyperframes_compose.py`.

### Workspace-local authoring artifacts

Upstream's `website-to-hyperframes` skill uses `DESIGN.md`, `SCRIPT.md`, and
`STORYBOARD.md` as step-by-step workspace files. OpenMontage does **not**
replace its canonical artifact contracts with these — `brief`, `script`,
`scene_plan`, `edit_decisions`, etc. remain the source of truth under
`projects/<p>/artifacts/`. Treat the upstream files as **convenience copies**
written into the HyperFrames workspace so the runtime workflow feels natural:

- `DESIGN.md` — derived from the selected playbook, written by
  `hyperframes_compose` or `lib/hyperframes_style_bridge.py`. Safe to use as
  a working brief in the workspace.
- `SCRIPT.md` — optional narration copy for human review. Canonical script
  stays in `artifacts/script.json`.
- `STORYBOARD.md` — optional per-beat creative direction. Canonical scene
  plan stays in `artifacts/scene_plan.json`.

If a workspace-local file and a canonical artifact disagree, the canonical
artifact wins.

---

## Runtime selection rules

1. **Proposal stage** chooses `render_runtime` and logs the decision in
   `decision_log` with category `render_runtime_selection`. It must consider
   the decision matrix above and the actual availability of each runtime.
2. **Preflight** reports which runtimes are available (see below). A
   runtime that is not available is not a valid proposal choice unless the
   user explicitly approves installing it.
3. **Edit stage** carries `render_runtime` forward unchanged.
4. **Compose stage** reads `edit_decisions.render_runtime` and routes via
   `video_compose` → `hyperframes_compose` (for HyperFrames) or the existing
   Remotion path (for Remotion). Compose may not swap runtime without a new
   `render_runtime_selection` decision.
5. **Final review** records `render_runtime_used` and sets
   `runtime_swap_detected = true` if it differs from proposal.

---

## Preflight — HyperFrames availability

At preflight, the provider menu reports HyperFrames availability. The
`hyperframes_compose` tool's `get_info()` returns:

```json
{
  "runtime_available": true | false,
  "node_major": 22,
  "ffmpeg_available": true,
  "doctor_ok": true,
  "install_instructions": "…"
}
```

Floor requirements (all must hold for `runtime_available: true`):

- Node.js major version ≥ 22
- `ffmpeg` binary on PATH
- `npx` on PATH (bundled with Node.js)
- `npx hyperframes doctor` exits 0, OR a lightweight equivalent check passes

`bun` is NOT required — HyperFrames is consumable via `npx hyperframes` (published npm package name is `hyperframes`; the monorepo-internal `@hyperframes/cli` name is NOT on the public npm registry and returns 404).

When `runtime_available: false`, preflight must surface the reason and the
install instructions. Per `AGENT_GUIDE.md` Setup Offer Protocol, group the
fix by effort:

- Missing Node 22 → 5-minute install, explain what it unlocks
- Missing FFmpeg → 1-minute install on macOS/Linux, longer on Windows
- `doctor` reports issues → show the doctor output verbatim

---

## Validation protocol

HyperFrames ships a real validation stack. Run **all** of these before
declaring a render complete:

1. **`npx hyperframes lint`** — static contract checks (duplicate ids,
   overlapping tracks, missing `data-composition-id`, unregistered timelines).
   MUST pass before render.
2. **`npx hyperframes validate`** — browser-based runtime checks: seeks into
   the paused composition, screenshots, samples pixels, computes WCAG
   contrast ratios, verifies `window.__timelines` registration and
   `class="clip"` on timed elements. MUST pass before render (contrast can
   be deferred with `--no-contrast` during iteration, but not for final).
3. **`npx hyperframes render --quality standard`** — produces the MP4.
4. **Post-render final review** — probe with ffprobe, sample frames,
   transcribe audio, compare to script. Same contract as the Remotion path.
   See `final_review.schema.json`.

If lint or validate fails, do **not** render. Fix the composition and re-run.
Silent render from a failing composition is a contract violation — the whole
point of HyperFrames is that validate catches issues that FFmpeg or Remotion
cannot.

---

## Style bridge (playbook → CSS)

OpenMontage playbooks currently translate into Remotion `themeConfig`
objects. For HyperFrames, the equivalent translation produces:

- A block of CSS custom properties on `:root` (`--color-bg`, `--color-fg`,
  `--color-accent`, `--font-heading`, `--font-body`, `--ease-primary`,
  `--duration-primary`, etc.).
- A short `DESIGN.md` that explains the visual system in plain language.
- Optional typography `@import` statements (only for fonts the HyperFrames
  font compiler supports).

See `lib/hyperframes_style_bridge.py`. Playbooks do NOT need to fork — the
existing playbook schema carries enough information to drive both Remotion
and HyperFrames output.

---

## Cost model

HyperFrames renders are local: $0 API cost, but CPU-intensive (headless
Chrome + FFmpeg). Track via `cost_tracker`:

- `estimate` — based on composition duration × resolution × `--workers`
- `reserve` — 0 (no API spend)
- `reconcile` — wall-clock render time

Same pattern as Remotion.

---

## Anti-patterns

- ❌ Forking playbook data for HyperFrames when the current schema already
  carries colors, typography, and motion.
- ❌ Writing HyperFrames compositions that reference `remotion-composer/public/`
  — the HyperFrames workspace is separate and self-contained.
- ❌ Running `hyperframes init` from the OpenMontage orchestrator. `init`
  creates its own project semantics and installs agent skills — it's meant
  for humans bootstrapping a project, not for the pipeline. `hyperframes_compose`
  generates the project files directly.
- ❌ Using HyperFrames as "React without Remotion." HyperFrames is
  HTML-first with GSAP. If your scene is authored as React JSX, it belongs
  in Remotion.
- ❌ Using `repeat: -1` in GSAP inside HyperFrames. Infinite tweens break the
  deterministic seek-and-capture render. Always bounded repeats.
- ❌ Animating from `async` context, `setTimeout`, or Promises during
  timeline construction. `window.__timelines` must be fully populated
  synchronously after page load.

---

## Pipelines adopting HyperFrames

| Pipeline | Status |
|----------|--------|
| `animation` | Wave 1 — HyperFrames is a first-class option for motion-graphics-heavy briefs |
| `animated-explainer` | Wave 1 — HyperFrames viable when the concept is HTML/GSAP-native; Remotion remains default for data-chart-heavy explainers |
| `screen-demo` | Wave 1 — HyperFrames viable for synthetic product UI; `TerminalScene` (Remotion) remains preferred for terminal-specific demos |
| `cinematic` | Wave 2 |
| `hybrid` | Wave 2 |
| `documentary-montage` | Wave 2 |
| `talking-head` | Deferred — depends on TalkingHead parity |
| `avatar-spokesperson` | Deferred — depends on TalkingHead parity |
| `clip-factory`, `podcast-repurpose`, `localization-dub` | Deferred — current compose paths rely on Remotion caption burn |
| `framework-smoke` | N/A (test pipeline) |

Proposal and compose directors for adopted pipelines describe runtime choice
explicitly — see each pipeline's `proposal-director.md` and
`compose-director.md`.
