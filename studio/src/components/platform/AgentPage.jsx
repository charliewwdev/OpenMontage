import { useEffect, useRef, useState } from "react";
import { CheckCircle2, Clapperboard, Loader2, Sparkles } from "lucide-react";
import { api } from "../../api";
import { toast } from "../../lib/toast";
import { PageShell } from "./PageShell";

import { configText } from "../../lib/configI18n";
import { tr, localized, useLocale } from "../../lib/i18n";

const STARTERS = localized(() => [
  tr("ui_agent_a_15_second_vertical_short_drama"),
  tr("ui_agent_urban_hit_drama_a_down_and"),
  tr("ui_agent_mystery_a_female_coroner_finds_the"),
  tr("ui_agent_sci_fi_in_a_city_where"),
]);

const STEP_LABEL = {
  get brief() {
    return tr("ui_agent_polish_brief");
  },

  get script() {
    return tr("ui_agent_generate_script");
  },

  get confirm() {
    return tr("ui_agent_lock_script");
  },

  get entities() {
    return tr("ui_agent_asset_images");
  },

  get storyboard() {
    return tr("ui_agent_split_shots");
  },

  get videos() {
    return tr("ui_agent_generate_video");
  },

  get audio() {
    return tr("ui_agent_voice_over");
  },

  get export() {
    return tr("ui_agent_export_cut");
  }
};

function formatElapsed(ms) {
  if (!Number.isFinite(ms) || ms < 0) return "";
  const s = Math.floor(ms / 1000);
  const m = Math.floor(s / 60);
  const r = s % 60;
  if (m <= 0) return `${r}s`;
  return tr("ui_agent_m_s", {
    m: m,
    1: String(r).padStart(2, "0")
  });
}

function stepElapsedMs(step, nowMs) {
  if (!step) return null;
  if (typeof step.elapsedMs === "number" && step.status !== "running") return step.elapsedMs;
  if (!step.startedAt) return null;
  const start = Date.parse(step.startedAt);
  if (!Number.isFinite(start)) return null;
  const end = step.endedAt && step.status !== "running" ? Date.parse(step.endedAt) : nowMs;
  if (!Number.isFinite(end)) return null;
  return Math.max(0, end - start);
}

export function AgentPage({ config, seedPrompt = "", onCreated, onNeedKeys, onRequireAuth }) {
  useLocale();
  const [prompt, setPrompt] = useState(seedPrompt || "");
  const [title, setTitle] = useState("");
  const defaults = config?.defaults || {};
  const [genre, setGenre] = useState(defaults.genre || config?.genres?.[0] || "");
  const [ratio, setRatio] = useState(defaults.ratio || config?.ratios?.[0]?.value || "");
  const [episodeCount, setEpisodeCount] = useState(10);
  const [mode, setMode] = useState("full"); // full | script
  const [busy, setBusy] = useState(false);
  const [logs, setLogs] = useState([]);
  const [job, setJob] = useState(null);
  const [projectId, setProjectId] = useState("");
  const [nowMs, setNowMs] = useState(() => Date.now());
  const pollRef = useRef(null);
  const caps = config?.capabilities || {};
  const llmReady = Boolean(caps.llmReady || caps.deepseek || caps.cursor);
  const backend = caps.llmBackend || (caps.cursor ? "cursor" : caps.deepseek ? "deepseek" : "none");
  const examples = (config?.inspirePrompts || []).slice(0, 6).map((p) => p.text);
  const imageReady = Boolean(caps.imageReady || caps.seedream || caps.comfyui);
  const seedreamReady = Boolean(caps.seedream);
  const videoReady = Boolean(caps.videoReady || caps.seedance || caps.comfyui);
  const seedanceReady = Boolean(caps.seedance);

  useEffect(() => {
    if (seedPrompt) setPrompt(seedPrompt);
  }, [seedPrompt]);

  useEffect(() => {
    if (!genre && config?.defaults?.genre) setGenre(config.defaults.genre);
    if (!ratio && config?.defaults?.ratio) setRatio(config.defaults.ratio);
  }, [config, genre, ratio]);

  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  useEffect(() => {
    if (job?.status !== "running") return undefined;
    const timer = setInterval(() => setNowMs(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [job?.status]);

  const pushLog = (text, ok = true) => setLogs((prev) => [...prev, { text, ok, at: Date.now() }]);

  const stopPolling = () => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  };

  const syncJobLogs = (next) => {
    const serverLogs = Array.isArray(next?.logs) ? next.logs : [];
    if (!serverLogs.length) return;
    setLogs(
      serverLogs.map((item, index) => ({
        text: item.text || "",
        ok: item.ok !== false,
        at: item.at ? Date.parse(item.at) || Date.now() + index : Date.now() + index,
      })),
    );
  };

  const pollJob = (pid) => {
    stopPolling();
    const tick = async () => {
      try {
        const res = await api(`/api/projects/${encodeURIComponent(pid)}/auto-produce`);
        const next = res.job;
        if (!next) return;
        setJob(next);
        syncJobLogs(next);
        if (next.status === "success" || next.status === "failed") {
          stopPolling();
          setBusy(false);
          if (next.status === "success") {
            toast.success(tr("ui_agent_short_drama_pipeline_finished"));
            onCreated?.(pid);
          } else {
            toast.error(next.error || tr("ui_agent_pipeline_failed"));
          }
        }
      } catch (error) {
        stopPolling();
        setBusy(false);
        pushLog(String(error.message || error), false);
      }
    };
    void tick();
    pollRef.current = setInterval(() => void tick(), 2500);
  };

  const runScriptOnly = async () => {
    const projectTitle = title.trim() || prompt.trim().slice(0, 24) || tr("ui_agent_agent_project");
    pushLog(tr("ui_agent_text_backend", {
      backend: backend
    }));
    pushLog(tr("ui_agent_creating_project"));
    const created = await api("/api/projects", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: projectTitle,
        brief: prompt.trim(),
        genre,
        ratio,
        visualStyle: config?.styles?.[0]?.promptValue || config?.defaults?.visualStyle || "",
      }),
    });
    const pid = created.project?.id;
    setProjectId(pid || "");
    pushLog(tr("ui_agent_project_created", {
      projectTitle: projectTitle
    }));
    pushLog(tr("ui_agent_generating_a_episode_script_with", {
      backend: backend,
      episodeCount: episodeCount
    }));
    await api(`/api/projects/${encodeURIComponent(pid)}/script`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "generate", episodeCount }),
    });
    pushLog(tr("ui_agent_script_ready_opening_the_film_workshop"));
    toast.success(tr("ui_agent_agent_created_the_project_and_generated"));
    onCreated?.(pid);
  };

  const runFull = async () => {
    if (!imageReady || !videoReady) {
      toast.error(
        imageReady
          ? tr("ui_agent_the_full_pipeline_needs_a_video")
          : tr("ui_agent_the_full_pipeline_needs_images_comfyui")
      );
      onNeedKeys?.();
      return;
    }
    const eps = Math.min(Math.max(Number(episodeCount) || 10, 1), 10);
    pushLog(tr("ui_agent_text_backend", {
      backend: backend
    }));
    pushLog(tr("ui_agent_one_click_pipeline_project_episode_script", {
      eps: eps
    }));
    const projectTitle = title.trim() || prompt.trim().slice(0, 24) || tr("ui_agent_one_click_drama");
    const res = await api("/api/auto-produce", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: projectTitle,
        brief: prompt.trim(),
        genre,
        ratio,
        visualStyle: config?.styles?.[0]?.promptValue || config?.defaults?.visualStyle || "",
        episodeCount: eps,
        maxShots: 24,
        maxCharacters: 6,
        maxScenes: 4,
        forceIllustration: false,
        textOnlyVideo: false,
        forceDubbing: false,
        resolution: "720p",
      }),
    });
    const pid = res.projectId;
    setProjectId(pid || "");
    setJob(res.job || null);
    pushLog(tr("ui_agent_project_created_producing_in_the_background", {
      projectTitle: projectTitle,
      eps: eps
    }));
    pushLog(tr("ui_agent_you_can_leave_this_page_multi"));
    toast.success(tr("ui_agent_started_full_production_of_episodes", {
      eps: eps
    }));
    pollJob(pid);
  };

  const run = async () => {
    if (!prompt.trim()) return toast.error(tr("ui_agent_write_a_one_sentence_idea_first"));
    if (onRequireAuth && !onRequireAuth()) return;
    if (!llmReady) {
      toast.error(tr("ui_agent_please_configure_a_text_llm_key"));
      onNeedKeys?.();
      return;
    }
    setBusy(true);
    setLogs([]);
    setJob(null);
    try {
      if (mode === "full") await runFull();
      else {
        await runScriptOnly();
        setBusy(false);
      }
    } catch (error) {
      stopPolling();
      pushLog(String(error.message || error), false);
      toast.error(String(error.message || error));
      setBusy(false);
    }
  };

  const steps = job?.steps || [];
  const runningStep = steps.find((step) => step.status === "running");
  const jobStartedMs = job?.startedAt ? Date.parse(job.startedAt) : null;
  const jobElapsed =
    job?.status === "running" && Number.isFinite(jobStartedMs) ? formatElapsed(nowMs - jobStartedMs) : "";

  return (
    <PageShell
      eyebrow="Creation agent"
      title={tr("ui_agent_creation_agent")}
      description={tr("ui_agent_one_sentence_or_a_whole_script")}
    >
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_340px]">
        <section className="panel p-5 md:p-6">
          <div className="mb-4 flex flex-wrap gap-2">
            <button
              type="button"
              className={mode === "full" ? "btn-primary" : "btn-secondary"}
              disabled={busy}
              onClick={() => {
                setMode("full");
                setEpisodeCount((n) => (n < 2 ? 10 : n));
              }}
            >
              <Clapperboard className="h-4 w-4" />{tr("ui_agent_one_click_full_production")}</button>
            <button
              type="button"
              className={mode === "script" ? "btn-primary" : "btn-secondary"}
              disabled={busy}
              onClick={() => setMode("script")}
            >
              <Sparkles className="h-4 w-4" />{tr("ui_agent_script_only")}</button>
          </div>

          <label>
            <span className="label">{tr("ui_agent_one_sentence_idea_paste_a_script")}</span>
            <textarea
              className="field min-h-56 resize-y leading-7"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder={tr("ui_agent_e_g_a_one_line_urban")}
              disabled={busy}
            />
          </label>

          <div className="mt-3 flex flex-wrap gap-2">
            {(examples.length ? examples : STARTERS).map((text) => (
              <button
                key={text}
                type="button"
                className="chip max-w-full truncate"
                disabled={busy}
                onClick={() => setPrompt(text)}
                title={text}
              >
                {text.slice(0, 28)}
                {text.length > 28 ? "…" : ""}
              </button>
            ))}
          </div>

          <div className="mt-4 grid gap-3 md:grid-cols-2">
            <label>
              <span className="label">{tr("ui_agent_title_optional")}</span>
              <input className="field" value={title} disabled={busy} onChange={(e) => setTitle(e.target.value)} />
            </label>
            <label>
              <span className="label">{mode === "full" ? tr("ui_agent_episodes_default_10") : tr("ui_agent_episodes_to_generate")}</span>
              <input
                className="field"
                type="number"
                min={1}
                max={10}
                value={episodeCount}
                disabled={busy}
                onChange={(e) => setEpisodeCount(Math.min(10, Math.max(1, Number(e.target.value) || 1)))}
              />
            </label>
            <label>
              <span className="label">{tr("ui_agent_genre")}</span>
              <select className="field" value={genre} disabled={busy} onChange={(e) => setGenre(e.target.value)}>
                {(config?.genres || []).map((item) => (
                  <option key={item} value={item}>
                    {configText(item)}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span className="label">{tr("ui_agent_frame")}</span>
              <select className="field" value={ratio} disabled={busy} onChange={(e) => setRatio(e.target.value)}>
                {(config?.ratios || []).map((item) => (
                  <option key={item.value} value={item.value}>
                    {item.value} {item.label}
                  </option>
                ))}
              </select>
            </label>
          </div>

          {mode === "full" ? (
            <p className="mt-3 text-xs leading-6 text-[var(--muted)]">{tr("ui_agent_by_default_a_full_short_drama")}</p>
          ) : null}

          <button type="button" className="btn-primary mt-5 min-h-12 w-full" disabled={busy} onClick={() => void run()}>
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : mode === "full" ? <Clapperboard className="h-4 w-4" /> : <Sparkles className="h-4 w-4" />}
            {busy
              ? mode === "full"
                ? tr("ui_agent_producing")
                : tr("ui_agent_agent_is_writing")
              : mode === "full"
                ? tr("ui_agent_start_one_click_production_ep", {
              0: Math.min(Math.max(Number(episodeCount) || 10, 1), 10)
            })
                : tr("ui_agent_start_writing_script")}
          </button>

          {projectId && job?.status === "success" ? (
            <button type="button" className="btn-secondary mt-3 w-full" onClick={() => onCreated?.(projectId)}>{tr("ui_agent_open_project_workshop")}</button>
          ) : null}
          {job?.seriesUrl || (job?.exports || []).length > 1 ? (
            <div className="mt-2 space-y-1">
              {job?.seriesUrl ? (
                <a className="btn-primary flex w-full items-center justify-center" href={job.seriesUrl} target="_blank" rel="noreferrer">{tr("ui_agent_play_full_series")}{job.exports?.length || tr("ui_agent_several")}{" "}{tr("ui_agent_ep")}</a>
              ) : null}
              {(job.exports || []).map((item) => (
                <a
                  key={item.episodeId || item.url}
                  className="btn-ghost flex w-full items-center justify-center text-xs"
                  href={item.url}
                  target="_blank"
                  rel="noreferrer"
                >{tr("ui_agent_preview_episode", {
                    0: item.episodeNumber || "?"
                  })}</a>
              ))}
            </div>
          ) : job?.exportUrl ? (
            <a className="btn-ghost mt-2 flex w-full items-center justify-center" href={job.exportUrl} target="_blank" rel="noreferrer">{tr("ui_agent_preview_cut")}</a>
          ) : null}
        </section>

        <aside className="space-y-4">
          <section className="panel space-y-3 p-5 text-sm leading-6">
            <strong className="block">{tr("ui_agent_run_check")}</strong>
            <p className="text-[var(--muted)]">{tr("ui_agent_text_backend", {
                backend: backend
              })}</p>
            <p className="text-[var(--muted)]">{tr("ui_agent_text_model")}{llmReady ? tr("ui_agent_ready", {
              backend: backend
            }) : tr("ui_agent_not_configured")}</p>
            <p className="text-[var(--muted)]">{tr("ui_agent_images")}{imageReady ? (caps.comfyui ? tr("ui_agent_comfyui_ready") : seedreamReady ? tr("ui_agent_seedream_ready") : tr("ui_agent_ready_2")) : tr("ui_agent_not_configured_comfyui_or_seedream")}</p>
            <p className="text-[var(--muted)]">{tr("ui_agent_video")}{videoReady ? (caps.comfyui ? tr("ui_agent_comfyui_ready") : seedanceReady ? tr("ui_agent_seedance_ready") : tr("ui_agent_ready_2")) : tr("ui_agent_not_configured_comfyui_or_seedance")}
            </p>
            {!llmReady || (mode === "full" && (!imageReady || !videoReady)) ? (
              <button type="button" className="btn-secondary mt-2 w-full" onClick={() => onNeedKeys?.()}>{tr("ui_agent_configure_keys")}</button>
            ) : null}
          </section>

          {steps.length ? (
            <section className="panel p-5">
              <div className="mb-3 flex items-center justify-between gap-2">
                <strong className="block text-sm">{tr("ui_agent_pipeline_progress")}</strong>
                {jobElapsed ? <span className="text-[11px] text-white/45">{tr("ui_agent_elapsed", {
                    jobElapsed: jobElapsed
                  })}</span> : null}
              </div>
              <ul className="space-y-2 text-xs">
                {steps.map((step) => {
                  const elapsed = formatElapsed(stepElapsedMs(step, nowMs));
                  return (
                    <li key={step.id} className="border-b border-white/5 pb-2">
                      <div className="flex items-start justify-between gap-2">
                        <span className="text-white/75">{STEP_LABEL[step.id] || step.label}</span>
                        <span
                          className={
                            step.status === "done"
                              ? "text-[var(--ok)]"
                              : step.status === "failed"
                                ? "text-red-300"
                                : step.status === "running"
                                  ? "text-[#b7acff]"
                                  : "text-[var(--muted)]"
                          }
                        >
                          {step.status === "running"
                            ? tr("ui_agent_running", {
                            0: elapsed ? ` · ${elapsed}` : ""
                          })
                            : step.status === "done"
                              ? tr("ui_agent_done", {
                            0: elapsed ? ` · ${elapsed}` : ""
                          })
                              : step.status === "failed"
                                ? tr("ui_agent_failed")
                                : step.status === "skipped"
                                  ? tr("ui_agent_skipped")
                                  : tr("ui_agent_waiting")}
                        </span>
                      </div>
                      {step.detail ? <p className="mt-1 text-[11px] text-white/40">{step.detail}</p> : null}
                    </li>
                  );
                })}
              </ul>
              {job?.status ? (
                <p className="mt-3 text-xs text-[var(--muted)]">{tr("ui_agent_status", {
                    status: job.status
                  })}{runningStep ? ` ${tr("ui_agent_now", {
  0: STEP_LABEL[runningStep.id] || runningStep.label
})}` : ""}
                  {job.error ? ` · ${job.error}` : ""}
                </p>
              ) : null}
              {runningStep?.id === "entities" ? (
                <p className="mt-2 text-[11px] leading-5 text-white/35">{tr("ui_agent_asset_images_call_seedream_one_by")}</p>
              ) : null}
            </section>
          ) : null}

          <section className="panel p-5">
            <strong className="mb-3 block text-sm">{tr("ui_agent_run_log")}</strong>
            {!logs.length ? (
              <p className="text-xs text-[var(--muted)]">{tr("ui_agent_after_you_start_project_creation_and")}</p>
            ) : (
              <ul className="space-y-2 text-xs">
                {logs.map((item) => (
                  <li key={`${item.at}-${item.text}`} className="flex items-start gap-2">
                    {item.ok ? (
                      <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[var(--ok)]" />
                    ) : (
                      <span className="mt-0.5 h-3.5 w-3.5 shrink-0 rounded-full bg-[var(--danger)]" />
                    )}
                    <span className={item.ok ? "text-white/75" : "text-red-300"}>{item.text}</span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </aside>
      </div>
    </PageShell>
  );
}
