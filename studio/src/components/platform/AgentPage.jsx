import { useEffect, useRef, useState } from "react";
import { CheckCircle2, Clapperboard, Loader2, Sparkles } from "lucide-react";
import { api } from "../../api";
import { toast } from "../../lib/toast";
import { PageShell } from "./PageShell";

const STARTERS = [
  "为国风茶饮品牌创作一支 15 秒竖屏短剧钩子：古风茶馆夜雨，女主推门而入。",
  "都市爽剧：落魄女婿被丈母娘羞辱三年后，以隐秘身份归来反击。",
  "悬疑：女法医发现每具尸体都带着同一串古语，破译者正是失踪多年的自己。",
  "科幻：记忆可交易的城市里，男主卖掉童年换工作，买家却是未来的自己。",
];

const STEP_LABEL = {
  brief: "优化需求",
  script: "生成剧本",
  confirm: "定稿",
  entities: "素材出图",
  storyboard: "拆分镜",
  videos: "生成视频",
  audio: "配音",
  export: "导出成片",
};

function formatElapsed(ms) {
  if (!Number.isFinite(ms) || ms < 0) return "";
  const s = Math.floor(ms / 1000);
  const m = Math.floor(s / 60);
  const r = s % 60;
  if (m <= 0) return `${r}s`;
  return `${m}分${String(r).padStart(2, "0")}秒`;
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
            toast.success("短剧全流程已完成");
            onCreated?.(pid);
          } else {
            toast.error(next.error || "全流程失败");
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
    const projectTitle = title.trim() || prompt.trim().slice(0, 24) || "Agent 项目";
    pushLog(`文本后端：${backend}`);
    pushLog("正在创建项目…");
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
    pushLog(`项目已创建：${projectTitle}`);
    pushLog(`正在用 ${backend} 生成 ${episodeCount} 集剧本…`);
    await api(`/api/projects/${encodeURIComponent(pid)}/script`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "generate", episodeCount }),
    });
    pushLog("剧本生成完成，进入影视工坊");
    toast.success("Agent 已创建项目并生成剧本");
    onCreated?.(pid);
  };

  const runFull = async () => {
    if (!imageReady || !videoReady) {
      toast.error(
        imageReady
          ? "全流程需要出片后端（ComfyUI 或 Seedance）"
          : "全流程需要出图（ComfyUI 或 Seedream）+ 出片（ComfyUI 或 Seedance）"
      );
      onNeedKeys?.();
      return;
    }
    const eps = Math.min(Math.max(Number(episodeCount) || 10, 1), 10);
    pushLog(`文本后端：${backend}`);
    pushLog(`一键全流程：建项 → ${eps} 集剧本 → 素材 → 分镜视频 → 配音 → 逐集成片`);
    const projectTitle = title.trim() || prompt.trim().slice(0, 24) || "一键短剧";
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
    pushLog(`项目已创建并开始后台制作：${projectTitle}（${eps} 集）`);
    pushLog("可离开本页；多集制作耗时较长，完成后可在工坊 / 作品频道查看");
    toast.success(`已开始 ${eps} 集全流程制作`);
    pollJob(pid);
  };

  const run = async () => {
    if (!prompt.trim()) return toast.error("先写一句话想法，或粘贴完整剧本");
    if (onRequireAuth && !onRequireAuth()) return;
    if (!llmReady) {
      toast.error("请先配置文本大模型 Key");
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
      title="创作 Agent"
      description="一句话或整段剧本，可只生成剧本，也可一键跑通整部短剧：多集剧本 → 角色场景 → 分镜视频 → 配音 → 逐集成片。"
    >
      <div className="grid gap-3 xl:grid-cols-[minmax(0,1fr)_300px]">
        <section className="panel p-3 md:p-3.5">
          <div className="mb-3 flex flex-wrap gap-1.5">
            <button
              type="button"
              className={mode === "full" ? "btn-primary" : "btn-secondary"}
              disabled={busy}
              onClick={() => {
                setMode("full");
                setEpisodeCount((n) => (n < 2 ? 10 : n));
              }}
            >
              <Clapperboard className="h-4 w-4" />
              一键全流程成片
            </button>
            <button
              type="button"
              className={mode === "script" ? "btn-primary" : "btn-secondary"}
              disabled={busy}
              onClick={() => setMode("script")}
            >
              <Sparkles className="h-4 w-4" />
              仅生成剧本
            </button>
          </div>

          <label>
            <span className="label">一句话想法 / 粘贴剧本</span>
            <textarea
              className="field min-h-40 resize-y leading-6"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="例如：都市爽剧一句话钩子；或直接粘贴已有分场剧本…"
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
              <span className="label">片名（可选）</span>
              <input className="field" value={title} disabled={busy} onChange={(e) => setTitle(e.target.value)} />
            </label>
            <label>
              <span className="label">{mode === "full" ? "短剧集数（默认 10 集）" : "本次生成集数"}</span>
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
              <span className="label">题材</span>
              <select className="field" value={genre} disabled={busy} onChange={(e) => setGenre(e.target.value)}>
                {(config?.genres || []).map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span className="label">画幅</span>
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
            <p className="mt-3 text-xs leading-6 text-[var(--muted)]">
              默认生成完整短剧（最多 10 集）：全剧定稿 → 角色/场景锁图 → 每集 12–30 镜 / 约 3–6 分钟（720p、原生口型对白）→ 轻 BGM →
              逐集导出成片。集数越多耗时与费用越高，可先用 2–3 集试跑。
            </p>
          ) : null}

          <button type="button" className="btn-primary mt-5 min-h-12 w-full" disabled={busy} onClick={() => void run()}>
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : mode === "full" ? <Clapperboard className="h-4 w-4" /> : <Sparkles className="h-4 w-4" />}
            {busy
              ? mode === "full"
                ? "全流程制作中…"
                : "Agent 创作中…"
              : mode === "full"
                ? `开始一键成片（${Math.min(Math.max(Number(episodeCount) || 10, 1), 10)} 集）`
                : "开始创作剧本"}
          </button>

          {projectId && job?.status === "success" ? (
            <button type="button" className="btn-secondary mt-3 w-full" onClick={() => onCreated?.(projectId)}>
              打开项目工坊
            </button>
          ) : null}
          {job?.seriesUrl || (job?.exports || []).length > 1 ? (
            <div className="mt-2 space-y-1">
              {job?.seriesUrl ? (
                <a className="btn-primary flex w-full items-center justify-center" href={job.seriesUrl} target="_blank" rel="noreferrer">
                  连续播放全剧（{job.exports?.length || "多"} 集）
                </a>
              ) : null}
              {(job.exports || []).map((item) => (
                <a
                  key={item.episodeId || item.url}
                  className="btn-ghost flex w-full items-center justify-center text-xs"
                  href={item.url}
                  target="_blank"
                  rel="noreferrer"
                >
                  预览第{item.episodeNumber || "?"}集
                </a>
              ))}
            </div>
          ) : job?.exportUrl ? (
            <a className="btn-ghost mt-2 flex w-full items-center justify-center" href={job.exportUrl} target="_blank" rel="noreferrer">
              预览成片
            </a>
          ) : null}
        </section>

        <aside className="space-y-4">
          <section className="panel space-y-3 p-5 text-sm leading-6">
            <strong className="block">运行检查</strong>
            <p className="text-[var(--muted)]">文本后端：{backend}</p>
            <p className="text-[var(--muted)]">文本模型：{llmReady ? `就绪（${backend}）` : "未配置"}</p>
            <p className="text-[var(--muted)]">出图：{imageReady ? (caps.comfyui ? "ComfyUI 就绪" : seedreamReady ? "Seedream 就绪" : "就绪") : "未配置（ComfyUI 或 Seedream）"}</p>
            <p className="text-[var(--muted)]">
              出片：{videoReady ? (caps.comfyui ? "ComfyUI 就绪" : seedanceReady ? "Seedance 就绪" : "就绪") : "未配置（ComfyUI 或 Seedance）"}
            </p>
            {!llmReady || (mode === "full" && (!imageReady || !videoReady)) ? (
              <button type="button" className="btn-secondary mt-2 w-full" onClick={() => onNeedKeys?.()}>
                去配置密钥
              </button>
            ) : null}
          </section>

          {steps.length ? (
            <section className="panel p-5">
              <div className="mb-3 flex items-center justify-between gap-2">
                <strong className="block text-sm">全流程进度</strong>
                {jobElapsed ? <span className="text-[11px] text-white/45">已耗时 {jobElapsed}</span> : null}
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
                            ? `进行中${elapsed ? ` · ${elapsed}` : ""}`
                            : step.status === "done"
                              ? `完成${elapsed ? ` · ${elapsed}` : ""}`
                              : step.status === "failed"
                                ? "失败"
                                : step.status === "skipped"
                                  ? "跳过"
                                  : "等待"}
                        </span>
                      </div>
                      {step.detail ? <p className="mt-1 text-[11px] text-white/40">{step.detail}</p> : null}
                    </li>
                  );
                })}
              </ul>
              {job?.status ? (
                <p className="mt-3 text-xs text-[var(--muted)]">
                  状态：{job.status}
                  {runningStep ? ` · 当前：${STEP_LABEL[runningStep.id] || runningStep.label}` : ""}
                  {job.error ? ` · ${job.error}` : ""}
                </p>
              ) : null}
              {runningStep?.id === "entities" ? (
                <p className="mt-2 text-[11px] leading-5 text-white/35">
                  素材出图会按角色/场景逐张调用 Seedream，单张常见 30–90 秒；日志会随每张开始/完成更新。
                </p>
              ) : null}
            </section>
          ) : null}

          <section className="panel p-5">
            <strong className="mb-3 block text-sm">执行日志</strong>
            {!logs.length ? (
              <p className="text-xs text-[var(--muted)]">点击开始后，这里会显示建项与各阶段进度。</p>
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
