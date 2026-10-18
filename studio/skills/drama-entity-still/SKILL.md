---
name: drama-entity-still
description: Generate QA-gated character / scene / prop stills for short-drama Studio; identity lock and fail-closed retry.
---

# 竖屏短剧 · 资产定妆图（角色 / 场景 / 道具）

本 Skill 是 **Studio Agent 出图链路的一部分**，不是独立商店模块。
剧本用 `drama-script`、分镜用 `drama-shot-prompt`；资产定妆用本 Skill，并与出片门禁（`qaPass` / `forceEntityQa`）同一套状态。

执行时由 `skill_runtime` 读取下方 **Runtime** 块 + 项目内累积的经验补丁，驱动 `build_entity_image_prompt`。

## 何时调用

- 本段资产出现「无图」或 `qaPass !== true`
- 工作台「补图」/ 实体批量生成 / 一键全流程素材阶段
- 出片前硬门禁拦住的 blockers

## 硬规则

1. **脸靠图**：角色变体（受伤后、揭穿后）必须锁同名「默认形象」参考脸；禁止只靠文字重描五官。
2. **一实体一主体**：角色图只能一个人；场景图禁止人物；道具图禁止街景/人群。
3. **Fail-closed**：软通过 / vision skip / JSON 解析失败 ≠ 通过；不得晋升为 `selectedImage`。
4. **先资产后出片**：引用实体未 `qaPass` 时默认阻断视频；仅人工 `forceEntityQa` 可绕过。
5. **与分镜同一项目状态**：生成结果写回 `entities[].images` / `qaPass`，供分镜 `@角色` 与 I2V 参考图使用。
6. **经验回流**：QA 失败原因写入 Skill 经验库；重试时自动叠加匹配的 promptBoost。

## 出图循环

```text
Observe blockers（无图 / qa_fail / soft_pass）
  → Act：Skill Runtime + 经验补丁 → generate_image（变体带默认脸参考）
  → Verify：vision QA
  → 未过：record_qa_failure → 强化 prompt 重试
  → 全过：才允许 video-segment
```

## Prompt 要点

### 角色

- 写明「画面中央只有一个人」+ 姓名·变体
- 五官/发型/服装可辨；氛围光不可盖过主体
- 变体必须写出**可见差异**（绷带、血迹、妆造），并锁参考脸
- Negative：航拍、城市空镜、无人风景、第二个人物

### 场景

- 可拍竖屏空间：层次、陈设、材质、光影
- 明确「不要出现人物」
- Negative：人脸特写、角色设定稿

### 道具

- 只表现物体外形与材质；产品级质感
- Negative：人物、城市空镜

## Runtime

出图引擎读取本块（YAML）。修改后无需改 Python 即可调整强化策略。

```yaml
skill_id: drama-entity-still
identity_lock: true
fail_closed: true
variant_prompt_hint: >
  Variant must change only wardrobe / injury / makeup state while keeping
  the identical face from the reference still.
experience_seeds:
  - id: injury-bandage
    kinds: [character]
    matchReason: [bandage, 绷带, white bandage, injury, 受伤, blood, 血迹]
    matchVariant: [受伤, 绷带, 伤]
    promptBoost: >
      CRITICAL visible injury props: thick WHITE gauze bandage wrapped around
      left shoulder AND upper chest, blood-stained torn coat, pale sweaty face,
      cold blue rim light. Bandage must be the first thing the eye notices.
      Keep the EXACT same face as the reference still — only wardrobe/injury changes.
    negativeBoost: >
      clean uninjured clothes, no bandage, pristine coat, healthy complexion,
      fashion portrait, unbroken skin, studio beauty shot
  - id: identity-lock
    kinds: [character]
    matchReason: [face, identity, different person, 五官, 不像]
    matchVariant: []
    promptBoost: >
      Identity lock: same bone structure, eyes, nose, jawline and hairline as reference.
    negativeBoost: different face, face swap, new identity
  - id: scene-no-people
    kinds: [scene]
    matchReason: [person, people, face, 人物, 人脸]
    matchVariant: []
    promptBoost: Empty location only — no human figures or silhouettes.
    negativeBoost: person, people, face, portrait, crowd
expert_review:
  - id: character-no-empty-plate
    kinds: [character]
    fail_if_reason_contains: [landscape, cityscape, aerial, empty location, 无人空镜, 风景空镜]
  - id: spirit-no-human
    kinds: [spirit]
    strategies: [spirit]
    fail_if_reason_contains: [person, portrait, human, woman, man, face, 人像, physical human]
    except_if_reason_contains: [spirit, orb, bead, 灵光, 珠影, not a person, no person]
  - id: scene-no-people
    kinds: [scene]
    fail_if_reason_contains: [portrait, character sheet, close-up face, fashion model, 人像]
  - id: prop-no-person
    kinds: [prop]
    fail_if_reason_contains: [character portrait, full character, portrait of a, shows a person, 人像, 角色定妆]
    except_if_reason_contains: [no person, product, object only, 道具]
```

## 与 Skill 专家页的关系

Skill 专家页用于发现/浏览，并展示本 Skill 的 **经验补丁与 Top 失败原因**。
**执行必须走当前项目 Agent**（entities generate → QA → 出片门禁）。
禁止把定妆当作与工作台脱节的一次性提示词玩具。
