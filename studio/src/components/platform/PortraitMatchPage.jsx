import { useCallback, useEffect, useMemo, useState } from "react";
import { ArrowLeft, Clapperboard, Film, Loader2, Play, RefreshCw, Sparkles } from "lucide-react";
import { api } from "../../api";
import { toast } from "../../lib/toast";
import { requireCapability, toastMaybeKeys } from "../../lib/keys";
import { PageShell } from "./PageShell";

function mediaUrl(projectId, path) {
  if (!path) return null;
  if (String(path).startsWith("http") || String(path).startsWith("/api/")) return path;
  return `/api/media/${projectId}/${path}`;
}

function ShotCard({ projectId, shot }) {
  const start = mediaUrl(projectId, shot.startFramePath);
  const end = mediaUrl(projectId, shot.endFramePath);
  const vid = shot.selectedVideo?.url || mediaUrl(projectId, shot.selectedVideo?.path);
  const status = shot.status || "pending";
  return (
    <article className="overflow-hidden rounded-2xl border border-[var(--line)] bg-white/[.03]">
      <div className="grid grid-cols-2 gap-px bg-[var(--line)]">
        <div className="bg-[var(--stage)] p-2">
          <p className="mb-1 text-[10px] uppercase tracking-wide text-white/40">首帧</p>
          {start ? <img src={start} alt="" className="aspect-[9/16] w-full rounded-lg object-cover" /> : null}
        </div>
        <div className="bg-[var(--stage)] p-2">
          <p className="mb-1 text-[10px] uppercase tracking-wide text-white/40">尾帧</p>
          {end ? <img src={end} alt="" className="aspect-[9/16] w-full rounded-lg object-cover" /> : null}
        </div>
      </div>
      <div className="flex items-center justify-between gap-2 p-3">
        <div>
          <p className="text-sm font-medium text-white/90">{shot.title || shot.id}</p>
          <p className="text-[11px] text-white/45">
            {status === "success" ? "已生成" : status === "generating" ? "生成中…" : status === "failed" ? shot.error || "失败" : "待生成"}
          </p>
        </div>
        {vid ? (
          <video src={vid} className="h-16 w-10 rounded object-cover" muted playsInline controls />
        ) : status === "generating" ? (
          <Loader2 className="h-4 w-4 animate-spin text-[#7c6cff]" />
        ) : null}
      </div>
    </article>
  );
}

export function PortraitMatchPage({
  config,
  projectId: initialProjectId = "",
  preferredTemplate = "",
  onBack,
  onOpenDrama,
  onNeedKeys,
}) {
  const [templates, setTemplates] = useState([]);
  const [loadingTemplates, setLoadingTemplates] = useState(true);
  const [creating, setCreating] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [assembling, setAssembling] = useState(false);
  const [bundle, setBundle] = useState(null);
  const [projectId, setProjectId] = useState(initialProjectId || "");

  const project = bundle?.project;
  const shots = useMemo(
    () =>
      [...(bundle?.shots || [])]
        .filter((s) => !s.deletedAt)
        .sort((a, b) => (a.shotOrder || a.order || 0) - (b.shotOrder || b.order || 0)),
    [bundle],
  );
  const sampleEdit = (bundle?.edits || []).find((e) => e.kind === "portrait-sample");
  const assembled = [...(bundle?.edits || [])].reverse().find((e) => e.kind === "portrait-assemble");
  const doneCount = shots.filter((s) => s.status === "success" && s.selectedVideoId).length;
  const genCount = shots.filter((s) => s.status === "generating").length;

  const refresh = useCallback(async (pid = projectId) => {
    if (!pid) return;
    const data = await api(`/api/projects/${pid}`);
    setBundle(data);
    setProjectId(pid);
  }, [projectId]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoadingTemplates(true);
      try {
        const data = await api("/api/portrait-match/templates");
        if (!cancelled) setTemplates(data.templates || []);
      } catch (err) {
        if (!cancelled) toast.error(err.message || "加载模板失败");
      } finally {
        if (!cancelled) setLoadingTemplates(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!initialProjectId) return;
    void refresh(initialProjectId).catch((err) => toast.error(err.message || "加载项目失败"));
  }, [initialProjectId]);

  // Poll while generating
  useEffect(() => {
    if (!projectId || genCount === 0) return undefined;
    const t = setInterval(() => {
      void refresh(projectId).catch(() => {});
    }, 4000);
    return () => clearInterval(t);
  }, [projectId, genCount, refresh]);

  const onCreate = async (templateId) => {
    if (!requireCapability(config?.capabilities, "videoReady", onNeedKeys, "出片后端（ComfyUI H3）")) return;
    setCreating(true);
    try {
      const res = await api("/api/portrait-match/projects", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ templateId, includeSample: true }),
      });
      setBundle(res.bundle);
      setProjectId(res.project?.id || res.bundle?.project?.id || "");
      toast.success("已创建写真对标项目");
    } catch (err) {
      toastMaybeKeys(err, onNeedKeys);
    } finally {
      setCreating(false);
    }
  };

  const onGenerateAll = async () => {
    if (!projectId) return;
    if (!requireCapability(config?.capabilities, "videoReady", onNeedKeys, "出片后端（ComfyUI H3）")) return;
    setGenerating(true);
    try {
      const res = await api(`/api/projects/${projectId}/portrait-match/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ onlyMissing: true, resolution: "720p" }),
      });
      setBundle(res.bundle);
      const n = (res.started || []).filter((x) => !x.error && !x.skipped).length;
      toast.success(n ? `已提交 ${n} 个镜头到智川云 H3` : "没有需要生成的镜头");
    } catch (err) {
      toastMaybeKeys(err, onNeedKeys);
    } finally {
      setGenerating(false);
    }
  };

  const onAssemble = async () => {
    if (!projectId) return;
    setAssembling(true);
    try {
      const res = await api(`/api/projects/${projectId}/portrait-match/assemble`, { method: "POST" });
      setBundle(res.bundle);
      toast.success("合片完成");
    } catch (err) {
      toast.error(err.message || "合片失败");
    } finally {
      setAssembling(false);
    }
  };

  const preferred = preferredTemplate || "ref1";

  return (
    <PageShell
      title="写真对标"
      description="抖音氛围写真 · MiniMax H3 首尾帧身份锁 · 请确认顶部出片后端为智川云 ComfyUI"
      actions={
        <button type="button" className="btn-ghost inline-flex items-center gap-1.5" onClick={onBack}>
          <ArrowLeft className="h-4 w-4" />
          返回工坊
        </button>
      }
    >
      {!projectId ? (
        <section className="space-y-4">
          <p className="text-sm text-white/60">
            选择甜屿三参考模板，系统会导入每镜首尾帧，用智川云 ComfyUI · MiniMax H3 做身份锁定动效，再合成为对标成片。
          </p>
          {loadingTemplates ? (
            <div className="flex items-center gap-2 text-sm text-white/50">
              <Loader2 className="h-4 w-4 animate-spin" /> 加载模板…
            </div>
          ) : (
            <div className="grid gap-4 md:grid-cols-3">
              {templates.map((t) => (
                <article
                  key={t.id}
                  className={`panel flex flex-col gap-3 border p-4 ${
                    t.id === preferred ? "border-[#7c6cff]/60" : "border-[var(--line)]"
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <h3 className="text-base font-semibold text-white">{t.title}</h3>
                      <p className="mt-1 text-xs text-white/50">{t.desc}</p>
                    </div>
                    <span className="rounded-full bg-white/[.06] px-2 py-0.5 text-[10px] text-white/50">
                      {t.shotCount} 镜
                    </span>
                  </div>
                  {t.sampleUrl ? (
                    <video src={t.sampleUrl} className="aspect-[9/16] w-full rounded-xl object-cover" muted playsInline controls />
                  ) : (
                    <div className="flex aspect-[9/16] items-center justify-center rounded-xl bg-white/[.04] text-white/30">
                      <Film className="h-8 w-8" />
                    </div>
                  )}
                  <button
                    type="button"
                    className="btn-primary inline-flex items-center justify-center gap-2"
                    disabled={creating || !t.ready}
                    onClick={() => void onCreate(t.id)}
                  >
                    {creating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
                    用此模板开项目
                  </button>
                </article>
              ))}
            </div>
          )}
        </section>
      ) : (
        <section className="space-y-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold text-white">{project?.title || "写真对标"}</h2>
              <p className="text-xs text-white/45">
                {doneCount}/{shots.length} 镜完成
                {genCount ? ` · ${genCount} 生成中` : ""}
                {" · "}请确认顶部出片后端为 ComfyUI · MiniMax H3
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <button type="button" className="btn-ghost inline-flex items-center gap-1.5" onClick={() => void refresh()}>
                <RefreshCw className="h-4 w-4" />
                刷新
              </button>
              <button
                type="button"
                className="btn-primary inline-flex items-center gap-1.5"
                disabled={generating || genCount > 0}
                onClick={() => void onGenerateAll()}
              >
                {generating || genCount > 0 ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
                生成全部镜头
              </button>
              <button
                type="button"
                className="btn-secondary inline-flex items-center gap-1.5"
                disabled={assembling || doneCount < 2}
                onClick={() => void onAssemble()}
              >
                {assembling ? <Loader2 className="h-4 w-4 animate-spin" /> : <Clapperboard className="h-4 w-4" />}
                合片
              </button>
              {onOpenDrama ? (
                <button type="button" className="btn-ghost" onClick={() => onOpenDrama(projectId)}>
                  打开编导台
                </button>
              ) : null}
            </div>
          </div>

          {(sampleEdit?.outputUrl || assembled?.outputUrl) && (
            <div className="grid gap-4 md:grid-cols-2">
              {sampleEdit?.outputUrl ? (
                <div className="panel border border-[var(--line)] p-3">
                  <p className="mb-2 text-xs text-white/50">模板样片（已生成参考）</p>
                  <video src={sampleEdit.outputUrl} className="max-h-80 w-full rounded-xl object-contain" controls playsInline />
                </div>
              ) : null}
              {assembled?.outputUrl ? (
                <div className="panel border border-[#7c6cff]/40 p-3">
                  <p className="mb-2 text-xs text-[#a5b4fc]">本次合片成片</p>
                  <video src={assembled.outputUrl} className="max-h-80 w-full rounded-xl object-contain" controls playsInline />
                </div>
              ) : null}
            </div>
          )}

          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {shots.map((s) => (
              <ShotCard key={s.id} projectId={projectId} shot={s} />
            ))}
          </div>
        </section>
      )}
    </PageShell>
  );
}
