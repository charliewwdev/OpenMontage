import { useEffect, useRef, useState } from "react";
import { Loader2, Radio, RefreshCw, WifiOff } from "lucide-react";
import { api } from "../../api";
import { getToken } from "../../lib/auth";
import { toast } from "../../lib/toast";
import { PageShell } from "./PageShell";

import { tr, useLocale } from "../../lib/i18n";

const STATUS_TONE = {
  running: "text-emerald-300 bg-emerald-500/15 border-emerald-500/30",
  queued: "text-sky-300 bg-sky-500/15 border-sky-500/30",
  paused: "text-amber-300 bg-amber-500/15 border-amber-500/30",
  failed: "text-rose-300 bg-rose-500/15 border-rose-500/30",
  done: "text-white/60 bg-white/5 border-white/10",
};

const STATUS_LABEL = {
  get running() {
    return tr("ui_jobs_running");
  },

  get queued() {
    return tr("ui_jobs_queued");
  },

  get paused() {
    return tr("ui_jobs_paused");
  },

  get failed() {
    return tr("ui_jobs_failed");
  },

  get done() {
    return tr("ui_jobs_completed");
  }
};

function jobsWsUrl() {
  if (typeof window === "undefined") return "";
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  const token = encodeURIComponent(getToken() || "");
  return `${proto}//${window.location.host}/api/settings/jobs/ws?token=${token}`;
}

function ProgressBar({ pct = 0, tone = "sky", label }) {
  useLocale();
  const width = Math.max(0, Math.min(100, Number(pct) || 0));
  const fill =
    tone === "emerald"
      ? "bg-emerald-400"
      : tone === "amber"
        ? "bg-amber-400"
        : tone === "rose"
          ? "bg-rose-400"
          : "bg-sky-400";
  return (
    <div className="space-y-1">
      {label ? (
        <div className="flex items-center justify-between text-[11px] text-[var(--muted)]">
          <span>{label}</span>
          <span className="tabular-nums text-white/70">{width.toFixed(width >= 10 ? 0 : 1)}%</span>
        </div>
      ) : null}
      <div className="h-1.5 overflow-hidden rounded-full bg-white/10">
        <div className={`h-full rounded-full transition-[width] duration-500 ease-out ${fill}`} style={{ width: `${width}%` }} />
      </div>
    </div>
  );
}

function StatCard({ label, value, hint, progress }) {
  useLocale();
  return (
    <div className="panel space-y-2 px-4 py-3">
      <div className="text-[11px] uppercase tracking-wide text-[var(--muted)]">{label}</div>
      <div className="text-2xl font-semibold tabular-nums">{value ?? "—"}</div>
      {hint ? <div className="text-[11px] text-[var(--muted)]">{hint}</div> : null}
      {typeof progress === "number" ? <ProgressBar pct={progress} tone="sky" /> : null}
    </div>
  );
}

function JobRow({ job, onOpen }) {
  useLocale();
  const tone = STATUS_TONE[job.status] || STATUS_TONE.done;
  const shots = job.shotProgress || {};
  const prog = job.progress || {};
  const barTone = job.status === "failed" ? "rose" : job.status === "paused" ? "amber" : job.status === "done" ? "emerald" : "sky";
  return (
    <div className="panel space-y-3 px-4 py-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <button
            type="button"
            className="truncate text-left text-sm font-semibold hover:underline"
            onClick={() => onOpen?.(job.projectId)}
          >
            {job.title || job.projectId}
          </button>
          <div className="mt-1 text-[11px] text-[var(--muted)]">{tr("ui_jobs_step", {
              projectId: job.projectId,
              1: job.step || "—"
            })}{job.updatedAt ? ` ${tr("ui_jobs_updated", {
  updatedAt: job.updatedAt
})}` : ""}
          </div>
        </div>
        <span className={`rounded-full border px-2.5 py-0.5 text-[11px] ${tone}`}>
          {STATUS_LABEL[job.status] || job.status}
        </span>
      </div>

      <ProgressBar
        pct={prog.overallPct ?? 0}
        tone={barTone}
        label={tr("ui_jobs_overall_stage", {
          0: prog.stepDone ?? 0,
          1: prog.stepTotal ?? 0
        })}
      />
      {(prog.shotTotal > 0 || shots.total > 0) && (
        <ProgressBar
          pct={prog.shotPct ?? 0}
          tone={barTone}
          label={tr("ui_jobs_videos", {
            0: prog.shotDone ?? shots.completed ?? 0,
            1: prog.shotTotal ?? shots.total ?? 0,
            2: shots.generating ? tr("ui_jobs_generating_suffix", { count: shots.generating }) : "",
            3: shots.failed ? tr("ui_jobs_failed_suffix", { count: shots.failed }) : ""
          })}
        />
      )}

      {job.detail ? <p className="text-sm text-white/80">{job.detail}</p> : null}
      {job.lastLog ? <p className="text-xs text-[var(--muted)]">{tr("ui_jobs_latest", {
          lastLog: job.lastLog
        })}</p> : null}
      {job.error ? <p className="text-xs text-rose-300">{tr("ui_jobs_error", {
          0: String(job.error).slice(0, 200)
        })}</p> : null}

      {Array.isArray(job.steps) && job.steps.length ? (
        <div className="flex flex-wrap gap-1.5">
          {job.steps.map((s) => (
            <span
              key={s.id}
              className={`rounded-md border px-2 py-0.5 text-[10px] ${
                s.status === "done"
                  ? "border-emerald-500/25 text-emerald-200/80"
                  : s.status === "running"
                    ? "border-sky-500/30 text-sky-200"
                    : s.status === "failed"
                      ? "border-rose-500/30 text-rose-200"
                      : "border-white/10 text-white/45"
              }`}
              title={s.detail || s.label}
            >
              {s.label || s.id}
            </span>
          ))}
        </div>
      ) : null}
    </div>
  );
}

export function JobsPage({ onOpenProject }) {
  useLocale();
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState(null);
  const [live, setLive] = useState("connecting"); // connecting | live | polling | offline
  const wsRef = useRef(null);
  const pollRef = useRef(null);
  const retryRef = useRef(0);

  const applySnapshot = (payload) => {
    if (!payload || typeof payload !== "object") return;
    setData(payload);
    setLoading(false);
  };

  const loadHttp = async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const res = await api("/api/settings/jobs");
      applySnapshot(res);
    } catch (e) {
      if (!silent) toast.error(String(e.message || e));
    } finally {
      if (!silent) setLoading(false);
    }
  };

  const stopPoll = () => {
    if (pollRef.current) {
      window.clearInterval(pollRef.current);
      pollRef.current = null;
    }
  };

  const startPollFallback = () => {
    stopPoll();
    setLive("polling");
    void loadHttp(true);
    pollRef.current = window.setInterval(() => void loadHttp(true), 5000);
  };

  useEffect(() => {
    let cancelled = false;
    let reconnectTimer = null;

    const connect = () => {
      if (cancelled) return;
      stopPoll();
      setLive("connecting");
      let ws;
      try {
        ws = new WebSocket(jobsWsUrl());
      } catch {
        startPollFallback();
        return;
      }
      wsRef.current = ws;

      ws.onopen = () => {
        if (cancelled) return;
        retryRef.current = 0;
        setLive("live");
        stopPoll();
        try {
          ws.send(JSON.stringify({ type: "refresh" }));
        } catch {
          /* ignore */
        }
      };

      ws.onmessage = (event) => {
        if (cancelled) return;
        try {
          const msg = JSON.parse(event.data);
          if (msg?.type === "snapshot" && msg.data) {
            applySnapshot(msg.data);
            setLive("live");
          }
        } catch {
          /* ignore bad frames */
        }
      };

      ws.onerror = () => {
        /* onclose handles fallback */
      };

      ws.onclose = () => {
        if (cancelled) return;
        wsRef.current = null;
        const attempt = retryRef.current + 1;
        retryRef.current = attempt;
        startPollFallback();
        const delay = Math.min(15000, 1500 * attempt);
        reconnectTimer = window.setTimeout(connect, delay);
      };
    };

    void loadHttp(false);
    connect();

    const pingId = window.setInterval(() => {
      const ws = wsRef.current;
      if (ws && ws.readyState === WebSocket.OPEN) {
        try {
          ws.send(JSON.stringify({ type: "ping" }));
        } catch {
          /* ignore */
        }
      }
    }, 25000);

    return () => {
      cancelled = true;
      window.clearInterval(pingId);
      if (reconnectTimer) window.clearTimeout(reconnectTimer);
      stopPoll();
      try {
        wsRef.current?.close();
      } catch {
        /* ignore */
      }
      wsRef.current = null;
    };
  }, []);

  const requestRefresh = () => {
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      try {
        ws.send(JSON.stringify({ type: "refresh" }));
        return;
      } catch {
        /* fall through */
      }
    }
    void loadHttp(false);
  };

  const q = data?.mediaQueue || {};
  const pool = q.pool || {};
  const qProg = q.progress || {};
  const jobs = data?.autoProduce || [];

  const liveLabel =
    live === "live" ? tr("ui_jobs_websocket_live") : live === "polling" ? tr("ui_jobs_polling_fallback") : live === "connecting" ? tr("ui_jobs_connecting") : tr("ui_jobs_offline");
  const LiveIcon = live === "live" ? Radio : live === "polling" ? RefreshCw : WifiOff;

  return (
    <PageShell
      eyebrow="Ops"
      title={tr("ui_jobs_job_queue")}
      description={tr("ui_jobs_websocket_push_for_the_queue_and")}
      actions={
        <div className="flex flex-wrap items-center gap-2">
          <span
            className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] ${
              live === "live"
                ? "border-emerald-500/35 bg-emerald-500/10 text-emerald-200"
                : live === "polling"
                  ? "border-amber-500/35 bg-amber-500/10 text-amber-200"
                  : "border-white/15 bg-white/5 text-white/55"
            }`}
          >
            <LiveIcon className={`h-3 w-3 ${live === "live" ? "animate-pulse" : ""}`} />
            {liveLabel}
          </span>
          <button type="button" className="btn-secondary inline-flex items-center gap-1.5" onClick={requestRefresh}>
            <RefreshCw className="h-3.5 w-3.5" />{tr("ui_jobs_refresh")}</button>
        </div>
      }
    >
      <div className="space-y-5">
        {data?.note ? <p className="text-xs text-[var(--muted)]">{data.note}</p> : null}

        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard label={tr("ui_jobs_queue_backend")} value={q.backend || "—"} hint={data?.polledAt ? tr("ui_jobs_synced", {
            polledAt: data.polledAt
          }) : ""} />
          <StatCard
            label={tr("ui_jobs_pending")}
            value={q.redisPending ?? pool.pending ?? 0}
            hint={
              q.backend === "redis"
                ? tr("ui_jobs_images_videos", {
                0: q.redisImagePending ?? 0,
                1: q.redisVideoPending ?? 0
              })
                : tr("ui_jobs_thread_pool_queue")
            }
            progress={qProg.loadPct}
          />
          <StatCard label={tr("ui_jobs_processing")} value={q.redisProcessing ?? "—"} hint={tr("ui_jobs_pool_workers", {
            0: pool.workers ?? "—"
          })} />
          <StatCard label={tr("ui_jobs_pipeline_jobs")} value={jobs.length} hint={tr("ui_jobs_running_paused_failed_recently_done")} />
        </div>

        {q.redisError ? (
          <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">
            Redis：{q.redisError}
          </div>
        ) : null}

        <section className="space-y-3">
          <h2 className="text-sm font-semibold">{tr("ui_jobs_one_click_pipeline")}</h2>
          {loading && !data ? (
            <div className="panel flex items-center gap-2 px-5 py-10 text-sm text-[var(--muted)]">
              <Loader2 className="h-4 w-4 animate-spin" />{" "}{tr("ui_jobs_loading_jobs")}</div>
          ) : jobs.length === 0 ? (
            <div className="panel px-5 py-10 text-sm text-[var(--muted)]">{tr("ui_jobs_no_visible_pipeline_jobs_right_now")}</div>
          ) : (
            <div className="space-y-3">
              {jobs.map((job) => (
                <JobRow key={`${job.projectId}-${job.jobId}`} job={job} onOpen={onOpenProject} />
              ))}
            </div>
          )}
        </section>
      </div>
    </PageShell>
  );
}
