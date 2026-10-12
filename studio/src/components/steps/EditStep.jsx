import { useEffect, useState } from "react";
import { Download, Film, GripVertical, Scissors } from "lucide-react";
import { api } from "../../api";

export function EditStep({ project, view, onBundle }) {
  const shots = view.shots || [];
  const [order, setOrder] = useState(shots.map((s) => s.id));
  const [exports, setExports] = useState([]);
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(false);
  const [latestUrl, setLatestUrl] = useState("");

  useEffect(() => {
    setOrder(shots.map((s) => s.id));
  }, [shots.map((s) => s.id).join("|")]);

  useEffect(() => {
    api(`/api/project/exports?name=${encodeURIComponent(project)}`)
      .then((d) => {
        setExports(d.exports || []);
        if (d.exports?.[0]?.url) setLatestUrl(d.exports[0].url);
      })
      .catch(() => {});
  }, [project]);

  const move = (index, dir) => {
    const next = [...order];
    const target = index + dir;
    if (target < 0 || target >= next.length) return;
    [next[index], next[target]] = [next[target], next[index]];
    setOrder(next);
  };

  const saveOrder = async () => {
    setBusy(true);
    setStatus("");
    try {
      await api("/api/project/storyboard/reorder", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ project, shot_ids: order }),
      });
      const bundle = await api(`/api/project/bundle?name=${encodeURIComponent(project)}`);
      onBundle?.(bundle);
      setStatus("镜头顺序已保存");
    } catch (e) {
      setStatus(String(e.message || e));
    } finally {
      setBusy(false);
    }
  };

  const exportMp4 = async () => {
    setBusy(true);
    setStatus("正在用 FFmpeg 拼接成片…");
    try {
      await api("/api/project/storyboard/reorder", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ project, shot_ids: order }),
      });
      const res = await api("/api/project/export/mp4", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ project, shot_ids: order }),
      });
      if (res.bundle) onBundle?.(res.bundle);
      else {
        const bundle = await api(`/api/project/bundle?name=${encodeURIComponent(project)}`);
        onBundle?.(bundle);
      }
      setLatestUrl(res.url);
      setExports((prev) => [
        { path: res.path, url: res.url, bytes: res.bytes, mtime: Date.now() / 1000 },
        ...prev,
      ]);
      setStatus(`成片已导出 · ${res.clips} 镜 · ${(res.bytes / 1024).toFixed(0)} KB`);
    } catch (e) {
      setStatus(String(e.message || e));
    } finally {
      setBusy(false);
    }
  };

  if (!shots.length) {
    return (
      <div className="panel flex flex-col items-center border-dashed py-24 text-center">
        <Scissors className="mb-4 h-10 w-10 text-[var(--projector)]" />
        <strong className="display-type text-xl">还没有可剪辑镜头</strong>
        <p className="mt-2 text-sm text-[var(--muted)]">先在分镜步骤批量生成镜头板 / 片段。</p>
      </div>
    );
  }

  const byId = Object.fromEntries(shots.map((s) => [s.id, s]));

  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
      <div className="space-y-4">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <div className="label">Edit room</div>
            <h3 className="display-type text-2xl font-semibold">分集时间线</h3>
            <p className="mt-1 text-sm text-[var(--muted)]">调整顺序后一键导出 MP4 成片。</p>
          </div>
          <div className="flex gap-2">
            <button type="button" className="btn-secondary" disabled={busy} onClick={saveOrder}>
              保存顺序
            </button>
            <button
              type="button"
              className="btn-primary !border-[var(--projector)] !bg-[var(--projector)] !text-[var(--navy)]"
              disabled={busy}
              onClick={exportMp4}
            >
              <Download className="h-4 w-4" />
              {busy ? "导出中…" : "导出 MP4"}
            </button>
          </div>
        </div>

        <div className="panel overflow-hidden">
          <div className="border-b border-[var(--line)] bg-[var(--panel-muted)] px-4 py-3">
            <div className="timecode text-[11px] text-[var(--muted)]">TIMELINE · {order.length} CLIPS</div>
          </div>
          <ul className="divide-y divide-[var(--line)]">
            {order.map((id, index) => {
              const shot = byId[id];
              const job = view.jobByShot[id];
              if (!shot) return null;
              return (
                <li key={id} className="flex items-center gap-3 px-4 py-3">
                  <GripVertical className="h-4 w-4 text-[var(--muted)]" />
                  <div className="timecode w-10 text-xs text-[var(--muted)]">{String(index + 1).padStart(2, "0")}</div>
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm font-semibold">{shot.id}</div>
                    <div className="truncate text-xs text-[var(--muted)]">{shot.description || "—"}</div>
                  </div>
                  <span className="timecode text-[11px] text-[var(--muted)]">{shot.duration_sec || 4}s</span>
                  <span className={`status-pill ${job?.status || "pending"}`}>{job?.status || "pending"}</span>
                  <div className="flex gap-1">
                    <button type="button" className="btn-quiet !min-h-8 !px-2" onClick={() => move(index, -1)}>
                      ↑
                    </button>
                    <button type="button" className="btn-quiet !min-h-8 !px-2" onClick={() => move(index, 1)}>
                      ↓
                    </button>
                  </div>
                </li>
              );
            })}
          </ul>
        </div>
        {status ? <p className="text-xs text-[var(--muted)]">{status}</p> : null}
      </div>

      <aside className="space-y-4">
        <div className="panel overflow-hidden">
          <div className="border-b border-[var(--line)] px-4 py-3">
            <div className="label !mb-0">Preview</div>
            <h4 className="display-type text-lg font-semibold">成片预览</h4>
          </div>
          <div className="flex aspect-[9/16] items-center justify-center bg-[var(--navy)]">
            {latestUrl ? (
              <video key={latestUrl} src={latestUrl} controls className="h-full w-full object-contain" />
            ) : (
              <div className="px-6 text-center text-sm text-white/45">
                <Film className="mx-auto mb-3 h-8 w-8" />
                导出后在此播放
              </div>
            )}
          </div>
        </div>
        <div className="panel p-4">
          <div className="label">Exports</div>
          <ul className="mt-2 space-y-2">
            {exports.length === 0 ? (
              <li className="text-xs text-[var(--muted)]">暂无导出记录</li>
            ) : (
              exports.slice(0, 5).map((item) => (
                <li key={item.path}>
                  <a className="text-xs font-semibold text-[var(--run)] underline" href={item.url} target="_blank" rel="noreferrer">
                    {item.path}
                  </a>
                  <div className="timecode text-[10px] text-[var(--muted)]">{((item.bytes || 0) / 1024).toFixed(0)} KB</div>
                </li>
              ))
            )}
          </ul>
        </div>
      </aside>
    </div>
  );
}
