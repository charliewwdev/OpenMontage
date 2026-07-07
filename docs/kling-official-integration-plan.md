# 可灵官方 API 全项目集成实施计划

状态：实施指导文档；阶段 1、阶段 2 和阶段 3 的 OpenMontage provider 接入已按本文边界落地，真实 API 验证仍需显式 live QA 或人工端到端测试。

最后核验日期：2026-07-03。

## 0. 结论

本计划的目标不是只新增一个视频工具，而是把可灵官方 API 作为 OpenMontage 的一组正式 provider 接入。实现可以分阶段，但设计必须覆盖完整官方能力族，并明确哪些能力第一阶段进入代码、哪些能力进入后续阶段。

当前已经达到指导后续实现的条件：

- 官方 API 的核心接口、模型枚举、请求字段、任务状态和结果路径已经从可灵当前官方文档 bundle 中抽取核对。
- OpenMontage 的切入点已经明确：新增 provider tool 自动接入 selector/registry，不需要重写 pipeline。
- fal.ai 现有 `kling_video` 的可复用边界已经明确：复用 OpenMontage 工具契约和落盘模式，不复用 fal.ai 队列协议。
- 分阶段实施范围、文件清单、测试门槛和验收标准已列出。

但实施前有三项硬门槛，不能作为后续 TODO 留到代码之后：

1. 重新抽取当前官方 schema chunk，并把关键字段固化为 fixture。官方文档是 SPA，同一个 build id 下资源文件名也可能漂移；本计划中的 chunk 表是核验记录，不是实现时唯一来源。
2. 所有官方可灵 provider 的 `agent_skills` 必须挂上新建的 `kling-official` skill。否则 OpenMontage 的 Layer 3 读取链路不会自动加载官方直连鉴权、任务协议、错误处理和参数注意事项。
3. 所有付费官方可灵工具必须实现非默认的成本估算策略。不能继承 `BaseTool.estimate_cost()` 的 `0.0` 默认值，让 proposal/preflight 误以为官方付费调用免费。

第一阶段建议交付：

1. 共享可灵官方 client 与任务解析器。
2. `tools/video/kling_official_video.py`：官方直连视频生成 provider。
3. `tools/graphics/kling_official_image.py`：官方直连图像生成 provider。
4. 配套 skill、provider 文档、环境变量、契约测试。

第二阶段交付 Omni/Element/Account Usage/Callback 增强；第三阶段交付音效、TTS、数字人、口型和视频特效。

阶段拆分状态：

- 阶段 1 已拆分到 `docs/kling-official-phase-1-core.md`。
- 阶段 2 已拆分到 `docs/kling-official-phase-2-omni-operations.md`，对应现有 `kling_official_video` / `kling_official_image` provider 的 Omni 深度接入、Elements helper、Account Usage helper 和 callback 透传。
- 阶段 3 已拆分到 `docs/kling-official-phase-3-media-avatar-effects.md`，并已接入 `kling_tts`、`kling_avatar`、`kling_lip_sync`；音效和视频特效保留为有记录的不接入端点。

## 1. 资料来源与核验方式

### 1.1 外部来源

- GitHub issue：`https://github.com/charliewwdev/OpenMontage/issues/249`
- GitHub issue comment：`https://github.com/charliewwdev/OpenMontage/issues/249#issuecomment-4859448877`
- 可灵鉴权：`https://kling.ai/document-api/api/get-started/authentication`
- 可灵错误码：`https://kling.ai/document-api/api/get-started/error-codes`
- 可灵并发规则：`https://kling.ai/document-api/api/get-started/concurrency-rules`
- 可灵 Callback：`https://kling.ai/document-api/api/get-started/callbacks`
- 可灵 3.0 Turbo 文生视频：`https://kling.ai/document-api/api/video/3-0-turbo/text-to-video`
- 可灵 3.0 Turbo 图生视频：`https://kling.ai/document-api/api/video/3-0-turbo/image-to-video`
- 可灵 3.0/Omni 文生视频：`https://kling.ai/document-api/api/video/3-0-omni/text-to-video`
- 可灵 3.0/Omni 图生视频：`https://kling.ai/document-api/api/video/3-0-omni/image-to-video`
- 可灵 Video Omni：`https://kling.ai/document-api/api/video/3-0-omni/video-omni`
- 可灵图像生成：`https://kling.ai/document-api/api/image/3-0-omni/image-generation`
- 可灵 Image Omni：`https://kling.ai/document-api/api/image/3-0-omni/image-omni`
- 可灵音效：`https://kling.ai/document-api/api/video/audio-generation/text-to-audio`
- 可灵数字人：`https://kling.ai/document-api/api/video/avatar`
- 可灵口型：`https://kling.ai/document-api/api/video/lip-sync`
- 可灵账户用量：`https://kling.ai/document-api/api/assets/account-usage`

### 1.2 本地仓库来源

- `tools/base_tool.py`：BaseTool 契约、依赖检查、ToolResult。
- `tools/tool_registry.py`：自动发现、capability/provider catalog、setup offer。
- `tools/video/video_selector.py`：视频 provider 自动选择与 reference image 传参。
- `tools/graphics/image_selector.py`：图像 provider 自动选择与 edit/generate 参数透传。
- `tools/video/kling_video.py`：现有 fal.ai Kling provider，不能覆盖。
- `tools/video/_shared.py`：视频探测、部分下载/上传辅助。
- `tools/audio/tts_selector.py`、`tools/audio/music_gen.py`、`tools/avatar/talking_head.py`、`tools/avatar/lip_sync.py`：后续音频、TTS、数字人、口型能力槽位。
- `.agents/skills/ai-video-gen/SKILL.md`、`skills/creative/video-gen-prompting.md`、`docs/PROVIDERS.md`、`docs/ARCHITECTURE.md`、`README.md`：需要同步的文档和 agent 知识。

### 1.3 官方文档 bundle 核验

可灵文档是 SPA，页面正文和 OpenAPI schema 被拆成懒加载 chunk。2026-07-02 首次核验、2026-07-03 复核时：

- 文档站 build id：`97252498`。
- 静态资源前缀：`https://s15-kling.klingai.com/kos/s101/nlav112918/api-doc/assets/`。
- OpenAPI 渲染器：`OpenApi-BGkF3Bnu.js`。
- 路由 chunk：`DocumentNavigation-DJ6d14u_.js`。

已抽取并核验的核心 schema chunk：

| 能力 | 官方 api chunk |
|------|----------------|
| 3.0 Turbo 文生视频 | `api-87SY-xdC.js` |
| 3.0 Turbo 图生视频 | `api-BaOnwzhN.js` |
| Classic/3.0 文生视频 | `api-qwrrg0NE.js` |
| Classic/3.0 图生视频 | `api-Bg8QrOwF.js` |
| Video Omni | `api-IkDT7j6i.js` |
| 图像生成 | `api-CvIMUKGk.js` |
| Image Omni | `api-Dri5nsY7.js` |
| 文生音效 | `api-CO4SG6Ul.js` |
| 视频生音效 | `api-yfdpaPQb.js` |
| 数字人 | `api-CV_RG5n5.js` |
| TTS | `api-I0zriKMl.js` |
| 口型 | `api-VYP3S4bE.js` |
| 账户用量 | `api-CjZSPO13.js` |
| 视频特效 | `api-CE_k4fTW.js` |
| 高级元素 | `api-Bgnhdwj2.js` |

后续实现时，应把这些 schema 的关键字段固化为测试 fixture；如果可灵文档 build id 改变，先重新抽取 schema，再更新测试。

补充约束：

- 该 chunk 表只作为 2026-07-03 的审计记录。实施前必须从当前 HTML 重新定位主入口、导航 chunk 和 OpenAPI schema chunk。
- 2026-07-03 复核时，页面仍显示 `buildId=97252498`，但当前 HTML 中的导航资源名为 `document-navigation-nxVgwiS5.js`，与早先记录的 `DocumentNavigation-DJ6d14u_.js` 不一致。这说明不能只以 build id 或本表文件名判断 schema 未变化。
- P0 阶段应输出或更新 schema fixture，至少记录 `build_id`、`source_urls`、`chunk_names`、`extracted_at`、核心字段枚举和任务状态枚举。没有刷新 fixture，不进入 P1 实现。

### 1.4 范围边界

GitHub issue #249 同时提到 Kling official API 和 Volcengine Jimeng official API，维护者评论也说 “these two” 都有价值。当前用户要求是“整个项目集成可灵官方 API”，因此本文件只覆盖 Kling official API。

Jimeng/即梦需要独立计划处理，不能混进本计划：

- 鉴权不同，Jimeng 需要 Volcengine AK/SK 签名。
- provider 命名、环境变量、签名 client、模型枚举都应独立。
- 如后续实现 issue #249 的另一个 provider，应新增单独的 Jimeng 计划或 PR。

## 2. 官方 API 事实

### 2.1 鉴权与域名

官方当前文档提供两类鉴权：

| 方式 | 适用范围 | Header | 本项目决策 |
|------|----------|--------|------------|
| API Key | 文档标注适用于所有模型 | `Authorization: Bearer <API Key>` | 第一阶段采用 |
| AK/SK JWT | 文档标注适用于 3.0 及更早模型 | `Authorization: Bearer <JWT>` | 暂不实现；仅当用户账号必须使用旧鉴权时再补 |

默认环境变量：

```bash
KLING_API_KEY=...
KLING_API_BASE_URL=https://api-singapore.klingai.com
```

`KLING_API_BASE_URL` 可选。默认使用 Singapore 域名；中国大陆服务器用户可覆盖为 `https://api-beijing.klingai.com`。

所有官方直连工具都应声明：

```python
dependencies = ["env:KLING_API_KEY"]
```

这样 `provider_menu_summary()` 才能自动提示配置 `KLING_API_KEY`。

### 2.2 错误与并发

官方错误码中需要重点处理：

| HTTP | 业务码 | 含义 | 实现要求 |
|------|--------|------|----------|
| 401 | 1000-1004 | 鉴权失败或 token 无效 | 返回清晰的 `KLING_API_KEY`/Authorization 错误 |
| 429 | 1101/1102 | 欠费、资源包耗尽或过期 | 不自动重试；提示账户/资源包 |
| 403 | 1103 | 接口或模型无权限 | 不自动重试；提示模型权限 |
| 400 | 1200/1201 | 参数非法 | 暴露官方 message，便于修 prompt 或参数 |
| 404 | 1202/1203 | method/resource/model 无效 | 标记为实现或模型配置问题 |
| 429 | 1302 | 请求过快 | 可退避重试 |
| 429 | 1303 | 并发或 QPS 超资源包限制 | 可退避重试，错误文案必须说明并发槽 |
| 400 | 1301 | 内容安全策略 | 不自动重试；提示修改输入 |
| 500/503/504 | 5000-5002 | 服务端错误/维护/积压超时 | 可有限退避重试 |

并发规则要点：

- 限制作用在任务创建接口，不作用在查询接口。
- 视频任务每个任务占用 1 个并发槽。
- 任务从 `submitted` 到终态期间占用并发。
- `code=1303` 示例 message 为 `parallel task over resource pack limit`。

### 2.3 两套任务协议

可灵官方视频 API 当前至少有两套任务协议，必须分开建 parser。

| 协议 | 创建端点 | 查询端点 | 创建 ID | 成功状态 | 结果路径 |
|------|----------|----------|---------|----------|----------|
| Classic | `/v1/videos/*`, `/v1/images/*`, `/v1/audio/*` 等 | `GET /.../{id}` | `data.task_id` | `succeed` | `data.task_result.videos/images/audios[]` |
| 3.0 Turbo | `/text-to-video/kling-3.0-turbo`, `/image-to-video/kling-3.0-turbo` | `GET /tasks?task_ids=...` | `data.id` | `succeeded` | `data[0].outputs[]` |

Classic 状态值：`submitted`, `processing`, `succeed`, `failed`。

Turbo 状态值：`submitted`, `processing`, `succeeded`, `failed`。

实现上建议：

- `_parse_classic_created(data) -> task_id`
- `_parse_classic_polled(data, result_key)`
- `_parse_turbo_created(data) -> id`
- `_parse_turbo_polled(data) -> outputs`
- `_wait_for_task(...)` 根据协议选择终态和查询路径。

不要写“猜字段”的通用解析器；这会把 `task_id/id`、`succeed/succeeded`、`task_result/outputs` 混淆。

## 3. 核心 API 合约

### 3.1 Classic 文生视频

端点：

```text
POST /v1/videos/text2video
GET  /v1/videos/text2video/{id}
GET  /v1/videos/text2video?pageNum=1&pageSize=30
```

创建字段：

| 字段 | 类型 | 必填 | 值/说明 |
|------|------|------|---------|
| `model_name` | string | 否 | `kling-v1`, `kling-v1-6`, `kling-v2-master`, `kling-v2-1-master`, `kling-v2-5-turbo`, `kling-v2-6`, `kling-v3` |
| `multi_shot` | boolean | 否 | 默认 `false`；为 true 时 `prompt` 无效 |
| `shot_type` | string | 条件 | `customize`, `intelligence`；`multi_shot=true` 时必填 |
| `prompt` | string | 条件 | 普通生成时使用 |
| `multi_prompt` | array | 条件 | 多镜头分镜 |
| `negative_prompt` | string | 否 | 负向提示 |
| `sound` | string | 否 | `on`, `off`，默认 `off` |
| `cfg_scale` | float | 否 | 默认 `0.5` |
| `mode` | string | 否 | `std`, `pro`, `4k`，默认 `std` |
| `camera_control.type` | string | 否 | `simple`, `down_back`, `forward_up`, `right_turn_forward`, `left_turn_forward` |
| `aspect_ratio` | string | 否 | `16:9`, `9:16`, `1:1`，默认 `16:9` |
| `duration` | string | 否 | `"3"` 到 `"15"`，默认 `"5"` |
| `watermark_info` | object | 否 | 至少支持 `enabled` |
| `callback_url` | string | 否 | 任务回调 |
| `external_task_id` | string | 否 | 同账号唯一 |

结果路径：`data.task_result.videos[]`，每个 video 至少含 `id`, `url`, `watermark_url`, `duration`。

### 3.2 Classic 图生视频

端点：

```text
POST /v1/videos/image2video
GET  /v1/videos/image2video/{id}
GET  /v1/videos/image2video?pageNum=1&pageSize=30
```

创建字段：

| 字段 | 类型 | 必填 | 值/说明 |
|------|------|------|---------|
| `model_name` | string | 否 | `kling-v1`, `kling-v1-5`, `kling-v1-6`, `kling-v2-master`, `kling-v2-1`, `kling-v2-1-master`, `kling-v2-5-turbo`, `kling-v2-6`, `kling-v3` |
| `image` | string | 条件 | 图片 URL 或 raw base64；base64 不带 `data:image/...` 前缀 |
| `image_tail` | string | 否 | 尾帧，模型支持范围需按能力地图限制 |
| `prompt` | string | 否 | 文本提示 |
| `multi_shot`, `shot_type`, `multi_prompt` | mixed | 否/条件 | 同文生视频 |
| `negative_prompt` | string | 否 | 负向提示 |
| `element_list[].element_id` | long | 否 | 高级元素 |
| `voice_list` | array | 否 | 高级语音能力 |
| `sound` | string | 否 | `on`, `off` |
| `mode` | string | 否 | `std`, `pro`, `4k` |
| `static_mask`, `dynamic_masks` | string/array | 否 | 运动控制能力 |
| `camera_control` | object | 否 | 同文生视频 |
| `duration` | string | 否 | `"3"` 到 `"15"` |
| `watermark_info`, `callback_url`, `external_task_id` | mixed | 否 | 通用任务字段 |

结果路径：`data.task_result.videos[]`。

### 3.3 3.0 Turbo 文生视频

端点：

```text
POST /text-to-video/kling-3.0-turbo
GET  /tasks?task_ids=<id>
POST /tasks
```

创建字段：

| 字段 | 类型 | 必填 | 值/说明 |
|------|------|------|---------|
| `prompt` | string | 是 | 文本提示 |
| `settings.resolution` | string | 否 | `720p`, `1080p`，默认 `720p` |
| `settings.aspect_ratio` | string | 否 | `16:9`, `9:16`, `1:1`，默认 `16:9` |
| `settings.duration` | int | 否 | `3` 到 `15`，默认 `5` |
| `options.callback_url` | string | 否 | 回调 |
| `options.external_task_id` | string | 否 | 同账号唯一 |
| `options.watermark_info.enabled` | boolean | 否 | 默认 `false` |

创建响应：`data.id`。

查询响应：`data[]`，结果路径 `data[0].outputs[]`。

列表查询：`POST /tasks`，可按 `status` 和 `product_type` 过滤，响应路径 `data.result[]`。

### 3.4 3.0 Turbo 图生视频

端点：

```text
POST /image-to-video/kling-3.0-turbo
GET  /tasks?task_ids=<id>
POST /tasks
```

创建字段：

| 字段 | 类型 | 必填 | 值/说明 |
|------|------|------|---------|
| `contents[]` | array | 是 | 内容块 |
| `contents[].type` | string | 是 | `prompt`, `first_frame` |
| `contents[].text` | string | 否 | prompt 内容块使用 |
| `contents[].url` | string | 否 | first frame 内容块使用 |
| `settings.resolution` | string | 否 | `720p`, `1080p` |
| `settings.duration` | int | 否 | `3` 到 `15` |
| `options.callback_url`, `external_task_id`, `watermark_info.enabled` | mixed | 否 | 通用任务字段 |

创建响应：`data.id`。

查询响应：`data[]`，结果路径 `data[0].outputs[]`。

### 3.5 Video Omni

端点：

```text
POST /v1/videos/omni-video
GET  /v1/videos/omni-video/{id}
GET  /v1/videos/omni-video?pageNum=1&pageSize=30
```

创建字段：

| 字段 | 类型 | 必填 | 值/说明 |
|------|------|------|---------|
| `model_name` | string | 否 | `kling-video-o1`, `kling-v3-omni`，默认 `kling-video-o1` |
| `prompt` | string | 条件 | 可包含正负向描述 |
| `multi_shot`, `shot_type`, `multi_prompt` | mixed | 否/条件 | 多镜头 |
| `image_list[].image_url` | string | 否 | 图片参考 |
| `image_list[].type` | string | 否 | `first_frame`, `end_frame` |
| `element_list[].element_id` | long | 否 | 元素参考 |
| `video_list[].video_url` | string | 否 | 视频参考 |
| `video_list[].refer_type` | string | 否 | `feature`, `base`，默认 `base` |
| `video_list[].keep_original_sound` | string | 否 | `yes`, `no` |
| `sound` | string | 否 | `on`, `off` |
| `mode` | string | 否 | `std`, `pro`, `4k`，默认 `pro` |
| `aspect_ratio` | string | 否 | `16:9`, `9:16`, `1:1` |
| `duration` | string | 否 | `"3"` 到 `"15"` |
| `watermark_info`, `callback_url`, `external_task_id` | mixed | 否 | 通用任务字段 |

结果路径：`data.task_result.videos[]`。

### 3.6 图像生成

端点：

```text
POST /v1/images/generations
GET  /v1/images/generations/{id}
GET  /v1/images/generations?pageNum=1&pageSize=30
```

创建字段：

| 字段 | 类型 | 必填 | 值/说明 |
|------|------|------|---------|
| `model_name` | string | 否 | `kling-v1`, `kling-v1-5`, `kling-v2`, `kling-v2-new`, `kling-v2-1`, `kling-v3` |
| `prompt` | string | 是 | 正向提示，最大 2500 字符 |
| `negative_prompt` | string | 否 | 负向提示 |
| `image` | string | 否 | 参考图 URL 或 raw base64 |
| `image_reference` | string | 否 | `subject`, `face` |
| `image_fidelity` | float | 否 | 默认 `0.5` |
| `human_fidelity` | float | 否 | 默认 `0.45` |
| `element_list[].element_id` | long | 否 | 元素参考 |
| `resolution` | string | 否 | `1k`, `2k`，默认 `1k` |
| `n` | int | 否 | 默认 `1` |
| `aspect_ratio` | string | 否 | `16:9`, `9:16`, `1:1`, `4:3`, `3:4`, `3:2`, `2:3`, `21:9` |
| `watermark_info`, `callback_url`, `external_task_id` | mixed | 否 | 通用任务字段 |

结果路径：`data.task_result.images[]`，每个 image 至少含 `url`。

### 3.7 Image Omni

端点：

```text
POST /v1/images/omni-image
GET  /v1/images/omni-image/{id}
GET  /v1/images/omni-image?pageNum=1&pageSize=30
```

创建字段：

| 字段 | 类型 | 必填 | 值/说明 |
|------|------|------|---------|
| `model_name` | string | 否 | `kling-image-o1`, `kling-v3-omni`，默认 `kling-image-o1` |
| `prompt` | string | 是 | 可通过 `<<<image_1>>>` 等格式引用图片 |
| `image_list[].image` | string | 否 | 图片 URL 或 raw base64 |
| `element_list[].element_id` | long | 否 | 元素参考 |
| `resolution` | string | 否 | `1k`, `2k`, `4k` |
| `result_type` | string | 否 | `single`, `series` |
| `n` | int | 否 | 默认 `1` |
| `series_amount` | int/string | 否 | `2` 到 `9` 或 `auto` |
| `aspect_ratio` | string | 否 | `16:9`, `9:16`, `1:1`, `4:3`, `3:4`, `3:2`, `2:3`, `21:9`, `auto` |
| `watermark_info`, `callback_url`, `external_task_id` | mixed | 否 | 通用任务字段 |

结果路径：`data.task_result.images[]`。

### 3.8 音效、TTS、数字人、口型、特效

这些能力不进入第一阶段的核心交付，但需要在架构中预留映射，避免后面返工。

| 能力 | 端点 | 主要字段 | 结果路径 | OpenMontage 映射 |
|------|------|----------|----------|------------------|
| 文生音效 | `POST /v1/audio/text-to-audio` | `prompt`, `duration` | `data.task_result.audios[]` | 新增 `tools/audio/kling_audio.py`，能力可归 `music_generation` 或新增 `sound_effects` |
| 视频生音效 | `POST /v1/audio/video-to-audio` | `video_id` 或 `video_url`, `sound_effect_prompt`, `bgm_prompt`, `asmr_mode` | `data.task_result.audios[]`，并可能返回 videos | `tools/audio/kling_audio.py`，适合后期配音效 |
| TTS | `POST /v1/audio/tts` | `text`, `voice_id`, `voice_language`=`zh/en`, `voice_speed` | `data.task_result.audios[]` | 新增 `tools/audio/kling_tts.py`，接入 `tts_selector` |
| 数字人 | `POST /v1/videos/avatar/image2video` | `image`, `audio_id` 或 `sound_file`, `prompt`, `mode`=`std/pro` | `data.task_result.videos[]` | 新增 `tools/avatar/kling_avatar.py` |
| 口型识别 | `POST /v1/videos/identify-face` | `video_id` 或 `video_url` | `data.session_id`, face 信息 | `tools/avatar/kling_lip_sync.py` 的前置步骤 |
| 口型生成 | `POST /v1/videos/advanced-lip-sync` | `session_id`, `face_choose[]`, `audio_id` 或 `sound_file` | `data.task_result.videos[]` | 新增 `tools/avatar/kling_lip_sync.py` |
| 视频特效 | `POST /v1/videos/effects` | `effect_scene`, `input.image/images` | `data.task_result.videos[]` | 新增 `tools/video/kling_effects.py`，不要混入通用视频生成 |
| 账户用量 | `GET /account/costs` | `start_time`, `end_time`, `resource_pack_name` | `data.resource_pack_subscribe_infos[]` | 新增诊断工具或 setup preflight |
| 高级元素 | `/v1/general/advanced-*elements` | 元素创建、查询、删除 | element/task 信息 | 新增 `tools/kling_elements.py` 或 client 管理接口 |

## 4. OpenMontage 切入点

### 4.1 不改 pipeline，优先新增 provider

OpenMontage 的 selector 已经按 capability 自动发现 provider：

- 视频：`tools/video/video_selector.py` 调 `registry.get_by_capability("video_generation")`。
- 图像：`tools/graphics/image_selector.py` 调 `registry.get_by_capability("image_generation")`。
- TTS：`tools/audio/tts_selector.py` 调 `registry.get_by_capability("tts")`。

因此官方可灵第一阶段只需要新增具体 BaseTool 子类，不需要改 pipeline manifest。

### 4.2 命名规则

不能覆盖现有 `tools/video/kling_video.py`。

现有工具：

| 文件 | tool name | provider | API |
|------|-----------|----------|-----|
| `tools/video/kling_video.py` | `kling_video` | `kling` | fal.ai |

新增官方工具建议：

| 文件 | tool name | provider | capability |
|------|-----------|----------|------------|
| `tools/video/kling_official_video.py` | `kling_official_video` | `kling_official` | `video_generation` |
| `tools/graphics/kling_official_image.py` | `kling_official_image` | `kling_official` | `image_generation` |
| `tools/audio/kling_tts.py` | `kling_tts` | `kling_official` | `tts` |
| `tools/audio/kling_audio.py` | `kling_audio` | `kling_official` | `music_generation` 或新 `sound_effects` |
| `tools/avatar/kling_avatar.py` | `kling_avatar` | `kling_official` | `avatar` |
| `tools/avatar/kling_lip_sync.py` | `kling_lip_sync` | `kling_official` | `avatar` |
| `tools/video/kling_effects.py` | `kling_effects` | `kling_official` | `video_generation` 或 `video_post`，建议独立讨论 |

`provider="kling_official"` 是为了避免和 fal.ai 版 `provider="kling"` 冲突。selector 的 `preferred_provider` 是按 provider 字符串匹配的；如果两个视频工具都叫 `kling`，用户无法稳定指定官方直连还是 fal.ai 网关。

### 4.3 共享 client 位置

建议新增：

```text
tools/_kling/
├── __init__.py
├── client.py
├── schemas.py
├── media.py
└── errors.py
```

职责：

- `client.py`
  - 读取 `KLING_API_KEY`、`KLING_API_BASE_URL`。
  - 统一 `Authorization: Bearer ...` 和 JSON headers。
  - `post_json`, `get_json`, `download_url`。
  - `create_task`, `poll_classic_task`, `poll_turbo_task`。
- `schemas.py`
  - 模型枚举、协议枚举、状态常量。
  - `ClassicTaskResult`, `TurboTaskResult` 这类轻量 dataclass。
- `media.py`
  - 本地图片转 raw base64，去掉 data URI 前缀。
  - URL/base64 输入标准化。
  - 下载图片/音频/视频到 output_path。
- `errors.py`
  - `KlingAPIError`，包含 `code`, `message`, `request_id`, `http_status`。
  - `is_retryable_kling_error()`。

不建议把这些放在 `tools/video/_shared.py`，因为图像、音频、TTS、头像也会使用。

### 4.4 fal.ai 现有 Kling 的复用边界

结论：具备抽离、复用一部分代码的可能，但只能复用 OpenMontage 层的 provider 骨架，不能复用 fal.ai 协议层。

可复用：

- `BaseTool` 契约字段：`name`, `version`, `capability`, `provider`, `dependencies`, `input_schema`, `supports`, `best_for`, `fallback_tools`。
- `ResourceProfile`, `RetryPolicy`, `idempotency_key_fields`, `side_effects`, `user_visible_verification`。
- `ToolResult` 返回结构：`data.output`, `data.output_path`, `artifacts`, `cost_usd`, `duration_seconds`, `model`。
- `tools/video/_shared.py::probe_output()`。
- output_path 的目录创建、下载落盘、artifact 返回模式。
- selector 传参语义：`prompt`, `operation`, `duration`, `aspect_ratio`, `reference_image_url`, `reference_image_path`。
- provider 文档/agent skill 的组织方式。

不可复用：

- `Authorization: Key {FAL_KEY}`；官方是 `Authorization: Bearer {KLING_API_KEY}`。
- `https://queue.fal.run/fal-ai/...`。
- fal.ai `status_url` / `response_url`。
- fal.ai 状态 `COMPLETED`, `FAILED`, `CANCELLED`。
- fal.ai 结果路径 `data["video"]["url"]`。
- fal.ai endpoint path：`kling-video/{variant}/{operation}`。
- `upload_image_fal()`，官方可直接接收图片 URL 或 raw base64。
- fal.ai 成本估算。

建议抽离的 provider-neutral helper：

| helper | 建议位置 | 复用方 |
|--------|----------|--------|
| `download_binary(url, output_path, timeout)` | `tools/_media/download.py` 或 `tools/_kling/media.py` 第一阶段局部实现 | 官方视频、图像、音频 |
| `ensure_parent(output_path)` | 同上 | 所有 API provider |
| `image_file_to_raw_base64(path)` | `tools/_kling/media.py` | 官方 I2V、Image、Avatar |
| `strip_data_uri_prefix(value)` | `tools/_kling/media.py` | 所有图片/音频 base64 输入 |

短期为了降低改动面，可以先在 `tools/_kling/media.py` 实现，不改现有 fal.ai 工具。等官方可灵、后续其它 provider 都稳定后，再考虑抽到更通用的 `tools/_media/`。

### 4.5 selector 参数注意事项

`video_selector.py` 有一个重要行为：

```python
if operation == "image_to_video" and reference_image_path:
    if "image_url" in selected_tool.input_schema.properties:
        upload_image_fal(reference_image_path)
```

因此官方视频工具第一阶段不要在 input_schema 暴露顶层 `image_url` 字段，否则 selector 会误以为需要 fal.ai 上传。

建议 schema：

- 暴露 `reference_image_url`
- 暴露 `reference_image_path`
- 内部把 `reference_image_path` 转成 raw base64 填入官方 `image`
- 内部把 `reference_image_url` 直接填入官方 `image`
- 需要尾帧时使用 `reference_tail_image_url/path` 或 `image_tail_url/path`

图像 selector 没有 fal.ai 自动上传逻辑，可以暴露 `image_url`, `image_path`, `image_urls`, `image_paths`，但官方工具内部仍应统一转换为官方字段 `image` 或 `image_list`。

## 5. 第一阶段实现方案

### 5.1 共享 client

新增 `tools/_kling/client.py`。

最低接口：

```python
class KlingClient:
    def __init__(self, api_key=None, base_url=None, session=None): ...
    def post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]: ...
    def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]: ...
    def download(self, url: str, output_path: Path, timeout: int = 180) -> Path: ...
```

任务接口：

```python
def create_classic_task(path: str, payload: dict[str, Any]) -> str
def poll_classic(path: str, task_id: str, result_key: str, timeout_seconds: int, poll_interval: float) -> list[dict]
def create_turbo(path: str, payload: dict[str, Any]) -> str
def poll_turbo(task_id: str, timeout_seconds: int, poll_interval: float) -> list[dict]
```

错误规则：

- HTTP 非 2xx：读取 JSON 中 `code/message/request_id`；如果不是 JSON，也保留响应文本片段。
- 业务 `code != 0`：抛 `KlingAPIError`。
- `code=1303`：错误 message 必须包含“并发/资源包限制”。
- `code in {1302,1303,5000,5001,5002}` 可有限退避重试。

### 5.2 官方视频 provider

新增 `tools/video/kling_official_video.py`。

基础契约：

```python
class KlingOfficialVideo(BaseTool):
    name = "kling_official_video"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "video_generation"
    provider = "kling_official"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API
    dependencies = ["env:KLING_API_KEY"]
    agent_skills = ["ai-video-gen", "kling-official"]
```

第一阶段支持操作：

| OpenMontage operation | provider 参数 | 官方协议 | 端点 |
|-----------------------|---------------|----------|------|
| `text_to_video` | `api_family=classic` | Classic | `/v1/videos/text2video` |
| `image_to_video` | `api_family=classic` | Classic | `/v1/videos/image2video` |
| `text_to_video` | `api_family=turbo` | Turbo | `/text-to-video/kling-3.0-turbo` |
| `image_to_video` | `api_family=turbo` | Turbo | `/image-to-video/kling-3.0-turbo` |
| `text_to_video` | `api_family=omni` | Classic Omni | `/v1/videos/omni-video` |
| `image_to_video` | `api_family=omni` | Classic Omni | `/v1/videos/omni-video` |
| `reference_to_video` | `api_family=omni` | Classic Omni | `/v1/videos/omni-video` |

`video_selector` 当前的标准 operation 只有 `text_to_video`、`image_to_video`、`reference_to_video`、`rank`。因此 Turbo 和 Omni 都不应设计成 selector 层的新 operation；应由官方 provider 的 `api_family` 选择协议。

如果直接调用 `kling_official_video`，可以额外接受 provider-specific 的 `operation="omni_video"` 作为别名；但 selector 路径必须保持标准 operation。

建议 input_schema：

```python
{
  "required": ["prompt"],
  "properties": {
    "prompt": {"type": "string"},
    "operation": {
      "enum": [
        "text_to_video",
        "image_to_video",
        "reference_to_video"
      ],
      "default": "text_to_video"
    },
    "api_family": {
      "enum": ["classic", "turbo", "omni"],
      "default": "classic",
      "description": "Official Kling protocol family. Selector-compatible operations stay text_to_video/image_to_video; this field chooses Classic, Turbo, or Omni."
    },
    "model_name": {
      "enum": [
        "kling-v1",
        "kling-v1-5",
        "kling-v1-6",
        "kling-v2-master",
        "kling-v2-1",
        "kling-v2-1-master",
        "kling-v2-5-turbo",
        "kling-v2-6",
        "kling-v3",
        "kling-video-o1",
        "kling-v3-omni"
      ],
      "default": "kling-v3"
    },
    "duration": {"enum": ["3","4","5","6","7","8","9","10","11","12","13","14","15"], "default": "5"},
    "aspect_ratio": {"enum": ["16:9","9:16","1:1"], "default": "16:9"},
    "resolution": {"enum": ["720p","1080p"], "default": "720p"},
    "mode": {"enum": ["std","pro","4k"], "default": "std"},
    "sound": {"enum": ["on","off"], "default": "off"},
    "negative_prompt": {"type": "string"},
    "reference_image_url": {"type": "string"},
    "reference_image_path": {"type": "string"},
    "reference_tail_image_url": {"type": "string"},
    "reference_tail_image_path": {"type": "string"},
    "image_list": {"type": "array"},
    "video_list": {"type": "array"},
    "element_list": {"type": "array"},
    "camera_control": {"type": "object"},
    "watermark": {"type": "boolean", "default": False},
    "callback_url": {"type": "string"},
    "external_task_id": {"type": "string"},
    "output_path": {"type": "string"}
  }
}
```

注意：

- `supports` 至少声明 `{"text_to_video": True, "image_to_video": True, "reference_to_video": True, "reference_image": True, "negative_prompt": True, "aspect_ratio": True}`。这样 selector 和 scoring 不需要只靠 schema 字段猜能力。
- 顶层不要暴露 `image_url`，避免触发 `video_selector` 的 fal.ai 自动上传。
- `model_variant` 可兼容老 fal.ai 工具，但官方工具内部主字段应是 `model_name`。
- 对 OpenMontage 传入的 `duration` 字符串，Turbo payload 需要转成 int。
- Classic 默认建议 `model_name="kling-v3"`，Turbo 不需要 `model_name`。
- `aspect_ratio` 只发送给官方 schema 支持的端点：Classic 文生视频、Turbo 文生视频、Video Omni。Classic 图生视频和 Turbo 图生视频当前 schema 未列出 `aspect_ratio`，不要盲目发送。
- `operation=image_to_video` 如果没有 reference image，应返回参数错误，不要退回文生视频。
- P1 应同步在 `video_selector.input_schema` 增加可选透传字段 `api_family`, `model_name`, `mode`, `sound`, `watermark`。selector 当前不会剥离未知字段，但 schema 不声明会降低 agent 可发现性，也不利于后续 contract 测试。
- `agent_skills` 必须同时包含 `ai-video-gen` 和 `kling-official`。前者提供通用视频生成提示结构，后者提供官方直连 API 的鉴权、任务协议、错误码、字段限制和成本治理注意事项。
- 必须重写 `estimate_cost()`。如果官方价格无法稳定映射到美元，仍要返回保守估算并在结果或 dry-run metadata 中标明 `cost_estimate_confidence="low"`；禁止静默返回 `0.0`。

输出：

- 下载第一个无水印 `url` 到 `output_path`。
- 返回 `provider="kling_official"`、`model=model_name 或 kling-3.0-turbo`、`task_id`、`operation`、`output_path`。
- 视频调用 `probe_output(output_path)`。

### 5.3 官方图像 provider

新增 `tools/graphics/kling_official_image.py`。

基础契约：

```python
class KlingOfficialImage(BaseTool):
    name = "kling_official_image"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "image_generation"
    provider = "kling_official"
    runtime = ToolRuntime.API
    dependencies = ["env:KLING_API_KEY"]
    agent_skills = ["kling-official"]
```

第一阶段支持：

| image_selector 语义 | provider 参数 | 官方端点 |
|--------------------|---------------|----------|
| `generation_mode=generate` | `api_family=generation` | `/v1/images/generations` |
| `generation_mode=edit` 或有 `image_url/image_path` | `api_family=generation` | `/v1/images/generations`，填 `image` + `image_reference` |
| `generation_mode=generate/edit` | `api_family=omni` | `/v1/images/omni-image` |

`image_selector` 当前 `operation` 只有 `generate` 和 `rank`，编辑语义由 `generation_mode=edit` 和图片输入触发。因此不要把 `operation="omni"` 作为 selector 层约定；Omni 应由 `api_family=omni` 表达。直接调用 provider 时可以兼容 `operation="omni"`，但 selector 文档和测试应使用 `api_family`。

建议 input_schema：

```python
{
  "required": ["prompt"],
  "properties": {
    "prompt": {"type": "string"},
    "negative_prompt": {"type": "string"},
    "operation": {"enum": ["generate"], "default": "generate"},
    "generation_mode": {"enum": ["generate", "edit"], "default": "generate"},
    "api_family": {"enum": ["generation", "omni"], "default": "generation"},
    "model_name": {
      "enum": ["kling-v3", "kling-v2-1", "kling-v2-new", "kling-image-o1", "kling-v3-omni"],
      "default": "kling-v3"
    },
    "image_url": {"type": "string"},
    "image_path": {"type": "string"},
    "image_urls": {"type": "array", "items": {"type": "string"}},
    "image_paths": {"type": "array", "items": {"type": "string"}},
    "image_reference": {"enum": ["subject", "face"]},
    "image_fidelity": {"type": "number", "default": 0.5},
    "human_fidelity": {"type": "number", "default": 0.45},
    "resolution": {"enum": ["1k", "2k", "4k"], "default": "1k"},
    "aspect_ratio": {"enum": ["16:9","9:16","1:1","4:3","3:4","3:2","2:3","21:9","auto"], "default": "16:9"},
    "n": {"type": "integer", "default": 1},
    "result_type": {"enum": ["single", "series"], "default": "single"},
    "series_amount": {"type": "string"},
    "element_list": {"type": "array"},
    "watermark": {"type": "boolean", "default": False},
    "callback_url": {"type": "string"},
    "external_task_id": {"type": "string"},
    "output_path": {"type": "string"}
  }
}
```

输出：

- `supports` 至少声明 `{"text_to_image": True, "image_edit": True, "negative_prompt": True, "aspect_ratio": True}`，并在 `best_for` 中说明官方 Kling 适合角色/主体一致性和 Omni 多参考图。
- 下载 `data.task_result.images[]` 中的图片。
- 如果 `n > 1` 或 `result_type=series`，`artifacts` 返回全部图片路径，`data.output_path` 指向第一张。
- 统一返回 `format`，根据 URL 或响应 Content-Type 判断扩展名，默认 `.png`。
- P1 应同步在 `image_selector.input_schema` 增加可选透传字段 `api_family`, `model_name`, `image_reference`, `image_fidelity`, `human_fidelity`, `result_type`, `series_amount`, `watermark`。否则 selector 仍能透传未知字段，但 agent 从 schema 看不到这些官方能力。
- `agent_skills` 必须包含 `kling-official`。不要只依赖现有 FLUX/BFL 图像 skill，因为官方可灵图像生成的鉴权、任务轮询、参考图字段和结果路径不同。
- 必须重写 `estimate_cost()`，并在 contract 测试中防止继承 `BaseTool` 的免费默认值。

### 5.4 文档和 skill 更新

第一阶段必须同步：

- `.env.example`
  - 增加 `KLING_API_KEY=`
  - 增加 `KLING_API_BASE_URL=`
- `README.md`
  - provider key 列表加入官方可灵。
  - 明确 fal.ai Kling 和 official Kling 是两个路径。
- `docs/PROVIDERS.md`
  - 新增 “Kling Official” 小节。
  - provider summary 表加入 `KLING_API_KEY`。
- `docs/ARCHITECTURE.md`
  - API key 映射表加入官方可灵。
- `.agents/skills/ai-video-gen/SKILL.md`
  - metadata `env_any` 加入 `KLING_API_KEY`。
  - provider 表加入官方可灵直连。
  - 提示：fal.ai Kling 和 official Kling 不同。
- `skills/creative/video-gen-prompting.md`
  - 加入官方可灵适用场景和参数注意事项。
- `skills/INDEX.md`
  - 在视频/图像生成相关说明中标出 `kling-official` 作为官方直连 Layer 3 skill。
- 新增 `.agents/skills/kling-official/SKILL.md`
  - 包含 prompt、模型、参数、官方任务状态、错误处理注意事项。
  - 后续 `kling_official_video`、`kling_official_image` 可引用它。

### 5.5 付费成本治理

官方可灵是付费 API，P1 不能让成本治理依赖人工记忆。

实现要求：

- `kling_official_video.estimate_cost()` 和 `kling_official_image.estimate_cost()` 必须显式实现，不能继承 `BaseTool` 的 `0.0` 默认值。
- 如果官方价格随资源包、区域、模型权限变化，工具应采用保守估算，并在 `dry_run()` 或成功结果 `data` 中记录 `cost_estimate_confidence` 和估算依据。
- `ToolResult.cost_usd` 应来自同一估算函数或官方返回的实际计费信息；如果后续 Account Usage 接入能拿到实际用量，应优先用实际用量 reconciled cost。
- proposal/preflight 中展示成本时必须说明官方可灵为 paid API；默认不启用 `4k`、声音、多结果或批量生成。
- contract 测试必须断言默认视频/图像输入的 `estimate_cost()` 不是静默 `0.0`，除非该工具明确返回可审计的免费额度/未知成本标记。

## 6. 第二阶段实现方案

第二阶段做增强能力，不阻塞基础视频/图像 provider。

### 6.1 Callback 支持

目标：

- 允许工具透传 `callback_url`。
- 若 OpenMontage 后续有本地/远端 callback receiver，再把 task state 写入 project artifacts。

当前没有 callback receiver 时：

- 工具仍以 polling 为主。
- `callback_url` 只是透传给官方 API。
- 文档必须说明 callback 是可选高级功能。

### 6.2 Account Usage 诊断

新增诊断工具候选：

```text
tools/kling_account_usage.py
```

或放在：

```text
tools/_kling/account.py
```

端点：`GET /account/costs`。

字段：`start_time`, `end_time`, `resource_pack_name`。

用途：

- setup preflight：检查资源包余额。
- 错误 `1101/1102` 后给出更清楚的诊断。

注意：官方说明该接口 QPS <= 1，应做本地节流。

### 6.3 Elements 管理

端点：

- `POST /v1/general/advanced-custom-elements`
- `GET /v1/general/advanced-custom-elements/{id}`
- `GET /v1/general/advanced-custom-elements`
- `GET /v1/general/advanced-presets-elements`
- `POST /v1/general/delete-elements`

建议不做成常规生成 provider，而是做“资源管理工具”：

```text
tools/kling_elements.py
```

用途：

- 创建并查询自定义角色/物体/声音元素。
- 为 Video Omni 和 Image Omni 提供 `element_id`。
- 把生成的 element metadata 写入项目 artifacts，便于复用。

### 6.4 Omni 深度接入

第一阶段 `api_family=omni` 的视频/图像路径可以只支持基础字段。

第二阶段补：

- `image_list` 多图引用。
- `video_list` 视频引用。
- `element_list` 元素引用。
- prompt 中 `<<<image_1>>>` 这类引用规则的 helper。
- 多镜头 `multi_prompt` schema。
- 结果中多媒体类型筛选。

## 7. 第三阶段实现方案

### 7.1 可灵 TTS

新增 `tools/audio/kling_tts.py`：

- capability：`tts`
- provider：`kling_official`
- 端点：`POST /v1/audio/tts`
- 字段：`text`, `voice_id`, `voice_language`, `voice_speed`
- 结果：`data.task_result.audios[]`

接入后 `tts_selector` 自动发现；需要测试 provider ranking 和 preferred_provider。

### 7.2 可灵音效

新增 `tools/audio/kling_audio.py`：

- `text_to_audio`：`POST /v1/audio/text-to-audio`
- `video_to_audio`：`POST /v1/audio/video-to-audio`

能力归属需要实施前定一次：

- 如果只做短音效，建议新增 capability `sound_effects` 并同步 skill index。
- 如果要快速接入，可暂归 `music_generation`，但必须在 `best_for/not_good_for` 说明它不是长音乐生成。

### 7.3 可灵数字人

新增 `tools/avatar/kling_avatar.py`：

- capability：`avatar`
- provider：`kling_official`
- 端点：`POST /v1/videos/avatar/image2video`
- 字段：`image`, `audio_id` 或 `sound_file`, `prompt`, `mode`
- 结果：`data.task_result.videos[]`

与本地 `talking_head.py` 并存。官方工具适合云端高质量数字人；本地工具适合无 API 成本和可控离线运行。

### 7.4 可灵口型

新增 `tools/avatar/kling_lip_sync.py`：

流程：

1. `POST /v1/videos/identify-face`，输入 `video_id` 或 `video_url`。
2. 用户或自动策略选择 `face_id`。
3. `POST /v1/videos/advanced-lip-sync`，输入 `session_id`, `face_choose[]`。
4. 轮询 `/v1/videos/advanced-lip-sync/{id}`。
5. 下载 `data.task_result.videos[]`。

注意：face 选择可能需要人工确认；默认可选择最大/最居中的 face，但计划中要保留人工选择出口。

### 7.5 可灵视频特效

新增 `tools/video/kling_effects.py`：

- 端点：`POST /v1/videos/effects`
- 字段：`effect_scene`, `input.image/images`
- 结果：`data.task_result.videos[]`

该能力不是通用视频生成，不应让 `video_selector` 在普通 text_to_video 场景误选。建议：

- capability 使用 `video_post` 或新增 `video_effects`。
- 如果必须挂在 `video_generation`，则 `_tool_selectable` 需要按 operation 严格过滤。

## 8. 测试计划

第一阶段最低测试：

### 8.1 client 单元测试

新增 `tests/contracts/test_kling_official_client.py`。

覆盖：

- 未设置 `KLING_API_KEY` 时工具不可用。
- 设置 `KLING_API_KEY` 后 headers 是 `Authorization: Bearer ...`。
- base URL 默认 `https://api-singapore.klingai.com`。
- `KLING_API_BASE_URL` 可覆盖。
- `code != 0` 抛 `KlingAPIError`，保留 `code/message/request_id`。
- `code=1303` 被识别为可重试并发错误。
- Classic create 解析 `data.task_id`。
- Classic poll 成功解析 `data.task_result.videos/images/audios[]`。
- Turbo create 解析 `data.id`。
- Turbo poll 成功解析 `data[0].outputs[]`。
- schema fixture 包含 `build_id`、`source_urls`、`chunk_names`、`extracted_at` 和核心枚举；如果当前官方 HTML 的 build id 或 chunk 名与 fixture 不一致，测试应提示先刷新 fixture。

### 8.2 视频 provider 测试

新增 `tests/contracts/test_kling_official_video.py`。

覆盖：

- registry 能发现 `kling_official_video`。
- `capability="video_generation"`，`provider="kling_official"`。
- input_schema 不包含顶层 `image_url`。
- `operation=text_to_video, api_family=classic` 构造 `/v1/videos/text2video` payload。
- `operation=image_to_video, api_family=classic` 使用 `reference_image_url/path` 构造官方 `image` 字段。
- `operation=text_to_video, api_family=turbo` 构造 `prompt/settings/options`。
- `operation=image_to_video, api_family=turbo` 构造 `contents[]`。
- `operation=reference_to_video, api_family=omni` 构造 `video_list[]` 或多参考输入。
- 成功后下载视频、返回 artifact、调用 `probe_output`。
- `video_selector` 用 `preferred_provider="kling_official"` 能选中官方工具。
- `reference_image_path` 不触发 `upload_image_fal()`。
- `video_selector.input_schema` 暴露 `api_family` 等官方透传字段，且不会破坏其它 provider。
- `agent_skills` 包含 `kling-official`。
- `estimate_cost()` 对默认 paid 输入不返回静默 `0.0`，并记录估算置信度或依据。

### 8.3 图像 provider 测试

新增 `tests/contracts/test_kling_official_image.py`。

覆盖：

- registry 能发现 `kling_official_image`。
- `capability="image_generation"`，`provider="kling_official"`。
- generate payload 使用 `/v1/images/generations`。
- edit payload 将 `image_path` 转 raw base64。
- `api_family=omni` payload 使用 `/v1/images/omni-image` 和 `image_list[]`。
- 多图片结果全部写入 artifacts。
- `image_selector` 用 `preferred_provider="kling_official"` 能选中官方工具。
- `image_selector.input_schema` 暴露 `api_family` 等官方透传字段，且不会破坏其它 provider。
- `agent_skills` 包含 `kling-official`。
- `estimate_cost()` 对默认 paid 输入不返回静默 `0.0`，并记录估算置信度或依据。

### 8.4 文档/skill 测试

若仓库已有 contract 测试：

- provider catalog 包含 `kling_official`。
- docs provider table 包含 `KLING_API_KEY`。
- `.agents/skills/ai-video-gen/SKILL.md` metadata `env_any` 包含 `KLING_API_KEY`。
- `.agents/skills/kling-official/SKILL.md` 存在，且官方可灵 provider 的 `agent_skills` 引用它。
- `skills/INDEX.md` 或等价索引能让后续 agent 发现官方直连 skill。
- `docs/kling-official-integration-plan.md` 中列出的模型枚举与测试 fixture 保持一致。

### 8.5 付费 API 测试

默认不在 CI 中打真实可灵 API。

可选新增手工 QA：

```bash
RUN_KLING_LIVE_TESTS=1 KLING_API_KEY=... pytest tests/qa/test_kling_official_live.py
```

真实调用只做低成本 smoke：

- 文生图 1 张。
- 文生视频最短时长 3s 或 5s。
- 不跑批量、不跑 4k、不默认开声音。

## 9. 实施顺序

### P0：准备与保护

1. 创建分支。
2. 确认工作区未覆盖用户改动。
3. 安装/确认 Python 依赖，尤其是 `requests`。
4. 重新抽取当前官方 schema chunk，新建或更新官方 schema fixture。
5. 写 client/parser 测试，先红后绿。

### P1：核心视频与图像

1. 新增 `tools/_kling/` client、media、errors。
2. 新增 `kling_official_video`。
3. 新增 `kling_official_image`。
4. 补 selector/registry contract 测试。
5. 补 docs 和 skill。
6. 跑相关 contract 测试。

### P2：Omni、元素、账户、callback

1. 强化 Omni payload builder。
2. 新增 elements 管理。
3. 新增 account usage 查询。
4. 增加 callback_url 透传文档和 artifacts 记录。

### P3：音频、TTS、数字人、口型、特效

1. 新增 `kling_tts` 并接入 `tts_selector`。
2. 新增 `kling_audio`。
3. 新增 `kling_avatar`。
4. 新增 `kling_lip_sync`。
5. 新增 `kling_effects` 或明确不纳入 selector。
6. 为每个工具补 skill 和 contract 测试。

## 10. 验收标准

第一阶段完成标准：

- `registry.support_envelope()` 能看到 `kling_official_video` 和 `kling_official_image`。
- 未设置 `KLING_API_KEY` 时两个工具状态为 `UNAVAILABLE`，setup offer 指向 `KLING_API_KEY`。
- 设置 `KLING_API_KEY` 时两个工具状态为 `AVAILABLE`。
- `video_selector` 可通过 `preferred_provider="kling_official"` 选中官方视频工具。
- `image_selector` 可通过 `preferred_provider="kling_official"` 选中官方图像工具。
- `kling_video` fal.ai 版本行为不变。
- 官方视频工具没有顶层 `image_url` schema，避免 fal.ai 上传误触发。
- Classic/Turbo 两套任务 parser 均有 fixture 覆盖。
- schema fixture 已按当前官方 HTML/chunk 重新抽取；不能只沿用本计划中的旧 chunk 文件名。
- 两个官方 provider 的 `agent_skills` 都包含 `kling-official`。
- 两个官方 provider 都实现非默认 `estimate_cost()`，不会把 paid API 静默报告为 `0.0` 成本。
- 图像结果、多结果 artifacts 有测试覆盖。
- README、docs、skill 中明确 fal.ai Kling 与 official Kling 的差异。

全项目集成完成标准：

- 官方可灵每个主要能力族都有明确实现或明确不接入理由。
- 视频、图像、TTS、音效、数字人、口型、特效、元素、账户用量均有对应设计和测试策略。
- selector 不会在不适合的 operation 中误选特效、口型、音效工具。
- 付费调用默认不进 CI；live QA 需要显式环境变量开启。
- 所有新增工具都遵守 OpenMontage 的 BaseTool 契约、artifact 路径和项目目录约定。

## 11. 风险与处理

| 风险 | 影响 | 处理 |
|------|------|------|
| 官方文档 schema 更新 | 字段/模型变化 | schema fixture 固化；实现前重新抽取 build chunk |
| fal.ai 与 official provider 名称混淆 | selector 误选 | official provider 固定 `kling_official` |
| `reference_image_path` 被上传到 fal.ai | 错误依赖 `FAL_KEY` | 官方视频 schema 不暴露顶层 `image_url` |
| 图片/音频 URL 30 天清理 | artifact 失效 | 生成后立即下载到项目目录 |
| 账户无模型权限 | 真实调用失败 | 错误 `1103` 明确提示模型权限 |
| 并发槽耗尽 | 任务创建失败 | `1303` 退避和明确错误 |
| 4k/声音/Omni 成本高 | 费用不可控 | 默认不开高成本能力；执行前按 AGENT_GUIDE 宣告工具/模型/成本 |
| 口型 face 选择不准 | 输出错误人物 | 保留人工选择或至少返回 face list |

## 12. 立即可执行的开发清单

推荐从这些文件开始：

```text
tools/_kling/__init__.py
tools/_kling/client.py
tools/_kling/errors.py
tools/_kling/media.py
tools/_kling/schemas.py
tools/video/kling_official_video.py
tools/graphics/kling_official_image.py
tests/contracts/test_kling_official_client.py
tests/contracts/test_kling_official_video.py
tests/contracts/test_kling_official_image.py
.agents/skills/kling-official/SKILL.md
```

随后更新：

```text
.env.example
README.md
docs/PROVIDERS.md
docs/ARCHITECTURE.md
.agents/skills/ai-video-gen/SKILL.md
skills/creative/video-gen-prompting.md
```

本计划到这里已经足以指导第一阶段代码实现；第二、三阶段也有明确能力边界和接口入口，可以按同一 client/parser 体系继续扩展。
