import { useEffect, useState } from "react";
import { Loader2, RefreshCw } from "lucide-react";
import { api } from "../../api";
import { toast } from "../../lib/toast";
import { PageShell } from "./PageShell";

const STATUS_TONE = {
  running: "text-emerald-300 bg-emerald-500/15 border-emerald-500/30",
  queued: "text-sky-300 bg-sky-500/15 border-sky-500/30",
  paused: "text-amber-300 bg-amber-500/15 border-amber-500/30",
  failed: "text-rose-300 bg-rose-500/15 border-rose-500/30",
  done: "text-white/60 bg-white/5 border-white/10",
};

const STATUS_LABEL = {
  running: "运行中",
  queued: "排队",
  paused: "已暂停",
  failed: "失败",
  done: "已完成",
};

function StatCard({ label, value, hint }) {
  return (
    <div className="panel px-4 py-3">
      <div className="text-[11px] uppercase tracking-wide text-[var(--muted)]">{label}</div>
      <div className="mt-1 text-2xl font-semibold tabular-nums">{value ?? "—"}</div>
      {hint ? <div className="mt-1 text-[11px] text-[var(--muted)]">{hint}</div> : null}
    </div>
  );
}

function JobRow({ job, onOpen }) {
  const tone = STATUS_TONE[job.status] || STATUS_TONE.done;
  const shots = job.shotProgress || {};
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
          <div className="mt-1 text-[11px] text-[var(--muted)]">
            {job.projectId} · 步骤 {job.step || "—"}
            {job.updatedAt ? ` · 更新 ${job.updatedAt}` : ""}
          </div>
        </div>
        <span className={`rounded-full border px-2.5 py-0.5 text-[11px] ${tone}`}>
          {STATUS_LABEL[job.status] || job.status}
        </span>
      </div>
      {job.detail ? <p className="text-sm text-white/80">{job.detail}</p> : null}
      {job.lastLog ? <p className="text-xs text-[var(--muted)]">最近：{job.lastLog}</p> : null}
      {job.error ? <p className="text-xs text-rose-300">错误：{String(job.error).slice(0, 200)}</p> : null}
      <div className="flex flex-wrap gap-3 text-[11px] text-[var(--muted)]">
        <span>
          镜头 {shots.completed || 0}/{shots.total || 0}
          {shots.generating ? ` · 生成中 ${shots.generating}` : ""}
          {shots.failed ? ` · 失败 ${shots.failed}` : ""}
        </span>
      </div>
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
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState(null);

  const load = async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const res = await api("/api/settings/jobs");
      setData(res);
    } catch (e) {
      if (!silent) toast.error(String(e.message || e));
    } finally {
      if (!silent) setLoading(false);
    }
  };

  useEffect(() => {
    void load();
    const id = window.setInterval(() => void load(true), 5000);
    return () => window.clearInterval(id);
  }, []);

  const q = data?.mediaQueue || {};
  const pool = q.pool || {};
  const jobs = data?.autoProduce || [];

  return (
    <PageShell
      eyebrow="Ops"
      title="任务队列"
      description="查看媒体后台队列与一键全流程任务。系统没有独立 cron 定时表，任务由队列与项目流水线驱动。"
      actions={
        <button type="button" className="btn-secondary inline-flex items-center gap-1.5" onClick={() => void load()}>
          <RefreshCw className="h-3.5 w-3.5" />
          刷新
        </button>
      }
    >
      <div className="space-y-5">
        {data?.note ? <p className="text-xs text-[var(--muted)]">{data.note}</p> : null}

        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard label="队列后端" value={q.backend || "—"} hint={data?.polledAt ? `轮询 ${data.polledAt}` : ""} />
          <StatCard
            label="待处理"
            value={q.redisPending ?? pool.pending ?? 0}
            hint={
              q.backend === "redis"
                ? `图 ${q.redisImagePending ?? 0} · 视频 ${q.redisVideoPending ?? 0}`
                : "线程池排队"
            }
          />
          <StatCard label="处理中" value={q.redisProcessing ?? "—"} hint={`池 workers ${pool.workers ?? "—"}`} />
          <StatCard label="全流程任务" value={jobs.length} hint="含运行 / 暂停 / 失败 / 近完成" />
        </div>

        {q.redisError ? (
          <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">
            Redis：{q.redisError}
          </div>
        ) : null}

        <section className="space-y-3">
          <h2 className="text-sm font-semibold">一键全流程</h2>
          {loading && !data ? (
            <div className="panel flex items-center gap-2 px-5 py-10 text-sm text-[var(--muted)]">
              <Loader2 className="h-4 w-4 animate-spin" /> 加载任务…
            </div>
          ) : jobs.length === 0 ? (
            <div className="panel px-5 py-10 text-sm text-[var(--muted)]">当前没有可见的全流程任务。</div>
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
