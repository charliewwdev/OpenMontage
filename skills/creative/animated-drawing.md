# Animated Drawing — animate a supplied drawing/photo with real mocap

> Command: `/animated-drawing` · **Path A (raster).** Sibling: `/ink-art` (vector, from scratch).
> Tool: Meta open-source **AnimatedDrawings** (github.com/facebookresearch/AnimatedDrawings — code MIT, repo archived 2025).

**When to use:** the user *has* a drawing or photo of a **humanoid** character and wants **that image** to move (dance / walk / jump / wave). Output = a raster **GIF (transparent) or MP4** of the original drawing *warped* to the motion. To **create** a vector doodle from scratch that draws itself and moves → use **`/ink-art`** instead.

**What it does:** auto-rigs the drawing (predicts a 16-joint skeleton), then retargets a BVH mocap clip onto it via As-Rigid-As-Possible mesh warp of the flat texture. It only *moves an already-complete drawing* — there is **no draw-on / self-sketching reveal** (that's `/ink-art`).

## Two run modes

**A · Bundled character + preset motion — turnkey, no Docker (verified on Windows):**
```bash
git clone --depth 1 https://github.com/facebookresearch/AnimatedDrawings.git && cd AnimatedDrawings
# the repo pins Python 3.8 + old wheels; get 3.8 via uv:
uv python install 3.8 && uv venv --python 3.8 .venv
uv pip install --python .venv -e .
uv pip install --python .venv "setuptools<81"      # repo imports pkg_resources but doesn't declare it
.venv/Scripts/python -c "from animated_drawings import render; render.start('./examples/config/mvc/export_gif_example.yaml')"
```
~10–12 s/clip on CPU, no GPU/Docker/model download.

**B · Auto-rig a NEW drawing — heavy (Docker + ~670 MB models, ~16 GB RAM):**
```bash
python image_to_animation.py drawing.png out_dir    # detect → segment → rig → retarget → render
```
Needs the repo's TorchServe container (`docker/`) which downloads `drawn_humanoid_detector.mar` (311 MB) + `drawn_humanoid_pose_estimator.mar` (357 MB). Windows: run the rig stack only via that container (OpenMMLab is Linux-only in practice).

## Input requirements (auto-rig)
One clearly-drawn **humanoid**, roughly T/A-pose (limbs separated, not overlapping), on a **plain light background** (segmentation is threshold + floodfill), exactly one figure.

## Config the agent generates (all YAML)
`char_cfg.yaml` (+ `texture.png`, `mask.png`; auto-produced by `image_to_annotations.py`) · a **motion** config (bvh + frames + groundplane) · a **retarget** config (BVH-joint → rig-joint; reuse bundled `fair1_ppf` / `cmu1_pfp` unless the skeleton differs) · an **MVC** config (`controller.MODE: video_render`, `OUTPUT_VIDEO_PATH`, optional `WINDOW_DIMENSIONS` / `CLEAR_COLOR` / `BACKGROUND_IMAGE` / `CAMERA_POS`).

## Preset motions
`dab`, `jesse_dance`, `jumping`, `jumping_jacks`, `wave_hello`, `zombie` — plus any Mixamo-skeleton BVH.

## Output & honest limits
GIF (transparent) / MP4 (H.264, `avc1`), resolution from `WINDOW_DIMENSIONS` (examples 500×500). **Raster only** (warps the drawing's pixels — zoom shows stretched texture), **humanoid-only**, **no draw-on reveal**, **crude background**. A delightful "your doodle comes to life" novelty; behind a Docker service for the auto-rig path. Not a general vector engine — for white-ink vector doodles that draw themselves, use `/ink-art`.

Sample renders from the session eval: `.tmp/animated-drawings/out/` (`char3_dab.gif`, `char1_zombie.mp4`).
