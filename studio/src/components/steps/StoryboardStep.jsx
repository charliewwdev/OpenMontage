import { useEffect, useMemo, useState } from "react";
import { Clapperboard, Play, RefreshCw, Save } from "lucide-react";
import { api } from "../../api";

export function StoryboardStep({ project, view, onBundle, onGenerate, genState }) {
  const shots = view.shots || [];
  const [selectedId, setSelectedId] = useState(shots[0]?.id || null);
  const [desc, setDesc] = useState("");
  const [duration, setDuration] = useState(4);
  const [chat, setChat] = useState("");
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(false);

  const selected = useMemo(() => shots.find((s) => s.id === selectedId) || shots[0] || null, [shots, selectedId]);
  const job = selected ? view.jobByShot[selected.id] : null;

  useEffect(() => {
    if (!selected) return;
    setSelectedId(selected.id);
    setDesc(selected.description || selected.prompt || "");
    setDuration(Number(selected.duration_sec || selected.duration || 4));
  }, [selected?.id]);

  const save = async (patch) => {
    if (!selected) return;
    setBusy(true);
    setStatus("");
    try {
      const res = await api("/api/project/storyboard/patch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ project, shot_id: selected.id, patch }),
      });
      const bundle = await api(`/api/project/bundle?name=${encodeURIComponent(project)}`);
      onBundle?.(bundle);
      setStatus(res.message || "镜头已保存");
    } catch (e) {
      setStatus(String(e.message || e));
    } finally {
      setBusy(false);
    }
  };

  const applyChat = async () => {
    const text = chat.trim();
    if (!text || !selected) return;
    const patch = {};
    const dur = text.match(/(\d+(?:\.\d+)?)\s*秒|duration\s*[:=]?\s*(\d+(?:\.\d+)?)/i);
    if (dur) patch.duration_sec = Number(dur[1] || dur[2]);
    if (/仰拍|low\s*angle/i.test(text)) {
      patch.shot_language = { ...(selected.shot_language || {}), camera_movement: "tilt_up" };
      patch.description = `${selected.description || ""} (仰拍)`.trim();
    }
    if (/特写|close.?up/i.test(text)) {
      patch.shot_language = { ...(selected.shot_language || {}), shot_size: "close_up" };
    }
    if (!Object.keys(patch).length) {
      patch.description = text;
    }
    await save(patch);
    setChat("");
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
        <p className="mt-2 max-w-md text-sm text-[var(--muted)]">先完成剧本拆解；分镜会从 storyboard.json 载入，再逐镜生成视频。</p>
      </div>
    );
  }

  return (
    <div className="grid gap-4 xl:grid-cols-[320px_minmax(0,1fr)]">
      <div className="panel max-h-[75vh] overflow-y-auto p-2 scrollbar-thin">
        <div className="panel-muted mb-2 flex items-center justify-between px-3 py-2 text-[11px] text-[var(--muted)]">
          <span>{shots.length} shots</span>
          <button type="button" className="btn-quiet !min-h-7 !px-2 text-xs" onClick={syncLedger}>
            <RefreshCw className="h-3 w-3" /> 同步账本
          </button>
        </div>
        <div className="space-y-1">
          {shots.map((shot, i) => {
            const j = view.jobByShot[shot.id];
            return (
              <button
                key={shot.id}
                type="button"
                className={`w-full rounded-xl border px-3 py-3 text-left transition ${
                  selected?.id === shot.id ? "border-[var(--projector)]/45 bg-[var(--projector)]/10" : "border-transparent hover:bg-[var(--panel-muted)]"
                }`}
                onClick={() => setSelectedId(shot.id)}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="timecode text-[10px] text-[var(--muted)]">SH {String(i + 1).padStart(2, "0")}</span>
                  <span className={`status-pill ${j?.status || "pending"}`}>{j?.status || "pending"}</span>
                </div>
                <div className="mt-1 truncate text-sm font-semibold">{shot.id}</div>
                <div className="mt-1 line-clamp-2 text-[11px] leading-4 text-[var(--muted)]">
                  {shot.description || shot.prompt || "—"}
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {selected ? (
        <div className="space-y-4">
          <div className="panel p-5 md:p-6">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <div className="label">Shot director</div>
                <h3 className="display-type text-2xl font-semibold">{selected.id}</h3>
                <div className="mt-2 flex flex-wrap gap-2 text-xs text-[var(--muted)]">
                  <span className="panel-muted px-2 py-1">{selected.shot_intent || "shot"}</span>
                  <span className="panel-muted px-2 py-1">{selected.shot_language?.shot_size || "景别未设"}</span>
                  <span className="panel-muted px-2 py-1">{selected.shot_language?.camera_movement || "运镜未设"}</span>
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
                  {genState?.running ? "生成中…" : "批量生成"}
                </button>
              </div>
            </div>

            <div className="mt-5 grid gap-4 md:grid-cols-[1fr_140px]">
              <label className="block">
                <span className="label">镜头描述 / 提示词</span>
                <textarea className="field min-h-40 resize-y leading-7" value={desc} onChange={(e) => setDesc(e.target.value)} />
              </label>
              <label className="block">
                <span className="label">时长（秒）</span>
                <input className="field" type="number" min={1} max={30} step={0.5} value={duration} onChange={(e) => setDuration(e.target.value)} />
                {job?.output_path ? (
                  <a className="mt-3 block text-xs font-semibold text-[var(--run)] underline" href={`/api/media/${project}/${job.output_path}`}>
                    查看产物
                  </a>
                ) : null}
              </label>
            </div>

            <div className="mt-4 flex gap-2">
              <input
                className="field"
                value={chat}
                onChange={(e) => setChat(e.target.value)}
                placeholder="快捷改镜：仰拍 / 特写 / 时长 4 秒"
                onKeyDown={(e) => e.key === "Enter" && void applyChat()}
              />
              <button type="button" className="btn-secondary shrink-0" onClick={applyChat}>
                应用
              </button>
            </div>
            {status ? <p className="mt-3 text-xs text-[var(--muted)]">{status}</p> : null}
            {genState ? (
              <p className="mt-2 timecode text-[11px] text-[var(--muted)]">
                GEN {genState.running ? "RUNNING" : "IDLE"} · done {genState.processed || 0}
                {genState.failed ? ` · fail ${genState.failed}` : ""}
              </p>
            ) : null}
          </div>
        </div>
      ) : null}
    </div>
  );
}
