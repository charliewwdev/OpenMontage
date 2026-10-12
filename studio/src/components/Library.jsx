import { useMemo, useState } from "react";
import {
  Clapperboard,
  FolderOpen,
  Plus,
  RefreshCw,
  Search,
  Sparkles,
  Trash2,
  Upload,
} from "lucide-react";
import { api } from "../api";
import { toast } from "../lib/toast";
import { ConfirmDialog } from "./ConfirmDialog";

const STEP_LABELS = ["剧本", "角色", "场景", "道具", "分镜", "剪辑"];
const PIPELINE = ["剧本创作", "剧本定稿", "智能分析", "素材生成", "分镜编排", "视频成片"];

const ENTRY_CARDS = [
  {
    id: "drama",
    title: "爽剧",
    badge: "+",
    desc: "专业爽剧模型 · 竖屏 9:16",
    tone: "from-[#ef4444] via-[#f97316] to-[#fb7185]",
    available: true,
  },
  {
    id: "short",
    title: "短剧",
    badge: "+",
    desc: "小说改编 / 横屏 16:9",
    tone: "from-[#3b82f6] via-[#6366f1] to-[#8b5cf6]",
    available: true,
  },
  {
    id: "formal",
    title: "正剧",
    badge: "",
    desc: "即将上线",
    tone: "from-[#475569] to-[#334155]",
    available: false,
  },
  {
    id: "upload",
    title: "上传剧本",
    badge: "+",
    desc: "TXT / MD / DOCX 转制作",
    tone: "from-[#eab308] via-[#f59e0b] to-[#f97316]",
    available: false,
  },
];

function progressSteps(project) {
  const p = project.progress || {};
  return [
    (p.episodes?.total || 0) > 0,
    (p.characters?.total || 0) > 0,
    (p.scenes?.total || 0) > 0,
    (p.props?.total || 0) > 0,
    (p.shots?.total || 0) > 0,
    (p.shots?.completed || 0) > 0,
  ];
}

export function Library({ projects, config, onOpen, onCreate, onDeleted, onRefresh }) {
  const [confirmId, setConfirmId] = useState(null);
  const [query, setQuery] = useState("");
  const caps = config?.capabilities || {};

  const visible = useMemo(() => {
    const keyword = query.trim().toLocaleLowerCase("zh-CN");
    if (!keyword) return projects || [];
    return (projects || []).filter((project) =>
      `${project.title} ${project.genre}`.toLocaleLowerCase("zh-CN").includes(keyword),
    );
  }, [projects, query]);

  const remove = async (id) => {
    try {
      await api(`/api/projects/${encodeURIComponent(id)}`, { method: "DELETE" });
      onDeleted?.(id);
      toast.success("项目已删除");
    } catch (e) {
      toast.error(String(e.message || e));
    } finally {
      setConfirmId(null);
    }
  };

  const target = (projects || []).find((p) => p.id === confirmId);

  return (
    <main className="min-h-screen p-3 md:p-5 lg:p-6">
      <div className="yc-frame mx-auto min-h-[calc(100vh-2.5rem)] max-w-[1480px] overflow-hidden p-4 md:p-7">
        <header className="relative overflow-hidden rounded-[22px] border border-white/10 bg-[linear-gradient(135deg,#15182a_0%,#1a1240_45%,#0d1b3a_100%)] px-5 py-7 md:px-8 md:py-9">
          <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_80%_20%,rgba(124,108,255,.28),transparent_40%)]" />
          <div className="relative">
            <div className="flex items-center gap-2 text-xs font-semibold text-white/55">
              <Clapperboard className="h-4 w-4 text-[#b7acff]" />
              影视创作工坊
            </div>
            <h1 className="mt-3 text-3xl font-semibold tracking-tight md:text-4xl">从剧本到成片，一站式 AI 影视生产</h1>
            <p className="mt-2 max-w-2xl text-sm text-white/55">
              剧本创作 → 剧本定稿 → 智能分析 → 素材生成 → 分镜编排 → 视频成片
            </p>
            <div className="mt-6 flex flex-wrap gap-2">
              {PIPELINE.map((label, index) => (
                <div
                  key={label}
                  className="flex items-center gap-2 rounded-full border border-white/10 bg-black/25 px-3 py-1.5 text-xs text-white/75"
                >
                  <span className="timecode text-[10px] text-[#b7acff]">{String(index + 1).padStart(2, "0")}</span>
                  {label}
                </div>
              ))}
            </div>
          </div>
        </header>

        <section className="mt-6 rounded-2xl border border-[#7c6cff]/35 bg-[linear-gradient(90deg,rgba(124,108,255,.18),rgba(79,140,255,.12))] px-4 py-3 md:px-5">
          <div className="flex flex-wrap items-center gap-3 text-sm text-white/80">
            <Sparkles className="h-4 w-4 text-[#c4b5fd]" />
            <span className="font-semibold">六步生产线</span>
            <span className="text-white/35">|</span>
            {STEP_LABELS.map((label, i) => (
              <span key={label} className="inline-flex items-center gap-1.5 text-white/70">
                <span className="timecode text-[10px] text-[#a5b4fc]">{i + 1}</span>
                {label}
                {i < STEP_LABELS.length - 1 ? <span className="text-white/25">→</span> : null}
              </span>
            ))}
          </div>
        </section>

        <section className="mt-7">
          <div className="mb-3 flex items-end justify-between gap-3">
            <div>
              <div className="label !mb-1">开始创作</div>
              <h2 className="text-xl font-semibold">选择创作入口</h2>
            </div>
          </div>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {ENTRY_CARDS.map((card) => (
              <button
                key={card.id}
                type="button"
                disabled={!card.available}
                onClick={() => {
                  if (!card.available) return toast.info(`${card.title}入口建设中，当前走统一建片场`);
                  onCreate();
                }}
                className={`group relative overflow-hidden rounded-2xl bg-gradient-to-br p-5 text-left text-white shadow-float transition ${card.tone} ${
                  card.available ? "hover:-translate-y-0.5 hover:brightness-110" : "cursor-not-allowed opacity-70"
                }`}
              >
                <div className="flex items-start justify-between">
                  <strong className="text-2xl font-semibold">
                    {card.title}
                    <span className="ml-1 text-xl opacity-80">{card.badge}</span>
                  </strong>
                  {card.id === "upload" ? <Upload className="h-5 w-5 opacity-80" /> : <Plus className="h-5 w-5 opacity-80" />}
                </div>
                <p className="mt-8 text-sm text-white/85">{card.desc}</p>
                {!card.available ? (
                  <span className="mt-3 inline-block rounded-full bg-black/25 px-2 py-0.5 text-[10px]">即将上线</span>
                ) : null}
              </button>
            ))}
          </div>
        </section>

        <section className="mt-8">
          <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <div className="label !mb-1">我的项目</div>
              <h2 className="text-xl font-semibold">本地项目中心</h2>
              <p className="mt-1 text-xs text-[var(--muted)]">
                供应商 {caps.configured ?? 0}/{caps.total ?? 3}
                {caps.deepseek ? " · DeepSeek" : ""}
                {caps.seedream ? " · Seedream" : ""}
                {caps.seedance ? " · Seedance" : ""}
              </p>
            </div>
            <div className="flex w-full flex-wrap items-center gap-2 sm:w-auto">
              <label className="relative w-full sm:w-72">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--muted)]" />
                <input
                  className="field !pl-10"
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="搜索项目名称"
                />
              </label>
              <button type="button" className="btn-secondary" onClick={onRefresh}>
                <RefreshCw className="h-3.5 w-3.5" /> 刷新
              </button>
              <button type="button" className="btn-primary" onClick={onCreate}>
                <Plus className="h-4 w-4" /> 新建项目
              </button>
            </div>
          </div>

          {!projects?.length ? (
            <button
              type="button"
              onClick={onCreate}
              className="panel group flex w-full flex-col items-center border-dashed border-white/15 py-20 text-center hover:border-[#7c6cff]/50"
            >
              <FolderOpen className="mb-4 h-10 w-10 text-[#a78bfa]" />
              <strong className="text-xl">还没有项目</strong>
              <span className="mt-2 text-sm text-[var(--muted)]">从爽剧 / 短剧入口开始第一部作品。</span>
            </button>
          ) : visible.length === 0 ? (
            <div className="panel py-16 text-center text-sm text-[var(--muted)]">没有匹配的项目。</div>
          ) : (
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {visible.map((project) => {
                const steps = progressSteps(project);
                const doneCount = steps.filter(Boolean).length;
                return (
                  <article
                    key={project.id}
                    className="panel group overflow-hidden transition hover:-translate-y-0.5 hover:border-white/20"
                  >
                    <button type="button" className="w-full p-5 text-left" onClick={() => onOpen(project.id)}>
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="rounded-full border border-white/10 bg-white/[.04] px-2 py-0.5 text-[10px] text-white/60">
                          {project.genre || "未分类"}
                        </span>
                        <span className="rounded-full border border-white/10 bg-white/[.04] px-2 py-0.5 text-[10px] text-white/60">
                          {project.ratio || "9:16"}
                        </span>
                      </div>
                      <h3 className="mt-3 truncate text-xl font-semibold">{project.title}</h3>
                      <p className="mt-1 line-clamp-2 min-h-10 text-sm leading-5 text-[var(--muted)]">
                        {project.synopsis || project.brief || "尚未生成剧本"}
                      </p>
                      <div className="mt-5">
                        <div className="mb-2 flex items-center justify-between text-[10px] text-[var(--muted)]">
                          <span>制作进度</span>
                          <span className="timecode text-[#a5b4fc]">
                            {doneCount}/{STEP_LABELS.length}
                          </span>
                        </div>
                        <div className="grid grid-cols-6 gap-1">
                          {steps.map((done, index) => (
                            <div
                              key={STEP_LABELS[index]}
                              className={`h-1.5 rounded-full ${done ? "bg-[var(--ok)]" : "bg-white/10"}`}
                              title={STEP_LABELS[index]}
                            />
                          ))}
                        </div>
                      </div>
                      <div className="mt-4 flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-white/40">
                        <span>{project.progress?.episodes?.total || 0} 集</span>
                        <span>{project.progress?.characters?.total || 0} 角色</span>
                        <span>{project.progress?.scenes?.total || 0} 场景</span>
                        <span>
                          更新{" "}
                          {project.updatedAt ? new Date(project.updatedAt).toLocaleDateString("zh-CN") : "—"}
                        </span>
                      </div>
                    </button>
                    <div className="flex items-center justify-between border-t border-[var(--line)] bg-black/20 px-5 py-3">
                      <span className="timecode text-[10px] text-white/35">
                        {project.progress?.shots?.completed || 0}/{project.progress?.shots?.total || 0} SHOTS
                      </span>
                      <button
                        type="button"
                        className="btn-quiet !min-h-8 !px-2 text-xs hover:!text-[var(--danger)]"
                        onClick={() => setConfirmId(project.id)}
                      >
                        <Trash2 className="h-3.5 w-3.5" /> 删除
                      </button>
                    </div>
                  </article>
                );
              })}
            </div>
          )}
        </section>
      </div>

      <ConfirmDialog
        open={Boolean(confirmId)}
        title="删除整个项目？"
        message={`《${target?.title || confirmId}》及其剧本、素材档案、分镜和剪辑记录将被删除。`}
        confirmLabel="删除项目"
        danger
        onCancel={() => setConfirmId(null)}
        onConfirm={() => void remove(confirmId)}
      />
    </main>
  );
}
