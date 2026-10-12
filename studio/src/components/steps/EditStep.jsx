import { useState } from "react";
import { Download, GripVertical, Scissors } from "lucide-react";
import { api } from "../../api";

export function EditStep({ project, view, onBundle }) {
  const shots = view.shots || [];
  const [order, setOrder] = useState(shots.map((s) => s.id));
  const [timeline, setTimeline] = useState(null);
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(false);

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

  const exportTimeline = async () => {
    setBusy(true);
    try {
      const res = await api(`/api/project/export/timeline?name=${encodeURIComponent(project)}`);
      setTimeline(res.timeline || res);
      setStatus("时间线草稿已导出");
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
        <p className="mt-2 text-sm text-[var(--muted)]">先在分镜步骤生成或导入镜头片段。</p>
      </div>
    );
  }

  const byId = Object.fromEntries(shots.map((s) => [s.id, s]));

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="label">Edit room</div>
          <h3 className="display-type text-2xl font-semibold">分集时间线</h3>
          <p className="mt-1 text-sm text-[var(--muted)]">调整镜头顺序，导出时间线草稿；成片编码可接 FFmpeg 导出。</p>
        </div>
        <div className="flex gap-2">
          <button type="button" className="btn-secondary" disabled={busy} onClick={saveOrder}>
            保存顺序
          </button>
          <button type="button" className="btn-primary" disabled={busy} onClick={exportTimeline}>
            <Download className="h-4 w-4" /> 导出时间线
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
      {timeline ? (
        <pre className="panel max-h-72 overflow-auto p-4 text-xs leading-5 text-[var(--muted)]">
          {JSON.stringify(timeline, null, 2)}
        </pre>
      ) : null}
    </div>
  );
}
