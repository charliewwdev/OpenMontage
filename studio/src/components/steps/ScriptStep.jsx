import { useEffect, useMemo, useState } from "react";
import {
  Check,
  ChevronDown,
  ChevronUp,
  Clock3,
  Copy,
  FilePenLine,
  Forward,
  Loader2,
  Save,
  Sparkles,
  Trash2,
  X,
} from "lucide-react";
import { api } from "../../api";
import { requireCapability, toastMaybeKeys } from "../../lib/keys";
import { toast } from "../../lib/toast";
import { useTimer } from "../../lib/useTimer";
import { ConfirmDialog } from "../ConfirmDialog";
import { ModalOverlay } from "../ModalPortal";
import { AspectRatioPicker } from "../project-settings/AspectRatioPicker";
import { GenrePicker } from "../project-settings/GenrePicker";
import { VideoStylePicker } from "../project-settings/VideoStylePicker";

import { tr, useLocale } from "../../lib/i18n";

const MAX_PER_REQUEST = 10;

function parseCount(value, max = MAX_PER_REQUEST) {
  const count = Number(value);
  return Number.isInteger(count) && count >= 1 && count <= max ? count : null;
}

export function ScriptStep({
  projectId,
  bundle,
  config,
  setBusyMsg,
  onBundle,
  onRefresh,
  onNeedKeys,
  onRequireAuth,
  readOnly = false,
  focusEpisodeId,
  onFocusEpisode,
}) {
  useLocale();
  const project = bundle?.project || {};
  const caps = config?.capabilities || {};
  const episodes = useMemo(
    () => [...(bundle?.episodes || [])].sort((a, b) => a.episodeNumber - b.episodeNumber),
    [bundle?.episodes],
  );

  const [form, setForm] = useState({
    title: project.title || "",
    brief: project.brief || "",
    synopsis: project.synopsis || "",
    genre: project.genre || "",
    visualStyle: project.visualStyle || "",
    ratio: project.ratio || "9:16",
  });
  const [generationEpisodeCount, setGenerationEpisodeCount] = useState(() => {
    const planned = Number(project.plannedEpisodes);
    if (Number.isInteger(planned) && planned >= 1) return Math.min(planned, MAX_PER_REQUEST);
    return 1;
  });
  const [plannedEpisodes, setPlannedEpisodes] = useState(project.plannedEpisodes ?? "");
  const [saving, setSaving] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [continuing, setContinuing] = useState(false);
  const [rewriting, setRewriting] = useState(false);
  const [batchConfirming, setBatchConfirming] = useState(false);
  const [briefCollapsed, setBriefCollapsed] = useState(() => {
    try {
      const raw = sessionStorage.getItem(`om-script-brief-collapsed:${projectId}`);
      if (raw === "1") return true;
      if (raw === "0") return false;
    } catch {
      /* ignore */
    }
    // Already have episodes → collapse public brief so the editor gets space.
    return (bundle?.episodes || []).length > 0;
  });
  const [selectedId, setSelectedId] = useState(focusEpisodeId || episodes[0]?.id || null);
  const [confirmRegen, setConfirmRegen] = useState(false);
  const [confirmBatch, setConfirmBatch] = useState(false);
  const [showContinue, setShowContinue] = useState(false);
  const [showRewrite, setShowRewrite] = useState(false);
  const [continueEpisodeCount, setContinueEpisodeCount] = useState(1);
  const [continueInstruction, setContinueInstruction] = useState("");
  const [continueBrief, setContinueBrief] = useState("");
  const [continueAsFinale, setContinueAsFinale] = useState(false);
  const [rewriteStartEpisode, setRewriteStartEpisode] = useState(1);
  const [rewriteEpisodeCount, setRewriteEpisodeCount] = useState(1);
  const [rewriteInstruction, setRewriteInstruction] = useState("");

  const operationBusy = saving || generating || continuing || rewriting || batchConfirming;
  const creativeBusy = generating || continuing || rewriting;
  const { formatted: elapsedTime } = useTimer(creativeBusy);
  const creativeStatus = generating
    ? tr("ui_script_writing_the_script_and_organizing_asset")
    : continuing
      ? tr("ui_script_continuing_with_the_next_episodes")
      : rewriting
        ? tr("ui_script_rewriting_the_selected_episodes")
        : "";

  useEffect(() => {
    setForm({
      title: project.title || "",
      brief: project.brief || "",
      synopsis: project.synopsis || "",
      genre: project.genre || "",
      visualStyle: project.visualStyle || "",
      ratio: project.ratio || "9:16",
    });
    setPlannedEpisodes(project.plannedEpisodes ?? "");
    const planned = Number(project.plannedEpisodes);
    if (Number.isInteger(planned) && planned >= 1) {
      setGenerationEpisodeCount((current) => {
        const n = Number(current);
        if (!Number.isInteger(n) || n < 1) return Math.min(planned, MAX_PER_REQUEST);
        return Math.min(n, planned, MAX_PER_REQUEST);
      });
    }
  }, [project.title, project.brief, project.synopsis, project.genre, project.visualStyle, project.ratio, project.plannedEpisodes]);

  useEffect(() => {
    if (focusEpisodeId && focusEpisodeId !== selectedId) {
      setSelectedId(focusEpisodeId);
    }
  }, [focusEpisodeId]); // eslint-disable-line react-hooks/exhaustive-deps -- sync from shell focus only

  useEffect(() => {
    if (selectedId && !episodes.some((e) => e.id === selectedId)) {
      const next = episodes[0]?.id || null;
      setSelectedId(next);
      if (next) onFocusEpisode?.(next);
    } else if (!selectedId && episodes[0]) {
      setSelectedId(episodes[0].id);
      onFocusEpisode?.(episodes[0].id);
    }
  }, [episodes, selectedId, onFocusEpisode]);

  useEffect(() => {
    try {
      sessionStorage.setItem(`om-script-brief-collapsed:${projectId}`, briefCollapsed ? "1" : "0");
    } catch {
      /* ignore */
    }
  }, [briefCollapsed, projectId]);

  const selected = useMemo(() => episodes.find((e) => e.id === selectedId) || null, [episodes, selectedId]);
  const maxEpisodeNumber = useMemo(() => Math.max(0, ...episodes.map((e) => e.episodeNumber)), [episodes]);
  const draftEpisodes = useMemo(() => episodes.filter((e) => e.status !== "confirmed"), [episodes]);
  const maxRewriteCount = Math.max(1, Math.min(MAX_PER_REQUEST, maxEpisodeNumber - rewriteStartEpisode + 1));

  const apply = (b) => {
    if (b?.project) onBundle?.(b);
    else onRefresh?.();
  };

  const saveProject = async (quiet = false) => {
    if (!form.genre.trim()) {
      toast.error(tr("ui_script_pick_a_genre_or_enter_a"));
      return false;
    }
    setSaving(true);
    setBusyMsg?.(quiet ? "" : tr("ui_script_saving_settings"));
    try {
      const planned =
        plannedEpisodes === "" || plannedEpisodes === null
          ? null
          : Number(plannedEpisodes);
      const b = await api(`/api/projects/${encodeURIComponent(projectId)}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: form.title,
          brief: form.brief,
          synopsis: form.synopsis,
          genre: form.genre,
          visualStyle: form.visualStyle,
          ratio: form.ratio,
          plannedEpisodes: Number.isFinite(planned) ? planned : null,
        }),
      });
      apply(b);
      if (!quiet) toast.success(tr("ui_script_project_settings_saved"));
      return true;
    } catch (e) {
      toast.error(String(e.message || e));
      return false;
    } finally {
      setSaving(false);
      setBusyMsg?.("");
    }
  };

  const plannedCount = useMemo(() => {
    if (plannedEpisodes === "" || plannedEpisodes === null) return null;
    const n = Number(plannedEpisodes);
    return Number.isInteger(n) && n >= 1 ? n : null;
  }, [plannedEpisodes]);

  const runGenerate = async () => {
    if (onRequireAuth && !onRequireAuth()) return;
    if (!requireCapability(caps, "deepseek", onNeedKeys, tr("ui_script_text_llm_key"))) return;
    if (!form.brief.trim()) return toast.error(tr("ui_script_fill_in_the_brief_or_paste"));
    if (!form.genre.trim()) return toast.error(tr("ui_script_pick_a_genre_or_enter_a"));
    const episodeCount = parseCount(generationEpisodeCount);
    if (episodeCount === null) return toast.error(tr("ui_script_episodes_this_run_must_be_a", {
      MAX_PER_REQUEST: MAX_PER_REQUEST
    }));
    if (plannedCount !== null && episodeCount > plannedCount) {
      return toast.error(tr("ui_script_episodes_this_run_can_t_exceed", {
        plannedCount: plannedCount
      }));
    }
    if (episodes.length > 0 && !confirmRegen) {
      setConfirmRegen(true);
      return;
    }
    setConfirmRegen(false);
    setGenerating(true);
    setBusyMsg(tr("ui_script_writing_script"));
    try {
      if (!(await saveProject(true))) return;
      const b = await api(`/api/projects/${encodeURIComponent(projectId)}/script`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "generate",
          episodeCount,
          plannedEpisodes: plannedCount,
        }),
      });
      apply(b);
      const nextEps = b.episodes || [];
      const firstId = nextEps[0]?.id || null;
      setSelectedId(firstId);
      if (firstId) onFocusEpisode?.(firstId);
      const backend = caps.llmBackend || "LLM";
      toast.success(tr("ui_script_finished_the_script_and_asset_profiles", {
        backend: backend,
        length: nextEps.length
      }));
    } catch (e) {
      toastMaybeKeys(e, onNeedKeys);
    } finally {
      setGenerating(false);
      setBusyMsg("");
    }
  };

  const runContinue = async () => {
    if (!requireCapability(caps, "deepseek", onNeedKeys, tr("ui_script_text_llm_key"))) return;
    const episodeCount = parseCount(continueEpisodeCount);
    if (episodeCount === null) return toast.error(tr("ui_script_episodes_to_continue_must_be_a", {
      MAX_PER_REQUEST: MAX_PER_REQUEST
    }));
    setContinuing(true);
    setShowContinue(false);
    setBusyMsg(tr("ui_script_continuing"));
    try {
      if (!(await saveProject(true))) return;
      const b = await api(`/api/projects/${encodeURIComponent(projectId)}/script`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "continue",
          episodeCount,
          instruction: continueInstruction.trim(),
          brief: continueBrief.trim(),
          asFinale: continueAsFinale,
        }),
      });
      apply(b);
      toast.success(tr("ui_script_continuation_done"));
    } catch (e) {
      toastMaybeKeys(e, onNeedKeys);
    } finally {
      setContinuing(false);
      setBusyMsg("");
    }
  };

  const runRewrite = async () => {
    if (!requireCapability(caps, "deepseek", onNeedKeys, tr("ui_script_text_llm_key"))) return;
    const episodeCount = parseCount(rewriteEpisodeCount, maxRewriteCount);
    if (episodeCount === null) return toast.error(tr("ui_script_invalid_number_of_episodes_to_rewrite"));
    if (!rewriteInstruction.trim()) return toast.error(tr("ui_script_please_enter_rewrite_notes"));
    setRewriting(true);
    setShowRewrite(false);
    setBusyMsg(tr("ui_script_rewriting"));
    try {
      const b = await api(`/api/projects/${encodeURIComponent(projectId)}/script`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "rewrite",
          startEpisode: rewriteStartEpisode,
          episodeCount,
          instruction: rewriteInstruction.trim(),
        }),
      });
      apply(b);
      toast.success(tr("ui_script_rewrote_episodes", {
        rewriteStartEpisode: rewriteStartEpisode,
        1: rewriteStartEpisode + episodeCount - 1
      }));
    } catch (e) {
      toastMaybeKeys(e, onNeedKeys);
    } finally {
      setRewriting(false);
      setBusyMsg("");
    }
  };

  const confirmAllDrafts = async () => {
    if (!draftEpisodes.length) return toast.info(tr("ui_script_no_episodes_waiting_to_be_locked"));
    setConfirmBatch(false);
    setBatchConfirming(true);
    setBusyMsg(tr("ui_script_locking_in_bulk"));
    try {
      const b = await api(`/api/projects/${encodeURIComponent(projectId)}/episodes`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ episodeIds: draftEpisodes.map((e) => e.id), status: "confirmed" }),
      });
      apply(b);
      toast.success(tr("ui_script_locked_episodes", {
        length: draftEpisodes.length
      }));
    } catch (e) {
      toast.error(String(e.message || e));
    } finally {
      setBatchConfirming(false);
      setBusyMsg("");
    }
  };

  const copyAll = async () => {
    const text = episodes
      .map((ep) => `${ep.title || tr("ui_script_ep_2", {
      episodeNumber: ep.episodeNumber
    })}\n\n${ep.content || ""}`)
      .join("\n\n");
    try {
      await navigator.clipboard.writeText(text);
      toast.success(tr("ui_script_copied_all_episode_scripts"));
    } catch {
      toast.error(tr("ui_script_copy_failed"));
    }
  };

  return (
    <div className="mx-auto max-w-[1500px] space-y-5">
      <section className="panel overflow-hidden">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--line)] px-4 py-3 md:px-5">
          <div className="min-w-0">
            <div className="label !mb-0">Story brief</div>
            <div className="flex flex-wrap items-baseline gap-2">
              <h3 className="display-type text-lg font-semibold md:text-xl">{tr("ui_script_working_draft")}</h3>
              {briefCollapsed ? (
                <span className="truncate text-xs text-[var(--muted)]">
                  {form.title || tr("ui_script_untitled")}· {form.ratio || "9:16"}· {form.genre || tr("ui_script_no_genre")}{" "}{tr("ui_script_episodes_generated", {
                    length: episodes.length
                  })}</span>
              ) : null}
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {!briefCollapsed ? (
              <button type="button" className="btn-secondary !min-h-9" disabled={operationBusy} onClick={() => void saveProject()}>
                <Save className="h-4 w-4" />
                {saving ? tr("ui_script_saving") : tr("ui_script_save_settings")}
              </button>
            ) : null}
            <button
              type="button"
              className="btn-secondary !min-h-9"
              onClick={() => setBriefCollapsed((v) => !v)}
              aria-expanded={!briefCollapsed}
            >
              {briefCollapsed ? <ChevronDown className="h-4 w-4" /> : <ChevronUp className="h-4 w-4" />}
              {briefCollapsed ? tr("ui_script_show_shared_settings") : tr("ui_script_hide_shared_settings")}
            </button>
          </div>
        </div>
        {!briefCollapsed ? (
          <div className="grid lg:grid-cols-[minmax(0,1fr)_360px]">
            <div className="p-5 md:p-6">
              <p className="text-sm text-[var(--muted)]">{tr("ui_script_deepseek_writes_in_batches_of_this")}</p>
              <div className="mt-5 grid gap-4 md:grid-cols-2">
                <label className="md:col-span-2">
                  <span className="label">{tr("ui_script_title")}</span>
                  <input
                    className="field"
                    value={form.title}
                    disabled={operationBusy}
                    onChange={(e) => setForm({ ...form, title: e.target.value })}
                  />
                </label>
                <div className="min-w-0 md:col-span-2">
                  <span className="label">{tr("ui_script_aspect_ratio")}</span>
                  <AspectRatioPicker
                    value={form.ratio}
                    disabled={operationBusy}
                    ratios={config?.ratios}
                    onChange={(ratio) => setForm({ ...form, ratio })}
                  />
                </div>
                <div className="md:col-span-2">
                  <span className="label">{tr("ui_script_genre")}</span>
                  <GenrePicker
                    value={form.genre}
                    disabled={operationBusy}
                    genres={config?.genres}
                    onChange={(genre) => setForm({ ...form, genre })}
                  />
                </div>
                <div className="md:col-span-2">
                  <span className="label">{tr("ui_script_visual_style")}</span>
                  <VideoStylePicker
                    value={form.visualStyle}
                    disabled={operationBusy}
                    styles={config?.styles}
                    categories={config?.styleCategories}
                    onChange={(visualStyle) => setForm({ ...form, visualStyle })}
                  />
                </div>
                <label className="md:col-span-2">
                  <span className="label">{tr("ui_script_synopsis")}</span>
                  <textarea
                    className="field min-h-20 resize-y"
                    value={form.synopsis}
                    disabled={operationBusy}
                    onChange={(e) => setForm({ ...form, synopsis: e.target.value })}
                    placeholder={tr("ui_script_filled_in_automatically_after_generation_or")}
                  />
                </label>
                <label className="md:col-span-2">
                  <span className="label">{tr("ui_script_brief_source_material")}</span>
                  <textarea
                    className="field min-h-52 resize-y leading-7"
                    value={form.brief}
                    disabled={operationBusy}
                    onChange={(e) => setForm({ ...form, brief: e.target.value })}
                    placeholder={tr("ui_script_paste_a_story_or_novel_excerpt")}
                  />
                </label>
              </div>
            </div>

            <div className="flex flex-col justify-between border-t border-[var(--line)] bg-[var(--navy)] p-6 text-white lg:border-l lg:border-t-0">
              <div>
                <div className="timecode text-[10px] text-[var(--timecode)]">TEXT MODEL</div>
                <div className="mt-2 text-lg font-semibold">{caps.llmBackend || "LLM"} · drama-script</div>
                <p className="mt-2 text-xs leading-6 text-white/55">{tr("ui_script_episodes_this_run_sets_how_many")}</p>
                {episodes.length > 0 ? (
                  <div className="mt-5 rounded-xl border border-white/10 bg-white/5 p-4">
                    <div className="timecode text-[10px] text-white/40">CURRENT PROGRESS</div>
                    <div className="mt-2 text-xl font-semibold">{tr("ui_script_episodes_generated_2", {
                        length: episodes.length
                      })}</div>
                    <div className="mt-1 text-xs text-white/50">{tr("ui_script_planned")}{" "}{plannedEpisodes === "" ? tr("ui_script_not_set") : tr("ui_script_ep_3", {
                        plannedEpisodes: plannedEpisodes
                      })}
                    </div>
                  </div>
                ) : null}
                {creativeBusy ? (
                  <div className="mt-5 rounded-xl border border-[var(--projector)]/35 bg-[var(--projector)]/10 p-4" role="status">
                    <div className="flex items-center gap-2 text-sm font-semibold">
                      <Loader2 className="h-4 w-4 shrink-0 animate-spin text-[var(--projector)]" />
                      <span>{creativeStatus}</span>
                    </div>
                    <div className="timecode mt-2 flex items-center gap-1.5 pl-6 text-[var(--timecode)]">
                      <Clock3 className="h-3.5 w-3.5" />
                      {elapsedTime}
                    </div>
                  </div>
                ) : null}
              </div>
              <div className="mt-8 space-y-4">
                <div className="grid grid-cols-2 gap-3">
                  <label className="min-w-0">
                    <span className="mb-2 flex items-center gap-2 text-xs text-white/60">{tr("ui_script_this_run")}{" "}<b className="text-[var(--timecode)]">{tr("ui_script_required")}</b>
                    </span>
                    <input
                      type="number"
                      min={1}
                      max={plannedCount ?? MAX_PER_REQUEST}
                      className="field !border-white/20 !bg-[#17243a] !text-white [color-scheme:dark] focus:!border-[var(--projector)]"
                      value={generationEpisodeCount}
                      disabled={operationBusy}
                      onChange={(e) => {
                        const raw = e.target.value === "" ? "" : Number(e.target.value);
                        if (raw === "") {
                          setGenerationEpisodeCount("");
                          return;
                        }
                        const capped =
                          plannedCount !== null ? Math.min(Number(raw), plannedCount, MAX_PER_REQUEST) : Math.min(Number(raw), MAX_PER_REQUEST);
                        setGenerationEpisodeCount(capped);
                      }}
                    />
                  </label>
                  <label className="min-w-0">
                    <span className="mb-2 flex items-center gap-2 text-xs text-white/60">{tr("ui_script_planned_total")}{" "}<b className="font-normal text-white/35">{tr("ui_script_optional")}</b>
                    </span>
                    <input
                      type="number"
                      min={1}
                      max={200}
                      className="field !border-white/20 !bg-[#17243a] !text-white [color-scheme:dark] focus:!border-[var(--projector)]"
                      value={plannedEpisodes}
                      disabled={operationBusy}
                      onChange={(e) => {
                        const next = e.target.value === "" ? "" : Number(e.target.value);
                        setPlannedEpisodes(next);
                        if (next !== "" && Number.isInteger(Number(next)) && Number(next) >= 1) {
                          setGenerationEpisodeCount((current) => {
                            const n = Number(current);
                            if (!Number.isInteger(n) || n < 1) return Math.min(Number(next), MAX_PER_REQUEST);
                            return Math.min(n, Number(next), MAX_PER_REQUEST);
                          });
                        }
                      }}
                      placeholder={tr("ui_script_leave_empty_for_open_ended")}
                    />
                  </label>
                </div>
                {plannedCount !== null && Number(generationEpisodeCount) > plannedCount ? (
                  <p className="text-xs text-amber-300/90">{tr("ui_script_this_run_can_t_exceed_the", {
                      plannedCount: plannedCount
                    })}</p>
                ) : null}
                <button
                  type="button"
                  className="btn-primary flex min-h-12 w-full !rounded-xl font-bold disabled:opacity-45"
                  disabled={operationBusy}
                  onClick={() => void runGenerate()}
                >
                  {generating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
                  {generating ? tr("ui_script_writing", {
                    elapsedTime: elapsedTime
                  }) : episodes.length ? tr("ui_script_regenerate_with_this_episode_count") : tr("ui_script_generate_script_and_asset_profiles")}
                </button>
              </div>
            </div>
          </div>
        ) : null}
      </section>

      <section className="space-y-4">
        {episodes.length > 0 ? (
          <div className="panel flex flex-wrap items-center justify-between gap-3 px-4 py-3">
            <div>
              <div className="label !mb-0">Episodes</div>
              <strong className="text-sm">{tr("ui_script_episodes_switch_on_the_left", {
                  length: episodes.length
                })}</strong>
            </div>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                className="btn-secondary !min-h-9 !justify-center !gap-1 !px-2.5 text-[11px]"
                disabled={operationBusy || !draftEpisodes.length}
                onClick={() => setConfirmBatch(true)}
              >
                {batchConfirming ? <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin" /> : <Check className="h-3.5 w-3.5 shrink-0" />}{tr("ui_script_lock", {
                  0: draftEpisodes.length ? ` ${draftEpisodes.length}` : ""
                })}</button>
              <button
                type="button"
                className="btn-secondary !min-h-9 !justify-center !gap-1 !px-2.5 text-[11px]"
                disabled={operationBusy}
                onClick={() => void copyAll()}
              >
                <Copy className="h-3.5 w-3.5 shrink-0" />{tr("ui_script_copy")}</button>
              <button
                type="button"
                className="btn-secondary !min-h-9 !justify-center !gap-1 !px-2.5 text-[11px]"
                disabled={operationBusy}
                onClick={() => setShowContinue(true)}
              >
                {continuing ? <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin" /> : <Forward className="h-3.5 w-3.5 shrink-0" />}
                {continuing ? elapsedTime : tr("ui_script_continue")}
              </button>
              <button
                type="button"
                className="btn-secondary !min-h-9 !justify-center !gap-1 !px-2.5 text-[11px]"
                disabled={operationBusy}
                onClick={() => {
                  setRewriteStartEpisode(episodes[0]?.episodeNumber || 1);
                  setShowRewrite(true);
                }}
              >
                {rewriting ? <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin" /> : <FilePenLine className="h-3.5 w-3.5 shrink-0" />}
                {rewriting ? elapsedTime : tr("ui_script_rewrite")}
              </button>
            </div>
          </div>
        ) : null}

        {selected ? (
          <EpisodeEditor
            key={selected.id + (selected.updatedAt || "")}
            projectId={projectId}
            episode={selected}
            onRefresh={onRefresh}
            onBundle={onBundle}
          />
        ) : (
          <div className="panel flex min-h-[320px] items-center justify-center px-6 text-center text-sm text-[var(--muted)]">
            {episodes.length
              ? tr("ui_script_select_an_episode_on_the_left")
              : tr("ui_script_after_the_script_is_generated_episodes")}
          </div>
        )}
      </section>

      {showContinue ? (
        <Modal title={tr("ui_script_continue_script")} label="Continue script" onClose={() => setShowContinue(false)}>
          <p className="text-sm text-[var(--muted)]">{tr("ui_script_continues_from_episode_existing_episodes_won", {
              0: maxEpisodeNumber + 1
            })}</p>
          <label className="mt-5 block">
            <span className="label">{tr("ui_script_new_brief_optional")}</span>
            <textarea className="field min-h-28 resize-y" value={continueBrief} onChange={(e) => setContinueBrief(e.target.value)} />
          </label>
          <label className="mt-4 block">
            <span className="label">{tr("ui_script_continuation_notes_optional")}</span>
            <textarea
              className="field min-h-24 resize-y"
              value={continueInstruction}
              onChange={(e) => setContinueInstruction(e.target.value)}
              placeholder={tr("ui_script_e_g_villain_escalates_stronger_romance")}
            />
          </label>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <label>
              <span className="label">{tr("ui_script_episodes_to_continue")}</span>
              <input
                className="field"
                type="number"
                min={1}
                max={MAX_PER_REQUEST}
                value={continueEpisodeCount}
                onChange={(e) => setContinueEpisodeCount(e.target.value === "" ? "" : Number(e.target.value))}
              />
            </label>
            <label className="panel-muted flex min-h-20 items-center gap-3 p-4">
              <input
                type="checkbox"
                className="h-4 w-4 accent-[var(--projector)]"
                checked={continueAsFinale}
                onChange={(e) => setContinueAsFinale(e.target.checked)}
              />
              <span>
                <strong className="block text-sm">{tr("ui_script_end_the_series_after_this_continuation")}</strong>
                <span className="mt-1 block text-xs text-[var(--muted)]">{tr("ui_script_the_last_episode_wraps_everything_up")}</span>
              </span>
            </label>
          </div>
          <div className="mt-6 flex justify-end gap-3 border-t border-[var(--line)] pt-4">
            <button type="button" className="btn-secondary" onClick={() => setShowContinue(false)}>{tr("ui_script_cancel")}</button>
            <button type="button" className="btn-primary" onClick={() => void runContinue()}>
              <Forward className="h-4 w-4" />{tr("ui_script_confirm_continue")}</button>
          </div>
        </Modal>
      ) : null}

      {showRewrite ? (
        <Modal title={tr("ui_script_rewrite_selected_episodes")} label="Rewrite episodes" onClose={() => setShowRewrite(false)}>
          <label className="block">
            <span className="label">{tr("ui_script_rewrite_notes")}</span>
            <textarea
              className="field min-h-32 resize-y"
              value={rewriteInstruction}
              onChange={(e) => setRewriteInstruction(e.target.value)}
              placeholder={tr("ui_script_e_g_keep_the_relationships_rewrite")}
              autoFocus
            />
          </label>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <label>
              <span className="label">{tr("ui_script_start_from_episode")}</span>
              <select
                className="field"
                value={rewriteStartEpisode}
                onChange={(e) => {
                  setRewriteStartEpisode(Number(e.target.value));
                  setRewriteEpisodeCount(1);
                }}
              >
                {episodes.map((ep) => (
                  <option key={ep.id} value={ep.episodeNumber}>{tr("ui_script_ep", {
                      episodeNumber: ep.episodeNumber,
                      title: ep.title
                    })}</option>
                ))}
              </select>
            </label>
            <label>
              <span className="label">{tr("ui_script_episodes_to_rewrite")}</span>
              <input
                className="field"
                type="number"
                min={1}
                max={maxRewriteCount}
                value={rewriteEpisodeCount}
                onChange={(e) => setRewriteEpisodeCount(e.target.value === "" ? "" : Number(e.target.value))}
              />
            </label>
          </div>
          <div className="mt-6 flex justify-end gap-3 border-t border-[var(--line)] pt-4">
            <button type="button" className="btn-secondary" onClick={() => setShowRewrite(false)}>{tr("ui_script_cancel")}</button>
            <button
              type="button"
              className="btn-primary"
              disabled={!rewriteInstruction.trim()}
              onClick={() => void runRewrite()}
            >
              <FilePenLine className="h-4 w-4" />{tr("ui_script_confirm_rewrite")}</button>
          </div>
        </Modal>
      ) : null}

      <ConfirmDialog
        open={confirmRegen}
        title={tr("ui_script_regenerate_the_whole_script")}
        message={tr("ui_script_existing_episodes_and_asset_profiles_will")}
        confirmLabel={tr("ui_script_regenerate")}
        danger
        onCancel={() => setConfirmRegen(false)}
        onConfirm={() => void runGenerate()}
      />
      <ConfirmDialog
        open={confirmBatch}
        title={tr("ui_script_lock_episodes_in_bulk", {
          length: draftEpisodes.length
        })}
        message={tr("ui_script_only_locked_episodes_can_move_on")}
        confirmLabel={tr("ui_script_lock_all")}
        onCancel={() => setConfirmBatch(false)}
        onConfirm={() => void confirmAllDrafts()}
      />
    </div>
  );
}

function Modal({ title, label, onClose, children }) {
  useLocale();
  return (
    <ModalOverlay onClose={onClose} className="bg-[#09101d]/80 backdrop-blur-sm">
      <section
        role="dialog"
        aria-modal="true"
        className="scrollbar-thin my-auto max-h-[min(760px,calc(100vh-2rem))] w-full max-w-3xl overflow-y-auto rounded-3xl bg-[var(--panel)] p-6 shadow-float"
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="label">{label}</div>
            <h3 className="display-type text-2xl font-semibold">{title}</h3>
          </div>
          <button type="button" className="btn-quiet !min-h-9 !px-2.5" onClick={onClose}>
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="mt-4">{children}</div>
      </section>
    </ModalOverlay>
  );
}

function EpisodeEditor({ projectId, episode, onRefresh, onBundle }) {
  useLocale();
  const [title, setTitle] = useState(episode.title || "");
  const [content, setContent] = useState(episode.content || "");
  const [saving, setSaving] = useState(false);
  const locked = episode.status === "confirmed";

  const save = async (status = episode.status) => {
    setSaving(true);
    try {
      await api(`/api/projects/${encodeURIComponent(projectId)}/episodes`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ episodeId: episode.id, title, content, status }),
      });
      await onRefresh?.();
      toast.success(status === "confirmed" ? tr("ui_script_episode_locked") : tr("ui_script_episode_saved"));
    } catch (e) {
      toast.error(String(e.message || e));
    } finally {
      setSaving(false);
    }
  };

  const remove = async () => {
    if (!window.confirm(tr("ui_script_delete_episode", {
      episodeNumber: episode.episodeNumber
    }))) return;
    try {
      // soft: mark draft empty via rewrite range not available — keep confirm only for status for now
      toast.info(tr("ui_script_use_rewrite_to_overwrite_it_single"));
    } catch (e) {
      toast.error(String(e.message || e));
    }
  };

  return (
    <div className="panel flex min-h-0 flex-col overflow-hidden">
      <div className="space-y-3 border-b border-[var(--line)] bg-[var(--panel-muted)] px-4 py-3 sm:px-5">
        <div className="flex min-w-0 items-center gap-3">
          <span className="timecode shrink-0 text-xs text-[var(--muted)]">
            EP {String(episode.episodeNumber).padStart(2, "0")}
          </span>
          <input
            className="field min-w-0 flex-1 !bg-transparent !py-2 font-semibold read-only:cursor-not-allowed read-only:opacity-70"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            readOnly={locked}
          />
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button type="button" className="btn-secondary !min-h-9" disabled={saving || locked} onClick={() => void save()}>
            <Save className="h-3.5 w-3.5" />{" "}{tr("ui_script_save")}</button>
          <button
            type="button"
            className={episode.status === "confirmed" ? "btn-secondary !min-h-9" : "btn-primary !min-h-9"}
            disabled={saving}
            onClick={() => void save(episode.status === "confirmed" ? "draft" : "confirmed")}
          >
            <Check className="h-3.5 w-3.5" />
            {episode.status === "confirmed" ? tr("ui_script_unlock") : tr("ui_script_lock_2")}
          </button>
          <button type="button" className="btn-danger !min-h-9 !px-2.5" onClick={() => void remove()}>
            <Trash2 className="h-4 w-4" />
          </button>
        </div>
      </div>
      {locked ? (
        <div className="border-b border-[var(--line)] bg-[var(--ok)]/10 px-5 py-2 text-xs text-[var(--ok)]">{tr("ui_script_this_episode_is_locked_unlock_it")}</div>
      ) : null}
      <textarea
        className="min-h-[500px] flex-1 resize-y border-0 bg-transparent p-5 font-mono text-sm leading-7 text-[var(--ink)] outline-none read-only:cursor-not-allowed read-only:bg-black/20 lg:resize-none"
        value={content}
        onChange={(e) => setContent(e.target.value)}
        placeholder={tr("ui_script_write_this_episode_s_scenes_actions")}
        readOnly={locked}
      />
    </div>
  );
}
