---
name: drama-shot-prompt
description: Split a confirmed episode into Seedance-ready shot prompts with asset refs.
---

# 分镜镜头拆解

把已定稿单集剧本拆成 4–15 秒可生成视频片段，保持原剧情顺序与对白含义。

## 要求

- 把情绪转成表情、视线、动作、空间关系与可见细节。
- 每镜组织：主体、动作、景别、机位、运镜、光影、对白、环境音。
- 用 `@角色名-造型`、`@场景名`、`@道具名` 标注素材引用（仅限本集可用资产）。
- 每个镜头 duration 为 4–15 整数秒。
- 不擅自改写故事结局或人物关系。

## 输出 JSON

```json
{
  "shots": [
    {
      "shotOrder": 1,
      "sceneName": "场景名",
      "characters": ["角色名"],
      "action": "可见动作",
      "dialogue": "对白或空",
      "prompt": "完整视频提示词，含 @引用",
      "duration": 6
    }
  ]
}
```
