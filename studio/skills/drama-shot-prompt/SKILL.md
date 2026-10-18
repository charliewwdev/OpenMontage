---
name: drama-shot-prompt
description: Split a confirmed episode into SceneMixer-style segments (片段) with short beats for 3–6 min episodes.
---

# 竖屏短剧分镜（对齐 SceneMixer · 片段 → 段内分镜）

参考样片《染血玉令》与教程 [一镜怎么写](https://scenemixer.cn/guides/yi-jing-zenme-xie/)：

- **资产库先锁**：角色 / 场景 / 道具设定图；脸靠图，不靠提示词反复描五官
- **两层结构（必须）**：
  1. **片段 segment**：整集 **10–14 段**（默认 **12**）；每段 **10–15 秒**；一段 = **一次出片**（Seedance / H3）
  2. **分镜 beat**：每段内 **3–4 个节拍**；单拍多数 **2.5–6s**（对白可到 5.5s）
- **整集硬目标**：各段 `duration` 之和 **150–360 秒**（样片密度约 162s / 12 段；可写到 3–6 分钟）
- **一镜一个节拍**：推信 / 横剑 / 放匣 / 一句台词——两拍就拆两镜
- **音画同生**：对白写进镜头，说完写「闭唇」；听的人写「闭唇、唇部未动」
- **配乐单独一层**，不要用后期解说盖掉口型

## 片段层（对齐《染血玉令》工作台）

每一段先写场头，再写段内分镜：

```text
地点：场景名（@场景）
时间：清晨 / 夜 / …
天气：晨雾、冷青天光…
起始画面状态：景别——谁在左/右，道具在哪；本段机位都在轴线同一侧。
场上布景：可见陈设与局部材质。
（段尾）环境音：……
```

段内 3–4 个【分镜】秒数相加 ≈ 本段 `duration`（10–15）。

## 整集编排

1. **建立**（段 1）：远景入画 / 环境 → 拦阻或召唤
2. **冲突升级**（中段多段）：动作 → 对白（闭唇）→ 反应（无对白）→ 道具/证据
3. **权威打断 / 反转**（中后段）
4. **高潮证物 / 指控**（后段）
5. **外部事件 + 悬念定格**（末 1–2 段）：无对白特写 / 大远景收束

## 一镜标准形状（观众注意顺序）

```text
【分镜N】Xs:
承接分镜N-1（段首第一镜写「起始：」）。
景别+机位。@角色A 在画面左/中，@角色B 在画面右；谁面朝谁。
发生的那一件可见事（手/脸/身体/物件），情绪用「由X转Y」括注。
有台词则：@名字（语气括注）：台词。说完最后一个字闭唇，再跟一个微动作。
听的人：闭唇、唇部未动 / 抿唇静默。
光源写方向与种类。无对白则末尾写「无对白」。
```

### 可照抄

**反应（无对白）**

```text
【分镜4】3s: 特写。画面内仅 @朱尔斯。他低头看信，下颌绷紧。无对白。
```

**对白+闭唇（对齐《染血玉令》）**

```text
【分镜3】3s: 承接分镜2。中近景固定，画面主体为 @林晚，3/4 侧身朝画面右侧；右侧对手仅见虚化肩线。
@林晚 撑膝抬头、下颌绷紧（由喘息转硬顶）；唇部跟「我去苍梧」字音同步，重音在「取剑」。
@林晚（撑膝抬头，字字咬实，倔强压怒）：我去苍梧岭，是替宗门取剑。
说完最后一个字她闭唇。听的人抿唇静默。冷青天光自左上方斜下。
```

**道具揭示（无对白）**

```text
【分镜3】2.5s: 承接分镜2。大特写。@染血青冥剑穗 自匣缝垂出，暗褐血痕浸透丝线。无对白。
```

## 硬规则

- 画幅按项目 `ratio`（默认 9:16）。
- **一镜只一个可见动作**；换景别 = 新镜。
- **出片前一致性**：对白里的物证（疤、戒指、信、照片）必须写进该镜提示词；对白没提到的手机/屏幕不得抢画面。角色名、`@资产` 必须在本集资产库里。出片时自动改写不合格提示词。
- **一镜最多一句对白、一个说话人**。
- `dialogue`：`角色名：原话`（可空）。
- `prompt` 用标准形状；用 `@角色` / `@道具` / `@场景` 点名本集资产。
- 台词：中文约 **每秒 4–5 字**。
- 连续对手戏写 **轴线同一侧**、**承接上一镜**。
- 说完必须 **闭唇**；无对白镜写 **无对白**。
- **禁止** `8K` / `大师级` / `体积光` / `best quality`。
- 画面外的人不要 @。
- **禁止**只输出扁平超长单镜、或不写 `segments`。

## 输出 JSON（必须）

```json
{
  "segments": [
    {
      "segmentOrder": 1,
      "location": "青云宗山门外·云海石阶牌坊",
      "timeOfDay": "清晨",
      "weather": "晨雾翻涌，冷青天光",
      "openingState": "大远景低角度仰拍——……谁在左/右",
      "setDressing": "白玉石阶、牌坊铜铃……",
      "ambientSound": "云海风声，鞋底踏阶",
      "duration": 14,
      "beats": [
        {
          "beatIndex": 1,
          "sceneName": "青云宗山门外·云海石阶牌坊",
          "characters": ["林晚", "执法弟子甲"],
          "action": "一个可见动作 + 由X转Y",
          "dialogue": "",
          "prompt": "【分镜1】3s: 起始：……无对白。",
          "duration": 3
        }
      ]
    }
  ],
  "totals": {
    "segmentCount": 12,
    "beatCount": 40,
    "durationSec": 162
  }
}
```

只输出 JSON。`segments.length` ∈ [10, 14]；每段 `beats.length` ∈ [3, 4]；每段 `duration` ∈ [10, 15] 且约等于段内 beats 秒数之和。

## Runtime

出片 / 拆镜引擎读取本块。修改后无需改 Python 即可调整密度与专家复审。

```yaml
skill_id: drama-shot-prompt
segment_count_min: 10
segment_count_max: 14
segment_count_target: 12
beats_per_segment: "3-4"
segment_duration_sec: "10-15"
episode_duration_sec_min: 150
episode_duration_sec_max: 360
episode_duration_sec_target: 162
temperature: 0.35
max_tokens: 28000
expert_review:
  - id: shot-cast-coherence
    kinds: [shot, segment, video]
    fail_if_reason_contains:
      - wrong gender
      - blank frame
      - black frame
      - unrelated scenery
      - soft mushy
      - missing cast
  - id: shot-sharpness
    kinds: [shot, segment, video]
    fail_if_reason_contains:
      - out of focus
      - mushy face
      - soft protagonist
```

