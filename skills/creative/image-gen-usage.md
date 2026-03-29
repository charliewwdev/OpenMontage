# Image Generation Usage for OpenMontage

> Sources: OpenAI DALL-E 3 documentation, FLUX/BFL API documentation, existing Layer 3 skills
> at `.agents/skills/flux-best-practices/` and `.agents/skills/bfl-api/`

## Quick Reference Card

```
FLUX RESOLUTION:  1920x1088 (16:9) | 1088x1920 (9:16) — must be multiples of 16
MAX TOTAL:        4 megapixels (width x height)
CONSISTENCY:      Use hero image as input_image for subsequent frames
STYLE PREFIX:     Set in playbook, prepend to every prompt
BATCH STRATEGY:   Hero at max quality → iterate with klein → final pass with pro
```

## Resolution for Video Frames

All FLUX dimensions **must be multiples of 16**. Maximum total is 4MP.

| Target | FLUX Resolution | Cost (FLUX.2 pro) |
|--------|----------------|-------------------|
| YouTube 16:9 | `1920x1088` | $0.03/image |
| YouTube 4K | `3840x2160` | Requires pro/max |
| TikTok/Reels 9:16 | `1088x1920` | $0.03/image |
| Square 1:1 | `1024x1024` | $0.03/image |
| Thumbnail | `1280x720` | $0.03/image |

## Maintaining Visual Consistency

The biggest challenge: making 8-12 generated images look like they belong in the same video.

### Strategy 1 — Style Prefix (Always Use)

Prepend the playbook's `image_prompt_prefix` to every prompt. Example from `clean-professional`:

```
"Clean, minimal illustration with soft shadows, muted color palette,
white background, professional vector art style. [YOUR SCENE DESCRIPTION]"
```

### Strategy 2 — Hero Reference Image (Recommended)

1. Generate one "hero" image at maximum quality (`FLUX.2 [max]`, $0.07)
2. Use it as `input_image` for all subsequent frames:

```
Frame 1: T2I with detailed prompt → hero.png
Frame 2: I2I with hero.png + "Same style, camera pans right to show..."
Frame 3: I2I with hero.png + "Same style, zoomed in on..."
```

FLUX.2 supports up to 4 references (klein) or 8 references (pro/max/flex). Reference by number: "The character from image 1 in the environment from image 2."

### Strategy 3 — Seed Locking

Use the same `seed` parameter across generations with similar prompts. Produces similar compositions but is fragile to prompt changes — use as supplement, not primary strategy.

## Prompt Template

```
[STYLE PREFIX from playbook].
[SCENE DESCRIPTION: subject, action, environment].
[LIGHTING: golden hour / overcast / studio softbox / dramatic side-light].
[COMPOSITION: wide shot / medium shot / close-up / overhead / isometric].
[CAMERA: Shot on [camera] with [lens] at [aperture]] (for photorealistic only).
16:9 aspect ratio.
```

### Style-Specific Prompt Patterns

| Style | Prompt Pattern |
|-------|---------------|
| **Flat illustration** | "Flat vector illustration, bold colors, clean edges, no gradients, white background" |
| **Isometric** | "Isometric 3D illustration, 30-degree angle, clean geometric shapes, soft shadows" |
| **Photorealistic** | "Photorealistic, shot on Canon EOS R5 with 85mm f/1.4, shallow depth of field" |
| **Diagram-style** | "Technical diagram, labeled components, clean lines, minimal color, white background" |
| **Watercolor** | "Soft watercolor illustration, muted tones, visible brush strokes, paper texture" |

## Batch Generation Strategy

| Phase | Model | Cost/Image | Purpose |
|-------|-------|-----------|---------|
| 1. Style guide | FLUX.2 [max] | $0.07 | One hero image, maximum quality |
| 2. Storyboard iteration | FLUX.2 [klein] 9B | $0.015 | Rapid variations during planning |
| 3. Final frames | FLUX.2 [pro] | $0.03 | Re-generate finals with hero as reference |

**Rate limit:** 24 concurrent requests max. Pipeline accordingly.

**Budget for 8-image explainer:** $0.07 (hero) + $0.12 (8x klein iterations) + $0.24 (8x pro finals) = ~$0.43

## Common Pitfalls

1. **Text in images** — AI image generators are unreliable with text. Never include text in prompts; add text as overlays in the compose stage
2. **Hands and fingers** — DALL-E 3 and FLUX still struggle. Avoid prompts requiring detailed hand poses
3. **Inconsistent characters** — Without reference images, the same character will look different each time. Always use the hero reference strategy
4. **Over-prompting** — Long, complex prompts produce unpredictable results. Keep to 2-3 sentences
5. **Ignoring the playbook** — Every image must match the style playbook. The style prefix is not optional

## Applying to OpenMontage

When using the `image_selector` tool in the asset stage:

1. **Always prepend the playbook's style prefix** to every prompt
2. **Generate a hero image first** at highest quality, use as reference for all others
3. **Use `1920x1088`** for 16:9 video frames (FLUX multiple-of-16 requirement)
4. **Never request text in images** — add text overlays in the compose stage
5. **Budget check** — estimate total image cost before generating; switch to local diffusers if over budget
6. **Iterate with klein** during planning, finalize with pro
7. **Keep prompts to 2-3 sentences** — style prefix + scene description + composition
8. **Match the scene plan** — each image maps to a specific scene in the script
