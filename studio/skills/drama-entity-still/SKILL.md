---
name: drama-entity-still
description: Generate QA-gated character / scene / prop stills for short-drama Studio; identity lock and fail-closed retry. Optimized for first-pass cast stills.
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
7. **一次过线优先（First-pass）**：默认定妆以「第一次就过」为目标；`qaPass` 后禁止因统一构图再次强制重画。
8. **受伤变体隔离**：白纱布 / 绷带 QA 与 promptBoost **只**作用于变体名含受伤/绷带的实体；禁止因 prompt 里出现英文 `injury` 把默认定妆判成受伤图。
9. **近通过锁图**：score≥0.35 的失败图下一轮用 img2img 精修，禁止整图冷启动重抽浪费。

## 出图循环

```text
Observe blockers（无图 / qa_fail / soft_pass）
  → Act：Skill Runtime + 可画化视觉清单 → generate_image（变体带默认脸参考）
  → Verify：vision QA（PRIMARY only）
  → 未过且 score≥0.35：img2img 精修 + 经验补丁
  → 未过且 score<0.35：强化 prompt 重试（有上限）
  → qaPass：停。不得自动 forceRefresh
  → 全过：才允许 video-segment
```

## Prompt 要点

### 角色（一次过线）

- **先写可核验视觉清单（英文优先）**，再跟人设原文：发型轮廓 → 服装类别 → 鞋履 → 年龄体型
- 例：`messy straw-yellow double buns tied with hemp rope` 优于只写「枯黄乱发双丫髻」
- 写明「画面中央只有一个人」+ 姓名·变体
- **默认透明抠图底**：纯白无缝底板，禁止场景、地面、墙面
- 出图后引擎会做 alpha 抠底（含封闭空洞 + 去白边 despill）；若仍见白边，可对实体执行 `punch-alpha`
- **全身定妆**：从头到脚，五官与整套服装可读
- 变体必须写出**可见差异**（绷带、血迹、妆造），并锁参考脸
- Negative：航拍、城市空镜、无人风景、第二个人物、半身胸上裁切、彩色棚景
- **不要**在默认定妆 prompt 里写 medical gauze / bandage

### 场景

- 可拍竖屏空间：层次、陈设、材质、光影
- 明确「不要出现人物」
- Negative：人脸特写、角色设定稿

### 道具

- 只表现物体外形与材质；产品级质感
- **默认透明抠图底**：同角色，一物一图、边缘干净可抠
- Negative：人物、城市空镜、桌面杂物

## QA PRIMARY / SECONDARY

**PRIMARY（缺一即 Fail）**

1. 画面只有一个人
2. 全身从头到脚（站姿，服装+鞋履可读）
3. 纯白/浅灰/透明抠图底，无风景
4. 发型轮廓符合人设（如双丫髻+草绳）
5. 服装类别符合人设（如粗布短褐+破麻背心）

**SECONDARY（单独不构成 Fail）**

- 精确发色深浅、唇色干裂、臂上旧淤痕、布料色号、诗意月光

受伤变体另加 PRIMARY：上身可见白色医用纱布包扎。

## Runtime

出图引擎读取本块（YAML）。修改后无需改 Python 即可调整强化策略。

```yaml
skill_id: drama-entity-still
identity_lock: true
fail_closed: true
first_pass: true
pass_and_stop: true
near_pass_img2img: true
near_pass_min_score: 0.35
# Cast stills: same full-body scale for every character so the asset rail stays consistent.
# Video shots may still change camera distance.
framing_lock: full_body
# Default cutout plate. Skill 专家改 cutout_prompt 即影响出图。
cutout_background: transparent
cutout_prompt: >
  ISOLATED CUTOUT on a seamless PURE WHITE (#FFFFFF) studio plate
  (flat even white, no gradient) so the backdrop can be keyed to transparent alpha.
  NO room, NO floor, NO wall texture, NO colored backdrop, NO scenery.
  透明抠图底板：主体以外必须是纯白无缝底板 #FFFFFF（均匀、无渐变），便于键控成透明 PNG；
  禁止场景、地面、墙面、彩色背景与棚拍道具。
framing_prompt: >
  FULL BODY character sheet: head-to-toe in frame, standing pose, slight headroom and footroom,
  face and wardrobe readable, centered. Not extreme face close-up, not chest-up crop only.
  Isolated cutout on seamless PURE WHITE (#FFFFFF) plate for alpha keying — no scenery.
first_pass_prompt: >
  FIRST-PASS cast still: render the CRITICAL visual checklist early (hair silhouette, wardrobe
  category, shoes, age/body). Prefer drawable English anchors over poetic-only Chinese.
  Do not invent medical gauze on the default look.
variant_prompt_hint: >
  Variant must change only wardrobe / injury props / makeup state while keeping
  the identical face from the reference still.
experience_seeds:
  - id: cutout-transparent-bg
    kinds: [character, prop]
    matchReason: [background, scenery, landscape, room, floor, wall, 背景, 场景, 地面, 墙面]
    matchVariant: []
    promptBoost: >
      CRITICAL cutout plate: seamless PURE WHITE (#FFFFFF) only — flat, no gradient.
      Remove any room, floor, wall, scenic or colored backdrop. Subject edges clean for alpha keying.
    negativeBoost: >
      room interior, wooden floor, concrete wall, scenery, colored backdrop,
      gradient studio background, light-gray plate, mid-gray background, environment, landscape

  - id: injury-bandage
    kinds: [character]
    matchReason: [bandage, 绷带, white bandage, gauze, 受伤, blood, 血迹]
    matchVariant: [受伤, 绷带, 负伤, 外伤, 伤势]
    promptBoost: >
      FULL BODY standing. CRITICAL visible injury props: thick WHITE gauze bandage wrapped around
      left shoulder AND upper chest, blood-stained torn coat, pale sweaty face,
      cold blue rim light. Bandage must be readable. Keep the EXACT same face as the reference still.
    negativeBoost: >
      clean uninjured clothes, no bandage, pristine coat, healthy complexion,
      fashion portrait, unbroken skin, studio beauty shot

  - id: identity-lock
    kinds: [character]
    matchReason: [face, identity, different person, 五官, 不像]
    matchVariant: []
    promptBoost: >
      Identity lock: same bone structure, eyes, nose, jawline and hairline as reference.
      Only wardrobe or variant state may change.
    negativeBoost: different face, face swap, new identity

  - id: hair-double-bun-rope
    kinds: [character]
    matchReason: [hairstyle, hair, bun, buns, topknot, 发型, 双丫, 丫髻, 枯黄, 草绳]
    matchVariant: []
    promptBoost: >
      CRITICAL hair fix: messy dry straw-yellow double buns (双丫髻) tied with rough hemp rope,
      loose cheek wisps — NOT neat glossy black buns, NOT a single topknot, NOT platinum blonde.
    negativeBoost: >
      neat black double buns, sleek salon hair, single topknot, platinum blonde

  - id: wardrobe-coarse-tunic
    kinds: [character]
    matchReason: [garment, clothing, wardrobe, vest, tunic, 服装, 短褐, 背心, 粗布]
    matchVariant: []
    promptBoost: >
      CRITICAL wardrobe fix: washed gray-blue coarse short tunic (青灰粗布短褐) with a torn hemp vest;
      frayed edges, not clean modern costume.
    negativeBoost: >
      clean blue hanfu, fashion coat, pristine costume, modern clothes

  - id: framing-full-body
    kinds: [character]
    matchReason: [close-up, closeup, extreme, forehead, chest-up, half-body, 特写, 半身, 胸上, 额头]
    matchVariant: []
    promptBoost: >
      Framing lock: FULL BODY head-to-toe — standing, face + full wardrobe readable,
      slight headroom and footroom. Same scale as other cast stills;
      do not extreme-crop the face and do not stop at chest-up only.
    negativeBoost: >
      extreme close-up, forehead only, eyes only crop, chest-up only, half-body crop,
      bust portrait, shoulders only
  - id: scene-no-people
    kinds: [scene]
    matchReason: [person, people, face, 人物, 人脸]
    matchVariant: []
    promptBoost: Empty location only — no human figures or silhouettes.
    negativeBoost: person, people, face, portrait, crowd
expert_review:
  - id: character-framing-full-body
    kinds: [character]
    fail_if_reason_contains:
      - extreme close-up
      - forehead only
      - eyes only
      - chest-up only
      - half-body only
      - bust portrait
      - 特写过近
      - 半身裁切
      - 只有胸上
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

改本 Skill 的 Runtime / experience_seeds 后，下次出图即生效（`skill_runtime` 读 SKILL.md）；无需改 Python 即可调强化策略。
