import { useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowLeft,
  Box,
  Check,
  Clapperboard,
  Image as ImageIcon,
  KeyRound,
  Loader2,
  Mic2,
  RefreshCw,
  Scissors,
  ScrollText,
  Users,
  Wand2,
} from "lucide-react";
import { api } from "../api";
import { ScriptStep } from "./steps/ScriptStep";
import { EntityStep } from "./steps/EntityStep";
import { StoryboardStep } from "./steps/StoryboardStep";
import { AudioStep } from "./steps/AudioStep";
import { EditStep } from "./steps/EditStep";

const STEP_ICONS = {
  script: ScrollText,
  character: Users,
  scene: ImageIcon,
  prop: Box,
  storyboard: Clapperboard,
  audio: Mic2,
  edit: Scissors,
};

function entityHasImage(entity) {
  if (!entity || entity.deletedAt) return false;
  if (entity.selectedImageId) return true;
  return (entity.images || []).some((img) => img && !img.deletedAt && (img.path || img.url));
}

function shotHasVideo(shot) {
  if (!shot || shot.deletedAt) return false;
  if (shot.status === "success" && (shot.selectedVideoId || (shot.videos || []).length)) return true;
  if (shot.status === "stale" && (shot.selectedVideoId || (shot.videos || []).length)) return true;
  return false;
}

function entityTouchesEpisode(entity, episode) {
  if (!episode) return true;
  const nums = entity?.episodes;
  if (!Array.isArray(nums) || nums.length === 0) return true;
  const n = Number(episode.episodeNumber);
  return nums.some((x) => Number(x) === n);
}

function stepCounts(bundle, episode = null) {
  if (!bundle) {
    return { script: "0 集", character: "0", scene: "0", prop: "0", storyboard: "0 镜", audio: "0", edit: "未开始" };
  }
  const ents = (bundle.entities || []).filter((e) => !e.deletedAt);
  const shotsAll = (bundle.shots || []).filter((s) => !s.deletedAt);
  const episodes = bundle.episodes || [];
  const confirmed = episodes.filter((e) => e.status === "confirmed");
  const audios = bundle.audios || [];

  if (episode) {
    const n = episode.episodeNumber;
    const eid = episode.id;
    const shots = shotsAll.filter((s) => s.episodeId === eid);
    const successful = shots.filter(shotHasVideo).length;
    const byKind = (kind) => {
      const list = ents.filter((e) => e.kind === kind && entityTouchesEpisode(e, episode));
      const ready = list.filter(entityHasImage).length;
      if (!list.length) return "0";
      return `${ready}/${list.length}`;
    };
    const hasAudio = audios.some((a) => a.episodeId === eid && a.kind !== "bgm" && (a.path || a.url));
    const hasEdit = (bundle.edits || []).some(
      (e) => e.episodeId === eid && (e.outputPath || e.outputUrl),
    );
    return {
      script: episode.status === "confirmed" ? `第${n}集·定稿` : `第${n}集·草稿`,
      character: byKind("character"),
      scene: byKind("scene"),
      prop: byKind("prop"),
      storyboard: `${successful}/${shots.length} 镜`,
      audio: hasAudio ? "已配音" : "未配音",
      edit: hasEdit ? "已成片" : "未成片",
    };
  }

  const successful = shotsAll.filter(shotHasVideo).length;
  const audioReady = confirmed.filter((ep) =>
    audios.some((a) => a.episodeId === ep.id && a.kind !== "bgm" && (a.path || a.url)),
  ).length;
  const byKind = (kind) => {
    const list = ents.filter((e) => e.kind === kind);
    const ready = list.filter(entityHasImage).length;
    if (!list.length) return "0";
    return `${ready}/${list.length}`;
  };
  return {
    script: `${confirmed.length}/${episodes.length} 集定稿`,
    character: byKind("character"),
    scene: byKind("scene"),
    prop: byKind("prop"),
    storyboard: `${successful}/${shotsAll.length} 镜`,
    audio: `${audioReady}/${Math.max(confirmed.length, 1)}`,
    edit: (bundle.edits || []).some((e) => e.outputPath || e.outputUrl) ? "已成片" : "未成片",
  };
}

function stepDone(bundle, key, episode = null) {
  if (!bundle) return false;
  const ents = (bundle.entities || []).filter((e) => !e.deletedAt);
  const shotsAll = (bundle.shots || []).filter((s) => !s.deletedAt);
  const episodes = bundle.episodes || [];
  const confirmed = episodes.filter((e) => e.status === "confirmed");
  const audios = bundle.audios || [];

  if (episode) {
    const eid = episode.id;
    if (key === "script") return episode.status === "confirmed";
    if (key === "character" || key === "scene" || key === "prop") {
      const list = ents.filter((e) => e.kind === key && entityTouchesEpisode(e, episode));
      return list.length > 0 && list.every(entityHasImage);
    }
    if (key === "storyboard") {
      const shots = shotsAll.filter((s) => s.episodeId === eid);
      return shots.length > 0 && shots.every(shotHasVideo);
    }
    if (key === "audio") {
      return audios.some((a) => a.episodeId === eid && a.kind !== "bgm" && (a.path || a.url));
    }
    if (key === "edit") {
      return (bundle.edits || []).some((e) => e.episodeId === eid && (e.outputPath || e.outputUrl));
    }
    return false;
  }

  if (key === "script") {
    return episodes.length > 0 && confirmed.length === episodes.length;
  }
  if (key === "character" || key === "scene" || key === "prop") {
    const list = ents.filter((e) => e.kind === key);
    // 没有该类实体时不算完成（避免 0 个也打勾）
    return list.length > 0 && list.every(entityHasImage);
  }
  if (key === "storyboard") {
    // 全部分镜都有可用视频才打勾（2/4 不能算完成）
    return shotsAll.length > 0 && shotsAll.every(shotHasVideo);
  }
  if (key === "audio") {
    // 每个已定稿集都有对白配音才打勾（BGM 不算）
    return (
      confirmed.length > 0 &&
      confirmed.every((ep) =>
        audios.some((a) => a.episodeId === ep.id && a.kind !== "bgm" && (a.path || a.url)),
      )
    );
  }
  if (key === "edit") {
    return (bundle.edits || []).some((e) => e.outputPath || e.outputUrl);
  }
  return false;
}

export function StudioShell({
  projectId,
  bundle,
  loading,
  step,
  setStep,
  config,
  busyMsg,
  setBusyMsg,
  onBack,
  onRefresh,
  onBundle,
  onNeedKeys,
}) {
  const project = bundle?.project || {};
  const autoJob = project.autoProduce || null;
  const episodes = useMemo(
    () => [...(bundle?.episodes || [])].sort((a, b) => a.episodeNumber - b.episodeNumber),
    [bundle?.episodes],
  );
  const [focusEpisodeId, setFocusEpisodeId] = useState("");
  useEffect(() => {
    if (focusEpisodeId && !episodes.some((e) => e.id === focusEpisodeId)) {
      setFocusEpisodeId(episodes[0]?.id || "");
    } else if (!focusEpisodeId && episodes[0]) {
      setFocusEpisodeId(episodes[0].id);
    }
  }, [episodes, focusEpisodeId]);
  const focusEpisode = useMemo(
    () => episodes.find((e) => e.id === focusEpisodeId) || null,
    [episodes, focusEpisodeId],
  );
  const counts = stepCounts(bundle, focusEpisode);
  const caps = config?.capabilities || {};
  const steps = (config?.six_steps || []).map((s) => ({
    key: s.id,
    label: s.label,
    note: s.note || "",
    icon: STEP_ICONS[s.id] || Clapperboard,
  }));
  const activeMeta = steps.find((s) => s.key === step) || steps[0] || { key: step, label: step, note: "", icon: Clapperboard };
  const keysMissing = !(caps.deepseek && caps.seedream && caps.seedance);
  const pollRef = useRef(null);

  useEffect(() => {
    if (!projectId || autoJob?.status !== "running") {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
      return undefined;
    }
    pollRef.current = setInterval(() => {
      onRefresh?.();
    }, 5000);
    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [projectId, autoJob?.status, onRefresh]);

  const startAutoFromWorkshop = async () => {
    if (!projectId) return;
    try {
      setBusyMsg?.("正在启动一键全流程…");
      await api(`/api/projects/${encodeURIComponent(projectId)}/auto-produce`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          episodeCount: 1,
          maxShots: 24,
          maxCharacters: 6,
          maxScenes: 4,
          forceIllustration: false,
          resolution: "720p",
        }),
      });
      onRefresh?.();
    } catch (error) {
      setBusyMsg?.(String(error.message || error));
      setTimeout(() => setBusyMsg?.(""), 2500);
      return;
    }
    setBusyMsg?.("");
  };

  const common = {
    projectId,
    bundle,
    config,
    setBusyMsg,
    onBundle,
    onRefresh,
    onNeedKeys,
    focusEpisodeId,
    onFocusEpisode: setFocusEpisodeId,
  };

  if (loading && !bundle) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 text-sm text-[var(--muted)]">
        <div className="inline-flex items-center gap-2">
          <Loader2 className="h-4 w-4 animate-spin" /> 正在开机片场…
        </div>
        <button type="button" className="btn-secondary !min-h-9" onClick={onBack}>
          <ArrowLeft className="h-4 w-4" /> 返回主界面
        </button>
      </div>
    );
  }

  return (
    <main className="min-h-screen lg:h-screen lg:overflow-hidden">
      <div className="grid min-h-screen lg:h-screen lg:grid-cols-[92px_1fr]">
        <aside className="flex border-r border-[var(--line)] bg-[#0a0b10] lg:h-screen lg:flex-col">
          <div className="border-b border-[var(--line)] p-2 lg:px-2 lg:pt-3 lg:pb-1">
            <button
              type="button"
              onClick={onBack}
              className="btn-secondary flex w-full !min-h-9 items-center justify-center gap-1.5 !px-2 text-xs"
              aria-label="返回主界面"
              title="返回影视工坊主界面"
            >
              <ArrowLeft className="h-4 w-4 shrink-0" />
              <span className="truncate">返回</span>
            </button>
          </div>
          {focusEpisode ? (
            <div className="hidden border-b border-[var(--line)] px-2 py-2 lg:block">
              <div className="timecode text-[9px] text-white/35">FOCUS EP</div>
              <div className="mt-0.5 truncate text-[11px] font-semibold text-white/80">
                第{focusEpisode.episodeNumber}集
              </div>
              <div className="truncate text-[10px] text-white/40">{focusEpisode.title || "未命名"}</div>
            </div>
          ) : null}
          <div className="flex gap-1 overflow-x-auto p-2 lg:min-h-0 lg:flex-1 lg:flex-col lg:overflow-y-auto lg:py-2">
            {steps.map((item, index) => {
              const Icon = item.icon;
              const active = item.key === step;
              const done = stepDone(bundle, item.key, focusEpisode);
              return (
                <button
                  key={item.key}
                  type="button"
                  onClick={() => setStep(item.key)}
                  className={`flex min-w-[72px] flex-col items-center gap-2 rounded-2xl px-2 py-3 text-center transition lg:min-w-0 ${
                    active ? "bg-white/[.06]" : "hover:bg-white/[.03]"
                  }`}
                >
                  <span
                    className={`relative flex h-10 w-10 items-center justify-center rounded-full border text-sm ${
                      active
                        ? "border-transparent bg-[var(--gradient)] text-white shadow-[0_0_20px_rgba(124,108,255,.45)]"
                        : done
                          ? "border-[var(--ok)]/40 bg-[var(--ok)]/15 text-[var(--ok)]"
                          : "border-white/10 bg-white/[.03] text-white/45"
                    }`}
                  >
                    {done && !active ? <Check className="h-4 w-4" /> : <Icon className="h-4 w-4" />}
                    <span className="timecode absolute -right-1 -top-1 rounded-full bg-black/70 px-1 text-[8px] text-white/50">
                      {index + 1}
                    </span>
                  </span>
                  <span className="min-w-0">
                    <span className={`block text-xs font-semibold ${active ? "text-white" : "text-white/70"}`}>
                      {item.label}
                    </span>
                    <span className="mt-0.5 block truncate text-[9px] text-white/35">{counts[item.key]}</span>
                  </span>
                </button>
              );
            })}
          </div>
        </aside>

        <section className="relative min-w-0 lg:h-screen lg:overflow-hidden">
          {(busyMsg || loading) && (
            <div className="absolute inset-x-0 top-16 z-20 flex items-center justify-center gap-2 bg-[#7c6cff]/90 px-4 py-2 text-sm text-white">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              {busyMsg || "加载中…"}
            </div>
          )}
          <header className="sticky top-0 z-30 flex min-h-16 items-center justify-between gap-3 border-b border-[var(--line)] bg-[#0c0e14]/95 px-4 py-2 backdrop-blur md:px-6">
            <div className="flex min-w-0 items-center gap-3">
              <button
                type="button"
                onClick={onBack}
                className="btn-secondary !min-h-9 shrink-0 !px-3"
                aria-label="返回主界面"
                title="返回影视工坊主界面"
              >
                <ArrowLeft className="h-4 w-4" />
                返回主界面
              </button>
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <h1 className="truncate text-lg font-semibold">{project.title || projectId}</h1>
                  <span className="rounded-full border border-white/10 bg-white/[.04] px-2 py-0.5 text-[10px] text-white/55">
                    {project.genre || "题材未设"}
                  </span>
                  <span className="rounded-full border border-white/10 bg-white/[.04] px-2 py-0.5 text-[10px] text-white/55">
                    {project.ratio || "9:16"}
                  </span>
                </div>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <div className="hidden text-[10px] text-white/35 sm:block">
                文本模型 {caps.deepseek || caps.llmReady ? "就绪" : "未配置"}
                {caps.llmBackend && caps.llmBackend !== "none" ? `（${caps.llmBackend}）` : ""} · Seedream{" "}
                {caps.seedream ? "✓" : "—"} · Seedance{" "}
                {caps.seedance ? "✓" : "—"}
              </div>
              {keysMissing ? (
                <button type="button" className="btn-secondary !min-h-9" onClick={() => onNeedKeys?.()}>
                  <KeyRound className="h-3.5 w-3.5" /> 配置密钥
                </button>
              ) : null}
              <button type="button" className="btn-secondary !min-h-9" onClick={onRefresh} disabled={loading}>
                <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} /> 刷新
              </button>
            </div>
          </header>
          {keysMissing ? (
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[#f59e0b]/30 bg-[#f59e0b]/10 px-4 py-2.5 text-xs text-[#fde68a] md:px-6">
              <span>当前步骤可能需要 API Key。未配置时会报错，可一键跳转配置并立即生效。</span>
              <button type="button" className="btn-primary !min-h-8 !px-3" onClick={() => onNeedKeys?.()}>
                <KeyRound className="h-3.5 w-3.5" /> 一键配置
              </button>
            </div>
          ) : null}
          {autoJob?.status === "running" ? (
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[#7c6cff]/35 bg-[#7c6cff]/15 px-4 py-2.5 text-xs text-[#ddd6fe] md:px-6">
              <span className="inline-flex items-center gap-2">
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                一键全流程进行中：{autoJob.step || "准备"} · 页面会自动刷新进度
              </span>
              <span className="text-white/45">完成后可在剪辑台查看成片</span>
            </div>
          ) : null}
          {autoJob?.status === "success" && autoJob.exportUrl ? (
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[var(--ok)]/30 bg-[var(--ok)]/10 px-4 py-2.5 text-xs text-[var(--ok)] md:px-6">
              <span>一键全流程已完成</span>
              <a className="btn-secondary !min-h-8 !px-3" href={autoJob.exportUrl} target="_blank" rel="noreferrer">
                预览成片
              </a>
            </div>
          ) : null}
          {autoJob?.status === "failed" ? (
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-red-500/30 bg-red-500/10 px-4 py-2.5 text-xs text-red-200 md:px-6">
              <span>一键全流程失败：{autoJob.error || "未知错误"}</span>
              <button type="button" className="btn-secondary !min-h-8 !px-3" onClick={() => void startAutoFromWorkshop()}>
                <Wand2 className="h-3.5 w-3.5" /> 重试
              </button>
            </div>
          ) : null}
          {!keysMissing && (project.brief || "").trim() && (!autoJob || autoJob.status === "success") ? (
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-white/10 bg-white/[.03] px-4 py-2.5 text-xs text-white/60 md:px-6">
              <span>已有创作需求时，可一键后台跑通到成片（首集、12–30 镜 / 约 3–6 分钟）。</span>
              <button type="button" className="btn-secondary !min-h-8 !px-3" onClick={() => void startAutoFromWorkshop()}>
                <Wand2 className="h-3.5 w-3.5" /> 一键全流程
              </button>
            </div>
          ) : null}
          <div className="border-b border-[var(--line)] bg-black/20 px-4 py-2 md:px-6">
            <div className="label !mb-0">Stage {String(Math.max(0, steps.findIndex((s) => s.key === step)) + 1).padStart(2, "0")}</div>
            <h2 className="text-base font-semibold">
              {activeMeta.label}
              {focusEpisode ? (
                <span className="ml-2 text-sm font-normal text-white/45">
                  · 第{focusEpisode.episodeNumber}集{focusEpisode.title ? `「${focusEpisode.title}」` : ""}
                </span>
              ) : null}
            </h2>
          </div>
          <div className="scrollbar-thin min-h-[calc(100vh-7.5rem)] overflow-y-auto p-4 md:p-6 lg:h-[calc(100vh-7.5rem)]">
            {step === "script" && <ScriptStep {...common} />}
            {step === "character" && <EntityStep {...common} kind="character" />}
            {step === "scene" && <EntityStep {...common} kind="scene" />}
            {step === "prop" && <EntityStep {...common} kind="prop" />}
            {step === "storyboard" && <StoryboardStep {...common} />}
            {step === "audio" && <AudioStep {...common} />}
            {step === "edit" && <EditStep {...common} />}
          </div>
        </section>
      </div>
    </main>
  );
}
