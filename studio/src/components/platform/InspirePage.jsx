import { useMemo, useState } from "react";
import { Copy, Lightbulb } from "lucide-react";
import { toast } from "../../lib/toast";
import { PageShell } from "./PageShell";

export function InspirePage({ config, onUsePrompt }) {
  const prompts = config?.inspirePrompts || [];
  const page = config?.pages?.inspire || {};
  const [filter, setFilter] = useState("全部");
  const tags = useMemo(() => ["全部", ...new Set(prompts.map((p) => p.tag))], [prompts]);
  const list = filter === "全部" ? prompts : prompts.filter((p) => p.tag === filter);

  return (
    <PageShell
      eyebrow={page.eyebrow || "Inspiration"}
      title={page.title || "灵感广场"}
      description={page.description || "精选短剧开篇点子。"}
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
