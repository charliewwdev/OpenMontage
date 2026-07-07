# 可灵官方 API 集成阶段 3：TTS、音效、数字人、口型与视频特效

状态：已按本阶段边界完成 OpenMontage provider 接入；真实可灵 API 调用仍需显式 live QA 或人工端到端测试。

来源：从 `docs/kling-official-integration-plan.md` 拆分而来。本阶段对应原计划中的 P3「音频、TTS、数字人、口型、特效」。

执行顺序：必须在以下两个阶段完成后执行：

1. `docs/kling-official-phase-1-core.md`
2. `docs/kling-official-phase-2-omni-operations.md`

## 1. 阶段目标

本阶段目标是在已有 OpenMontage capability 中继续增加 `kling_official` provider 覆盖，而不是新增产品功能：

- 可灵 TTS：接入现有 `tts` capability 和 `tts_selector`。
- 可灵数字人：作为可选 provider 工具接入现有 `avatar` capability，不自动替代 `talking_head.py`。
- 可灵口型：作为可选 provider 工具接入现有 `avatar` capability，与已有 `lip_sync.py` 并存，不自动替代本地口型工具。
- 可灵音效：仅当能自然映射到现有 `music_generation` 或已有音频后期流程时才接；默认不新增 `sound_effects` capability。
- 可灵视频特效：默认不接入普通 `video_generation`，除非已有 pipeline 明确消费该类 operation；默认不新增 `video_effects` capability。

本阶段的重点是“给已有槽位增加可灵官方供应商”，不是把官方 API 的所有端点都产品化。

当前实现记录：

- 已新增 `tools/audio/kling_tts.py`，注册到 `tts` capability，并可由 `tts_selector` 通过 `preferred_provider="kling_official"` 选中。
- 已新增 `tools/avatar/kling_avatar.py`，注册到 `avatar` capability，与本地 `talking_head.py` 并存。
- 已新增 `tools/avatar/kling_lip_sync.py`，注册到 `avatar` capability，与本地 `lip_sync.py` 并存，并保留多人脸人工确认出口。
- 未新增 `kling_audio` 或 `kling_effects`，避免为当前 pipeline 引入未设计的 `sound_effects` / `video_effects` 能力面。
- 已更新 `docs/PROVIDERS.md`、`docs/ARCHITECTURE.md`、`README.md`、`skills/INDEX.md`、`.agents/skills/kling-official/SKILL.md` 和 contract tests。

注意：仓库当前只有 `tts_selector`、`image_selector`、`video_selector` 三类 selector；没有 `avatar_selector`。`avatar-spokesperson` 和 `localization-dub` pipeline 目前通过 manifest/director 显式列出 `talking_head` / `lip_sync`。因此 `kling_avatar` / `kling_lip_sync` 被 registry 发现并不等于现有 avatar pipeline 会自动消费它们。如需让现有 pipeline 使用，只能在对应 pipeline 的 `tools_available`、`optional_tools` 和 stage director tool plan 中做最小供应商选项更新，不新增 stage、canonical artifact 或新的 selector。

## 2. 进入条件

开始前必须确认：

- 阶段 1 的官方视频和图像 provider 已完成并验收。
- 阶段 2 的 Omni、Elements helper、Account Usage helper、Callback 已完成并验收。
- `tools/_kling/` client 能复用到音频、头像、口型和特效端点。
- `kling-official` skill 已覆盖任务协议、错误处理、成本治理和 Omni 引用。
- 当前官方 schema fixture 已刷新，并包含本阶段端点的核心字段。
- CI 仍默认不打真实可灵 API。

## 3. 全局规则

本阶段新增的每个工具都必须遵守：

- 继承 `BaseTool`。
- 使用 `provider="kling_official"`。
- 声明 `dependencies = ["env:KLING_API_KEY"]`。
- 声明 `runtime = ToolRuntime.API`。
- `agent_skills` 至少包含 `kling-official`，并按能力补充对应 Layer 3 skill。
- 显式实现 `estimate_cost()`，不能静默返回 `0.0`。
- 成功的 paid ToolResult 必须写入 `cost_usd`。如果阶段 2 的 Account Usage 能提供实际用量，可记录估算成本和实际用量的校正信息。
- 所有远端结果必须下载到本地 output path 或项目 artifacts。
- ToolResult 必须包含 `task_id`、`provider`、`model`、`operation`、`output_path` 或等价字段。
- 官方错误必须保留 `code`、`message`、`request_id`。
- 真实 API 测试必须由显式环境变量开启。

Selector 规则：

- TTS 可以接入 `tts_selector`。
- 音效不要伪装成长音乐生成，除非 capability 暂时只能挂到 `music_generation`，且 `best_for/not_good_for` 必须写清楚。
- 数字人和口型可以挂到 `avatar` capability，但仓库当前没有 `avatar_selector`。现有 avatar pipeline 是显式工具槽位模式，不能假设新增 provider 会自动被 pipeline 选择。
- 如果要让 `avatar-spokesperson` 或 `localization-dub` 使用 `kling_avatar` / `kling_lip_sync`，必须按现有 pipeline 规范显式更新 manifest 和 director skill 的工具选择规则；这只能是供应商选项更新，不能新增流程。
- 视频特效不应挂到普通 `video_generation` 自动选择路径。
- 本阶段默认不新增 capability。若确实需要 `sound_effects`、`video_effects` 这类新 capability，必须另写设计文档，并说明对应 pipeline、selector、artifact 和用户入口；不能混在“新增可灵供应商”任务里。

## 4. 工作流 A：可灵 TTS

### 4.1 建议文件

```text
tools/audio/kling_tts.py
```

### 4.2 Tool 契约

建议：

```python
class KlingTTS(BaseTool):
    name = "kling_tts"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "tts"
    provider = "kling_official"
    runtime = ToolRuntime.API
    dependencies = ["env:KLING_API_KEY"]
    agent_skills = ["kling-official", "text-to-speech"]
```

### 4.3 API 范围

目标端点：

```text
POST /v1/audio/tts
GET  /v1/audio/tts/{id}
```

核心字段：

- `text`
- `voice_id`
- `voice_language`，例如 `zh`、`en`
- `voice_speed`

结果路径：

```text
data.task_result.audios[]
```

### 4.4 实现要求

- 接入 `tts_selector`，确保 `preferred_provider="kling_official"` 可选中。
- `text` 必填，并在调用前做长度校验。
- `voice_language` 使用官方枚举，不要用自由文本。
- `voice_speed` 做范围校验。
- 如果没有传 `voice_id`，要么使用官方默认，要么返回清晰错误；不要硬编码不存在的 voice。
- 输出音频必须下载到 `output_path`。
- 如果返回多个音频，全部写入 artifacts，`data.output_path` 指向第一条。
- 记录 `voice_id`、`voice_language`、`voice_speed`。

### 4.5 测试

覆盖：

- registry 能发现 `kling_tts`。
- `capability="tts"`。
- `provider="kling_official"`。
- `tts_selector` 可通过 `preferred_provider="kling_official"` 选中。
- payload 字段正确。
- 成功结果下载音频。
- `agent_skills` 包含 `kling-official`。
- `estimate_cost()` 不静默返回 `0.0`。

## 5. 工作流 B：可灵音效

### 5.1 建议文件

```text
tools/audio/kling_audio.py
```

### 5.2 Capability 决策

实施前必须做一次“是否接入现有能力槽位”的决策：

| 选择 | 适用情况 | 要求 |
|------|----------|------|
| 接入 `music_generation` | 官方返回内容能满足现有音乐/音频生成 stage 的消费方式 | `best_for/not_good_for` 必须写明它偏音效，不是长音乐生成 |
| 暂不接入 | 端点更像短音效或视频后期声音，不符合现有 pipeline 消费方式 | 只在 `kling-official` skill 和后续计划中记录，不新增工具 |

推荐：默认暂不接入，除非现有 pipeline 明确需要该 provider。不要在本阶段新增 `sound_effects` capability。

### 5.3 API 范围

文生音效：

```text
POST /v1/audio/text-to-audio
GET  /v1/audio/text-to-audio/{id}
```

核心字段：

- `prompt`
- `duration`

视频生音效：

```text
POST /v1/audio/video-to-audio
GET  /v1/audio/video-to-audio/{id}
```

核心字段：

- `video_id` 或 `video_url`
- `sound_effect_prompt`
- `bgm_prompt`
- `asmr_mode`

结果路径：

```text
data.task_result.audios[]
```

视频生音效也可能返回 videos，必须按当前 schema fixture 处理。

### 5.4 实现要求

- 使用 `operation` 区分 `text_to_audio` 和 `video_to_audio`。
- 如果接入 `music_generation`，必须保证现有音乐 stage 能消费输出；否则不要接入 registry，只保留在官方 skill/后续计划里。
- `text_to_audio` 必须有 `prompt`。
- `video_to_audio` 必须有 `video_id` 或 `video_url`。
- 如果输入本地视频而官方只接受 URL，必须明确要求 URL 或先实现官方支持的上传路径；不能静默使用其它 provider。
- 输出音频必须下载到本地。
- 如果返回视频，也要下载并放入 artifacts。
- `duration` 必须进入成本估算。
- `asmr_mode`、bgm、长时长属于更高成本/更强效果差异参数，默认不启用。

### 5.5 测试

覆盖：

- 如果接入现有 capability，registry 能发现音效 provider。
- 如果暂不接入，文档明确“不接入当前 registry”的理由。
- `text_to_audio` payload。
- `video_to_audio` payload。
- 无必需输入时报参数错误。
- 多音频 artifacts。
- 如返回视频，视频 artifacts。
- 不被普通 TTS 或普通音乐流程误选；如果无法保证，则不接入 registry。
- `estimate_cost()` 不静默返回 `0.0`。

## 6. 工作流 C：可灵数字人

### 6.1 建议文件

```text
tools/avatar/kling_avatar.py
```

### 6.2 Tool 契约

建议：

```python
class KlingAvatar(BaseTool):
    name = "kling_avatar"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "avatar"
    provider = "kling_official"
    runtime = ToolRuntime.API
    dependencies = ["env:KLING_API_KEY"]
    agent_skills = ["kling-official", "avatar-video"]
```

### 6.3 API 范围

目标端点：

```text
POST /v1/videos/avatar/image2video
GET  /v1/videos/avatar/image2video/{id}
```

核心字段：

- `image`
- `audio_id` 或 `sound_file`
- `prompt`
- `mode`，例如 `std`、`pro`

结果路径：

```text
data.task_result.videos[]
```

### 6.4 实现要求

- 与本地 `talking_head.py` 并存，不替代本地工具。
- 官方工具适合云端高质量数字人；本地工具适合无 API 成本、离线可控。
- 不修改 `talking_head.py` 的行为，不把 `kling_avatar` 包装成 `talking_head` 的内部分支。
- 如果需要在 `avatar-spokesperson` 中启用，只在现有 pipeline 的工具列表和 director 决策里增加一个可选供应商路径；不改变 scene_plan、asset_manifest 或 checkpoint 契约。
- 输入头像图片可接受 URL 或本地路径；本地路径按官方要求转 raw base64 或报清晰错误。
- 音频可以使用 `audio_id` 或 `sound_file`，具体字段按当前 schema fixture。
- `mode="pro"` 进入成本估算。
- 输出视频必须下载到本地，并调用 `probe_output()`。
- ToolResult 记录头像来源、音频来源、模式、任务 ID。

### 6.5 测试

覆盖：

- registry 能发现 `kling_avatar`。
- `capability="avatar"`。
- payload 使用头像和音频字段。
- 缺少头像或音频时报参数错误。
- 成功后下载视频并 probe。
- 与本地 `talking_head.py` 不冲突。
- 若更新了 `avatar-spokesperson`，测试或文档必须证明它是显式选择 `kling_avatar`，不是靠 registry 自动替换 `talking_head`。
- `estimate_cost()` 不静默返回 `0.0`。

## 7. 工作流 D：可灵口型

### 7.1 建议文件

```text
tools/avatar/kling_lip_sync.py
```

### 7.2 流程

口型生成至少分两步：

1. 识别人脸：

```text
POST /v1/videos/identify-face
```

输入：

- `video_id` 或 `video_url`

输出：

- `data.session_id`
- face 信息列表

2. 生成口型：

```text
POST /v1/videos/advanced-lip-sync
GET  /v1/videos/advanced-lip-sync/{id}
```

输入：

- `session_id`
- `face_choose[]`
- `audio_id` 或 `sound_file`

输出：

```text
data.task_result.videos[]
```

### 7.3 Tool 契约

建议：

```python
class KlingLipSync(BaseTool):
    name = "kling_lip_sync"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "avatar"
    provider = "kling_official"
    runtime = ToolRuntime.API
    dependencies = ["env:KLING_API_KEY"]
    agent_skills = ["kling-official", "avatar-video"]
```

### 7.4 人脸选择规则

口型 face 选择可能影响输出人物，必须保留人工确认出口。

规则：

- 如果用户明确传入 `face_id` 或 `face_choose`，直接使用。
- 如果未传入，工具可以返回 face list 并要求上层确认。
- 如果实现自动选择，只能作为显式参数启用，例如 `auto_select_face=True`。
- 自动策略应选择最大或最居中的 face，并在 ToolResult 中记录选择理由。
- 不允许在多人视频中静默选择第一张脸。

### 7.5 Artifacts

建议记录：

```text
projects/<project-name>/artifacts/kling_lip_sync_faces.json
```

内容：

- `session_id`
- face list
- 每个 face 的位置、大小、置信度等官方字段
- 选中的 face
- 选择方式：`user_selected` 或 `auto_selected`

### 7.6 实现要求

- 识别人脸和生成口型可以是同一个工具的不同 operation，也可以拆 helper。
- `identify_face` operation 可以只返回 face list，不生成视频。
- `advanced_lip_sync` operation 必须有 `session_id` 和音频输入。
- 一站式 operation 可以执行识别、选择、生成，但多人场景必须遵守人工确认规则。
- 不修改 `lip_sync.py` 的行为，不把 `kling_lip_sync` 包装成 `lip_sync` 的内部分支。
- 如果需要在 `localization-dub` 或 `avatar-spokesperson` 中启用，只在现有 pipeline 的工具列表和 director 决策里增加一个可选供应商路径；不改变 artifact schema 或 stage 顺序。
- 输出视频下载到本地，并调用 `probe_output()`。
- 成本估算要覆盖识别和生成两个步骤。

### 7.7 测试

覆盖：

- `identify_face` payload。
- face list 解析。
- 无 face 时报清晰错误。
- 多 face 未启用自动选择时不静默继续。
- `auto_select_face=True` 时记录选择理由。
- `advanced_lip_sync` payload。
- 成功后下载视频并 probe。
- 若更新了 `localization-dub` 或 `avatar-spokesperson`，测试或文档必须证明它是显式选择 `kling_lip_sync`，不是靠 registry 自动替换 `lip_sync`。
- `estimate_cost()` 不静默返回 `0.0`。

## 8. 工作流 E：可灵视频特效

### 8.1 建议文件

```text
tools/video/kling_effects.py
```

### 8.2 Capability 决策

视频特效不是普通 text-to-video，也不是通用 image-to-video。

本阶段默认不接入 `kling_effects`，原因是现有 `video_selector` 的标准 operation 是 `text_to_video`、`image_to_video`、`reference_to_video`、`rank`，视频特效没有稳定的 pipeline 消费路径。

只有满足以下条件时才允许接入：

- 已有 pipeline 或 stage 明确需要视频特效 operation。
- 已定义该 operation 如何进入 stage artifact。
- 不新增普通视频生成选择分支。
- 不让 `video_selector` 在 `text_to_video` / `image_to_video` / `reference_to_video` 中自动选择它。

不要在本阶段新增 `video_effects` capability。若确实需要，应另写设计文档。

### 8.3 API 范围

目标端点：

```text
POST /v1/videos/effects
GET  /v1/videos/effects/{id}
```

核心字段：

- `effect_scene`
- `input.image`
- `input.images`

结果路径：

```text
data.task_result.videos[]
```

### 8.4 实现要求

默认不实现。若满足上面的接入条件：

- 使用 `operation="video_effect"` 或更具体的 effect operation。
- `effect_scene` 必须是官方枚举或 fixture 中记录的有效值。
- 必须有输入图片，除非官方某个 effect 明确不需要。
- 支持单图和多图输入。
- 本地图片转 raw base64 或按官方要求处理。
- 输出视频下载到本地，并调用 `probe_output()`。
- `best_for` 写清楚它适合特效模板，不适合普通视频生成。
- `not_good_for` 写清楚不要用于普通叙事视频、解释器视频、连续镜头生成。

### 8.5 测试

覆盖：

- 如果实现，registry 路由方式被文档和测试固化。
- 如果不实现，阶段验收中明确记录“不接入当前 registry”的理由。
- 普通 `video_selector` text_to_video 不会误选 `kling_effects`。
- effect payload。
- 缺少图片或 effect_scene 时报参数错误。
- 成功后下载视频并 probe。
- `estimate_cost()` 不静默返回 `0.0`。

## 9. 文档和 Skill 更新

本阶段更新：

```text
docs/PROVIDERS.md
docs/ARCHITECTURE.md
README.md
skills/INDEX.md
.agents/skills/kling-official/SKILL.md
```

要求：

- `docs/PROVIDERS.md` 增加已接入的 TTS、数字人、口型 provider；音效和特效若不接入，只记录为官方 API 未映射端点。
- `docs/ARCHITECTURE.md` 只标明现有 capability 的 provider 扩展；不要描述未落地的新 capability。
- `README.md` provider key 列表不重复，只保留 `KLING_API_KEY` / `KLING_API_BASE_URL` 说明。
- `skills/INDEX.md` 能让 agent 发现对应能力。
- 若让现有 avatar pipeline 消费 `kling_avatar` / `kling_lip_sync`，对应 `pipeline_defs/` 和 `skills/pipelines/...` 只记录供应商选择规则，不新增 pipeline 阶段或 canonical artifact。
- `.agents/skills/kling-official/SKILL.md` 增加：
  - TTS voice 参数注意事项。
  - 音效 prompt 注意事项，以及默认不新增 `sound_effects` capability 的原因。
  - 数字人头像/音频输入注意事项。
  - 口型 face 选择规则。
  - 视频特效默认不接入普通 `video_generation` 的警告。

## 10. 测试总要求

新增或更新：

```text
tests/contracts/test_kling_tts.py
tests/contracts/test_kling_avatar.py
tests/contracts/test_kling_lip_sync.py
```

可选测试：

- 如果 `kling_audio` 接入现有 capability，新增 `tests/contracts/test_kling_audio.py`。
- 如果 `kling_effects` 有明确 pipeline 消费路径并被实现，新增 `tests/contracts/test_kling_effects.py`。

本阶段默认不新增 capability。如果后续单独设计了新 capability，该设计必须自带 registry、provider menu、selector 或非 selector 路由测试。

Live QA 必须显式开启：

```bash
RUN_KLING_LIVE_TESTS=1 KLING_API_KEY=... pytest tests/qa/test_kling_official_live.py
```

live smoke 限制：

- 每类能力只跑最小调用。
- 不跑批量。
- 不默认使用高成本模式。
- 不在 CI 默认开启。

## 11. 阶段验收清单

阶段 3 完成前逐项确认：

- `kling_tts` 存在并接入 `tts_selector`。
- `kling_audio` 只有在能映射到现有 capability 时才存在；否则验收记录为“暂不接入，避免新增功能面”。
- `kling_avatar` 存在，并与本地 `talking_head.py` 并存；除非现有 pipeline 显式加入它，否则不要求 pipeline 自动消费。
- `kling_lip_sync` 存在，并保留 face 人工选择出口；除非现有 pipeline 显式加入它，否则不要求 pipeline 自动消费。
- `kling_effects` 默认不存在；若存在，必须证明不会被普通视频生成误选，并说明对应 pipeline 消费路径。
- 每个新增工具都声明 `provider="kling_official"`。
- 每个新增工具都声明 `dependencies = ["env:KLING_API_KEY"]`。
- 每个新增工具都包含 `agent_skills = ["kling-official", ...]` 或等价配置。
- 每个新增工具都实现非默认 `estimate_cost()`。
- 每个新增 paid 工具的成功 ToolResult 都写入 `cost_usd`。
- 每个新增工具都有 contract 测试。
- 真实 API 测试默认不进 CI。
- 文档、skill、provider table 已更新。
- 阶段 1 和阶段 2 的测试仍通过。

## 12. 全项目完成标准

三阶段全部完成后，OpenMontage 的可灵官方 API 集成应达到：

- 官方可灵每个主要能力族都有明确实现或不接入理由。
- 视频、图像和已接入现有 OpenMontage capability 的 TTS、数字人、口型等能力有实现和测试；未接入端点有清楚的不接入理由。
- selector 或现有 stage routing 不会在不适合的 operation 中误选特效、口型、音效工具。
- 付费调用默认不进 CI，live QA 需要显式环境变量开启。
- 所有新增工具遵守 OpenMontage 的 BaseTool 契约、artifact 路径和项目目录约定。
- fal.ai Kling 和 official Kling 在 provider 命名、文档、skill 和 selector 使用上清楚分离。
- 未新增 pipeline、stage、canonical artifact 或未设计的新 capability。
