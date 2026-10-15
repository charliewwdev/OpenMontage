import { useState } from "react";
import { ArrowUp, Clapperboard, Film, Mic2, Palette, PenLine, Sparkles, Workflow } from "lucide-react";
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
  {
    id: "text",
    title: "文本创作",
    desc: "AI剧本创作、短剧脚本、影视分镜、叙事构思",
    accent: "from-[#1d4ed8] to-[#60a5fa]",
    nav: "workshop",
    step: "script",
  },
  {
    id: "visual",
    title: "视觉创作",
    desc: "概念设计、角色原画、场景绘制、视觉分镜",
    accent: "from-[#9d174d] to-[#f472b6]",
    nav: "workshop",
    step: "character",
  },
  {
    id: "audio",
    title: "音频创作",
    desc: "配音合成、音效设计、背景音乐、角色语音",
    accent: "from-[#c2410c] to-[#fb923c]",
    nav: "help",
  },
  {
    id: "video",
    title: "视频创作",
    desc: "AI视频生成、动态分镜、影像合成、特效制作",
    accent: "from-[#047857] to-[#34d399]",
    nav: "workshop",
    step: "storyboard",
  },
  {
    id: "workshop",
    title: "影视工坊",
    desc: "面向短剧、MV、广告等成片目标的专业场景化工作流",
    accent: "from-[#4c1d95] to-[#8b5cf6]",
    nav: "workshop",
  },
  {
    id: "canvas",
    title: "画布创作",
    desc: "可视化工作流编排，连接多个AI节点，创造无限可能",
    accent: "from-[#a16207] to-[#fbbf24]",
    nav: "canvas",
  },
];

const DEFAULT_WORKFLOW = {
  title: "AI短剧创作完整流程",
  description: "用导演思维驾驭AI创作：平台提供AI创作能力，你是导演——生成素材、把控品质、剪辑成片",
  steps: [
    { title: "定剧本", desc: "AI生成分镜剧本，包含场景描述、角色对话、动作指示" },
    { title: "选演员", desc: "AI生成虚拟角色形象和场景概念图" },
    { title: "拍画面", desc: "AI图生视频，让静态角色和场景动起来" },
    { title: "做配音", desc: "AI生成背景音乐、音效，以及角色配音" },
    { title: "剪成片", desc: "把素材剪辑成完整短剧并导出" },
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
      eyebrow={page.eyebrow || "Creation center"}
      title={page.title || "AI创作中心"}
      description={page.description || "直接描述创意，或选择专业分类开始创作"}
    >
      {/* Hero band — 对齐有彩顶部氛围条 */}
      <div className="relative mb-6 overflow-hidden rounded-2xl border border-white/10">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_20%_20%,rgba(124,108,255,.35),transparent_50%),radial-gradient(ellipse_at_80%_0%,rgba(56,189,248,.2),transparent_45%),linear-gradient(135deg,#0b1020,#12182c_55%,#1a1030)]" />
        <div className="relative px-5 py-10 md:px-8 md:py-14">
          <div className="label !mb-2 !text-white/50">OPENMONTAGE</div>
          <h2 className="max-w-xl text-2xl font-semibold text-white md:text-3xl">从一句话灵感到可拍成片</h2>
          <p className="mt-2 max-w-lg text-sm text-white/60">文本 · 视觉 · 音频 · 视频 · 工坊 · 画布，按导演流程组织创作入口</p>
        </div>
      </div>

      {/* Prompt composer */}
      <section className="panel mb-8 p-5 md:p-6">
        <div className="mb-3 flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-[#a78bfa]" />
          <h3 className="text-base font-semibold">说出灵感，让创意成为作品</h3>
          <span className="rounded-full bg-[#7c6cff]/15 px-2 py-0.5 text-[10px] text-[#c4b5fd]">创作 Agent</span>
        </div>
        <p className="mb-4 text-sm text-[var(--muted)]">描述你的想法，Agent 会调用专业技能，并直接生成图片、音乐、音频或视频。</p>
        <label className="block">
          <span className="sr-only">描述你的创作需求</span>
          <textarea
            className="field min-h-[120px] resize-y !py-3"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="例如：为国风茶饮品牌创作一张夏日海报，再配一段轻快的古筝音乐"
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                e.preventDefault();
                startCreate();
              }
            }}
          />
        </label>
        <div className="mt-3 flex justify-end">
          <button type="button" className="btn-primary" disabled={!prompt.trim()} onClick={startCreate}>
            <ArrowUp className="h-3.5 w-3.5" /> 开始创作
          </button>
        </div>
      </section>

      {/* Category cards 2×3 */}
      <div className="mb-10 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {categories.map((cat) => {
          const Icon = ICONS[cat.id] || Sparkles;
          return (
            <button
              key={cat.id}
              type="button"
              className={`relative overflow-hidden rounded-2xl border border-white/10 bg-gradient-to-br ${cat.accent || "from-[#312e81] to-[#7c6cff]"} p-5 text-left text-white shadow-lg transition hover:-translate-y-0.5 hover:brightness-110`}
              onClick={() => openCategory(cat)}
            >
              <Icon className="mb-6 h-7 w-7 opacity-90" />
              <strong className="block text-lg">{cat.title}</strong>
              <p className="mt-2 text-sm leading-6 text-white/80">{cat.desc}</p>
            </button>
          );
        })}
      </div>

      {/* Workflow */}
      <section className="mb-8">
        <h3 className="text-lg font-semibold">{workflow.title}</h3>
        <p className="mt-2 max-w-3xl text-sm text-[var(--muted)]">{workflow.description}</p>
        <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          {(workflow.steps || []).map((step, index) => {
            const stepMap = {
              定剧本: "script",
              选演员: "character",
              拍画面: "storyboard",
              做配音: "audio",
              剪成片: "edit",
            };
            const workshopStep = stepMap[step.title] || step.step;
            return (
              <button
                key={step.title}
                type="button"
                className="panel p-4 text-left transition hover:-translate-y-0.5 hover:border-white/20"
                onClick={() => onOpenTool?.({ nav: "workshop", step: workshopStep })}
              >
                <div className="mb-3 flex h-8 w-8 items-center justify-center rounded-full bg-[var(--gradient)] text-sm font-bold text-white">
                  {index + 1}
                </div>
                <strong className="block text-sm">{step.title}</strong>
                <p className="mt-2 text-xs leading-5 text-[var(--muted)]">{step.desc}</p>
              </button>
            );
          })}
        </div>
      </section>

      {/* Workshop CTA */}
      <section className="overflow-hidden rounded-2xl border border-white/10 bg-gradient-to-r from-[#1e1b4b] via-[#312e81] to-[#4c1d95] p-6 md:flex md:items-center md:justify-between md:gap-6">
        <div>
          <h3 className="text-lg font-semibold text-white">影视创作工坊</h3>
          <p className="mt-2 text-sm text-white/70">从剧本到成片，全流程 AI 辅助创作</p>
          <p className="mt-1 text-xs text-white/45">剧本AI创作 · 素材一键生成 · 智能分镜脚本</p>
        </div>
        <button
          type="button"
          className="btn-primary mt-4 shrink-0 md:mt-0"
          onClick={() => onOpenTool?.({ nav: "workshop" })}
        >
          进入影视工坊
        </button>
      </section>
    </PageShell>
  );
}
