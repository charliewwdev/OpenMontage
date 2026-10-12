import { useEffect, useMemo, useState } from "react";
import { Clapperboard, Play, RefreshCw, Save } from "lucide-react";
import { api } from "../../api";

function mediaUrl(project, rel) {
  if (!rel) return null;
  return `/api/media/${encodeURIComponent(project)}/${rel.split("/").map(encodeURIComponent).join("/")}`;
}

export function StoryboardStep({ project, view, onBundle, onGenerate, genState }) {
  const shots = view.shots || [];
  const [selectedId, setSelectedId] = useState(shots[0]?.id || null);
  const [desc, setDesc] = useState("");
  const [duration, setDuration] = useState(4);
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(false);

  const selected = useMemo(() => shots.find((s) => s.id === selectedId) || shots[0] || null, [shots, selectedId]);
  const job = selected ? view.jobByShot[selected.id] : null;
  const readyCount = shots.filter((s) => {
    const j = view.jobByShot[s.id];
    return j && ["needs_review", "succeeded", "approved"].includes(j.status);
  }).length;

  useEffect(() => {
    if (!selected) return;
    setSelectedId(selected.id);
    setDesc(selected.description || selected.prompt || "");
    setDuration(Number(selected.duration_sec || selected.duration || 4));
  }, [selected?.id]);

  const previewSrc = mediaUrl(project, job?.clip_path || job?.keyframe_path || selected?.keyframe_path);
  const isVideo = Boolean(job?.clip_path);

  const save = async (patch) => {
    if (!selected) return;
    setBusy(true);
    setStatus("");
    try {
      await api("/api/project/storyboard/patch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ project, shot_id: selected.id, patch }),
      });
      const bundle = await api(`/api/project/bundle?name=${encodeURIComponent(project)}`);
      onBundle?.(bundle);
      setStatus("镜头已保存");
    } catch (e) {
      setStatus(String(e.message || e));
    } finally {
      setBusy(false);
    }
  };

  const syncLedger = async () => {
    setBusy(true);
    try {
      await api("/api/project/ledger/sync", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ project }),
      });
      const bundle = await api(`/api/project/bundle?name=${encodeURIComponent(project)}`);
      onBundle?.(bundle);
      setStatus("账本已从分镜同步");
    } catch (e) {
      setStatus(String(e.message || e));
    } finally {
      setBusy(false);
    }
  };

  if (!shots.length) {
    return (
      <div className="panel flex flex-col items-center border-dashed py-24 text-center">
        <Clapperboard className="mb-4 h-10 w-10 text-[var(--projector)]" />
        <strong className="display-type text-xl">本集还没有分镜</strong>
        <p className="mt-2 max-w-md text-sm text-[var(--muted)]">回到剧本页，从小说重新拆解后会自动生成镜头列表。</p>
      </div>
    );
  }

  return (
    <div className="grid gap-4 xl:grid-cols-[300px_minmax(0,1fr)]">
      <div className="panel max-h-[75vh] overflow-y-auto p-2 scrollbar-thin">
        <div className="panel-muted mb-2 flex items-center justify-between px-3 py-2 text-[11px] text-[var(--muted)]">
          <span>
            {readyCount}/{shots.length} ready
          </span>
          <button type="button" className="btn-quiet !min-h-7 !px-2 text-xs" onClick={syncLedger}>
            <RefreshCw className="h-3 w-3" /> 同步账本
          </button>
        </div>
        <div className="space-y-1">
          {shots.map((shot, i) => {
            const j = view.jobByShot[shot.id];
            const thumb = mediaUrl(project, j?.keyframe_path);
            return (
              <button
                key={shot.id}
                type="button"
                className={`flex w-full items-start gap-3 rounded-xl border px-2 py-2 text-left transition ${
                  selected?.id === shot.id ? "border-[var(--projector)]/45 bg-[var(--projector)]/10" : "border-transparent hover:bg-[var(--panel-muted)]"
                }`}
                onClick={() => setSelectedId(shot.id)}
              >
                <div className="h-14 w-10 shrink-0 overflow-hidden rounded-lg bg-[var(--navy)]">
                  {thumb ? <img src={thumb} alt="" className="h-full w-full object-cover" /> : null}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between gap-2">
                    <span className="timecode text-[10px] text-[var(--muted)]">SH {String(i + 1).padStart(2, "0")}</span>
                    <span className={`status-pill ${j?.status || "pending"}`}>{j?.status || "pending"}</span>
                  </div>
                  <div className="mt-1 line-clamp-2 text-[11px] leading-4 text-[var(--muted)]">
                    {shot.description || shot.prompt || "—"}
                  </div>
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {selected ? (
        <div className="space-y-4">
          <div className="panel overflow-hidden">
            <div className="flex aspect-[9/16] max-h-[52vh] items-center justify-center bg-[var(--navy)] md:aspect-video md:max-h-[420px]">
              {previewSrc ? (
                isVideo ? (
                  <video key={previewSrc} src={previewSrc} controls className="h-full w-full object-contain" />
                ) : (
                  <img key={previewSrc} src={previewSrc} alt={selected.id} className="h-full w-full object-contain" />
                )
              ) : (
                <div className="px-6 text-center text-sm text-white/50">尚未生成预览 · 点击批量生成</div>
              )}
            </div>
          </div>

          <div className="panel p-5 md:p-6">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <div className="label">Shot director</div>
                <h3 className="display-type text-2xl font-semibold">{selected.id}</h3>
                <div className="mt-2 flex flex-wrap gap-2 text-xs text-[var(--muted)]">
                  <span className="panel-muted px-2 py-1">{selected.shot_intent || "shot"}</span>
                  <span className={`status-pill ${job?.status || "pending"}`}>{job?.status || "pending"}</span>
                </div>
              </div>
              <div className="flex gap-2">
                <button
                  type="button"
                  className="btn-secondary"
                  disabled={busy}
                  onClick={() => save({ description: desc, duration_sec: Number(duration) || 4 })}
                >
                  <Save className="h-4 w-4" /> 保存
                </button>
                <button
                  type="button"
                  className="btn-primary !border-[var(--projector)] !bg-[var(--projector)] !text-[var(--navy)]"
                  disabled={!!genState?.running}
                  onClick={() => onGenerate?.()}
                >
                  <Play className="h-4 w-4" />
                  {genState?.running ? "生成中…" : "批量生成镜头"}
                </button>
              </div>
            </div>

            <div className="mt-5 grid gap-4 md:grid-cols-[1fr_140px]">
              <label className="block">
                <span className="label">镜头描述 / 提示词</span>
                <textarea className="field min-h-32 resize-y leading-7" value={desc} onChange={(e) => setDesc(e.target.value)} />
              </label>
              <label className="block">
                <span className="label">时长（秒）</span>
                <input className="field" type="number" min={1} max={30} step={0.5} value={duration} onChange={(e) => setDuration(e.target.value)} />
              </label>
            </div>

            {status ? <p className="mt-3 text-xs text-[var(--muted)]">{status}</p> : null}
            {genState ? (
              <p className="mt-2 timecode text-[11px] text-[var(--muted)]">
                GEN {genState.running ? "RUNNING" : "IDLE"} · {genState.mode || "offline"} · done {genState.processed || 0}
                {genState.failed ? ` · fail ${genState.failed}` : ""}
                {genState.last_error ? ` · ${genState.last_error}` : ""}
              </p>
            ) : null}
            <p className="mt-3 text-xs leading-5 text-[var(--muted)]">
              离线模式会生成关键帧板 + FFmpeg 镜头片段；配置 ARK/FAL 等密钥后可切换真实视频供应商。生成完成后去「剪辑」导出 MP4。
            </p>
          </div>
        </div>
      ) : null}
    </div>
  );
}
