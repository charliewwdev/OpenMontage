# 可灵官方 API 集成阶段 1：核心视频与图像 Provider

状态：实施指导文档。

来源：从 `docs/kling-official-integration-plan.md` 拆分而来。本阶段合并原计划中的 P0「准备与保护」和 P1「核心视频与图像」。

执行顺序：必须先完成本文件，再进入 `docs/kling-official-phase-2-omni-operations.md`。

## 1. 阶段目标

本阶段的目标是让可灵官方 API 以正式 provider 形式接入 OpenMontage 的工具系统，先交付两个可用能力：

| 能力 | 文件 | tool name | provider | capability |
|------|------|-----------|----------|------------|
| 官方视频生成 | `tools/video/kling_official_video.py` | `kling_official_video` | `kling_official` | `video_generation` |
| 官方图像生成 | `tools/graphics/kling_official_image.py` | `kling_official_image` | `kling_official` | `image_generation` |

本阶段完成后，OpenMontage 应能通过 registry 自动发现这两个工具，并通过 `video_selector` / `image_selector` 在用户指定 `preferred_provider="kling_official"` 时选中官方直连路径。

本阶段不要求完整接入音频、TTS、数字人、口型、视频特效、元素管理和账户用量。这些能力只在后续阶段评估；只有能自然落入现有 OpenMontage capability 或作为 provider 内部 helper 的部分才接入。

本阶段是 provider 接入，不是新增 OpenMontage 功能面。现有 pipeline、stage director、selector、artifact schema 和 checkpoint 规则保持不变。

## 2. 不可变规则

实施时必须遵守以下规则：

- 本阶段只覆盖 Kling official API。Volcengine Jimeng/即梦不属于本计划；Jimeng 的鉴权、provider 命名、环境变量、签名 client 和模型枚举都必须单独设计，不能混进这些可灵官方工具。
- 不改 pipeline 体系。官方可灵第一阶段只新增 BaseTool provider，不新增 pipeline，不重写已有 pipeline manifest。
- 不改 pipeline stage 顺序，不新增 canonical artifact，不新增 orchestrator 状态。
- 不覆盖 `tools/video/kling_video.py`。该文件是现有 fal.ai Kling provider，行为必须保持不变。
- 官方 provider 必须统一使用 `provider="kling_official"`，不能复用 `provider="kling"`，否则 selector 无法稳定区分 fal.ai 网关和官方直连。
- 第一阶段只实现 API Key 鉴权：`Authorization: Bearer <KLING_API_KEY>`。AK/SK JWT 不进入本阶段。
- 所有官方可灵工具都必须声明 `dependencies = ["env:KLING_API_KEY"]`，使 `provider_menu_summary()` 能自动生成 setup offer。
- `KLING_API_BASE_URL` 是可选覆盖项，默认值应为 `https://api-singapore.klingai.com`。
- 所有付费官方可灵 provider 必须重写 `estimate_cost()`，不能继承 `BaseTool.estimate_cost()` 的 `0.0` 默认值。
- 所有官方可灵 provider 的 `agent_skills` 必须包含新建的 `kling-official` skill。视频工具还必须保留通用视频提示 skill，例如 `ai-video-gen`。
- 实施前必须重新抽取当前官方文档 schema chunk，并固化为测试 fixture。不能直接把原总计划中的 chunk 文件名当作当前事实。
- 官方视频工具的 input schema 不得暴露顶层 `image_url` 字段，避免 `video_selector` 误触发 fal.ai 的图片上传逻辑。
- 所有远端生成结果必须下载到 OpenMontage 的输出路径或项目 artifacts 中，不能只返回官方临时 URL。
- CI 默认不能打真实可灵付费 API。真实调用必须通过显式环境变量开启。

## 3. Pipeline 调用链

本阶段必须接入现有调用链，而不是创造新的编排路径：

```text
pipeline stage director
-> selector tool（video_selector / image_selector）
-> registry.get_by_capability(...)
-> kling_official_* provider
-> tools/_kling client/parser/media helper
-> Kling official API
-> ToolResult + artifacts
-> stage canonical artifact
-> checkpoint
```

实施含义：

- pipeline 只看到 `video_generation` / `image_generation` capability，不感知官方可灵协议细节。
- stage director 仍按现有方式调用 selector 或具体 tool，不写可灵专用编排。
- selector 只做 provider selection 和通用参数转发，不承担可灵 payload 构造。
- 官方 API 协议差异只存在于 `kling_official_video`、`kling_official_image` 和 `tools/_kling/` helper。
- 所有生成文件仍写入 stage 传入的 `output_path` 或项目目录，不写 repo root。
- 如果用户选择官方可灵，proposal/preflight 只说明 provider/model/cost，不改变 pipeline。

## 4. 准备与保护

开始写代码前先完成这些检查：

1. 创建实现分支，建议使用 `codex/` 前缀，例如 `codex/kling-official-phase-1`。
2. 查看工作区状态，确认不会覆盖用户已有改动。
3. 确认 Python 依赖可用，尤其是 HTTP 客户端依赖。优先复用仓库现有依赖；若新增依赖，必须同步依赖文件和文档。
4. 阅读这些本地文件以确认当前实现契约：
   - `tools/base_tool.py`
   - `tools/tool_registry.py`
   - `tools/video/video_selector.py`
   - `tools/graphics/image_selector.py`
   - `tools/video/kling_video.py`
   - `tools/video/_shared.py`
5. 不开始实现 provider，直到 schema fixture 刷新完成。

## 5. 官方 Schema Fixture

官方文档是 SPA，正文和 OpenAPI schema 会被拆进懒加载 chunk。同一个 build id 下资源文件名也可能变化，因此必须在实施时重新定位当前文档资源。

建议新增 fixture 路径：

```text
tests/fixtures/kling_official/schema_snapshot.json
```

fixture 至少包含：

```json
{
  "build_id": "...",
  "source_urls": ["..."],
  "chunk_names": ["..."],
  "extracted_at": "YYYY-MM-DDTHH:MM:SSZ",
  "endpoints": {},
  "models": {},
  "task_statuses": {},
  "result_paths": {},
  "core_field_enums": {}
}
```

必须固化的核心信息：

- API base URL 默认值和可覆盖环境变量。
- Classic 任务状态：`submitted`、`processing`、`succeed`、`failed`。
- Turbo 任务状态：`submitted`、`processing`、`succeeded`、`failed`。
- Classic 创建 ID 路径：`data.task_id`。
- Turbo 创建 ID 路径：`data.id`。
- Classic 结果路径：`data.task_result.videos[]`、`data.task_result.images[]`。
- Turbo 结果路径：`data[0].outputs[]`。
- 第一阶段要支持的视频模型枚举。
- 第一阶段要支持的图像模型枚举。
- `aspect_ratio`、`duration`、`resolution`、`mode`、`sound` 等核心字段枚举。

测试要求：

- 如果当前官方 HTML 的 build id、入口 chunk 或核心 schema 与 fixture 不一致，测试应提示先刷新 fixture。
- 测试不应依赖原计划中的旧 chunk 文件名。
- fixture 是实现依据之一，不是替代错误处理和 runtime 验证的借口。

## 6. 共享可灵 Client

新增目录：

```text
tools/_kling/
├── __init__.py
├── client.py
├── errors.py
├── media.py
└── schemas.py
```

### 6.1 `client.py`

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
def create_classic_task(path: str, payload: dict[str, Any]) -> str: ...
def poll_classic(path: str, task_id: str, result_key: str, timeout_seconds: int, poll_interval: float) -> list[dict]: ...
def create_turbo(path: str, payload: dict[str, Any]) -> str: ...
def poll_turbo(task_id: str, timeout_seconds: int, poll_interval: float) -> list[dict]: ...
```

实现规则：

- 从 `KLING_API_KEY` 读取默认 API Key。
- 从 `KLING_API_BASE_URL` 读取可选 base URL；未设置时使用 `https://api-singapore.klingai.com`。
- 所有请求都发送 `Authorization: Bearer <key>`。
- 所有 JSON 请求都发送明确的 JSON headers。
- HTTP 非 2xx 时尝试解析 JSON 中的 `code`、`message`、`request_id`；如果不是 JSON，保留响应文本片段。
- 业务 `code != 0` 时抛出 `KlingAPIError`。
- 下载方法负责创建父目录，返回最终 `Path`。

### 6.2 `errors.py`

新增：

```python
class KlingAPIError(Exception):
    code: str | int | None
    message: str
    request_id: str | None
    http_status: int | None
```

新增：

```python
def is_retryable_kling_error(error: KlingAPIError) -> bool: ...
```

错误处理规则：

| HTTP | 业务码 | 含义 | 行为 |
|------|--------|------|------|
| 401 | 1000-1004 | 鉴权失败或 token 无效 | 不重试，提示 `KLING_API_KEY` / Authorization |
| 429 | 1101/1102 | 欠费、资源包耗尽或过期 | 不重试，提示账户或资源包 |
| 403 | 1103 | 接口或模型无权限 | 不重试，提示模型权限 |
| 400 | 1200/1201 | 参数非法 | 不重试，暴露官方 message |
| 404 | 1202/1203 | method/resource/model 无效 | 不重试，标记实现或模型配置问题 |
| 429 | 1302 | 请求过快 | 可有限退避重试 |
| 429 | 1303 | 并发或 QPS 超资源包限制 | 可有限退避重试，错误文案必须说明并发槽 |
| 400 | 1301 | 内容安全策略 | 不重试，提示修改输入 |
| 500/503/504 | 5000-5002 | 服务端错误、维护、积压超时 | 可有限退避重试 |

退避规则：

- 只对 `1302`、`1303`、`5000`、`5001`、`5002` 做有限重试。
- 不对鉴权、余额、权限、参数、安全策略错误重试。
- 重试耗尽后保留最后一次官方错误信息。

### 6.3 `schemas.py`

放置轻量常量和 dataclass：

- Classic/Turbo 协议枚举。
- Classic/Turbo 状态常量。
- 第一阶段模型枚举。
- `ClassicTaskResult`、`TurboTaskResult` 等轻量解析结果。

不要写“猜字段”的通用任务解析器。Classic 和 Turbo 的字段名、状态值、结果路径不同，必须分开解析。

### 6.4 `media.py`

实现：

- `strip_data_uri_prefix(value)`：去掉 `data:image/...;base64,` 等前缀。
- `image_file_to_raw_base64(path)`：本地图片转 raw base64。
- `normalize_image_input(url=None, path=None)`：URL 直接返回 URL，本地路径转 raw base64。
- 下载图片/音频/视频到 output path 的共用 helper。

第一阶段可以先把这些 helper 放在 `tools/_kling/media.py`。不要为了抽象过早修改现有 fal.ai 工具。

## 7. 官方视频 Provider

新增：

```text
tools/video/kling_official_video.py
```

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

### 7.1 支持范围

| OpenMontage operation | `api_family` | 官方协议 | 端点 |
|-----------------------|--------------|----------|------|
| `text_to_video` | `classic` | Classic | `/v1/videos/text2video` |
| `image_to_video` | `classic` | Classic | `/v1/videos/image2video` |
| `text_to_video` | `turbo` | Turbo | `/text-to-video/kling-3.0-turbo` |
| `image_to_video` | `turbo` | Turbo | `/image-to-video/kling-3.0-turbo` |
| `text_to_video` | `omni` | Classic Omni | `/v1/videos/omni-video` |
| `image_to_video` | `omni` | Classic Omni | `/v1/videos/omni-video` |
| `reference_to_video` | `omni` | Classic Omni | `/v1/videos/omni-video` |

`video_selector` 的标准 operation 仍是 `text_to_video`、`image_to_video`、`reference_to_video`、`rank`。Turbo 和 Omni 不应变成 selector 层的新 operation，而应通过 `api_family` 选择。

直接调用 provider 时可以兼容 `operation="omni_video"` 作为别名，但 selector 路径不要依赖这个别名。

### 7.2 Input Schema 规则

建议字段：

```python
{
  "required": ["prompt"],
  "properties": {
    "prompt": {"type": "string"},
    "operation": {"enum": ["text_to_video", "image_to_video", "reference_to_video"], "default": "text_to_video"},
    "api_family": {"enum": ["classic", "turbo", "omni"], "default": "classic"},
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
    "duration": {"enum": ["3", "4", "5", "6", "7", "8", "9", "10", "11", "12", "13", "14", "15"], "default": "5"},
    "aspect_ratio": {"enum": ["16:9", "9:16", "1:1"], "default": "16:9"},
    "resolution": {"enum": ["720p", "1080p"], "default": "720p"},
    "mode": {"enum": ["std", "pro", "4k"], "default": "std"},
    "sound": {"enum": ["on", "off"], "default": "off"},
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

强制规则：

- 不暴露顶层 `image_url`。
- 使用 `reference_image_url` / `reference_image_path` 表达首帧。
- 使用 `reference_tail_image_url` / `reference_tail_image_path` 表达尾帧。
- `reference_image_path` 在工具内部转 raw base64，不能走 fal.ai 上传。
- `model_variant` 可以兼容老参数，但内部主字段应是 `model_name`。
- `model_name` enum 必须来自当前 schema fixture。上面的枚举是阶段 1 初始范围；如果官方 schema 更新，先更新 fixture 和 contract 测试，再更新 input schema。
- `supports` 至少声明：

```python
{
  "text_to_video": True,
  "image_to_video": True,
  "reference_to_video": True,
  "reference_image": True,
  "negative_prompt": True,
  "aspect_ratio": True
}
```

### 7.3 Payload Builder 规则

Classic 文生视频：

- 端点：`POST /v1/videos/text2video`
- 发送 `model_name`、`prompt`、`negative_prompt`、`sound`、`cfg_scale`、`mode`、`camera_control`、`aspect_ratio`、`duration`、`watermark_info`、`callback_url`、`external_task_id` 等官方支持字段。
- 默认 `model_name` 建议为 `kling-v3`。

Classic 图生视频：

- 端点：`POST /v1/videos/image2video`
- 必须有 `reference_image_url` 或 `reference_image_path`。
- 将输入转换成官方字段 `image`。
- 支持尾帧时使用官方字段 `image_tail`。
- 不要盲目发送 `aspect_ratio`，除非当前 schema 明确支持。

Turbo 文生视频：

- 端点：`POST /text-to-video/kling-3.0-turbo`
- payload 结构为 `prompt`、`settings`、`options`。
- `duration` 必须从字符串转成 int。
- `settings.resolution` 支持 `720p` / `1080p`。
- `settings.aspect_ratio` 支持 `16:9` / `9:16` / `1:1`。

Turbo 图生视频：

- 端点：`POST /image-to-video/kling-3.0-turbo`
- payload 使用 `contents[]`。
- prompt 用 `{ "type": "prompt", "text": "..." }`。
- 首帧 URL 用 `{ "type": "first_frame", "url": "..." }`。
- 如果本地图片转成 raw base64 后当前官方 schema 不支持，必须给出清晰错误或先上传到可访问 URL；不要静默走 fal.ai。
- 不要盲目发送 `aspect_ratio`，除非当前 schema 明确支持。

Video Omni：

- 端点：`POST /v1/videos/omni-video`
- 第一阶段只要求基础 `prompt`、`image_list`、`video_list`、`element_list`、`sound`、`mode`、`aspect_ratio`、`duration` 可用。
- 深度多参考、多镜头 helper 放到第二阶段。

### 7.4 输出规则

成功后：

- 下载第一个无水印 `url` 到 `output_path`。
- 返回 `provider="kling_official"`。
- 返回 `model`，Classic/Omni 用 `model_name`，Turbo 可用 `kling-3.0-turbo`。
- 返回 `task_id`、`operation`、`api_family`、`output_path`。
- 将远端 URL、下载路径、任务 ID 放入 `artifacts` 或 `data`，便于复现。
- 对视频调用 `tools/video/_shared.py::probe_output(output_path)`。

失败时：

- 参数错误返回可理解的 ToolResult error，不要让 KeyError、IndexError 泄漏。
- 官方错误要保留 `code`、`message`、`request_id`。
- `1303` 并发错误文案必须包含“并发/资源包限制”。

### 7.5 成本估算

必须实现：

```python
def estimate_cost(self, params: dict[str, Any]) -> float: ...
```

要求：

- 默认 paid 输入不能返回静默 `0.0`。
- 如果官方价格无法稳定映射美元，返回保守估算，并在 dry-run 或结果 metadata 中写入 `cost_estimate_confidence="low"`。
- 成功的 paid ToolResult 必须写入 `cost_usd`。`cost_usd` 应来自同一个 `estimate_cost()` 逻辑；如果后续 Account Usage 能提供实际用量，可在阶段 2 以后用实际用量校正。
- 默认不启用 `4k`、`sound="on"`、批量、多结果等高成本能力。
- proposal/preflight 展示成本时必须说明官方可灵是 paid API。

### 7.6 Registry Metadata

视频 provider 必须补齐 registry/provider menu 可见的元数据：

- `best_for`：说明官方可灵直连适合哪些视频生成场景。
- `not_good_for`：说明不适合的场景，例如本地离线、免费生成、非可灵模型能力。
- `install_instructions`：说明配置 `KLING_API_KEY`，不要硬编码过期 URL。
- `fallback_tools`：列出可替代的视频 provider，例如现有 fal.ai Kling 或其它视频生成工具；只作为候选，不允许静默切换。
- `supports`：至少包含文生视频、图生视频、参考输入、负向提示、宽高比能力。
- `resource_profile` / `retry_policy`：如果 BaseTool 契约已有对应字段，按 API 远端生成和长轮询任务填写。
- `idempotency_key_fields`：至少考虑 `prompt`、`operation`、`api_family`、`model_name`、`reference_image_url/path`、`duration`、`aspect_ratio`。
- `side_effects`：标记为 paid remote generation，避免 proposal/preflight 把调用当作免费本地操作。

## 8. 官方图像 Provider

新增：

```text
tools/graphics/kling_official_image.py
```

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

### 8.1 支持范围

| image_selector 语义 | `api_family` | 官方端点 |
|--------------------|--------------|----------|
| `generation_mode=generate` | `generation` | `/v1/images/generations` |
| `generation_mode=edit` 或有图片输入 | `generation` | `/v1/images/generations`，填 `image` 和 `image_reference` |
| `generation_mode=generate/edit` | `omni` | `/v1/images/omni-image` |

`image_selector` 的标准 operation 仍是 `generate` 和 `rank`。Omni 不应变成 selector 层的新 operation，应通过 `api_family=omni` 表达。

### 8.2 Input Schema 规则

建议字段：

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
      "enum": [
        "kling-v1",
        "kling-v1-5",
        "kling-v2",
        "kling-v2-new",
        "kling-v2-1",
        "kling-v3",
        "kling-image-o1",
        "kling-v3-omni"
      ],
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
    "aspect_ratio": {"enum": ["16:9", "9:16", "1:1", "4:3", "3:4", "3:2", "2:3", "21:9", "auto"], "default": "16:9"},
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

图像工具可以暴露 `image_url` / `image_path`，因为 `image_selector` 没有 fal.ai 自动上传逻辑。

`model_name` enum 必须来自当前 schema fixture。上面的枚举覆盖普通图像生成和 Image Omni 的第一阶段范围；如果官方 schema 更新，先更新 fixture 和 contract 测试，再更新 input schema。

`supports` 至少声明：

```python
{
  "text_to_image": True,
  "image_edit": True,
  "negative_prompt": True,
  "aspect_ratio": True
}
```

### 8.3 Payload Builder 规则

图像生成：

- 端点：`POST /v1/images/generations`
- 必填 `prompt`。
- 支持 `negative_prompt`、`image`、`image_reference`、`image_fidelity`、`human_fidelity`、`element_list`、`resolution`、`n`、`aspect_ratio`。
- `prompt` 长度要遵守官方限制；超限应在调用前报参数错误。

图像编辑：

- 当 `generation_mode=edit` 或存在 `image_url` / `image_path` 时走同一 generation 端点。
- `image_url` 直接填官方 `image`。
- `image_path` 转 raw base64 后填官方 `image`。
- `image_reference` 只允许官方枚举，例如 `subject`、`face`。

Image Omni：

- 端点：`POST /v1/images/omni-image`
- 支持 `image_list`、`element_list`、`resolution`、`result_type`、`n`、`series_amount`、`aspect_ratio`。
- 第一阶段只要求基础可用；复杂多图引用 helper 放到第二阶段。

### 8.4 输出规则

成功后：

- 下载 `data.task_result.images[]` 中的图片。
- `data.output_path` 指向第一张图片。
- 如果 `n > 1` 或 `result_type="series"`，`artifacts` 必须返回全部图片路径。
- 根据响应 Content-Type 或 URL 推断扩展名；无法判断时默认 `.png`。
- 返回 `provider`、`model`、`task_id`、`api_family`、`output_path`。

失败时：

- 保留官方 `code`、`message`、`request_id`。
- 参数错误应清楚说明是 prompt、参考图、分辨率、数量还是权限问题。

### 8.5 成本估算

同视频 provider：

- 必须重写 `estimate_cost()`。
- 默认 paid 输入不能静默返回 `0.0`。
- `n > 1`、`2k/4k`、`series` 应提高估算。
- 估算不确定时记录 `cost_estimate_confidence="low"`。
- 成功的 paid ToolResult 必须写入 `cost_usd`。`cost_usd` 应来自同一个 `estimate_cost()` 逻辑；如果后续 Account Usage 能提供实际用量，可在阶段 2 以后用实际用量校正。

### 8.6 Registry Metadata

图像 provider 必须补齐 registry/provider menu 可见的元数据：

- `best_for`：说明官方可灵适合主体一致性、角色参考、Omni 多参考图等场景。
- `not_good_for`：说明不适合的场景，例如本地离线、免费生成、非可灵模型能力。
- `install_instructions`：说明配置 `KLING_API_KEY`，不要硬编码过期 URL。
- `fallback_tools`：列出可替代图像 provider；只作为候选，不允许静默切换。
- `supports`：至少包含文生图、图像编辑、负向提示、宽高比能力。
- `resource_profile` / `retry_policy`：如果 BaseTool 契约已有对应字段，按 API 远端生成和长轮询任务填写。
- `idempotency_key_fields`：至少考虑 `prompt`、`api_family`、`model_name`、`image_url/path`、`aspect_ratio`、`resolution`、`n`。
- `side_effects`：标记为 paid remote generation，避免 proposal/preflight 把调用当作免费本地操作。

## 9. Selector 衔接

原则：新增官方可灵 provider 不应要求重写 selector。`video_selector` 和 `image_selector` 已经通过 registry 自动发现 provider，本阶段优先只新增 provider 和 contract 测试。

不要为了可灵专用字段改 selector 的核心选择逻辑。只有当字段属于跨 provider 的通用参数，且现有 selector 会丢弃该字段时，才允许补充 selector schema 或透传列表。

`video_selector` 当前应继续使用这些通用字段：

- `prompt`
- `operation`
- `preferred_provider`
- `allowed_providers`
- `aspect_ratio`
- `duration`
- `reference_image_path`
- `reference_image_url`
- `output_path`

`image_selector` 当前应继续使用这些通用字段：

- `prompt`
- `negative_prompt`
- `generation_mode`
- `image_url`
- `image_path`
- `image_urls`
- `image_paths`
- `preferred_provider`
- `allowed_providers`
- `aspect_ratio`
- `resolution`
- `n`
- `output_path`

要求：

- `api_family`、`model_name`、`sound`、`watermark`、`image_reference` 等可灵专用参数优先放在 provider input_schema 中，通过直接调用 provider 或 selector 的普通透传进入 provider。
- 如果 selector 当前已经透传未知字段，不要仅为“可发现性”改 selector。
- 如果必须改 selector，只能做 provider-neutral 的最小透传；不得加入可灵专用分支。
- 不能破坏其他 provider 的选择和调用。
- `video_selector` 用 `preferred_provider="kling_official"` 时必须选中官方视频工具。
- `image_selector` 用 `preferred_provider="kling_official"` 时必须选中官方图像工具。
- `reference_image_path` 不能触发 `upload_image_fal()`。

## 10. 文档和 Skill 更新

本阶段必须同步更新：

```text
.env.example
README.md
docs/PROVIDERS.md
docs/ARCHITECTURE.md
.agents/skills/ai-video-gen/SKILL.md
skills/creative/video-gen-prompting.md
skills/INDEX.md
.agents/skills/kling-official/SKILL.md
```

具体要求：

- `.env.example` 增加 `KLING_API_KEY=` 和 `KLING_API_BASE_URL=`。
- `README.md` provider key 列表加入官方可灵。
- `docs/PROVIDERS.md` 新增 “Kling Official” 小节。
- `docs/PROVIDERS.md` 明确 fal.ai Kling 和 official Kling 是两个路径。
- `docs/ARCHITECTURE.md` API key 映射表加入 `KLING_API_KEY`。
- `.agents/skills/ai-video-gen/SKILL.md` metadata `env_any` 加入 `KLING_API_KEY`。
- `skills/creative/video-gen-prompting.md` 增加官方可灵适用场景和参数注意事项。
- `skills/INDEX.md` 让后续 agent 能发现 `kling-official`。
- 新增 `.agents/skills/kling-official/SKILL.md`，覆盖鉴权、任务协议、错误处理、参数、成本治理和提示注意事项。

## 11. 测试要求

新增或更新以下测试。

### 11.1 Client 测试

建议文件：

```text
tests/contracts/test_kling_official_client.py
```

覆盖：

- 未设置 `KLING_API_KEY` 时工具不可用。
- 设置 `KLING_API_KEY` 后 headers 是 `Authorization: Bearer ...`。
- base URL 默认 `https://api-singapore.klingai.com`。
- `KLING_API_BASE_URL` 可以覆盖。
- `code != 0` 抛 `KlingAPIError`，保留 `code`、`message`、`request_id`。
- `code=1303` 被识别为可重试并发错误。
- Classic create 解析 `data.task_id`。
- Classic poll 成功解析 `data.task_result.videos/images/audios[]`。
- Turbo create 解析 `data.id`。
- Turbo poll 成功解析 `data[0].outputs[]`。
- schema fixture 包含必需字段。

### 11.2 视频 Provider 测试

建议文件：

```text
tests/contracts/test_kling_official_video.py
```

覆盖：

- registry 能发现 `kling_official_video`。
- `capability="video_generation"`。
- `provider="kling_official"`。
- input schema 不包含顶层 `image_url`。
- `operation=text_to_video, api_family=classic` 构造 `/v1/videos/text2video` payload。
- `operation=image_to_video, api_family=classic` 使用 `reference_image_url/path` 构造官方 `image` 字段。
- `operation=text_to_video, api_family=turbo` 构造 `prompt/settings/options`。
- `operation=image_to_video, api_family=turbo` 构造 `contents[]`。
- `operation=reference_to_video, api_family=omni` 构造 `video_list[]` 或基础参考输入。
- 成功后下载视频、返回 artifact、调用 `probe_output`。
- `video_selector` 用 `preferred_provider="kling_official"` 能选中官方工具。
- `reference_image_path` 不触发 `upload_image_fal()`。
- `agent_skills` 包含 `kling-official`。
- 默认 paid 输入的 `estimate_cost()` 不返回静默 `0.0`。

### 11.3 图像 Provider 测试

建议文件：

```text
tests/contracts/test_kling_official_image.py
```

覆盖：

- registry 能发现 `kling_official_image`。
- `capability="image_generation"`。
- `provider="kling_official"`。
- generate payload 使用 `/v1/images/generations`。
- edit payload 将 `image_path` 转 raw base64。
- `api_family=omni` payload 使用 `/v1/images/omni-image` 和 `image_list[]`。
- 多图片结果全部写入 artifacts。
- `image_selector` 用 `preferred_provider="kling_official"` 能选中官方工具。
- `agent_skills` 包含 `kling-official`。
- 默认 paid 输入的 `estimate_cost()` 不返回静默 `0.0`。

### 11.4 文档和 Skill 测试

若仓库已有相关 contract 测试，补充：

- provider catalog 包含 `kling_official`。
- docs provider table 包含 `KLING_API_KEY`。
- `.agents/skills/ai-video-gen/SKILL.md` metadata `env_any` 包含 `KLING_API_KEY`。
- `.agents/skills/kling-official/SKILL.md` 存在。
- 官方可灵 provider 的 `agent_skills` 引用 `kling-official`。

### 11.5 Live QA

真实调用只允许显式开启：

```bash
RUN_KLING_LIVE_TESTS=1 KLING_API_KEY=... pytest tests/qa/test_kling_official_live.py
```

live smoke 限制：

- 文生图 1 张。
- 文生视频最短时长 3s 或 5s。
- 不跑批量。
- 不跑 4k。
- 不默认开声音。

## 12. 阶段验收清单

阶段 1 完成前逐项确认：

- `registry.support_envelope()` 能看到 `kling_official_video`。
- `registry.support_envelope()` 能看到 `kling_official_image`。
- 未设置 `KLING_API_KEY` 时两个工具状态为 `UNAVAILABLE`。
- setup offer 指向 `KLING_API_KEY`。
- 设置 `KLING_API_KEY` 时两个工具状态为 `AVAILABLE`。
- `video_selector` 可通过 `preferred_provider="kling_official"` 选中官方视频工具。
- `image_selector` 可通过 `preferred_provider="kling_official"` 选中官方图像工具。
- selector 没有新增可灵专用选择分支；如有 selector 改动，必须是 provider-neutral 的最小透传。
- `tools/video/kling_video.py` fal.ai 版本行为不变。
- 官方视频工具没有顶层 `image_url` schema。
- Classic 和 Turbo 两套 parser 均有 fixture 覆盖。
- schema fixture 已按当前官方 HTML/chunk 重新抽取。
- 两个官方 provider 的 `agent_skills` 都包含 `kling-official`。
- 两个官方 provider 都实现非默认 `estimate_cost()`。
- 两个官方 provider 的 paid 成功结果都写入 `ToolResult.cost_usd`。
- 两个官方 provider 都补齐 `best_for`、`not_good_for`、`install_instructions`、`fallback_tools`、`supports` 等 registry metadata。
- 图像多结果 artifacts 有测试覆盖。
- README、docs、skill 明确 fal.ai Kling 与 official Kling 的差异。
- 相关 contract 测试通过。

## 13. 完成后进入下一阶段

只有当本阶段验收清单全部完成后，才能进入第二阶段：

```text
docs/kling-official-phase-2-omni-operations.md
```

第二阶段会在本阶段 client、parser、provider 基础上增强 Omni、Elements、Account Usage 和 Callback。
