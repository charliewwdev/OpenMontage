import { useEffect, useState } from "react";
import { FileText, Save } from "lucide-react";
import { api } from "../../api";

export function ScriptStep({ project, view, onBundle }) {
  const [title, setTitle] = useState(view.title);
  const [synopsis, setSynopsis] = useState(view.synopsis);
  const [brief, setBrief] = useState(view.brief || view.sourceExcerpt);
  const [selectedId, setSelectedId] = useState(view.episodes[0]?.id || null);
  const [episodeText, setEpisodeText] = useState("");
  const [status, setStatus] = useState("");
  const [saving, setSaving] = useState(false);

  const selected = view.episodes.find((e) => e.id === selectedId) || view.episodes[0] || null;

  useEffect(() => {
    setTitle(view.title);
    setSynopsis(view.synopsis);
    setBrief(view.brief || view.sourceExcerpt);
  }, [view.title, view.synopsis, view.brief, view.sourceExcerpt]);

  useEffect(() => {
    if (!selected) {
      setEpisodeText("");
      return;
    }
    setEpisodeText(selected.content || selected.text || selected.script || selected.summary || "");
  }, [selected]);

  const saveMeta = async () => {
    setSaving(true);
    setStatus("");
    try {
      const next = {
        ...(view.script || {}),
        title,
        synopsis,
        brief,
        aspect_ratio: view.ratio,
        genre: view.genre,
      };
      const res = await api("/api/project/artifact", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ project, kind: "script", data: next }),
      });
      onBundle?.(res.bundle || null);
      setStatus("剧本元数据已保存");
    } catch (e) {
      setStatus(String(e.message || e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="grid gap-5 xl:grid-cols-[minmax(0,1.35fr)_320px]">
      <section className="space-y-4">
        <div className="panel p-5 md:p-6">
          <div className="label">创作底稿</div>
          <h3 className="display-type text-xl font-semibold">Story brief</h3>

          <div className="mt-5 grid gap-4 md:grid-cols-2">
            <label className="block md:col-span-2">
              <span className="label">片名</span>
              <input className="field" value={title} onChange={(e) => setTitle(e.target.value)} />
            </label>
            <div>
              <span className="label">画幅</span>
              <div className="panel-muted px-3 py-2.5 text-sm font-semibold">{view.ratio}</div>
            </div>
            <div>
              <span className="label">题材 / 风格</span>
              <div className="panel-muted px-3 py-2.5 text-sm font-semibold">
                {view.genre}
                {view.style ? ` · ${view.style}` : ""}
              </div>
            </div>
            <label className="block md:col-span-2">
              <span className="label">故事梗概</span>
              <textarea className="field min-h-28 resize-y" value={synopsis} onChange={(e) => setSynopsis(e.target.value)} />
            </label>
            <label className="block md:col-span-2">
              <span className="label">创作需求 / 源素材</span>
              <textarea className="field min-h-36 resize-y" value={brief} onChange={(e) => setBrief(e.target.value)} />
            </label>
          </div>

          <div className="mt-4 flex flex-wrap items-center gap-2">
            <button type="button" className="btn-primary" disabled={saving} onClick={saveMeta}>
              <Save className="h-4 w-4" />
              {saving ? "保存中…" : "保存底稿"}
            </button>
            {status ? <span className="text-xs text-[var(--muted)]">{status}</span> : null}
          </div>
        </div>

        <div className="panel p-5 md:p-6">
          <div className="mb-4 flex items-end justify-between gap-3">
            <div>
              <div className="label">Episodes</div>
              <h3 className="display-type text-xl font-semibold">分集剧本</h3>
            </div>
            <span className="timecode text-[11px] text-[var(--muted)]">{view.episodes.length} EPS</span>
          </div>

          {view.episodes.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-[var(--line)] py-16 text-center">
              <FileText className="mx-auto mb-3 h-9 w-9 text-[var(--projector)]" />
              <p className="text-sm text-[var(--muted)]">还没有分集。新建项目时会从源文本拆出场次与分集草稿。</p>
            </div>
          ) : (
            <div className="grid gap-4 lg:grid-cols-[220px_minmax(0,1fr)]">
              <div className="space-y-1">
                {view.episodes.map((ep, i) => (
                  <button
                    key={ep.id || i}
                    type="button"
                    className={`w-full rounded-xl border px-3 py-3 text-left transition ${
                      (selected?.id || selectedId) === ep.id
                        ? "border-[var(--projector)]/50 bg-[var(--projector)]/10"
                        : "border-transparent hover:bg-[var(--panel-muted)]"
                    }`}
                    onClick={() => setSelectedId(ep.id)}
                  >
                    <div className="timecode text-[10px] text-[var(--muted)]">EP {String(ep.episodeNumber || i + 1).padStart(2, "0")}</div>
                    <div className="mt-1 text-sm font-semibold">{ep.title || `第 ${i + 1} 集`}</div>
                  </button>
                ))}
              </div>
              <div>
                <div className="mb-2 flex items-center justify-between">
                  <strong className="text-sm">{selected?.title || "分集正文"}</strong>
                  <span className={`status-pill ${selected?.status || "draft"}`}>{selected?.status || "draft"}</span>
                </div>
                <textarea className="field min-h-[420px] resize-y font-[inherit] leading-7" value={episodeText} readOnly />
                <p className="mt-2 text-xs text-[var(--muted)]">分集正文来自拆解产物；后续可接续写/改写 API。</p>
              </div>
            </div>
          )}
        </div>
      </section>

      <aside className="space-y-4">
        <div className="panel p-5">
          <div className="label">Pipeline status</div>
          <h4 className="display-type text-lg font-semibold">制片进度</h4>
          <ul className="mt-4 space-y-3">
            {(view.steps || []).map((step) => (
              <li key={step.id} className="flex items-center justify-between gap-3 border-b border-[var(--line)] pb-2">
                <span className="text-sm font-semibold">{step.label}</span>
                <span className={`status-pill ${step.state}`}>{step.state}</span>
              </li>
            ))}
          </ul>
        </div>
        <div className="panel-muted p-5 text-sm leading-6 text-[var(--muted)]">
          <div className="label !mb-2">Tip</div>
          先定稿剧本与资产档案，再进分镜批量生成。角色/场景/道具会从 bible 自动带入。
        </div>
      </aside>
    </div>
  );
}
