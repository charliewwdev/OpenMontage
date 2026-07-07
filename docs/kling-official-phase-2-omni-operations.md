# 可灵官方 API 集成阶段 2：Omni、Elements、账户用量与 Callback

状态：实施指导文档。

来源：从 `docs/kling-official-integration-plan.md` 拆分而来。本阶段对应原计划中的 P2「Omni、元素、账户、callback」。

执行顺序：必须在 `docs/kling-official-phase-1-core.md` 完成并验收后执行。本阶段完成后再进入 `docs/kling-official-phase-3-media-avatar-effects.md`。

## 1. 阶段目标

本阶段不再解决“官方可灵能否被 OpenMontage 调用”的基础问题，而是在阶段 1 的视频、图像 provider 和共享 client 基础上增强同一个可灵官方 provider：

- 深化 Video Omni / Image Omni 支持。
- 增加 Elements 引用能力，但默认作为 `kling_official_video` / `kling_official_image` 的内部 helper，不新增 OpenMontage 管理功能。
- 增加 Account Usage 账户用量读取能力，但默认作为 provider preflight/错误诊断 helper，不新增常规 pipeline 工具。
- 规范 callback 透传和 artifacts 记录。

这些能力提高的是官方可灵 provider 的参数覆盖和诊断质量，不应该改变 OpenMontage 现有 pipeline、selector、stage artifact 或 checkpoint 流程。

## 2. 进入条件

开始本阶段前必须确认：

- 阶段 1 验收清单已完成。
- `tools/_kling/` client、errors、media、schemas 已存在并有测试覆盖。
- `kling_official_video` 和 `kling_official_image` 已能被 registry 发现。
- `preferred_provider="kling_official"` 对视频和图像 selector 均可用。
- schema fixture 已按当前官方文档刷新。
- 付费成本估算不再静默返回 `0.0`。
- fal.ai 版 `kling_video` 行为未被改变。

如果上述任一条件不满足，先回到阶段 1 修复。

## 3. 不可变规则

本阶段必须遵守：

- 不新增 pipeline。仍通过现有 provider/selector/capability 体系接入。
- 不新增 OpenMontage capability。阶段 2 的能力都挂在阶段 1 已有的 `video_generation` / `image_generation` provider 内部。
- 不更改 `provider="kling_official"` 命名。
- 不把 Elements 做成普通生成 provider，也不新增 `asset_management` capability。
- 不把 callback 作为默认执行路径。当前仍以 polling 为主，callback 是高级透传能力。
- Account Usage 不进入生产 pipeline stage，不进 selector；它只是 `tools/_kling` 下的可选诊断 helper。官方 QPS 限制为低频接口，必须做本地节流或缓存。
- Omni 深度能力必须建立在阶段 1 的 `api_family=omni` 上，不新增 selector 层 operation。
- 高成本 Omni、多参考、多元素调用必须进入成本估算。
- Omni 付费调用的成功 ToolResult 必须继续写入 `cost_usd`。如果 Account Usage 能返回可核对的实际用量，应把估算成本和实际用量的校正结果记录到 ToolResult data 或项目 artifacts。
- 所有远端结果、元素 ID、任务 ID、引用关系必须写入 artifacts 或 ToolResult data，便于复现。
- 如果官方 schema 有变化，先更新 fixture 和测试，再改实现。

## 4. 工作流 A：Omni 深度接入

阶段 1 只要求基础 Omni 可用。本阶段要让 Omni 能真正承担复杂参考输入。

### 4.1 Video Omni 增强范围

目标端点：

```text
POST /v1/videos/omni-video
GET  /v1/videos/omni-video/{id}
GET  /v1/videos/omni-video?pageNum=1&pageSize=30
```

增强字段：

- `image_list[].image_url`
- `image_list[].type`，例如 `first_frame`、`end_frame`
- `video_list[].video_url`
- `video_list[].refer_type`，例如 `feature`、`base`
- `video_list[].keep_original_sound`
- `element_list[].element_id`
- `multi_shot`
- `shot_type`
- `multi_prompt`
- `sound`
- `mode`
- `aspect_ratio`
- `duration`

实现要求：

- 在 `kling_official_video` 中把 Omni payload builder 拆成独立 helper，避免塞进 `execute()`。
- 支持 URL 和本地文件输入的标准化。本地图片仍由 `tools/_kling/media.py` 转换；本地视频如果官方只接受 URL，必须明确报错或要求用户提供可访问 URL，不能静默上传到 fal.ai。
- `operation=reference_to_video` 时，必须明确要求至少一种参考输入：图片、视频或 element。
- `video_list` 中的 `refer_type` 必须保留官方枚举，不要随意翻译成内部枚举后丢失原值。
- `keep_original_sound` 默认应保守设置为 `no` 或不发送，避免无意保留参考视频声音。
- `sound="on"` 属于高成本/高差异输出能力，默认不启用。
- `mode="4k"` 默认不启用。

### 4.2 Image Omni 增强范围

目标端点：

```text
POST /v1/images/omni-image
GET  /v1/images/omni-image/{id}
GET  /v1/images/omni-image?pageNum=1&pageSize=30
```

增强字段：

- `image_list[].image`
- `element_list[].element_id`
- `resolution`
- `result_type`
- `n`
- `series_amount`
- `aspect_ratio`
- prompt 中的 `<<<image_1>>>` 引用语法

实现要求：

- 提供 prompt reference helper，把用户输入的多图参考稳定映射为 `<<<image_1>>>`、`<<<image_2>>>` 等。
- helper 必须返回映射 metadata，例如第几个引用对应哪个 URL/path。
- 如果用户 prompt 已经包含 `<<<image_1>>>`，不要重复插入；应校验引用数量和 `image_list` 是否一致。
- `result_type="series"` 和 `series_amount` 必须进入成本估算。
- `resolution="4k"` 默认不启用。
- `aspect_ratio="auto"` 只在官方当前 schema 支持时发送。

### 4.3 多镜头 `multi_prompt`

多镜头能力要做成明确结构，不要把用户自然语言拆分后随意发送。

建议 schema：

```python
"multi_prompt": {
  "type": "array",
  "items": {
    "type": "object",
    "properties": {
      "prompt": {"type": "string"},
      "duration": {"type": "string"},
      "camera_control": {"type": "object"},
      "image_refs": {"type": "array"},
      "element_refs": {"type": "array"}
    },
    "required": ["prompt"]
  }
}
```

规则：

- `multi_shot=true` 时，普通 `prompt` 是否生效以官方 schema 为准；如果官方标注无效，不要同时依赖它。
- `shot_type` 必须为官方枚举，例如 `customize` 或 `intelligence`。
- 多镜头 payload builder 要有单元测试覆盖。
- 多镜头默认不在 selector 自动路径启用，除非用户明确传入。

### 4.4 Omni 输出处理

输出规则：

- 仍下载最终媒体到本地 output path。
- 如果官方返回多个媒体，全部写入 artifacts。
- ToolResult data 至少包含：
  - `task_id`
  - `api_family="omni"`
  - `operation`
  - `model`
  - `output_path`
  - `remote_outputs`
  - `references_used`
  - `element_ids`
- 对视频继续调用 `probe_output()`。
- 对图像继续推断文件扩展名，默认 `.png`。

## 5. 工作流 B：Elements 引用 Helper

Elements 是 Video Omni 和 Image Omni 的官方参数能力。本阶段只把它作为官方可灵 provider 的内部引用 helper，目的是让 `element_list[].element_id` 可以被视频/图像 provider 正确传入和记录。

不要在本阶段把 Elements 产品化成独立 OpenMontage 管理功能。

### 5.1 建议文件

建议只新增底层 helper：

```text
tools/_kling/elements.py
```

不建议新增 `tools/kling_elements.py`。只有当已有 pipeline 或用户工作流明确需要独立元素管理入口时，才另开设计文档讨论。

### 5.2 支持范围

本阶段的 Elements 范围只服务 `element_list[].element_id` 引用、校验和 metadata 记录。允许封装的端点应保持只读或引用校验：

```text
GET  /v1/general/advanced-custom-elements/{id}
GET  /v1/general/advanced-custom-elements
GET  /v1/general/advanced-presets-elements
```

明确不在本阶段实现：

```text
POST /v1/general/advanced-custom-elements
POST /v1/general/delete-elements
```

原因：创建/删除 element 是素材管理功能，不是“新增可灵官方供应商”的必要路径。若后续确实需要元素生命周期管理，必须单独设计用户入口、权限、artifact 生命周期和 pipeline 使用方式，不能混在本阶段 provider 增强里。

### 5.3 Helper 契约

helper 不继承 `BaseTool`，不进入 registry，不进入 selector。

建议函数：

| helper | 用途 |
|--------|------|
| `normalize_element_list(...)` | 校验并标准化传给视频/图像 provider 的 `element_list` |
| `get_custom_element(...)` | 可选查询单个自定义元素，用于校验用户传入的 element id |
| `list_preset_elements(...)` | 可选列出官方预设元素，供诊断或文档使用 |

输入规则：

- provider 接收 `element_list` 时，只负责校验结构、透传给官方 API、记录 metadata。
- 不在默认路径创建或删除 element。
- 如果后续确实需要创建/删除 element，必须单独设计，不混在本阶段 provider 接入里。
- 对 preset elements 只读。

输出规则：

- 在 ToolResult data 中记录本次使用的 `element_ids`。
- 如查询过 element 详情，将 element metadata 写入项目 artifacts，便于复现。
- 如果官方查询响应是异步任务，使用共享 Classic parser 或新增专用 parser，不要猜字段。

### 5.4 Artifacts 约定

建议在项目中记录：

```text
projects/<project-name>/artifacts/kling_elements.json
```

结构建议：

```json
{
  "provider": "kling_official",
  "elements": [
    {
      "element_id": 123,
      "kind": "character",
      "name": "main-presenter",
      "source": "...",
      "created_at": "...",
      "task_id": "...",
      "reusable": true
    }
  ]
}
```

## 6. 工作流 C：Account Usage 诊断

Account Usage 用于官方可灵 provider 的 setup/preflight 和错误诊断，不是生产生成能力，不进入 pipeline stage。

### 6.1 建议文件

建议只新增底层 helper：

```text
tools/_kling/account.py
```

不建议新增 `tools/kling_account_usage.py`。如果后续需要用户显式运行账户诊断，再单独设计工具入口。

### 6.2 支持端点

目标端点：

```text
GET /account/costs
```

字段：

- `start_time`
- `end_time`
- `resource_pack_name`

### 6.3 使用场景

必须支持：

- provider setup/preflight 中检查资源包或余额可见性。
- 捕获 `1101` / `1102` 后提供更清楚的账户诊断。
- 在用户要求排查“为什么可灵不能生成”时提供低成本诊断。

不要求：

- 每次生成前都调用账户用量接口。
- 在 CI 中调用真实账户接口。

### 6.4 节流和缓存

规则：

- 官方 Account Usage QPS 低，必须本地节流。
- 同一进程内相同参数短时间重复查询应使用缓存。
- 如果被节流，返回“最近一次缓存结果”或清楚说明需要稍后重试。
- 不允许为了诊断在短时间内循环打账户接口。

### 6.5 输出

如果 helper 被 provider 调用，ToolResult data 建议包含：

- `resource_pack_subscribe_infos`
- `queried_range`
- `cached`
- `throttle_status`
- `provider="kling_official"`
- 如果用于校正生成成本，记录 `reconciled_cost_usd`、`cost_source` 和关联的 `task_id` 或时间窗口。

如果官方返回余额结构随资源包变化，保留原始字段，并给出轻量归一化摘要。

## 7. 工作流 D：Callback 支持

阶段 2 只要求 callback 透传和记录，不要求实现完整 callback receiver。

### 7.1 Provider 参数

视频、图像、Omni、后续音频工具都应接受：

```python
"callback_url": {"type": "string"}
```

并按官方 schema 放入对应字段：

- Classic：顶层 `callback_url`。
- Turbo：`options.callback_url`。
- 其他端点按当前 fixture 确认。

### 7.2 默认执行模式

默认仍然是 polling：

- 工具创建任务。
- 工具轮询任务到终态。
- 工具下载结果。
- 工具返回 ToolResult。

即使传入 `callback_url`，当前工具也不应立即假设 callback receiver 会写入 artifacts，除非 receiver 已明确存在并通过测试。

### 7.3 Artifacts 记录

如果传入 callback，ToolResult data 应记录：

- `callback_url`
- `callback_requested=true`
- `polling_used=true`
- `task_id`

如果后续实现 receiver，可追加：

- `callback_received_at`
- `callback_payload_path`
- `callback_status`

### 7.4 失败处理

- callback URL 无效时，优先在调用前做基本 URL 校验。
- 官方 callback 投递失败不应影响 polling 结果，只要 polling 成功。
- 如果 polling 失败但 callback 成功，必须能从 artifacts 找到 callback payload。

## 8. 文档和 Skill 更新

本阶段更新：

```text
docs/PROVIDERS.md
docs/ARCHITECTURE.md
.agents/skills/kling-official/SKILL.md
skills/INDEX.md
docs/kling-official-integration-plan.md
```

要求：

- `docs/PROVIDERS.md` 增加 Omni 深度能力、Elements、Account Usage 的说明。
- `docs/ARCHITECTURE.md` 标明 Elements 和 Account Usage 只是可灵官方 provider 的内部引用/helper 与诊断能力，不是生成 pipeline 或独立产品功能。
- `.agents/skills/kling-official/SKILL.md` 增加 Omni 引用语法、多参考输入、元素 ID 引用和 callback 注意事项。
- `skills/INDEX.md` 仅标出 Elements/Account Usage 作为 `kling_official` helper 的用途，不新增 capability 分类。
- 原总计划如果继续保留，应标注阶段 2 已拆分到本文件。

## 9. 测试要求

### 9.1 Omni 测试

覆盖：

- Video Omni 多 `image_list` payload。
- Video Omni `video_list` payload。
- Video Omni `element_list` payload。
- `reference_to_video` 无参考输入时报参数错误。
- `multi_prompt` payload。
- `sound="on"`、`mode="4k"` 成本估算提高或标记高成本。
- Image Omni 多图引用 prompt helper。
- prompt 中已有 `<<<image_1>>>` 时不重复插入。
- `result_type="series"` 多结果 artifacts。

### 9.2 Elements 测试

覆盖：

- Elements helper 不进入 registry。
- Elements helper 不挂到普通 `video_generation` / `image_generation` selector 路径。
- `element_list` 标准化和校验。
- 查询元素 payload。
- preset list payload。
- 默认路径不创建/删除 element。
- element metadata 写入 artifacts。

### 9.3 Account Usage 测试

覆盖：

- endpoint、参数和 Authorization header。
- QPS 节流。
- 相同查询缓存。
- `1101` / `1102` 错误后能触发诊断 helper 或输出建议。
- Account Usage helper 不进入 registry/selector。
- CI 默认不打真实账户接口。

### 9.4 Callback 测试

覆盖：

- Classic callback_url 顶层透传。
- Turbo callback_url 放入 `options.callback_url`。
- ToolResult 记录 `callback_requested` 和 `polling_used`。
- callback URL 基本校验。

## 10. 阶段验收清单

阶段 2 完成前逐项确认：

- Video Omni 支持多图、多视频、元素引用。
- Image Omni 支持多图引用和 series 输出。
- Omni prompt reference helper 有测试覆盖。
- 多镜头 `multi_prompt` 有测试覆盖。
- Elements helper 存在并能记录 element metadata。
- Elements helper 不进入 registry/selector。
- Account Usage helper 存在。
- Account Usage helper 不进入 registry/selector。
- Account Usage 有节流和缓存测试。
- callback_url 能在 Classic/Turbo/Omni 路径正确透传。
- callback 当前仍以 polling 为默认执行路径。
- 成本估算覆盖多参考、多结果、4k、声音等高成本参数。
- Omni paid 成功结果继续写入 `ToolResult.cost_usd`，Account Usage 可用时能记录校正信息。
- 文档和 `kling-official` skill 已更新。
- 阶段 1 的视频/图像基础测试仍通过。

## 11. 完成后进入下一阶段

只有当本阶段验收清单全部完成后，才能进入第三阶段：

```text
docs/kling-official-phase-3-media-avatar-effects.md
```

第三阶段会评估可灵官方在现有 OpenMontage capability 中还能补哪些 provider。没有现有 capability 或 pipeline 消费路径的端点默认不接。
