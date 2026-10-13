import { useMemo, useState } from "react";
import { Copy, Lightbulb } from "lucide-react";
import { toast } from "../../lib/toast";
import { PageShell } from "./PageShell";

const PROMPTS = [
  { tag: "都市爽剧", text: "落魄女婿被丈母娘羞辱三年后，以隐秘身份归来，用商业与人情双重反击。" },
  { tag: "悬疑", text: "女法医发现每具尸体都带着同一串古语，而破译者正是失踪多年的自己。" },
  { tag: "甜宠", text: "冷面总裁误把替身当成真正的青梅竹马，直到替身要离开，他才发现心动早已失控。" },
  { tag: "穿越", text: "游戏策划死后穿越进自己设计的副本，必须用策划知识通关，才能回到现实。" },
  { tag: "职场", text: "新人设计师被抢创意后反杀：她用一场直播让品牌方看到真正的创作者。" },
  { tag: "科幻", text: "记忆可交易的城市里，男主卖掉童年换工作机会，却发现买家正是未来的自己。" },
  { tag: "古风", text: "女刺客伪装成哑巴丫鬟潜入侯府，却发现侯爷早就识破，并故意留下她。" },
  { tag: "校园", text: "学渣为了追女神报名辩论社，结果被拉进一场关乎学校存亡的全国赛。" },
];

export function InspirePage({ onUsePrompt }) {
  const [filter, setFilter] = useState("全部");
  const tags = useMemo(() => ["全部", ...new Set(PROMPTS.map((p) => p.tag))], []);
  const list = filter === "全部" ? PROMPTS : PROMPTS.filter((p) => p.tag === filter);

  return (
    <PageShell
      eyebrow="Inspiration"
      title="灵感广场"
      description="精选短剧开篇点子，一键复制或带入创作 Agent / 新建项目。"
    >
      <div className="mb-4 flex flex-wrap gap-2">
        {tags.map((tag) => (
          <button
            key={tag}
            type="button"
            className={filter === tag ? "btn-primary !min-h-9 !px-3" : "btn-secondary !min-h-9 !px-3"}
            onClick={() => setFilter(tag)}
          >
            {tag}
          </button>
        ))}
      </div>
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {list.map((item) => (
          <article key={item.text} className="panel flex flex-col p-5">
            <span className="label">{item.tag}</span>
            <p className="mt-2 flex-1 text-sm leading-7 text-white/85">{item.text}</p>
            <div className="mt-4 flex gap-2">
              <button
                type="button"
                className="btn-secondary flex-1"
                onClick={async () => {
                  await navigator.clipboard.writeText(item.text);
                  toast.success("已复制灵感");
                }}
              >
                <Copy className="h-3.5 w-3.5" /> 复制
              </button>
              <button type="button" className="btn-primary flex-1" onClick={() => onUsePrompt?.(item.text)}>
                <Lightbulb className="h-3.5 w-3.5" /> 去创作
              </button>
            </div>
          </article>
        ))}
      </div>
    </PageShell>
  );
}
