# HunyuanVideo 1.5 — Prompting Guide

> Source: [Tencent Prompt Handbook](https://github.com/Tencent-Hunyuan/HunyuanVideo-1.5/blob/main/assets/HunyuanVideo_1_5_Prompt_Handbook_EN.md)
> For universal vocabulary, see: `skills/creative/video-gen-prompting.md`

## HunyuanVideo Prompt Formula

### Text-to-Video
```
Subject + Motion + Scene + [Shot Type] + [Camera Movement] + [Lighting] + [Style] + [Atmosphere]
```

### Image-to-Video
```
Subject Motion Dynamics + Scene Motion Dynamics + [Camera Movement]
```

For I2V, focus on describing MOTION, not appearance (the image provides appearance).

## HunyuanVideo-Specific Strengths

### Lighting as Atmosphere
Tencent emphasizes: **"Light is the soul of atmosphere."**

Describe lighting with multiple dimensions:
- **Style**: soft, hard, neon, ambient
- **Direction**: side-lit, backlit, overhead, underlighting
- **Quality**: harsh spotlight, diffuse glow
- **Shadows**: long dramatic shadows, soft shadow edges
- **Color temperature**: golden hour warmth, cool daylight blue
- **Reflections**: wet surface reflections, metallic glints

### Camera Movement Library

| Movement | Type | HunyuanVideo Prompt |
|----------|------|-------------------|
| Crane / Pedestal | Vertical | "camera rises vertically" |
| Truck / Tracking | Horizontal | "camera tracks left alongside subject" |
| Dolly In | Push | "camera pushes forward toward subject" |
| Dolly Out | Pull | "camera pulls back from subject" |
| Pan | Rotation | "camera pans right across the scene" |
| Orbit | Circular | "camera orbits around subject" |
| Follow | Lock-on | "camera follows subject from behind" |
| Static | Fixed | "static camera, no movement" |

### Style Keywords

**Photorealistic / Cinematic**:
- Film noir, hard sci-fi, cinematic photography
- Period drama, war documentary, nature documentary

**Animation / Illustration**:
- 2D animation, Japanese anime
- Watercolor painting, Chinese ink wash
- Low-poly 3D, pixel art

## I2V Best Practice

When using image-to-video, the input image defines appearance. Your prompt should ONLY describe:
1. How the subject moves
2. How the environment changes
3. Camera motion

**Good I2V prompt**: "The woman's hair blows in the wind as she turns to face the camera. Leaves scatter across the path. Camera slowly dollies in."

**Bad I2V prompt**: "A beautiful woman in a red dress standing in a forest" — this repeats what the image already shows.

## Example (T2V)

```
A young woman in a flowing white dress walks barefoot along
a deserted beach at golden hour. She trails her hand through
the shallow surf, leaving ripples. Her hair catches the warm
side-light from the setting sun. Medium tracking shot, camera
follows alongside at knee height. Soft golden lighting with
long shadows stretching toward the camera. Cinematic
photography style, shallow depth of field. Peaceful,
contemplative atmosphere.
```

## Example (I2V)

```
The cat stretches lazily, then leaps from the windowsill
to the floor. Dust motes scatter in the shaft of light.
Camera remains static, slight rack focus from window to
landing spot.
```
