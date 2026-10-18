import { useMemo, useState } from "react";
import {
  Clapperboard,
  FolderOpen,
  KeyRound,
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

function progressSteps(project, stepCount = 7) {
  const p = project.progress || {};
  const flags = [
    (p.episodes?.total || 0) > 0,
    (p.characters?.total || 0) > 0,
    (p.scenes?.total || 0) > 0,
    (p.props?.total || 0) > 0,
    (p.shots?.total || 0) > 0,
    (p.audios?.total || 0) > 0 || (p.shots?.completed || 0) > 0,
    (p.shots?.completed || 0) > 0,
  ];
  return flags.slice(0, stepCount);
}

function ProjectCover({ project, className }) {
  const [imgFailed, setImgFailed] = useState(false);
  const [videoFailed, setVideoFailed] = useState(false);
  const still =
    !imgFailed && (project.coverUrl || (project.coverPath ? `/api/media/${project.id}/${project.coverPath}` : ""));
  const video = !videoFailed ? project.coverVideoUrl || "" : "";

  if (still) {
    return (
      <img
        src={still}
        alt=""
        onError={() => setImgFailed(true)}
        className={className || "h-full w-full object-cover transition duration-500 group-hover:scale-[1.03]"}
      />
    );
  }
  if (video) {
    return (
      <video
        src={video}
        muted
        playsInline
        loop
        autoPlay
        preload="metadata"
        onError={() => setVideoFailed(true)}
        className={className || "h-full w-full object-cover transition duration-500 group-hover:scale-[1.03]"}
      />
    );
  }
  return (
    <div className="flex h-full flex-col items-center justify-center gap-2 text-white/25">
      <Clapperboard className="h-8 w-8" />
      <span className="text-[10px] text-white/30">暂无封面素材</span>
    </div>
  );
}

export function Library({
  projects,
  config,
  onOpen,
  onCreate,
  onDeleted,
  onRefresh,
  onNeedKeys,
  onRequireAuth,
  authed = false,
}) {
  const [confirmId, setConfirmId] = useState(null);
  const [query, setQuery] = useState("");
  const caps = config?.capabilities || {};
  const keysReady = (caps.configured ?? 0) >= 1;
  const stepLabels = (config?.six_steps || []).map((s) => s.label);
  const entryCards = config?.entryCards || [];
  const hasRealProject = (projects || []).some((p) => !String(p.id || "").startsWith("welcome"));
  const onboardingSteps = [
    { n: "01", title: "登录账号", done: Boolean(authed) },
    { n: "02", title: "配置模型密钥", done: Boolean(authed) && keysReady },
    { n: "03", title: "新建项目开拍", done: Boolean(authed) && keysReady && hasRealProject },
  ];
  const onboardingDone = onboardingSteps.every((s) => s.done);

  const visible = useMemo(() => {
    const keyword = query.trim().toLocaleLowerCase("zh-CN");
    if (!keyword) return projects || [];
    return (projects || []).filter((project) =>
      `${project.title} ${project.genre}`.toLocaleLowerCase("zh-CN").includes(keyword),
    );
  }, [projects, query]);

  const remove = async (id) => {
    if (onRequireAuth && !onRequireAuth()) return;
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
    <main className="min-h-screen p-2 md:p-3">
      <div className="yc-frame mx-0 min-h-[calc(100vh-2.5rem)] w-full max-w-none overflow-hidden p-3 md:p-4">
        <header className="relative overflow-hidden rounded-2xl border border-white/10 bg-[linear-gradient(135deg,#15182a_0%,#1a1240_45%,#0d1b3a_100%)] px-4 py-3 md:px-6 md:py-4">
          <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_80%_20%,rgba(124,108,255,.28),transparent_40%)]" />
          <div className="relative flex flex-wrap items-end justify-between gap-2">
            <div className="min-w-0">
              <div className="flex items-center gap-2 text-[11px] font-semibold text-white/55">
                <Clapperboard className="h-3.5 w-3.5 text-[#b7acff]" />
                影视创作工坊
              </div>
              <h1 className="mt-1 text-xl font-semibold tracking-tight md:text-2xl">从剧本到成片，一站式 AI 影视生产</h1>
              <p className="mt-1 max-w-2xl text-xs text-white/55">
                剧本创作 → 剧本定稿 → 智能分析 → 素材生成 → 分镜编排 → 视频成片
              </p>
            </div>
          </div>
        </header>

        {!authed ? (
          <section className="mt-3 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-amber-500/35 bg-amber-500/10 px-3 py-2.5 md:px-4">
            <div className="min-w-0 text-xs leading-5 text-amber-50/90">
              <strong className="font-semibold text-amber-100">浏览模式</strong>
              <span className="text-amber-100/70">
                {" "}
                · 可打开项目查看进度与素材；生成剧本 / 出图 / 出片 / 配音等耗 Token 操作需先登录
              </span>
            </div>
            <button
              type="button"
              className="btn-primary !min-h-8 shrink-0 !px-3 text-xs"
              onClick={() => onRequireAuth?.()}
            >
              登录后创作
            </button>
          </section>
        ) : null}

        <section className="mt-3 rounded-xl border border-[#7c6cff]/35 bg-[linear-gradient(90deg,rgba(124,108,255,.18),rgba(79,140,255,.12))] px-3 py-2 md:px-4">
          <div className="flex flex-wrap items-center gap-2 text-xs text-white/80">
            <Sparkles className="h-3.5 w-3.5 shrink-0 text-[#c4b5fd]" />
            <span className="font-semibold">六步生产线</span>
            <span className="text-white/35">|</span>
            {stepLabels.map((label, i) => (
              <span key={label} className="inline-flex items-center gap-1 text-white/70">
                <span className="timecode text-[10px] text-[#a5b4fc]">{i + 1}</span>
                {label}
                {i < stepLabels.length - 1 ? <span className="text-white/25">→</span> : null}
              </span>
            ))}
          </div>
        </section>

        <section className="mt-3 rounded-xl border border-white/10 bg-white/[.03] px-3 py-2.5 md:px-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="min-w-0">
              <strong className="text-sm text-white/90">
                {onboardingDone ? "上线三步已完成" : "上线三步"}
              </strong>
              <p className="mt-0.5 text-[11px] text-white/50">
                {onboardingDone
                  ? "密钥已就绪，可直接新建或打开下方项目。"
                  : "密钥按账号隔离保存，仅你可见；配好后即可建项目开拍。"}
              </p>
            </div>
            {!keysReady ? (
              <button type="button" className="btn-primary !min-h-8 shrink-0 !px-3 text-xs" onClick={() => onNeedKeys?.()}>
                <KeyRound className="h-3.5 w-3.5" /> 去配置模型
              </button>
            ) : (
              <button type="button" className="btn-secondary !min-h-8 shrink-0 !px-3 text-xs" onClick={() => onCreate?.("drama")}>
                <Plus className="h-3.5 w-3.5" /> 新建项目
              </button>
            )}
          </div>
          {!onboardingDone ? (
            <ol className="mt-2 grid gap-1.5 sm:grid-cols-3">
              {onboardingSteps.map((step) => (
                <li
                  key={step.n}
                  className={`rounded-lg border px-2.5 py-1.5 text-xs ${
                    step.done ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-100" : "border-white/10 text-white/55"
                  }`}
                >
                  <span className="timecode text-[10px] text-white/35">{step.n}</span>
                  <div className="mt-0.5 font-medium text-white/85">{step.title}</div>
                  <div className="text-[10px]">{step.done ? "已完成" : "待完成"}</div>
                </li>
              ))}
            </ol>
          ) : null}
        </section>

        <section className="mt-4">
          <div className="mb-2 flex items-end justify-between gap-3">
            <h2 className="text-base font-semibold">选择创作入口</h2>
          </div>
          <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
            {entryCards.map((card) => (
              <button
                key={card.id}
                type="button"
                disabled={!card.available}
                onClick={() => {
                  if (!card.available) return toast.info(`${card.title}入口建设中，当前走统一建片场`);
                  onCreate?.(card.id, card);
                }}
                className={`group relative overflow-hidden rounded-xl bg-gradient-to-br p-3 text-left text-white shadow-float transition ${card.tone} ${
                  card.available ? "hover:-translate-y-0.5 hover:brightness-110" : "cursor-not-allowed opacity-70"
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <strong className="text-lg font-semibold leading-tight">
                    {card.title}
                    <span className="ml-1 text-base opacity-80">{card.badge}</span>
                  </strong>
                  {card.id === "upload" ? <Upload className="h-4 w-4 shrink-0 opacity-80" /> : <Plus className="h-4 w-4 shrink-0 opacity-80" />}
                </div>
                <p className="mt-2 line-clamp-2 text-xs text-white/85">{card.desc}</p>
                {!card.available ? (
                  <span className="mt-1.5 inline-block rounded-full bg-black/25 px-2 py-0.5 text-[10px]">即将上线</span>
                ) : null}
              </button>
            ))}
          </div>
        </section>

        <section className="mt-5">
          <div className="mb-3 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <h2 className="text-base font-semibold">我的项目</h2>
              <p className="mt-0.5 text-xs text-[var(--muted)]">
                供应商 {caps.configured ?? 0}/{caps.total ?? 3}
                {caps.deepseek || caps.llmReady ? ` · LLM${caps.llmBackend && caps.llmBackend !== "none" ? `/${caps.llmBackend}` : ""}` : ""}
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
              className="panel group flex w-full flex-col items-center border-dashed border-white/15 py-10 text-center hover:border-[#7c6cff]/50"
            >
              <FolderOpen className="mb-3 h-8 w-8 text-[#a78bfa]" />
              <strong className="text-lg">还没有项目</strong>
              <span className="mt-2 text-sm text-[var(--muted)]">从爽剧 / 短剧入口开始第一部作品。</span>
            </button>
          ) : visible.length === 0 ? (
            <div className="panel py-16 text-center text-sm text-[var(--muted)]">没有匹配的项目。</div>
          ) : (
            <div className="grid gap-3 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5">
              {visible.map((project) => {
                const steps = progressSteps(project, stepLabels.length || 6);
                const doneCount = steps.filter(Boolean).length;
                return (
                  <article
                    key={project.id}
                    className="panel group overflow-hidden transition hover:-translate-y-0.5 hover:border-white/20"
                  >
                    <button type="button" className="w-full text-left" onClick={() => onOpen(project.id)}>
                      <div className="flex aspect-[16/9] items-center justify-center overflow-hidden bg-black/50">
                        <ProjectCover project={project} className="max-h-full max-w-full object-contain" />
                      </div>
                      <div className="p-3">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="rounded-full border border-white/10 bg-white/[.04] px-2 py-0.5 text-[10px] text-white/60">
                          {project.genre || "未分类"}
                        </span>
                        <span className="rounded-full border border-white/10 bg-white/[.04] px-2 py-0.5 text-[10px] text-white/60">
                          {project.ratio || "9:16"}
                        </span>
                      </div>
                      <h3 className="mt-2 truncate text-base font-semibold">{project.title}</h3>
                      <p className="mt-1 line-clamp-2 min-h-8 text-xs leading-4 text-[var(--muted)]">
                        {project.synopsis || project.brief || "尚未生成剧本"}
                      </p>
                      <div className="mt-3">
                        <div className="mb-2 flex items-center justify-between text-[10px] text-[var(--muted)]">
                          <span>制作进度</span>
                          <span className="timecode text-[#a5b4fc]">
                            {doneCount}/{stepLabels.length || steps.length}
                          </span>
                        </div>
                        <div className="grid grid-cols-6 gap-1">
                          {steps.map((done, index) => (
                            <div
                              key={stepLabels[index] || index}
                              className={`h-1.5 rounded-full ${done ? "bg-[var(--ok)]" : "bg-white/10"}`}
                              title={stepLabels[index] || ""}
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
                      </div>
                    </button>
                    <div className="flex items-center justify-between border-t border-[var(--line)] bg-black/20 px-3 py-2">
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
