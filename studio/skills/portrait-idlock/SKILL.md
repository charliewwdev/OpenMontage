---
name: portrait-idlock
description: Douyin portrait match — dual workshop paths: gen-likeness (H3 idlock) or reshoot brief (4K/60 remake bible).
---

# 写真对标 · 工坊双路径

## 路径选择（创建项目时）

| mode | 中文 | 做什么 | 质量目标 |
|------|------|--------|----------|
| `gen-likeness` | 极像生成 | 原片关键帧 → MiniMax H3 FL2VA → 卡点合片+原曲 | **接受极像并持续堆质量**（1080p / 非 turbo / 强化提示 / 锐化合片） |
| `reshoot` | 原片重拍 | 输出妆造/场地/卡点企划；工作台只展示参考帧 | 真机 4K/60 才对齐原片物理质量 |

字段：`project.portraitMatchMode`。

## 极像质量堆叠（gen-likeness）

默认不放弃生成、不改走重拍。叠这些杠杆：

1. **关键帧**：抖音原片 1080×1920（禁止 AI 样片帧）
2. **角色定妆**：原片关键帧直挂（避免 alpha 破图）；场景空镜过 drama-entity-still
3. **提示词**：ZH 含角色/场景/动作/运镜/转镜/光影 + 质量堆叠句；EN `modelPrompt` 含 Quality stack
4. **Runtime**：`duration_sec≈4.0`，`use_turbo=false`，**`resolution_default=1080p`**，backend=comfyui
5. **合片**：gap 持镜 + 加速 + 闪黑 + 强化 unsharp/eq + 原曲 m4a → 1080×1920

API：`GET .../quality` · `POST .../prepare-assets` · `POST .../generate`（默认 1080p）

## 工坊达标门禁（角色 / 场景 / 提示词）

1. **角色**：原片关键帧定妆 `qaPass`（`bypass=portrait-original-keyframe`）
2. **场景**：empty location plate 过 drama-entity-still
3. **提示词**：`promptQa.pass`；未达标则 `generate` 拦截

## reshoot 硬规则

1. **禁止**调用 H3 / `portrait-match/generate`
2. 剧本页 = `reshootBrief.markdown`
3. 镜头 `status=reference`

## Runtime

```yaml
skill_id: portrait-idlock
duration_sec: 4.0
use_turbo: false
backend: comfyui
video_model: minimax-h3
resolution_default: 1080p
ratio: "9:16"
match_modes: [gen-likeness, reshoot]
assemble:
  mode: douyin-gap-front-grade-audio
  upscale: 1080x1920
```
