import { useMemo, useState } from "react";
import { api } from "../api";
import { PROJECT_GENRES, PROJECT_RATIOS } from "../config/options";
import { VIDEO_STYLES, getDefaultVideoStyle } from "../config/videoStyles";

export function CreateProjectPage({ config, onBack, onCreated }) {
  const genres = config?.genres?.length ? config.genres : PROJECT_GENRES;
  const ratios = config?.ratios?.length ? config.ratios : PROJECT_RATIOS;
  const styles = config?.styles?.length ? config.styles : VIDEO_STYLES;
  const defaultStyle = useMemo(() => styles[0] || getDefaultVideoStyle(), [styles]);

  const [title, setTitle] = useState("");
  const [genre, setGenre] = useState(genres[0]);
  const [ratio, setRatio] = useState(ratios[0]?.value || "9:16");
  const [styleId, setStyleId] = useState(defaultStyle?.id || defaultStyle?.promptValue || "");
  const [brief, setBrief] = useState("");
  const [busy, setBusy] = useState(false);
  const [optimizing, setOptimizing] = useState(false);

  const selectedStyle = styles.find((s) => s.id === styleId || s.promptValue === styleId) || defaultStyle;
  const visualStyle = selectedStyle?.generationPrompt || selectedStyle?.promptValue || "";

  const optimize = async () => {
    if (!brief.trim()) {
      window.alert("请先填写创作需求");
      return;
    }
    setOptimizing(true);
    try {
      const res = await api("/api/script-brief", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          brief,
          genre,
          visualStyle,
          title,
        }),
      });
      if (res.brief) setBrief(res.brief);
      if (res.title && !title.trim()) setTitle(res.title);
    } catch (e) {
      window.alert(String(e.message || e));
    } finally {
      setOptimizing(false);
    }
  };

  const create = async () => {
    if (!title.trim()) {
      window.alert("请填写片名");
      return;
    }
    setBusy(true);
    try {
      const bundle = await api("/api/projects", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: title.trim(),
          brief: brief.trim(),
          genre,
          visualStyle,
          ratio,
        }),
      });
      onCreated?.(bundle.project?.id || bundle.id);
    } catch (e) {
      window.alert(String(e.message || e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto min-h-full max-w-3xl px-4 py-8 md:px-8">
      <button type="button" className="btn-ghost mb-4" onClick={onBack}>
        ← 返回片库
      </button>
      <h1 className="display-type text-4xl">创建片场</h1>
      <p className="mt-2 text-sm text-[var(--muted)]">片名、题材、视觉风格、画幅与创作需求。可用 AI 优化需求文案。</p>

      <div className="panel mt-6 space-y-5 p-5">
        <label className="block space-y-1.5">
          <span className="text-xs font-medium text-[var(--muted)]">片名</span>
          <input
            className="field"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="例如：重生之都市逆袭"
          />
        </label>

        <div className="space-y-1.5">
          <span className="text-xs font-medium text-[var(--muted)]">题材</span>
          <div className="flex flex-wrap gap-2">
            {genres.map((g) => (
              <button
                key={g}
                type="button"
                className={genre === g ? "chip-active" : "chip"}
                onClick={() => setGenre(g)}
              >
                {g}
              </button>
            ))}
          </div>
        </div>

        <div className="space-y-1.5">
          <span className="text-xs font-medium text-[var(--muted)]">画幅</span>
          <div className="grid gap-2 sm:grid-cols-3">
            {ratios.map((r) => (
              <button
                key={r.value}
                type="button"
                className={`rounded-xl border px-3 py-3 text-left ${
                  ratio === r.value ? "border-[var(--projector)] bg-[var(--panel-muted)]" : "border-[var(--line)]"
                }`}
                onClick={() => setRatio(r.value)}
              >
                <div className="font-medium">{r.label}</div>
                <div className="text-xs text-[var(--muted)]">
                  {r.value} · {r.description}
                </div>
              </button>
            ))}
          </div>
        </div>

        <label className="block space-y-1.5">
          <span className="text-xs font-medium text-[var(--muted)]">视觉风格（{styles.length}）</span>
          <select
            className="field"
            value={styleId}
            onChange={(e) => setStyleId(e.target.value)}
          >
            {styles.map((s) => (
              <option key={s.id || s.promptValue} value={s.id || s.promptValue}>
                {s.label || s.name || s.id}
              </option>
            ))}
          </select>
          {selectedStyle?.description ? (
            <p className="text-xs text-[var(--muted)]">{selectedStyle.description}</p>
          ) : null}
        </label>

        <label className="block space-y-1.5">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-[var(--muted)]">创作需求</span>
            <button type="button" className="btn-ghost !py-1 !text-xs" disabled={optimizing} onClick={() => void optimize()}>
              {optimizing ? "优化中…" : "AI 优化需求"}
            </button>
          </div>
          <textarea
            className="field min-h-[160px]"
            value={brief}
            onChange={(e) => setBrief(e.target.value)}
            placeholder="主角设定、冲突、节奏、结局倾向、目标集数等…"
          />
        </label>

        <div className="flex justify-end gap-2 border-t border-[var(--line)] pt-4">
          <button type="button" className="btn-ghost" onClick={onBack}>
            取消
          </button>
          <button type="button" className="btn-primary" disabled={busy} onClick={() => void create()}>
            {busy ? "创建中…" : "进入剧本台"}
          </button>
        </div>
      </div>
    </div>
  );
}
