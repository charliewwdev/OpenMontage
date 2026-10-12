import { useEffect, useMemo, useState } from "react";
import { api } from "../../api";

export function EditStep({ projectId, bundle, setBusyMsg, onBundle, onRefresh }) {
  const episodes = useMemo(
    () => [...(bundle?.episodes || [])].sort((a, b) => a.episodeNumber - b.episodeNumber),
    [bundle?.episodes],
  );
  const [episodeId, setEpisodeId] = useState(episodes[0]?.id || "");
  const [clips, setClips] = useState([]);

  useEffect(() => {
    if (!episodeId && episodes[0]) setEpisodeId(episodes[0].id);
  }, [episodes, episodeId]);

  const edit = (bundle?.edits || []).find((e) => e.episodeId === episodeId);
  const shots = useMemo(
    () =>
      (bundle?.shots || [])
        .filter((s) => s.episodeId === episodeId && !s.deletedAt)
        .sort((a, b) => a.shotOrder - b.shotOrder),
    [bundle?.shots, episodeId],
  );

  useEffect(() => {
    if (edit?.clips) setClips(edit.clips);
    else setClips([]);
  }, [edit?.id, edit?.updatedAt, episodeId]);

  const apply = (res) => {
    if (res?.bundle) onBundle?.(res.bundle);
    else onRefresh?.();
  };

  const ensure = async () => {
    if (!episodeId) return;
    setBusyMsg("从分镜构建时间线…");
    try {
      const res = await api(`/api/projects/${encodeURIComponent(projectId)}/edits`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "ensure", episodeId }),
      });
      apply(res);
      if (res.edit?.clips) setClips(res.edit.clips);
    } catch (e) {
      window.alert(String(e.message || e));
    } finally {
      setBusyMsg("");
    }
  };

  const save = async () => {
    setBusyMsg("保存剪辑草稿…");
    try {
      const res = await api(`/api/projects/${encodeURIComponent(projectId)}/edits`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "save", episodeId, clips }),
      });
      apply(res);
    } catch (e) {
      window.alert(String(e.message || e));
    } finally {
      setBusyMsg("");
    }
  };

  const exportMp4 = async () => {
    setBusyMsg("FFmpeg 导出中…");
    const t0 = performance.now();
    try {
      await save();
      const res = await api(`/api/projects/${encodeURIComponent(projectId)}/edits`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "export", episodeId }),
      });
      apply(res);
      setBusyMsg(`导出完成（${((performance.now() - t0) / 1000).toFixed(1)}s）`);
      setTimeout(() => setBusyMsg(""), 2000);
    } catch (e) {
      setBusyMsg("");
      window.alert(String(e.message || e));
    }
  };

  const updateClip = (idx, patch) => {
    setClips((list) => list.map((c, i) => (i === idx ? { ...c, ...patch } : c)));
  };

  const shotById = Object.fromEntries(shots.map((s) => [s.id, s]));
  const enabledCount = clips.filter((c) => c.enabled !== false).length;

  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="display-type text-3xl">剪辑室</h2>
          <p className="mt-1 text-sm text-[var(--muted)]">按分镜建时间线 · 启用/禁用 · 入出点 · FFmpeg 成片</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <select className="field !w-auto !py-1.5" value={episodeId} onChange={(e) => setEpisodeId(e.target.value)}>
            {episodes.map((ep) => (
              <option key={ep.id} value={ep.id}>
                EP{ep.episodeNumber} {ep.title || ""}
              </option>
            ))}
          </select>
          <button type="button" className="btn-ghost" onClick={() => void ensure()}>
            从分镜重建
          </button>
          <button type="button" className="btn-ghost" disabled={!clips.length} onClick={() => void save()}>
            保存草稿
          </button>
          <button type="button" className="btn-primary" disabled={!clips.length} onClick={() => void exportMp4()}>
            导出 MP4
          </button>
        </div>
      </header>

      {edit?.outputUrl ? (
        <section className="panel space-y-2 p-4">
          <p className="text-xs text-[var(--muted)]">最新成片预览</p>
          <video className="max-h-[360px] w-full rounded-xl bg-black" controls src={edit.outputUrl} />
        </section>
      ) : null}

      <section className="panel overflow-hidden">
        <div className="flex items-center justify-between border-b border-[var(--line)] px-4 py-2 text-xs text-[var(--muted)]">
          <span>
            片段 {clips.length} · 启用 {enabledCount}
          </span>
          {!clips.length && (
            <button type="button" className="text-[var(--run)] underline" onClick={() => void ensure()}>
              构建时间线
            </button>
          )}
        </div>
        <ul className="divide-y divide-[var(--line)]">
          {clips.map((clip, idx) => {
            const shot = shotById[clip.shotId];
            const videoUrl = shot?.selectedVideo?.url;
            return (
              <li key={clip.shotId || idx} className="flex flex-wrap items-center gap-3 px-4 py-3">
                <label className="flex items-center gap-2 text-xs">
                  <input
                    type="checkbox"
                    checked={clip.enabled !== false}
                    onChange={(e) => updateClip(idx, { enabled: e.target.checked })}
                  />
                  启用
                </label>
                <span className="timecode w-16 text-xs">
                  #{String(shot?.shotOrder || idx + 1).padStart(2, "0")}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="line-clamp-1 text-sm">{shot?.prompt || clip.shotId}</p>
                  {videoUrl ? (
                    <video className="mt-1 h-16 rounded bg-black" src={videoUrl} muted />
                  ) : (
                    <span className="text-[11px] text-[var(--danger)]">无选用 TAKE</span>
                  )}
                </div>
                <label className="text-[11px] text-[var(--muted)]">
                  入点
                  <input
                    type="number"
                    min={0}
                    step={0.1}
                    className="field ml-1 !w-20 !py-1"
                    value={clip.start ?? 0}
                    onChange={(e) => updateClip(idx, { start: Number(e.target.value) || 0 })}
                  />
                </label>
                <label className="text-[11px] text-[var(--muted)]">
                  出点
                  <input
                    type="number"
                    min={0}
                    step={0.1}
                    className="field ml-1 !w-20 !py-1"
                    value={clip.end ?? ""}
                    onChange={(e) =>
                      updateClip(idx, { end: e.target.value === "" ? null : Number(e.target.value) })
                    }
                    placeholder="末尾"
                  />
                </label>
              </li>
            );
          })}
          {!clips.length && (
            <li className="px-4 py-12 text-center text-sm text-[var(--muted)]">
              在分镜台选用 TAKE 后，点击「从分镜重建」生成时间线
            </li>
          )}
        </ul>
      </section>
    </div>
  );
}
