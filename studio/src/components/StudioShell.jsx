import { useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowLeft,
  Box,
  Check,
  Clapperboard,
  Image as ImageIcon,
  KeyRound,
  Loader2,
  RefreshCw,
  ScrollText,
  Users,
  Wand2,
} from "lucide-react";
import { api } from "../api";
import { useLocale } from "../lib/i18n";
import { StudioModelBar } from "./StudioModelBar";
import { ScriptStep } from "./steps/ScriptStep";
import { EntityStep } from "./steps/EntityStep";
import { SegmentWorkspace } from "./steps/SegmentWorkspace";

/** Condensed nav: prepare assets once, then live in the segment desk. */
const NAV_STEPS = [
  { key: "script", label: "剧本", note: "定稿分集", icon: ScrollText },
  { key: "character", label: "角色", note: "造型定妆", icon: Users },
  { key: "scene", label: "场景", note: "空间定妆", icon: ImageIcon },
  { key: "prop", label: "道具", note: "物件定妆", icon: Box },
  { key: "workspace", label: "工作台", note: "片段内聚制作", icon: Clapperboard },
];

const WORKSPACE_KEYS = new Set(["workspace", "storyboard", "audio", "edit"]);

const STEP_ICONS = {
  script: ScrollText,
  character: Users,
  scene: ImageIcon,
  prop: Box,
  workspace: Clapperboard,
  storyboard: Clapperboard,
  audio: Clapperboard,
  edit: Clapperboard,
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

/** Avoid「第1集 · 第1集·重逢」when episode.title already embeds the number. */
function formatEpisodeLabel(n, title) {
  const num = Number(n) || 0;
  const raw = String(title || "").trim();
  if (!raw) return num ? `第${num}集` : "";
  let stripped = raw;
  for (let i = 0; i < 4; i += 1) {
    const next = stripped
      .replace(new RegExp(`^第\\s*${num || "\\d+"}\\s*集\\s*[·・.\\-:：]*\\s*`, "i"), "")
      .replace(/^EP\s*\d+\s*[·・.\-:：]*\s*/i, "")
      .trim();
    if (next === stripped) break;
    stripped = next;
  }
  if (!stripped) return num ? `第${num}集` : raw;
  return num ? `第${num}集 · ${stripped}` : stripped;
}

function autoLiveProgress(autoJob, bundle) {
  const steps = Array.isArray(autoJob?.steps) ? autoJob.steps : [];
  const running = steps.find((step) => step.status === "running") || null;
  const doneSteps = steps.filter((step) => step.status === "done" || step.status === "skipped").length;
  const totalSteps = steps.length;
  const pct = totalSteps
    ? Math.min(100, Math.round(((doneSteps + (running ? 0.4 : 0)) / totalSteps) * 100))
    : 0;
  const epIds = new Set(
    [...(autoJob?.episodeIds || []), autoJob?.episodeId].filter(Boolean).map(String),
  );
  const shots = (bundle?.shots || []).filter(
    (shot) => !shot.deletedAt && (!epIds.size || epIds.has(String(shot.episodeId || ""))),
  );
  const segs = new Map();
  for (const shot of shots) {
    const key = `${shot.episodeId || ""}:${shot.segmentOrder ?? shot.shotOrder ?? shot.id}`;
    const prev = segs.get(key);
    if (!prev || (shot.isSegmentLead && !prev.isSegmentLead)) segs.set(key, shot);
  }
  const list = [...segs.values()];
  const videoDone = list.filter((shot) => shot.status === "success").length;
  const videoGen = list.filter((shot) => shot.status === "generating").length;
  const videoFail = list.filter((shot) => shot.status === "failed").length;
  const video = {
    total: list.length,
    done: videoDone,
    gen: videoGen,
    fail: videoFail,
    pending: Math.max(0, list.length - videoDone - videoGen - videoFail),
  };
  const ents = (bundle?.entities || []).filter((entity) => !entity.deletedAt);
  const images = {
    total: ents.length,
    done: ents.filter(entityHasImage).length,
    gen: ents.filter((entity) => entity.imageStatus === "generating").length,
  };
  const logs = Array.isArray(autoJob?.logs) ? autoJob.logs : [];
  const last = logs.length ? logs[logs.length - 1] : null;
  return {
    running,
    doneSteps,
    totalSteps,
    pct,
    video,
    images,
    detail: String(running?.detail || "").trim(),
    lastText: String(last?.text || "").trim(),
    lastOk: last ? last.ok !== false : true,
  };
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
    const refIds = new Set(shots.flatMap((s) => s.referenceEntityIds || []));
    const byKind = (kind) => {
      // Prefer entities referenced by this episode's beats; fall back to episode-tagged.
      const referenced = ents.filter((e) => e.kind === kind && refIds.has(e.id));
      const tagged = ents.filter((e) => e.kind === kind && entityTouchesEpisode(e, episode));
      const list = referenced.length ? referenced : tagged;
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
    return list.length > 0 && list.every(entityHasImage);
  }
  if (key === "storyboard") {
    return shotsAll.length > 0 && shotsAll.every(shotHasVideo);
  }
  if (key === "audio") {
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

function episodeShotSummary(bundle, episode) {
  if (!episode) return { total: 0, ready: 0, durationSec: 0 };
  const shots = (bundle?.shots || []).filter((s) => s.episodeId === episode.id && !s.deletedAt);
  const ready = shots.filter(shotHasVideo).length;
  const durationSec = shots.reduce((sum, s) => {
    const d = Number(s.selectedVideo?.duration || s.duration || 0);
    return sum + (Number.isFinite(d) ? d : 0);
  }, 0);
  return { total: shots.length, ready, durationSec };
}

function formatDuration(sec) {
  const n = Math.round(Number(sec) || 0);
  if (n <= 0) return "";
  const m = Math.floor(n / 60);
  const s = n % 60;
  if (m <= 0) return `${s}s`;
  return `${m}:${String(s).padStart(2, "0")}`;
}

export function StudioShell({
  projectId,
  bundle,
  loading,
  step,
  setStep,
  focusEpisodeId: focusEpisodeIdProp,
  onFocusEpisode,
  config,
  busyMsg,
  setBusyMsg,
  onBack,
  onRefresh,
  onBundle,
  onNeedKeys,
  onRequireAuth,
  readOnly = false,
}) {
  const { t } = useLocale();
  const project = bundle?.project || {};
  const autoJob = project.autoProduce || null;
  const episodes = useMemo(
    () => [...(bundle?.episodes || [])].sort((a, b) => a.episodeNumber - b.episodeNumber),
    [bundle?.episodes],
  );
  const [focusEpisodeIdLocal, setFocusEpisodeIdLocal] = useState(focusEpisodeIdProp || "");
  const focusEpisodeId = focusEpisodeIdProp ?? focusEpisodeIdLocal;
  const setFocusEpisodeId = onFocusEpisode || setFocusEpisodeIdLocal;
  const [mobileEpOpen, setMobileEpOpen] = useState(false);

  useEffect(() => {
    if (focusEpisodeIdProp && focusEpisodeIdProp !== focusEpisodeIdLocal) {
      setFocusEpisodeIdLocal(focusEpisodeIdProp);
    }
  }, [focusEpisodeIdProp, focusEpisodeIdLocal]);

  useEffect(() => {
    if (focusEpisodeId && !episodes.some((e) => e.id === focusEpisodeId)) {
      setFocusEpisodeId(episodes[0]?.id || "");
    } else if (!focusEpisodeId && episodes[0]) {
      setFocusEpisodeId(episodes[0].id);
    }
  }, [episodes, focusEpisodeId, setFocusEpisodeId]);

  const focusEpisode = useMemo(
    () => episodes.find((e) => e.id === focusEpisodeId) || null,
    [episodes, focusEpisodeId],
  );
  const autoLive = useMemo(
    () => (autoJob?.status === "running" ? autoLiveProgress(autoJob, bundle) : null),
    [autoJob, bundle],
  );
  const counts = stepCounts(bundle, focusEpisode);
  const caps = config?.capabilities || {};
  const steps = NAV_STEPS.map((s) => ({
    ...s,
    icon: STEP_ICONS[s.key] || s.icon || Clapperboard,
  }));
  const navStep = WORKSPACE_KEYS.has(step) ? "workspace" : step;
  const activeMeta =
    steps.find((s) => s.key === navStep) || steps[0] || { key: step, label: step, note: "", icon: Clapperboard };
  const keysMissing = !(caps.deepseek && caps.seedream && caps.seedance);
  const pollRef = useRef(null);
  const stageIndex = Math.max(0, steps.findIndex((s) => s.key === navStep)) + 1;

  // Legacy deep-links (storyboard/audio/edit) land on the unified workspace.
  useEffect(() => {
    if (WORKSPACE_KEYS.has(step) && step !== "workspace") {
      setStep("workspace");
    }
  }, [step, setStep]);

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
    if (onRequireAuth && !onRequireAuth()) return;
    try {
      setBusyMsg?.(t("studio_auto_starting"));
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
    onRequireAuth,
    readOnly,
    focusEpisodeId,
    onFocusEpisode: setFocusEpisodeId,
    setStep,
  };

  if (loading && !bundle) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 text-sm text-[var(--muted)]">
        <div className="inline-flex items-center gap-2">
          <Loader2 className="h-4 w-4 animate-spin" /> {t("studio_boot_loading")}
        </div>
        <button type="button" className="btn-secondary !min-h-9" onClick={onBack}>
          <ArrowLeft className="h-4 w-4" /> {t("studio_action_back")}
        </button>
      </div>
    );
  }

  const renderEpisodeButton = (episode) => {
    const active = episode.id === focusEpisodeId;
    const summary = episodeShotSummary(bundle, episode);
    const prepDone = ["script", "character", "scene", "prop"].filter((k) =>
      k === "script" ? episode.status === "confirmed" : stepDone(bundle, k, episode),
    );
    const deskDone = stepDone(bundle, "storyboard", episode) || stepDone(bundle, "edit", episode);
    const dur = formatDuration(summary.durationSec);
    const confirmed = episode.status === "confirmed";
    return (
      <button
        key={episode.id}
        type="button"
        onClick={() => {
          setFocusEpisodeId(episode.id);
          setMobileEpOpen(false);
          if (confirmed) setStep("workspace");
        }}
        className={`w-full rounded-xl border px-3 py-2.5 text-left transition ${
          active
            ? "border-[#7c6cff]/55 bg-[#7c6cff]/15 shadow-[0_0_20px_rgba(124,108,255,.2)]"
            : "border-transparent hover:border-white/10 hover:bg-white/[.04]"
        }`}
      >
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className="timecode text-[10px] text-white/40">
                {String(episode.episodeNumber).padStart(2, "0")}
              </span>
              <span className={`truncate text-sm font-semibold ${active ? "text-white" : "text-white/80"}`}>
                {formatEpisodeLabel(episode.episodeNumber, episode.title) ||
                  t("studio_episode_item_title", {
                    n: episode.episodeNumber,
                    title: episode.title || t("studio_episode_untitled"),
                  })}
              </span>
            </div>
            <div className="mt-1 flex flex-wrap items-center gap-1.5 text-[10px]">
              <span className={confirmed ? "text-[var(--ok)]" : "text-white/40"}>
                {confirmed ? t("studio_episode_status_confirmed") : t("studio_episode_status_draft")}
              </span>
              {summary.total > 0 ? (
                <span className="text-white/35">
                  {t("studio_episode_shots", { ready: summary.ready, total: summary.total })}
                </span>
              ) : null}
              {dur ? <span className="text-white/35">{dur}</span> : null}
            </div>
          </div>
          <span className="shrink-0 text-[10px] tabular-nums text-white/35">
            {prepDone.length + (deskDone ? 1 : 0)}/5
          </span>
        </div>
        <div className="mt-2 flex gap-1">
          {steps.map((s) => {
            const done =
              s.key === "workspace"
                ? deskDone
                : s.key === "script"
                  ? confirmed
                  : stepDone(bundle, s.key, episode);
            return (
              <span
                key={s.key}
                title={s.label}
                className={`h-1.5 flex-1 rounded-full ${done ? "bg-[var(--ok)]" : "bg-white/10"}`}
              />
            );
          })}
        </div>
      </button>
    );
  };

  return (
    <main className="min-h-screen lg:h-screen lg:overflow-hidden">
      <div className="grid min-h-screen lg:h-screen lg:grid-cols-[220px_1fr]">
        <aside className="hidden border-r border-[var(--line)] bg-[#0a0b10] lg:flex lg:h-screen lg:flex-col">
          <div className="border-b border-[var(--line)] p-3">
            <button
              type="button"
              onClick={onBack}
              className="btn-secondary flex w-full !min-h-9 items-center justify-center gap-1.5 !px-2 text-xs"
              aria-label={t("studio_action_back")}
              title={t("studio_action_back")}
            >
              <ArrowLeft className="h-4 w-4 shrink-0" />
              <span className="truncate">{t("studio_action_back")}</span>
            </button>
            <div className="mt-3">
              <div className="timecode text-[9px] text-white/35">{t("studio_episode_rail_label")}</div>
              <div className="mt-0.5 text-sm font-semibold text-white/85">
                {t("studio_episode_rail_count", { count: episodes.length })}
              </div>
            </div>
          </div>
          <div className="scrollbar-thin min-h-0 flex-1 space-y-1 overflow-y-auto p-2">
            {episodes.length ? (
              episodes.map(renderEpisodeButton)
            ) : (
              <div className="rounded-xl border border-dashed border-white/10 px-3 py-8 text-center">
                <p className="text-xs leading-5 text-white/45">{t("studio_episode_empty")}</p>
                <button
                  type="button"
                  className="btn-primary mt-3 !min-h-8 !px-3 text-xs"
                  onClick={() => setStep("script")}
                >
                  {t("studio_episode_empty_cta")}
                </button>
              </div>
            )}
          </div>
        </aside>

        <section className="relative flex min-w-0 flex-col lg:h-screen lg:overflow-hidden">
          {(busyMsg || loading) && (
            <div className="absolute inset-x-0 top-16 z-20 flex items-center justify-center gap-2 bg-[#7c6cff]/90 px-4 py-2 text-sm text-white">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              {busyMsg || t("common_state_loading")}
            </div>
          )}
          {readOnly ? (
            <div className="flex items-center justify-between gap-3 border-b border-amber-500/30 bg-amber-500/10 px-4 py-2 text-xs text-amber-100 md:px-6">
              <span>浏览模式：可查看项目进度与素材，生成 / 保存需登录</span>
              <button
                type="button"
                className="btn-primary !min-h-7 !px-3 text-[11px]"
                onClick={() => onRequireAuth?.()}
              >
                登录后创作
              </button>
            </div>
          ) : null}
          <header className="sticky top-0 z-30 border-b border-[var(--line)] bg-[#0c0e14]/95 backdrop-blur">
            <div className="flex min-h-14 items-center justify-between gap-3 px-4 py-2 md:px-6">
              <div className="flex min-w-0 items-center gap-3">
                <button
                  type="button"
                  onClick={onBack}
                  className="btn-secondary !min-h-9 shrink-0 !px-3 lg:hidden"
                  aria-label={t("studio_action_back")}
                >
                  <ArrowLeft className="h-4 w-4" />
                </button>
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <h1 className="truncate text-lg font-semibold">{project.title || projectId}</h1>
                    <span className="rounded-full border border-white/10 bg-white/[.04] px-2 py-0.5 text-[10px] text-white/55">
                      {project.genre || t("studio_meta_genre_unset")}
                    </span>
                    <span className="rounded-full border border-white/10 bg-white/[.04] px-2 py-0.5 text-[10px] text-white/55">
                      {project.ratio || "9:16"}
                    </span>
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  className="btn-secondary !min-h-9 lg:hidden"
                  onClick={() => setMobileEpOpen((v) => !v)}
                >
                  {focusEpisode
                    ? t("studio_episode_mobile_current", { n: focusEpisode.episodeNumber })
                    : t("studio_episode_rail_label")}
                </button>
                <StudioModelBar
                  config={config}
                  onChanged={() => {
                    onRefresh?.();
                  }}
                />
                {keysMissing ? (
                  <button type="button" className="btn-secondary !min-h-9" onClick={() => onNeedKeys?.()}>
                    <KeyRound className="h-3.5 w-3.5" /> {t("studio_action_keys")}
                  </button>
                ) : null}
                <button type="button" className="btn-secondary !min-h-9" onClick={onRefresh} disabled={loading}>
                  <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} /> {t("studio_action_refresh")}
                </button>
              </div>
            </div>

            {mobileEpOpen ? (
              <div className="max-h-64 space-y-1 overflow-y-auto border-t border-[var(--line)] bg-[#0a0b10] p-2 lg:hidden">
                {episodes.length ? episodes.map(renderEpisodeButton) : (
                  <p className="px-3 py-4 text-center text-xs text-white/45">{t("studio_episode_empty")}</p>
                )}
              </div>
            ) : null}

            <nav className="scrollbar-thin flex gap-1 overflow-x-auto border-t border-[var(--line)] px-3 py-2 md:px-5">
              {steps.map((item, index) => {
                const Icon = item.icon;
                const active = item.key === navStep;
                const done =
                  item.key === "workspace"
                    ? stepDone(bundle, "storyboard", focusEpisode) || stepDone(bundle, "edit", focusEpisode)
                    : item.key === "script"
                      ? focusEpisode?.status === "confirmed"
                      : stepDone(bundle, item.key, focusEpisode);
                const countLabel =
                  item.key === "workspace"
                    ? counts.storyboard
                    : counts[item.key];
                return (
                  <button
                    key={item.key}
                    type="button"
                    onClick={() => setStep(item.key)}
                    className={`flex min-w-[7.5rem] shrink-0 items-center gap-2 rounded-xl border px-3 py-2 text-left transition ${
                      active
                        ? "border-transparent bg-[var(--gradient)] text-white shadow-[0_0_18px_rgba(124,108,255,.35)]"
                        : done
                          ? "border-[var(--ok)]/30 bg-[var(--ok)]/10 text-white/85 hover:bg-[var(--ok)]/15"
                          : "border-white/10 bg-white/[.03] text-white/65 hover:bg-white/[.06] hover:text-white"
                    }`}
                  >
                    <span className="relative flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-black/20">
                      {done && !active ? <Check className="h-3.5 w-3.5" /> : <Icon className="h-3.5 w-3.5" />}
                      <span className="timecode absolute -right-1 -top-1 rounded-full bg-black/70 px-1 text-[8px] text-white/50">
                        {index + 1}
                      </span>
                    </span>
                    <span className="min-w-0">
                      <span className="block truncate text-xs font-semibold">{item.label}</span>
                      <span className={`mt-0.5 block truncate text-[9px] ${active ? "text-white/70" : "text-white/35"}`}>
                        {countLabel}
                      </span>
                    </span>
                  </button>
                );
              })}
            </nav>
          </header>

          {keysMissing ? (
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[#f59e0b]/30 bg-[#f59e0b]/10 px-4 py-2.5 text-xs text-[#fde68a] md:px-6">
              <span>{t("studio_banner_keys_hint")}</span>
              <button type="button" className="btn-primary !min-h-8 !px-3" onClick={() => onNeedKeys?.()}>
                <KeyRound className="h-3.5 w-3.5" /> {t("studio_action_keys")}
              </button>
            </div>
          ) : null}
          {autoJob?.status === "running" && autoLive ? (
            <div className="border-b border-[#7c6cff]/35 bg-[#7c6cff]/15 px-4 py-2.5 text-xs text-[#ddd6fe] md:px-6">
              <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
                <span className="inline-flex items-center gap-2 font-medium">
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  {autoLive.running?.label || autoJob.step || t("studio_auto_preparing")}
                  <span className="font-normal text-white/55">
                    {focusEpisode
                      ? t("studio_episode_mobile_current", { n: focusEpisode.episodeNumber })
                      : t("studio_episode_rail_label")}
                  </span>
                </span>
                <span className="inline-flex items-center gap-2 text-white/70">
                  <span className="h-1.5 w-28 overflow-hidden rounded-full bg-black/30">
                    <span
                      className="block h-full rounded-full bg-[#c4b5fd]"
                      style={{ width: `${autoLive.pct}%` }}
                    />
                  </span>
                  <span className="tabular-nums">
                    {t("studio_auto_live_steps", { done: autoLive.doneSteps, total: autoLive.totalSteps })}
                  </span>
                </span>
                {autoLive.running?.id === "videos" && (autoLive.video.gen || autoLive.video.fail) ? (
                  <span className="tabular-nums text-white/85">
                    {t("studio_auto_live_active", { gen: autoLive.video.gen, fail: autoLive.video.fail })}
                  </span>
                ) : null}
                {autoLive.running?.id === "entities" ? (
                  <span className="tabular-nums text-white/85">
                    {t("studio_auto_live_images", autoLive.images)}
                  </span>
                ) : null}
                {autoLive.detail ? (
                  <span className="text-white/80">{t("studio_auto_live_now", { detail: autoLive.detail })}</span>
                ) : null}
              </div>
              {autoLive.lastText && autoLive.lastText !== autoLive.detail ? (
                <p className={`mt-1 truncate text-[11px] ${autoLive.lastOk ? "text-white/45" : "text-red-200"}`}>
                  {autoLive.lastText}
                </p>
              ) : (
                <p className="mt-1 text-[11px] text-white/40">{t("studio_auto_running_hint")}</p>
              )}
            </div>
          ) : null}
          {autoJob?.status === "success" && autoJob.exportUrl ? (
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[var(--ok)]/30 bg-[var(--ok)]/10 px-4 py-2.5 text-xs text-[var(--ok)] md:px-6">
              <span>{t("studio_auto_success")}</span>
              <a className="btn-secondary !min-h-8 !px-3" href={autoJob.exportUrl} target="_blank" rel="noreferrer">
                {t("studio_auto_preview")}
              </a>
            </div>
          ) : null}
          {autoJob?.status === "failed" ? (
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-red-500/30 bg-red-500/10 px-4 py-2.5 text-xs text-red-200 md:px-6">
              <span>{t("studio_auto_failed", { error: autoJob.error || t("common_state_error") })}</span>
              <button type="button" className="btn-secondary !min-h-8 !px-3" onClick={() => void startAutoFromWorkshop()}>
                <Wand2 className="h-3.5 w-3.5" /> {t("common_action_retry")}
              </button>
            </div>
          ) : null}
          {!keysMissing && (project.brief || "").trim() && (!autoJob || autoJob.status === "success") ? (
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-white/10 bg-white/[.03] px-4 py-2.5 text-xs text-white/60 md:px-6">
              <span>{t("studio_auto_cta_hint")}</span>
              <button type="button" className="btn-secondary !min-h-8 !px-3" onClick={() => void startAutoFromWorkshop()}>
                <Wand2 className="h-3.5 w-3.5" /> {t("studio_auto_cta")}
              </button>
            </div>
          ) : null}

          {/* Workspace owns its own toolbar title — avoid duplicating「工作台 · 第N集」. */}
          {navStep !== "workspace" ? (
            <div className="border-b border-[var(--line)] bg-black/20 px-4 py-2 md:px-6">
              <div className="label !mb-0">
                {t("studio_stage_label", { n: String(stageIndex).padStart(2, "0") })}
              </div>
              <h2 className="text-base font-semibold">
                {activeMeta.label}
                {focusEpisode ? (
                  <span className="ml-2 text-sm font-normal text-white/45">
                    · {t("studio_stage_focus_episode", {
                      n: focusEpisode.episodeNumber,
                      title: focusEpisode.title || t("studio_episode_untitled"),
                    })}
                  </span>
                ) : null}
              </h2>
            </div>
          ) : null}

          <div
            className={
              navStep === "workspace"
                ? "flex min-h-0 flex-1 flex-col overflow-hidden p-3 md:p-4 lg:h-[calc(100vh-8.5rem)]"
                : "scrollbar-thin min-h-[calc(100vh-11rem)] overflow-y-auto p-4 md:p-6 lg:h-[calc(100vh-11rem)]"
            }
          >
            {navStep === "script" && <ScriptStep {...common} />}
            {navStep === "character" && <EntityStep {...common} kind="character" />}
            {navStep === "scene" && <EntityStep {...common} kind="scene" />}
            {navStep === "prop" && <EntityStep {...common} kind="prop" />}
            {navStep === "workspace" && <SegmentWorkspace {...common} />}
          </div>
        </section>
      </div>
    </main>
  );
}
