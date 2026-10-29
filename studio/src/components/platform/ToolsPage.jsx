import { useState } from "react";
import { ArrowRight, ArrowUp, Clapperboard, Film, Mic2, Palette, PenLine, Sparkles, Workflow } from "lucide-react";
import { PageShell } from "./PageShell";

const ICONS = {
  text: PenLine,
  visual: Palette,
  audio: Mic2,
  video: Film,
  workshop: Clapperboard,
  canvas: Workflow,
};

const DEFAULT_CATEGORIES = [
  { id: "workshop", title: "影视工坊", desc: "七步生产线主入口", nav: "workshop" },
  { id: "text", title: "文本 · 剧本", desc: "进入工坊「剧本」步", nav: "workshop", step: "script" },
  { id: "visual", title: "视觉 · 定妆", desc: "进入工坊「角色 / 场景 / 道具」", nav: "workshop", step: "character" },
  { id: "video", title: "分镜 · 视频", desc: "进入工坊「分镜」工作台", nav: "workshop", step: "storyboard" },
  { id: "audio", title: "配音", desc: "进入工坊「配音」工作台", nav: "workshop", step: "audio" },
  { id: "canvas", title: "无限画布", desc: "七步进度节点图（次级视图）", nav: "canvas" },
];

const DEFAULT_WORKFLOW = {
  title: "七步生产线",
  description: "与影视工坊同一套步骤：剧本 → 角色 → 场景 → 道具 → 分镜 → 配音 → 剪辑",
  steps: [
    { title: "剧本", desc: "故事与分集定稿", step: "script" },
    { title: "角色", desc: "人物造型定妆", step: "character" },
    { title: "场景", desc: "空间与光线", step: "scene" },
    { title: "道具", desc: "关键物件", step: "prop" },
    { title: "分镜", desc: "镜头与视频", step: "storyboard" },
    { title: "配音", desc: "旁白与对白", step: "audio" },
    { title: "剪辑", desc: "排序与成片导出", step: "edit" },
  ],
};

export function ToolsPage({ config, onOpenTool, onNavigate, onStartCreate }) {
  const page = config?.pages?.tools || {};
  const hub = config?.toolHub || {};
  const categories = hub.categories?.length ? hub.categories : DEFAULT_CATEGORIES;
  const workflow = hub.workflow || DEFAULT_WORKFLOW;
  const [prompt, setPrompt] = useState("");

  const openCategory = (cat) => {
    if (cat.nav === "workshop") {
      onOpenTool?.({ nav: "workshop", step: cat.step });
      return;
    }
    onNavigate?.(cat.nav);
  };

  const startCreate = () => {
    const text = prompt.trim();
    if (!text) return;
    onStartCreate?.(text);
  };

  return (
    <PageShell
      eyebrow={page.eyebrow || "Workshop shortcuts"}
      title={page.title || "创作捷径"}
      description={page.description || "次级入口：一句话交给 Agent，或跳进工坊某一步。主创作请回影视工坊。"}
    >
      <section className="panel mb-3 flex flex-wrap items-center justify-between gap-3 p-3 md:p-3.5">
        <div className="min-w-0">
          <h2 className="text-[13px] font-semibold">主入口：影视工坊</h2>
          <p className="mt-0.5 text-[12px] text-[var(--muted)]">建项目、开拍、按七步推进；这里只是跳转捷径。</p>
        </div>
        <button type="button" className="btn-primary shrink-0" onClick={() => onOpenTool?.({ nav: "workshop" })}>
          进入影视工坊 <ArrowRight className="h-3.5 w-3.5" />
        </button>
      </section>

      <section className="panel mb-4 p-3 md:p-3.5">
        <div className="mb-2 flex items-center gap-2">
          <Sparkles className="h-3.5 w-3.5 text-[var(--accent-2)]" />
          <h3 className="text-[13px] font-semibold">一句话交给创作 Agent</h3>
        </div>
        <p className="mb-2.5 text-[12px] text-[var(--muted)]">适合自动化跑通；需要逐步控片请回工坊。</p>
        <label className="block">
          <span className="sr-only">描述你的创作需求</span>
          <textarea
            className="field min-h-[88px] resize-y !py-2"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="例如：都市赘婿逆袭竖屏短剧，12 集，偏爽感节奏"
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                e.preventDefault();
                startCreate();
              }
            }}
          />
        </label>
        <div className="mt-3 flex justify-end">
          <button type="button" className="btn-secondary" disabled={!prompt.trim()} onClick={startCreate}>
            <ArrowUp className="h-3.5 w-3.5" /> 交给 Agent
          </button>
        </div>
      </section>

      <div className="mb-4 grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
        {categories.map((cat) => {
          const Icon = ICONS[cat.id] || Sparkles;
          return (
            <button
              key={cat.id}
              type="button"
              className="panel p-3 text-left transition hover:border-[var(--accent)]/35 hover:bg-white/[.04]"
              onClick={() => openCategory(cat)}
            >
              <Icon className="mb-2 h-4 w-4 text-[var(--accent-2)]" />
              <strong className="block text-[13px]">{cat.title}</strong>
              <p className="mt-1 text-[11px] leading-4 text-[var(--muted)]">{cat.desc}</p>
            </button>
          );
        })}
      </div>

      <section className="mb-2">
        <h3 className="text-[13px] font-semibold">{workflow.title}</h3>
        <p className="mt-1 max-w-3xl text-[12px] text-[var(--muted)]">{workflow.description}</p>
        <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-7">
          {(workflow.steps || []).map((step, index) => (
            <button
              key={step.title}
              type="button"
              className="panel p-2.5 text-left transition hover:border-[var(--accent)]/30"
              onClick={() => onOpenTool?.({ nav: "workshop", step: step.step })}
            >
              <div className="mb-2 flex h-6 w-6 items-center justify-center rounded-full bg-[var(--gradient)] text-[11px] font-bold text-white">
                {index + 1}
              </div>
              <strong className="block text-[12px]">{step.title}</strong>
              <p className="mt-1 text-[11px] leading-4 text-[var(--muted)]">{step.desc}</p>
            </button>
          ))}
        </div>
      </section>
    </PageShell>
  );
}
