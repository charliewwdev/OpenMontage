import { useCallback, useEffect, useMemo, useState } from "react";
import { Clapperboard, Clock3, Loader2, Plus, Save, Sparkles, Trash2, Video } from "lucide-react";
import { api } from "../../api";
import {
  blockersFromError,
  formatEntityQaBlockers,
  isEntityQaBlockedError,
  listEntityQaBlockers,
} from "../../lib/entityQaGate";
import { requireGithubStar } from "../../lib/githubStar";
import { requireCapability, toastMaybeKeys } from "../../lib/keys";
import { toast } from "../../lib/toast";
import { useTimer } from "../../lib/useTimer";
import { ConfirmDialog } from "../ConfirmDialog";

import { tr, useLocale } from "../../lib/i18n";

export function StoryboardStep({
  projectId,
  bundle,
  config,
  setBusyMsg,
  onBundle,
  onRefresh,
  onNeedKeys,
  focusEpisodeId,
  onFocusEpisode,
}) {
  useLocale();
  const caps = config?.capabilities || {};
  const splitStages = config?.splitStages || [];
  const confirmedEpisodes = useMemo(
    () =>
      [...(bundle?.episodes || [])]
        .filter((e) => e.status === "confirmed")
        .sort((a, b) => a.episodeNumber - b.episodeNumber),
    [bundle?.episodes],
  );
  const models = config?.seedanceModels || [];
  const [episodeId, setEpisodeId] = useState(focusEpisodeId || confirmedEpisodes[0]?.id || "");
  const [model, setModel] = useState(models[0]?.id || "");
  const selectedModel = models.find((m) => m.id === model) || models[0];
  const [resolution, setResolution] = useState(selectedModel?.resolutions?.[1] || selectedModel?.resolutions?.[0] || "720p");
  const [splitting, setSplitting] = useState(false);
  const [batching, setBatching] = useState(false);
  const [selectedShotIds, setSelectedShotIds] = useState(() => new Set());
  const [dirtyShotIds, setDirtyShotIds] = useState(() => new Set());
  const [confirmSplit, setConfirmSplit] = useState(false);
  const [confirmBatch, setConfirmBatch] = useState(false);
  const [forceQaDialog, setForceQaDialog] = useState(null); // { blockers, mode, payload }
  const { elapsed: splitElapsed, formatted: splitElapsedTime } = useTimer(splitting);

  useEffect(() => {
    if (focusEpisodeId && focusEpisodeId !== episodeId) {
      setEpisodeId(focusEpisodeId);
      setSelectedShotIds(new Set());
    }
  }, [focusEpisodeId, episodeId]);

  useEffect(() => {
    if (episodeId && !(bundle?.episodes || []).some((e) => e.id === episodeId)) {
      setEpisodeId(focusEpisodeId || confirmedEpisodes[0]?.id || "");
    }
  }, [bundle?.episodes, episodeId, focusEpisodeId, confirmedEpisodes]);

  useEffect(() => {
    const resolutions = selectedModel?.resolutions || ["720p"];
    if (!resolutions.includes(resolution)) setResolution(resolutions[0]);
  }, [selectedModel, resolution]);

  const episode = (bundle?.episodes || []).find((e) => e.id === episodeId);
  const shots = useMemo(
    () =>
      (bundle?.shots || [])
        .filter((s) => s.episodeId === episodeId && !s.deletedAt)
        .sort((a, b) => a.shotOrder - b.shotOrder),
    [bundle?.shots, episodeId],
  );
  const segments = useMemo(() => {
    const map = new Map();
    for (const shot of shots) {
      const so = Number(shot.segmentOrder || shot.shotOrder || 1);
      if (!map.has(so)) map.set(so, []);
      map.get(so).push(shot);
    }
    return [...map.entries()]
      .sort((a, b) => a[0] - b[0])
      .map(([segmentOrder, group]) => {
        const sorted = [...group].sort(
          (a, b) => (a.beatIndex || a.shotOrder) - (b.beatIndex || b.shotOrder),
        );
        const lead = sorted.find((s) => s.isSegmentLead) || sorted[0];
        const duration =
          Number(lead?.segmentDuration || 0) ||
          sorted.reduce((sum, s) => sum + Number(s.duration || 0), 0);
        return { segmentOrder, shots: sorted, lead, duration };
      });
  }, [shots]);
  const hasSegmentLayout = segments.some((g) => g.shots.some((s) => Number(s.segmentOrder || 0) > 0));
  const availableEntities = useMemo(
    () =>
      (bundle?.entities || []).filter(
        (entity) =>
          !entity.deletedAt &&
          (!episode || !entity.episodes?.length || entity.episodes.includes(episode.episodeNumber)),
      ),
    [bundle?.entities, episode],
  );
  const episodeHasGenerating = shots.some((s) => s.status === "generating");
  const workflowBusy = splitting || batching;
  const generatingIds = (bundle?.shots || [])
    .filter((s) => s.status === "generating" && !s.deletedAt)
    .map((s) => s.id)
    .join(",");
  const splitStageIndex = splitStages.reduce(
    (current, stage, index) => (splitElapsed >= stage.startsAt ? index : current),
    0,
  );
  const splitStage = splitStages[splitStageIndex] || { title: tr("ui_storyboard_processing"), detail: "" };

  useEffect(() => {
    const currentIds = new Set(shots.map((s) => s.id));
    setSelectedShotIds((prev) => new Set([...prev].filter((id) => currentIds.has(id))));
    setDirtyShotIds((prev) => new Set([...prev].filter((id) => currentIds.has(id))));
  }, [shots]);

  // Legacy boards: auto-assign segmentOrder so 片段 UI appears without full re-split.
  useEffect(() => {
    if (!episodeId || !shots.length || workflowBusy || splitting) return;
    const needsMigrate = shots.some((s) => !Number(s.segmentOrder || 0));
    if (!needsMigrate) return;
    let cancelled = false;
    (async () => {
      try {
        const res = await api(`/api/projects/${encodeURIComponent(projectId)}/storyboard`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ action: "migrate-segments", episodeId }),
        });
        if (!cancelled && res?.bundle) onBundle?.(res.bundle);
      } catch {
        /* keep flat list if migrate fails */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [episodeId, projectId, shots, workflowBusy, splitting, onBundle]);

  const handleDirtyChange = useCallback((shotId, dirty) => {
    setDirtyShotIds((prev) => {
      const next = new Set(prev);
      if (dirty) next.add(shotId);
      else next.delete(shotId);
      return next;
    });
  }, []);

  const apply = (res) => {
    if (res?.bundle) onBundle?.(res.bundle);
    else onRefresh?.();
  };

  useEffect(() => {
    if (!generatingIds) return undefined;
    let cancelled = false;
    const poll = async () => {
      const ids = generatingIds.split(",").filter(Boolean);
      let changed = false;
      await Promise.all(
        ids.map(async (id) => {
          try {
            const shot = await api(
              `/api/projects/${encodeURIComponent(projectId)}/shots/${encodeURIComponent(id)}`,
            );
            if (shot.status !== "generating") changed = true;
          } catch {
            /* next poll */
          }
        }),
      );
      if (changed && !cancelled) await onRefresh?.();
    };
    void poll();
    const timer = setInterval(() => void poll(), 5000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [generatingIds, projectId, onRefresh]);

  const split = async () => {
    if (!episode) return;
    if (batching || episodeHasGenerating) {
      toast.info(tr("ui_storyboard_wait_for_this_episode_s_video"));
      return;
    }
    if (shots.length && !confirmSplit) {
      setConfirmSplit(true);
      return;
    }
    if (!(await requireGithubStar())) return;
    if (!requireCapability(caps, "deepseek", onNeedKeys, tr("ui_storyboard_text_llm_key"))) return;
    setConfirmSplit(false);
    setSplitting(true);
    setBusyMsg?.(tr("ui_storyboard_ai_is_splitting_shots"));
    try {
      const res = await api(`/api/projects/${encodeURIComponent(projectId)}/storyboard`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "generate", episodeId: episode.id }),
      });
      apply(res);
      toast.success(tr("ui_storyboard_deepseek_split_shots", {
        0: res.shots?.length || 0
      }));
    } catch (error) {
      toastMaybeKeys(error, onNeedKeys);
    } finally {
      setSplitting(false);
      setBusyMsg?.("");
    }
  };

  const add = async () => {
    if (!episode) return;
    try {
      const res = await api(`/api/projects/${encodeURIComponent(projectId)}/storyboard`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "add", episodeId: episode.id }),
      });
      apply(res);
    } catch (error) {
      toast.error(String(error.message || error));
    }
  };

  const entitiesById = useMemo(
    () => new Map((bundle?.entities || []).filter((e) => !e.deletedAt).map((e) => [e.id, e])),
    [bundle?.entities],
  );

  const blockersForShot = useCallback(
    (shot) => {
      const ents = (shot?.referenceEntityIds || [])
        .map((id) => entitiesById.get(id))
        .filter(Boolean);
      return listEntityQaBlockers(ents);
    },
    [entitiesById],
  );

  const generateVideo = async (shotId, silent = false, { forceEntityQa = false } = {}) => {
    if (!(await requireGithubStar())) return;
    if (!requireCapability(caps, "seedance", onNeedKeys, tr("ui_storyboard_render_backend_comfyui_seedance"))) return;
    const shot = (bundle?.shots || []).find((s) => s.id === shotId);
    if (!forceEntityQa && shot) {
      const blockers = blockersForShot(shot);
      if (blockers.length) {
        if (!silent) {
          setForceQaDialog({
            blockers,
            mode: "shot",
            payload: { shotId },
          });
        }
        const err = new Error(tr("ui_storyboard_assets_failed_qa_rendering_blocked"));
        err.code = "entity_qa_blocked";
        err.blockers = blockers;
        throw err;
      }
    }
    try {
      const res = await api(`/api/projects/${encodeURIComponent(projectId)}/storyboard`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "video",
          shotId,
          model,
          resolution,
          forceEntityQa: Boolean(forceEntityQa),
        }),
      });
      if (!silent) {
        apply(res);
        toast.success(forceEntityQa ? tr("ui_storyboard_force_rendered_assets_that_failed_qa") : tr("ui_storyboard_render_job_submitted"));
      }
      return res;
    } catch (error) {
      if (!silent && isEntityQaBlockedError(error) && !forceEntityQa) {
        setForceQaDialog({
          blockers: blockersFromError(error).length ? blockersFromError(error) : blockersForShot(shot),
          mode: "shot",
          payload: { shotId },
        });
        toast.error(tr("ui_storyboard_assets_failed_qa_rendering_blocked"));
        return;
      }
      if (!silent) toastMaybeKeys(error, onNeedKeys);
      throw error;
    }
  };

  const generateSegment = async (segmentOrder, silent = false, { forceEntityQa = false } = {}) => {
    if (!(await requireGithubStar())) return;
    if (!requireCapability(caps, "seedance", onNeedKeys, tr("ui_storyboard_render_backend_comfyui_seedance"))) return;
    if (!episodeId) return;
    if (!forceEntityQa) {
      const segShots = shots.filter((s) => Number(s.segmentOrder || 0) === Number(segmentOrder));
      const ents = [];
      const seen = new Set();
      for (const s of segShots) {
        for (const id of s.referenceEntityIds || []) {
          if (seen.has(id)) continue;
          seen.add(id);
          const ent = entitiesById.get(id);
          if (ent) ents.push(ent);
        }
      }
      const blockers = listEntityQaBlockers(ents);
      if (blockers.length) {
        if (!silent) {
          setForceQaDialog({
            blockers,
            mode: "segment",
            payload: { segmentOrder },
          });
        }
        const err = new Error(tr("ui_storyboard_assets_failed_qa_rendering_blocked"));
        err.code = "entity_qa_blocked";
        err.blockers = blockers;
        throw err;
      }
    }
    try {
      const res = await api(`/api/projects/${encodeURIComponent(projectId)}/storyboard`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "video-segment",
          episodeId,
          segmentOrder,
          model,
          resolution,
          forceEntityQa: Boolean(forceEntityQa),
        }),
      });
      if (!silent) {
        apply(res);
        toast.success(
          forceEntityQa
            ? tr("ui_storyboard_segment_force_rendered", {
            segmentOrder: segmentOrder
          })
            : tr("ui_storyboard_segment_render_submitted_shots_in_the", {
            segmentOrder: segmentOrder
          }),
        );
      }
      return res;
    } catch (error) {
      if (!silent && isEntityQaBlockedError(error) && !forceEntityQa) {
        setForceQaDialog({
          blockers: blockersFromError(error),
          mode: "segment",
          payload: { segmentOrder },
        });
        toast.error(tr("ui_storyboard_assets_failed_qa_rendering_blocked"));
        return;
      }
      if (!silent) toastMaybeKeys(error, onNeedKeys);
      throw error;
    }
  };

  const runBatchGenerate = async ({ forceEntityQa = false } = {}) => {
    if (!(await requireGithubStar())) return;
    const selected = shots.filter((s) => selectedShotIds.has(s.id));
    setBatching(true);

    if (hasSegmentLayout) {
      const orders = [
        ...new Set(
          selected
            .filter((s) => s.status !== "generating")
            .map((s) => Number(s.segmentOrder || 0))
            .filter((n) => n > 0),
        ),
      ].sort((a, b) => a - b);
      if (!orders.length) {
        setBatching(false);
        return toast.info(tr("ui_storyboard_no_submittable_jobs_in_the_selected"));
      }
      if (!forceEntityQa) {
        const ents = [];
        const seen = new Set();
        for (const so of orders) {
          for (const s of shots.filter((x) => Number(x.segmentOrder || 0) === so)) {
            for (const id of s.referenceEntityIds || []) {
              if (seen.has(id)) continue;
              seen.add(id);
              const ent = entitiesById.get(id);
              if (ent) ents.push(ent);
            }
          }
        }
        const blockers = listEntityQaBlockers(ents);
        if (blockers.length) {
          setBatching(false);
          setForceQaDialog({ blockers, mode: "batch-segments", payload: { orders } });
          return;
        }
      }
      setBusyMsg?.(forceEntityQa ? tr("ui_storyboard_force_rendering_segments", {
        length: orders.length
      }) : tr("ui_storyboard_submitting_segments", {
        length: orders.length
      }));
      try {
        const res = await api(`/api/projects/${encodeURIComponent(projectId)}/storyboard`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            action: "batch-video",
            episodeId,
            segmentOrders: orders,
            model,
            resolution,
            forceEntityQa: Boolean(forceEntityQa),
          }),
        });
        apply(res);
        const started = res?.started || [];
        const blocked = started.filter((s) => s.code === "entity_qa_blocked");
        const failed = started.filter((s) => s.error && s.code !== "entity_qa_blocked");
        const ok = started.length - blocked.length - failed.length;
        if (blocked.length && !forceEntityQa) {
          const merged = [];
          const seen = new Set();
          for (const row of blocked) {
            for (const b of row.blockers || []) {
              if (seen.has(b.entityId)) continue;
              seen.add(b.entityId);
              merged.push(b);
            }
          }
          setForceQaDialog({ blockers: merged, mode: "batch-segments", payload: { orders } });
        }
        await onRefresh?.();
        if (ok === orders.length) toast.success(tr("ui_storyboard_submitted_segments", {
          ok: ok,
          length: orders.length
        }));
        else toast.error(tr("ui_storyboard_segment_submit_succeeded_blocked_by_qa", {
          ok: ok,
          length: blocked.length,
          length2: failed.length
        }));
      } catch (error) {
        toast.error(String(error.message || error));
      } finally {
        setBatching(false);
        setBusyMsg?.("");
      }
      return;
    }

    const pending = selected.filter((s) => s.status !== "generating" && (s.prompt || "").trim());
    if (!pending.length) {
      setBatching(false);
      return toast.info(tr("ui_storyboard_no_submittable_jobs_in_the_selected_2"));
    }
    if (!forceEntityQa) {
      const ents = [];
      const seen = new Set();
      for (const s of pending) {
        for (const id of s.referenceEntityIds || []) {
          if (seen.has(id)) continue;
          seen.add(id);
          const ent = entitiesById.get(id);
          if (ent) ents.push(ent);
        }
      }
      const blockers = listEntityQaBlockers(ents);
      if (blockers.length) {
        setBatching(false);
        setForceQaDialog({
          blockers,
          mode: "batch-shots",
          payload: { shotIds: pending.map((s) => s.id) },
        });
        return;
      }
    }
    setBusyMsg?.(forceEntityQa ? tr("ui_storyboard_force_rendering_shots", {
      length: pending.length
    }) : tr("ui_storyboard_submitting_shots", {
      length: pending.length
    }));
    try {
      const res = await api(`/api/projects/${encodeURIComponent(projectId)}/storyboard`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "batch-video",
          shotIds: pending.map((s) => s.id),
          model,
          resolution,
          forceEntityQa: Boolean(forceEntityQa),
        }),
      });
      apply(res);
      const started = res?.started || [];
      const blocked = started.filter((s) => s.code === "entity_qa_blocked");
      const failed = started.filter((s) => s.error && s.code !== "entity_qa_blocked");
      const ok = started.length - blocked.length - failed.length;
      if (blocked.length && !forceEntityQa) {
        const merged = [];
        const seen = new Set();
        for (const row of blocked) {
          for (const b of row.blockers || []) {
            if (seen.has(b.entityId)) continue;
            seen.add(b.entityId);
            merged.push(b);
          }
        }
        setForceQaDialog({
          blockers: merged,
          mode: "batch-shots",
          payload: { shotIds: pending.map((s) => s.id) },
        });
      }
      await onRefresh?.();
      if (ok === pending.length) toast.success(tr("ui_storyboard_submitted_video_jobs", {
        ok: ok,
        length: pending.length
      }));
      else toast.error(tr("ui_storyboard_bulk_submit_succeeded_blocked_by_qa", {
        ok: ok,
        length: blocked.length,
        length2: failed.length
      }));
    } catch (error) {
      toast.error(String(error.message || error));
    } finally {
      setBatching(false);
      setBusyMsg?.("");
    }
  };

  const batchGenerate = async () => {
    if (splitting) return toast.info(tr("ui_storyboard_wait_for_the_shot_split_to"));
    const selected = shots.filter((s) => selectedShotIds.has(s.id));
    if (!selected.length) return toast.info(tr("ui_storyboard_tick_the_shots_segments_to_generate"));
    if (selected.some((s) => dirtyShotIds.has(s.id))) {
      return toast.error(tr("ui_storyboard_selected_items_have_unsaved_changes_save"));
    }
    if (!confirmBatch) {
      setConfirmBatch(true);
      return;
    }
    setConfirmBatch(false);
    await runBatchGenerate({ forceEntityQa: false });
  };

  const confirmForceQa = () => {
    const dlg = forceQaDialog;
    setForceQaDialog(null);
    if (!dlg) return;
    if (dlg.mode === "shot") {
      void generateVideo(dlg.payload.shotId, false, { forceEntityQa: true });
    } else if (dlg.mode === "segment") {
      void generateSegment(dlg.payload.segmentOrder, false, { forceEntityQa: true });
    } else if (dlg.mode === "batch-segments" || dlg.mode === "batch-shots") {
      void runBatchGenerate({ forceEntityQa: true });
    }
  };

  const ratio = bundle?.project?.ratio || "9:16";
  const resolutions = selectedModel?.resolutions || ["720p"];

  return (
    <div className="mx-auto max-w-[1500px] space-y-5">
      <section className="panel p-5 md:p-6">
        <div className="grid gap-5 min-[1500px]:grid-cols-[480px_minmax(0,1fr)] min-[1500px]:items-end">
          <div className="min-w-0">
            <div className="label">Shot planning & generation</div>
            <h3 className="display-type text-2xl font-semibold">{tr("ui_storyboard_storyboard_desk")}</h3>
            <p className="mt-1 text-sm text-[var(--muted)]">{tr("ui_storyboard_split_into_segments_first_about_10")}</p>
          </div>
          <div className="grid min-w-0 gap-2 sm:grid-cols-2 md:grid-cols-3 min-[1500px]:grid-cols-[minmax(0,1.1fr)_minmax(0,1.3fr)_minmax(88px,.55fr)_auto_auto]">
            <div>
              <span className="label">{tr("ui_storyboard_current_episode")}</span>
              <div className="field flex items-center bg-white/[.03] text-sm">
                {confirmedEpisodes.some((e) => e.id === episodeId) ? (
                  <span>{tr("ui_storyboard_ep", {
                      episodeNumber: (confirmedEpisodes.find((e) => e.id === episodeId) || {}).episodeNumber,
                      1: " "
                    })}{(confirmedEpisodes.find((e) => e.id === episodeId) || {}).title || tr("ui_storyboard_untitled")}
                  </span>
                ) : (
                  <span className="text-white/45">{tr("ui_storyboard_select_a_locked_episode_on_the")}</span>
                )}
              </div>
            </div>
            <label>
              <span className="label">{tr("ui_storyboard_video_model")}</span>
              <select className="field" value={model} disabled={workflowBusy} onChange={(e) => setModel(e.target.value)}>
                {models.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name || item.id}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span className="label">{tr("ui_storyboard_resolution")}</span>
              <select
                className="field"
                value={resolution}
                disabled={workflowBusy}
                onChange={(e) => setResolution(e.target.value)}
              >
                {resolutions.map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
              </select>
            </label>
            <button
              type="button"
              className="btn-secondary self-end whitespace-nowrap"
              disabled={!episode || workflowBusy || episodeHasGenerating}
              onClick={() => void split()}
            >
              {splitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
              {splitting ? tr("ui_storyboard_splitting", {
                splitElapsedTime: splitElapsedTime
              }) : shots.length ? tr("ui_storyboard_re_split") : tr("ui_storyboard_ai_split")}
            </button>
            <button
              type="button"
              className="btn-primary self-end whitespace-nowrap md:col-span-2 min-[1500px]:col-span-1"
              disabled={!selectedShotIds.size || workflowBusy}
              onClick={() => void batchGenerate()}
            >
              {batching ? <Loader2 className="h-4 w-4 animate-spin" /> : <Video className="h-4 w-4" />}{tr("ui_storyboard_generate_in_bulk", {
                0: selectedShotIds.size ? ` (${selectedShotIds.size})` : ""
              })}</button>
          </div>
        </div>
        {splitting ? (
          <div className="mt-5 rounded-xl border border-[var(--projector)]/30 bg-[var(--projector)]/[.08] p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="flex min-w-0 items-start gap-3" role="status">
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-[var(--projector)]/15">
                  <Loader2 className="h-4 w-4 animate-spin text-[var(--projector)]" />
                </span>
                <div className="min-w-0">
                  <div className="timecode text-[10px] text-[var(--muted)]">{tr("ui_storyboard_ai_storyboard_director_stage", {
                      0: splitStageIndex + 1,
                      1: splitStages.length || 1
                    })}</div>
                  <strong className="mt-1 block text-sm">{splitStage.title}</strong>
                  <p className="mt-1 text-xs leading-5 text-[var(--muted)]">{tr("ui_storyboard_longer_scripts_take_longer_results_load", {
                      detail: splitStage.detail
                    })}</p>
                </div>
              </div>
              <span className="timecode flex shrink-0 items-center gap-1.5 rounded-lg border border-[var(--line)] bg-black/40 px-3 py-2 text-xs text-[var(--ink)]">
                <Clock3 className="h-3.5 w-3.5 text-[var(--projector)]" />{tr("ui_storyboard_elapsed", {
                  splitElapsedTime: splitElapsedTime
                })}</span>
            </div>
            <div className="mt-4 grid grid-cols-5 gap-1.5" aria-hidden="true">
              {splitStages.map((stage, index) => (
                <span
                  key={stage.title}
                  className={`h-1.5 rounded-full ${index <= splitStageIndex ? "bg-[var(--projector)]" : "bg-[var(--line)]"}`}
                />
              ))}
            </div>
          </div>
        ) : null}
      </section>

      {!episode || !confirmedEpisodes.some((e) => e.id === episodeId) ? (
        <div className="panel py-24 text-center text-sm text-[var(--muted)]">{tr("ui_storyboard_create_and_lock_episodes_in_the")}</div>
      ) : shots.length === 0 ? (
        <div className="panel flex flex-col items-center border-dashed py-24 text-center">
          <Clapperboard className="mb-4 h-10 w-10 text-[var(--projector)]" />
          <strong className="text-lg">{tr("ui_storyboard_no_shots_in_this_episode_yet")}</strong>
          <p className="mt-2 text-sm text-[var(--muted)]">{tr("ui_storyboard_once_the_script_and_assets_are")}</p>
          <button type="button" className="btn-primary mt-5" disabled={workflowBusy} onClick={() => void split()}>
            {splitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
            {splitting ? tr("ui_storyboard_splitting_2", {
              splitElapsedTime: splitElapsedTime
            }) : tr("ui_storyboard_ai_split_this_episode")}
          </button>
        </div>
      ) : (
        <div className="space-y-4">
          <div className="panel-muted flex flex-wrap items-center justify-between gap-3 px-4 py-3 text-xs text-[var(--muted)]">
            <span>
              {hasSegmentLayout
                ? tr("ui_storyboard_segments_beats_in_this_episode_tick", {
                length: segments.length,
                length2: shots.length
              })
                : tr("ui_storyboard_tick_the_shots_to_submit_together")}
            </span>
            <button
              type="button"
              className="btn-secondary !min-h-8 !py-1.5"
              disabled={workflowBusy}
              onClick={() =>
                setSelectedShotIds((current) =>
                  current.size === shots.length ? new Set() : new Set(shots.map((s) => s.id)),
                )
              }
            >
              {selectedShotIds.size === shots.length ? tr("ui_storyboard_clear_selection") : tr("ui_storyboard_select_all_in_episode")}
            </button>
          </div>
          {hasSegmentLayout
            ? segments.map((seg) => {
                const segGenerating = seg.shots.some((s) => s.status === "generating");
                const segReady = seg.lead?.status === "success" && seg.lead?.selectedVideoId;
                return (
                  <section key={`seg-${seg.segmentOrder}`} className="panel space-y-3 p-4 md:p-5">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <strong className="text-sm">{tr("ui_storyboard_segment", {
                              segmentOrder: seg.segmentOrder
                            })}</strong>
                          <span className="timecode rounded-md border border-white/10 px-2 py-0.5 text-[10px] text-white/55">{tr("ui_storyboard_s_shots", {
                              duration: seg.duration,
                              length: seg.shots.length
                            })}</span>
                          {segReady ? (
                            <span className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-[10px] text-emerald-300">{tr("ui_storyboard_done")}</span>
                          ) : segGenerating ? (
                            <span className="rounded-full border border-[var(--projector)]/30 bg-[var(--projector)]/10 px-2 py-0.5 text-[10px] text-[var(--projector)]">{tr("ui_storyboard_generating")}</span>
                          ) : null}
                        </div>
                        <p className="mt-1 text-xs text-white/45">
                          {[seg.lead?.location || seg.lead?.sceneName, seg.lead?.timeOfDay, seg.lead?.weather]
                            .filter(Boolean)
                            .join(" · ") || tr("ui_storyboard_no_location")}
                        </p>
                        {seg.lead?.openingState ? (
                          <p className="mt-1 line-clamp-2 text-[11px] leading-4 text-white/35">
                            {seg.lead.openingState}
                          </p>
                        ) : null}
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <button
                          type="button"
                          className="btn-secondary !min-h-8 !py-1.5 text-xs"
                          disabled={workflowBusy}
                          onClick={() =>
                            setSelectedShotIds((current) => {
                              const next = new Set(current);
                              const allOn = seg.shots.every((s) => next.has(s.id));
                              for (const s of seg.shots) {
                                if (allOn) next.delete(s.id);
                                else next.add(s.id);
                              }
                              return next;
                            })
                          }
                        >
                          {seg.shots.every((s) => selectedShotIds.has(s.id)) ? tr("ui_storyboard_untick_segment") : tr("ui_storyboard_tick_segment")}
                        </button>
                        <button
                          type="button"
                          className="btn-primary !min-h-8 !py-1.5 text-xs"
                          disabled={workflowBusy || segGenerating}
                          onClick={() => void generateSegment(seg.segmentOrder)}
                        >
                          {segGenerating ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Video className="h-3.5 w-3.5" />}{tr("ui_storyboard_generate_segment")}</button>
                      </div>
                    </div>
                    <div className="space-y-3">
                      {seg.shots.map((shot) => (
                        <ShotCard
                          key={`${shot.id}-${shot.updatedAt}`}
                          projectId={projectId}
                          shot={shot}
                          entities={availableEntities}
                          models={models}
                          ratio={ratio}
                          selected={selectedShotIds.has(shot.id)}
                          locked={workflowBusy}
                          compact
                          onToggleSelected={() =>
                            setSelectedShotIds((current) => {
                              const next = new Set(current);
                              if (next.has(shot.id)) next.delete(shot.id);
                              else next.add(shot.id);
                              return next;
                            })
                          }
                          onDirtyChange={handleDirtyChange}
                          onBundle={onBundle}
                          onRefresh={onRefresh}
                          onGenerate={generateVideo}
                        />
                      ))}
                    </div>
                  </section>
                );
              })
            : shots.map((shot) => (
                <ShotCard
                  key={`${shot.id}-${shot.updatedAt}`}
                  projectId={projectId}
                  shot={shot}
                  entities={availableEntities}
                  models={models}
                  ratio={ratio}
                  selected={selectedShotIds.has(shot.id)}
                  locked={workflowBusy}
                  onToggleSelected={() =>
                    setSelectedShotIds((current) => {
                      const next = new Set(current);
                      if (next.has(shot.id)) next.delete(shot.id);
                      else next.add(shot.id);
                      return next;
                    })
                  }
                  onDirtyChange={handleDirtyChange}
                  onBundle={onBundle}
                  onRefresh={onRefresh}
                  onGenerate={generateVideo}
                />
              ))}
          <button
            type="button"
            className="panel flex w-full items-center justify-center border-dashed py-5 text-sm font-semibold text-[var(--muted)] hover:border-[var(--projector)] hover:text-[var(--ink)]"
            disabled={workflowBusy}
            onClick={() => void add()}
          >
            <Plus className="mr-2 h-4 w-4" />{" "}{tr("ui_storyboard_add_shot_manually")}</button>
        </div>
      )}

      <ConfirmDialog
        open={confirmSplit}
        title={tr("ui_storyboard_re_split_this_episode_s_storyboard")}
        message={tr("ui_storyboard_this_episode_s_shots_video_version")}
        confirmLabel={tr("ui_storyboard_re_split")}
        onCancel={() => setConfirmSplit(false)}
        onConfirm={() => void split()}
      />
      <ConfirmDialog
        open={confirmBatch}
        title={hasSegmentLayout ? tr("ui_storyboard_submit_renders_by_segment") : tr("ui_storyboard_submit_video_jobs", {
          size: selectedShotIds.size
        })}
        message={
          hasSegmentLayout
            ? tr("ui_storyboard_submits_one_merged_render_for_each")
            : tr("ui_storyboard_jobs_run_2_at_a_time")
        }
        confirmLabel={tr("ui_storyboard_confirm_submit")}
        onCancel={() => setConfirmBatch(false)}
        onConfirm={() => void batchGenerate()}
      />
      <ConfirmDialog
        open={Boolean(forceQaDialog)}
        title={tr("ui_storyboard_assets_failed_qa_rendering_blocked")}
        message={
          forceQaDialog
            ? tr("ui_storyboard_regenerate_review_the_assets_above_first", {
            0: formatEntityQaBlockers(forceQaDialog.blockers)
          })
            : ""
        }
        confirmLabel={tr("ui_storyboard_force_render")}
        cancelLabel={tr("ui_storyboard_fix_assets_first")}
        danger
        maxWidthClass="max-w-lg"
        onCancel={() => setForceQaDialog(null)}
        onConfirm={confirmForceQa}
      />
    </div>
  );
}

function ShotCard({
  projectId,
  shot,
  entities,
  models,
  ratio,
  selected,
  locked,
  compact = false,
  onToggleSelected,
  onDirtyChange,
  onBundle,
  onRefresh,
  onGenerate,
}) {
  useLocale();
  const [prompt, setPrompt] = useState(shot.prompt || "");
  const [duration, setDuration] = useState(shot.duration || 5);
  const [referenceIds, setReferenceIds] = useState(shot.referenceEntityIds || []);
  const [saving, setSaving] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const dirty =
    prompt !== (shot.prompt || "") ||
    duration !== (shot.duration || 5) ||
    JSON.stringify(referenceIds) !== JSON.stringify(shot.referenceEntityIds || []);
  const editLocked = locked || shot.status === "generating";
  const isStale = shot.status === "stale";
  const caption =
    String(shot.dialogue || "").trim() ||
    (prompt.match(/[「""]([^」""]{2,80})[」""]/)?.[1] || "");

  // Keep local editors in sync when bundle refresh returns new shot data (skip while editing)
  useEffect(() => {
    if (dirty) return;
    setPrompt(shot.prompt || "");
    setDuration(shot.duration || 5);
    setReferenceIds(shot.referenceEntityIds || []);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only rehydrate from server fields
  }, [shot.id, shot.prompt, shot.duration, shot.selectedVideoId, shot.status, JSON.stringify(shot.referenceEntityIds || [])]);

  useEffect(() => {
    onDirtyChange(shot.id, dirty);
    return () => onDirtyChange(shot.id, false);
  }, [dirty, onDirtyChange, shot.id]);

  const apply = (res) => {
    if (res?.bundle) onBundle?.(res.bundle);
    else onRefresh?.();
  };

  const save = async (quiet = false) => {
    setSaving(true);
    try {
      const res = await api(`/api/projects/${encodeURIComponent(projectId)}/storyboard`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "patch",
          shotId: shot.id,
          patch: { prompt, duration, referenceEntityIds: referenceIds },
        }),
      });
      apply(res);
      if (!quiet) toast.success(tr("ui_storyboard_shot_saved", {
        shotOrder: shot.shotOrder
      }));
    } catch (error) {
      toast.error(String(error.message || error));
      throw error;
    } finally {
      setSaving(false);
    }
  };

  const generate = async () => {
    setGenerating(true);
    try {
      if (dirty) await save(true);
      await onGenerate(shot.id);
      await onRefresh?.();
    } finally {
      setGenerating(false);
    }
  };

  const cancelGenerate = async () => {
    try {
      const res = await api(`/api/projects/${encodeURIComponent(projectId)}/storyboard`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "cancel-video", shotId: shot.id }),
      });
      apply(res);
      toast.success(tr("ui_storyboard_generation_cancelled_you_can_resubmit"));
    } catch (error) {
      toast.error(String(error.message || error));
    }
  };

  const remove = async () => {
    if (!confirmDelete) {
      setConfirmDelete(true);
      return;
    }
    setConfirmDelete(false);
    try {
      const res = await api(`/api/projects/${encodeURIComponent(projectId)}/storyboard`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "delete", shotId: shot.id }),
      });
      apply(res);
    } catch (error) {
      toast.error(String(error.message || error));
    }
  };

  const selectVideo = async (videoId) => {
    try {
      const res = await api(`/api/projects/${encodeURIComponent(projectId)}/storyboard`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "select-take", shotId: shot.id, videoId }),
      });
      apply(res);
    } catch (error) {
      toast.error(String(error.message || error));
    }
  };

  const updateVideo = async (videoId, fields) => {
    try {
      const res = await api(`/api/projects/${encodeURIComponent(projectId)}/storyboard`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "patch-take", shotId: shot.id, videoId, ...fields }),
      });
      apply(res);
    } catch (error) {
      toast.error(String(error.message || error));
    }
  };

  const statusStyle =
    shot.status === "success"
      ? "bg-emerald-100 text-emerald-700"
      : shot.status === "stale"
        ? "bg-amber-100 text-amber-800"
        : shot.status === "generating"
          ? "bg-blue-100 text-blue-700"
          : shot.status === "failed"
            ? "bg-red-100 text-red-700"
            : "bg-slate-100 text-slate-600";
  const completeVideos = (shot.videos || []).filter((v) => v.path || v.url);
  const activeVideo = shot.selectedVideo?.url ? shot.selectedVideo : completeVideos[0] || null;

  return (
    <>
      <article className="panel overflow-hidden">
        <div className="grid xl:grid-cols-[minmax(0,1fr)_360px]">
          <div className="p-5">
            <div className="flex flex-wrap items-center gap-3">
              <label className="flex cursor-pointer items-center gap-2 text-xs font-semibold">
                <input type="checkbox" checked={selected} disabled={locked} onChange={onToggleSelected} />{" "}{tr("ui_storyboard_select_in_bulk")}</label>
              <span className="timecode rounded-md bg-[var(--navy)] px-2.5 py-1 text-xs text-white">
                {compact && shot.segmentOrder
                  ? tr("ui_storyboard_segment_shot", {
                  segmentOrder: shot.segmentOrder,
                  1: shot.beatIndex || shot.shotOrder
                })
                  : `SHOT ${String(shot.shotOrder).padStart(2, "0")}`}
              </span>
              <span className={`rounded-full px-2.5 py-1 text-[10px] font-bold ${statusStyle}`}>
                {shot.status === "success"
                  ? tr("ui_storyboard_done")
                  : shot.status === "stale"
                    ? tr("ui_storyboard_outdated")
                    : shot.status === "generating"
                      ? tr("ui_storyboard_generating")
                      : shot.status === "failed"
                        ? tr("ui_storyboard_failed")
                        : tr("ui_storyboard_not_generated")}
              </span>
              <label className="ml-auto flex items-center gap-2 text-xs text-[var(--muted)]">{tr("ui_storyboard_duration")}<input
                  type="number"
                  min={2}
                  max={15}
                  className="field !w-20 !py-1.5"
                  value={duration}
                  disabled={editLocked}
                  onChange={(e) => setDuration(Math.max(2, Math.min(15, Number(e.target.value) || 3)))}
                />{tr("ui_storyboard_s")}</label>
            </div>
            <label className="mt-4 block">
              <span className="label">{tr("ui_storyboard_seedance_prompt")}</span>
              <textarea
                className="field min-h-56 resize-y leading-6 md:min-h-72"
                value={prompt}
                disabled={editLocked}
                onChange={(e) => setPrompt(e.target.value)}
                placeholder={tr("ui_storyboard_subject_action_lines_framing_camera_lighting")}
              />
            </label>
            <div className="mt-4">
              <div className="label">{tr("ui_storyboard_reference_assets_up_to_9")}</div>
              <div className="flex flex-wrap gap-2">
                {entities.map((entity) => {
                  const on = referenceIds.includes(entity.id);
                  const thumb = entity.selectedImage?.url;
                  return (
                    <button
                      key={entity.id}
                      type="button"
                      disabled={editLocked}
                      onClick={() =>
                        setReferenceIds((current) =>
                          on
                            ? current.filter((id) => id !== entity.id)
                            : current.length < 9
                              ? [...current, entity.id]
                              : current,
                        )
                      }
                      className={`flex items-center gap-2 rounded-lg border px-2 py-1.5 text-xs ${
                        on ? "border-[var(--projector)] bg-[var(--projector)]/10" : "border-[var(--line)] bg-white/[.03]"
                      }`}
                    >
                      {thumb ? (
                        <img src={thumb} alt="" className="h-7 w-7 rounded object-cover" />
                      ) : (
                        <span className="flex h-7 w-7 items-center justify-center rounded bg-black/40 text-[9px] text-white/40">{tr("ui_storyboard_no_image")}</span>
                      )}
                      <span>
                        {entity.name}
                        {entity.variant ? ` / ${entity.variant}` : ""}
                      </span>
                    </button>
                  );
                })}
                {!entities.length ? (
                  <span className="text-xs text-[var(--muted)]">{tr("ui_storyboard_no_locked_images_in_this_episode")}</span>
                ) : null}
              </div>
            </div>
            {isStale || shot.staleReason ? (
              <p className="mt-3 rounded-lg bg-amber-500/15 px-3 py-2 text-xs text-amber-200">
                {shot.staleReason || tr("ui_storyboard_upstream_changed_the_current_video_may")}
              </p>
            ) : null}
            {shot.error ? (
              <p className="mt-3 rounded-lg bg-[var(--danger)]/10 px-3 py-2 text-xs text-[var(--danger)]">{shot.error}</p>
            ) : null}
            <div className="mt-5 flex flex-wrap gap-2">
              <button
                type="button"
                className="btn-secondary"
                disabled={locked || !dirty || saving || shot.status === "generating"}
                onClick={() => void save()}
              >
                {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}{" "}{tr("ui_storyboard_save_shot")}</button>
              <button
                type="button"
                className="btn-primary"
                disabled={locked || generating || shot.status === "generating" || !prompt.trim()}
                onClick={() => void generate()}
              >
                {generating || shot.status === "generating" ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Video className="h-4 w-4" />
                )}
                {shot.selectedVideo ? tr("ui_storyboard_generate_another_version") : tr("ui_storyboard_generate_shot_video")}
              </button>
              {shot.status === "generating" ? (
                <button
                  type="button"
                  className="btn-secondary"
                  disabled={locked}
                  onClick={() => void cancelGenerate()}
                >{tr("ui_storyboard_cancel_stuck_job")}</button>
              ) : null}
              <button
                type="button"
                className="btn-danger ml-auto"
                disabled={locked || shot.status === "generating"}
                onClick={() => void remove()}
              >
                <Trash2 className="h-4 w-4" />{" "}{tr("ui_storyboard_delete")}</button>
            </div>
          </div>
          <div className="border-t border-[var(--line)] bg-[var(--navy)] p-4 text-white xl:border-l xl:border-t-0">
            <div className="timecode mb-3 flex items-center justify-between text-[10px] text-white/45">
              <span>VIDEO TAKE · {ratio}</span>
              <span>{completeVideos.length} VERSIONS</span>
            </div>
            <div
              className={`relative flex items-center justify-center overflow-hidden rounded-xl bg-black/45 ${
                ratio === "9:16" ? "mx-auto aspect-[9/16] w-full max-w-[20rem]" : "aspect-video w-full"
              }`}
            >
              {activeVideo?.url ? (
                <>
                  <video
                    key={activeVideo.url}
                    src={activeVideo.url}
                    controls
                    preload="metadata"
                    className="h-full w-full object-contain"
                  />
                  {caption ? (
                    <div className="pointer-events-none absolute inset-x-3 bottom-10 rounded-md bg-black/70 px-3 py-2 text-center text-xs leading-5 text-white shadow-lg">
                      {caption}
                    </div>
                  ) : null}
                </>
              ) : shot.status === "generating" ? (
                <div className="text-center text-xs text-white/60">
                  <Loader2 className="mx-auto mb-2 h-6 w-6 animate-spin text-[var(--projector)]" />{tr("ui_storyboard_seedance_is_rendering")}</div>
              ) : (
                <div className="px-4 text-center text-xs leading-5 text-white/45">
                  <Video className="mx-auto mb-2 h-10 w-10 text-white/15" />{tr("ui_storyboard_no_video_generated_for_this_shot")}</div>
              )}
            </div>
            {completeVideos.length > 0 ? (
              <div className="mt-3 flex gap-2 overflow-x-auto">
                {completeVideos.map((video, index) => (
                  <button
                    key={video.id}
                    type="button"
                    disabled={editLocked}
                    onClick={() => void selectVideo(video.id)}
                    className={`timecode rounded-lg border px-3 py-2 text-[10px] ${
                      video.id === activeVideo?.id
                        ? "border-[var(--projector)] bg-[var(--projector)]/10 text-[var(--projector)]"
                        : "border-white/10 text-white/50"
                    }`}
                  >
                    TAKE {String(index + 1).padStart(2, "0")}
                  </button>
                ))}
              </div>
            ) : null}
            {activeVideo ? (
              <div className="mt-3 space-y-3 rounded-xl border border-white/10 bg-white/[.04] p-3 text-xs text-white/65">
                <div>
                  <strong className="block text-white">
                    {models.find((m) => m.id === activeVideo.model)?.name || activeVideo.model || "Seedance"}
                  </strong>
                  <span>{tr("ui_storyboard_s_2", {
                      0: activeVideo.resolution || "—",
                      1: " ",
                      2: Number(activeVideo.duration || shot.duration || 0).toFixed(1)
                    })}</span>
                </div>
                <div className="flex items-center gap-1" aria-label={tr("ui_storyboard_rate_video_version")}>
                  {[1, 2, 3, 4, 5].map((star) => (
                    <button
                      key={star}
                      type="button"
                      disabled={editLocked}
                      className={`text-base ${(activeVideo.rating ?? 0) >= star ? "text-amber-300" : "text-white/20"} hover:text-amber-200`}
                      onClick={() =>
                        void updateVideo(activeVideo.id, {
                          rating: activeVideo.rating === star ? null : star,
                        })
                      }
                      aria-label={tr("ui_storyboard_stars", {
                        star: star
                      })}
                    >
                      ★
                    </button>
                  ))}
                </div>
                <input
                  className="w-full rounded-md border border-white/10 bg-black/20 px-2 py-1.5 text-xs text-white placeholder:text-white/30 focus:border-[var(--projector)] focus:outline-none"
                  defaultValue={activeVideo.note || ""}
                  disabled={editLocked}
                  maxLength={200}
                  placeholder={tr("ui_storyboard_add_a_note_for_this_version")}
                  onBlur={(event) => {
                    const note = event.target.value.trim();
                    if (note !== (activeVideo.note || "")) void updateVideo(activeVideo.id, { note });
                  }}
                />
              </div>
            ) : null}
          </div>
        </div>
      </article>
      <ConfirmDialog
        open={confirmDelete}
        title={tr("ui_storyboard_delete_shot", {
          shotOrder: shot.shotOrder
        })}
        message={tr("ui_storyboard_this_shot_and_its_video_version")}
        confirmLabel={tr("ui_storyboard_delete_shot_2")}
        danger
        onCancel={() => setConfirmDelete(false)}
        onConfirm={() => void remove()}
      />
    </>
  );
}
