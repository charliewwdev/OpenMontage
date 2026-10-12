import { useEffect, useState } from "react";
import { FileText, RefreshCw, Save, Upload } from "lucide-react";
import { api } from "../../api";

export function ScriptStep({ project, view, onBundle }) {
  const [title, setTitle] = useState(view.title);
  const [synopsis, setSynopsis] = useState(view.synopsis);
  const [source, setSource] = useState("");
  const [selectedId, setSelectedId] = useState(view.episodes[0]?.id || null);
  const [episodeText, setEpisodeText] = useState("");
  const [status, setStatus] = useState("");
  const [saving, setSaving] = useState(false);
  const [rebuilding, setRebuilding] = useState(false);

  const selected = view.episodes.find((e) => e.id === selectedId) || view.episodes[0] || null;
  const scenes = view.breakdown?.episodes?.[0]?.scenes || view.script?.sections || [];

  useEffect(() => {
    setTitle(view.title);
    setSynopsis(view.synopsis);
  }, [view.title, view.synopsis]);

  useEffect(() => {
    api(`/api/project/source?name=${encodeURIComponent(project)}`)
      .then((d) => setSource(d.source || view.brief || view.sourceExcerpt || ""))
      .catch(() => setSource(view.brief || view.sourceExcerpt || ""));
  }, [project, view.brief, view.sourceExcerpt]);

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
      await api("/api/project/artifact", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          project,
          kind: "script",
          data: {
            ...(view.script || {}),
            title,
            synopsis,
            brief: source,
            aspect_ratio: view.ratio,
            genre: view.genre,
            visual_style: view.style,
          },
        }),
      });
      const bundle = await api(`/api/project/bundle?name=${encodeURIComponent(project)}`);
      onBundle?.(bundle);
      setStatus("剧本底稿已保存");
    } catch (e) {
      setStatus(String(e.message || e));
    } finally {
      setSaving(false);
    }
  };

  const rebuild = async () => {
    if (source.trim().length < 20) {
      setStatus("源文太短，无法重新拆解");
      return;
    }
    if (!window.confirm("从当前小说正文重新拆解？将覆盖场次、角色、分镜与镜头账本。")) return;
    setRebuilding(true);
    setStatus("");
    try {
      const res = await api("/api/project/rebuild", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          project,
          title,
          source_text: source,
          aspect_ratio: view.ratio,
          visual_style: view.style,
          genre: view.genre,
        }),
      });
      onBundle?.(res.bundle);
      setStatus(`已重新拆解：${res.rebuilt?.scenes || 0} 场 · ${res.rebuilt?.shots || 0} 镜 · ${res.rebuilt?.characters || 0} 角色`);
    } catch (e) {
      setStatus(String(e.message || e));
    } finally {
      setRebuilding(false);
    }
  };

  const onUpload = async (file) => {
    if (!file) return;
    const text = await file.text();
    setSource(text.slice(0, 100_000));
    setStatus(`已载入 ${file.name}（${text.length} 字），点击「重新拆解」生效`);
  };

  return (
    <div className="grid gap-5 xl:grid-cols-[minmax(0,1.35fr)_320px]">
      <section className="space-y-4">
        <div className="panel p-5 md:p-6">
          <div className="label">小说 → 剧本</div>
          <h3 className="display-type text-xl font-semibold">源文与拆解</h3>
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
              <textarea className="field min-h-24 resize-y" value={synopsis} onChange={(e) => setSynopsis(e.target.value)} />
            </label>
            <label className="block md:col-span-2">
              <div className="mb-2 flex items-center justify-between">
                <span className="label !mb-0">小说正文 / 源素材</span>
                <label className="btn-quiet !min-h-8 cursor-pointer text-xs">
                  <Upload className="h-3.5 w-3.5" /> 上传文件
                  <input
                    type="file"
                    accept=".txt,.md,.text,text/plain"
                    className="hidden"
                    onChange={(e) => void onUpload(e.target.files?.[0])}
                  />
                </label>
              </div>
              <textarea
                className="field min-h-48 resize-y leading-7"
                value={source}
                onChange={(e) => setSource(e.target.value)}
              />
            </label>
          </div>
          <div className="mt-4 flex flex-wrap items-center gap-2">
            <button type="button" className="btn-primary" disabled={saving} onClick={saveMeta}>
              <Save className="h-4 w-4" />
              {saving ? "保存中…" : "保存底稿"}
            </button>
            <button type="button" className="btn-secondary" disabled={rebuilding} onClick={rebuild}>
              <RefreshCw className={`h-4 w-4 ${rebuilding ? "animate-spin" : ""}`} />
              {rebuilding ? "拆解中…" : "从小说重新拆解"}
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
            <span className="timecode text-[11px] text-[var(--muted)]">{view.episodes.length} EPS · {scenes.length} SCENES</span>
          </div>

          {view.episodes.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-[var(--line)] py-16 text-center">
              <FileText className="mx-auto mb-3 h-9 w-9 text-[var(--projector)]" />
              <p className="text-sm text-[var(--muted)]">还没有分集。粘贴小说后点击「从小说重新拆解」。</p>
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
                <textarea
                  className="field min-h-[360px] resize-y font-[inherit] leading-7"
                  value={episodeText}
                  onChange={(e) => setEpisodeText(e.target.value)}
                />
              </div>
            </div>
          )}
        </div>
      </section>

      <aside className="space-y-4">
        <div className="panel p-5">
          <div className="label">Scenes</div>
          <h4 className="display-type text-lg font-semibold">场次清单</h4>
          <ul className="mt-4 max-h-[40vh] space-y-2 overflow-y-auto scrollbar-thin">
            {scenes.length === 0 ? (
              <li className="text-sm text-[var(--muted)]">拆解后显示场次</li>
            ) : (
              scenes.map((sc, i) => (
                <li key={sc.id || i} className="border-b border-[var(--line)] pb-2">
                  <div className="timecode text-[10px] text-[var(--muted)]">SC {String(i + 1).padStart(2, "0")}</div>
                  <div className="text-sm font-semibold">{sc.title || sc.label || sc.id}</div>
                  <div className="mt-0.5 line-clamp-2 text-[11px] text-[var(--muted)]">
                    {sc.purpose || sc.text || sc.body || ""}
                  </div>
                </li>
              ))
            )}
          </ul>
        </div>
        <div className="panel p-5">
          <div className="label">Pipeline</div>
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
          下一步：确认角色定妆 → 场景/道具 → 分镜批量生成 → 剪辑导出 MP4。
        </div>
      </aside>
    </div>
  );
}
