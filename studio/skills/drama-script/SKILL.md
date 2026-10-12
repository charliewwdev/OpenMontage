---
name: drama-script
description: Generate multi-episode short-drama scripts and asset bibles as JSON.
---

# 分集剧本生成

根据创作需求、题材、画幅、视觉风格生成可拍摄的短剧分集剧本，并同步角色/场景/道具档案。

## 要求

- 严格生成用户指定的集数（1–10）。
- 每集 8–15 场，场号从 [1] 递增；场次之间空一行。
- 每场写清地点、时间、人物、可见动作、有效对白；避免抽象心理描写。
- 建立角色（可多造型）、空镜场景、关键道具，并标记出场集数。
- 竖屏优先人物关系与近景冲突；横屏可增加空间调度。

## 输出 JSON

```json
{
  "summary": {
    "title": "片名",
    "synopsis": "梗概",
    "genre": "题材",
    "protagonist": "",
    "background": "",
    "setting": "",
    "oneSentence": ""
  },
  "episodes": [
    { "episodeNumber": 1, "title": "第1集标题", "content": "带场号的剧本正文" }
  ],
  "characters": [
    {
      "name": "角色名",
      "role": "protagonist|antagonist|supporting",
      "gender": "unknown",
      "introduction": "",
      "voiceDescription": "",
      "looks": [
        { "name": "默认形象", "description": "外貌服装光线", "episodes": [1] }
      ]
    }
  ],
  "scenes": [
    { "name": "场景名", "description": "空间光线陈设，无人物", "episodes": [1] }
  ],
  "props": [
    { "name": "道具名", "category": "item", "description": "外形材质", "episodes": [1] }
  ]
}
```
