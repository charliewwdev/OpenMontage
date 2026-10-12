import { useState } from "react";
import { X } from "lucide-react";
import { api } from "../api";

export function NewProjectModal({ open, onClose, onCreated }) {
  const [title, setTitle] = useState("");
  const [source, setSource] = useState("");
  const [aspect, setAspect] = useState("9:16");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  if (!open) return null;

  const submit = async () => {
    setBusy(true);
    setErr("");
    try {
      const res = await api("/api/projects", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title, source_text: source, aspect_ratio: aspect }),
      });
      onCreated(res.created.name, res.bundle);
      onClose();
      setTitle("");
      setSource("");
    } catch (e) {
      setErr(String(e.message || e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-[rgba(16,24,39,.55)] p-4" onClick={onClose}>
      <div
        className="panel max-h-[90vh] w-full max-w-2xl overflow-y-auto p-6 shadow-float"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="mb-5 flex items-start justify-between gap-4">
          <div>
            <div className="label !mb-1">New production</div>
            <h2 className="display-type text-2xl font-semibold">建立新片场</h2>
            <p className="mt-1 text-sm text-[var(--muted)]">粘贴小说或剧本正文，自动拆场次、角色、分镜与镜头账本。</p>
          </div>
          <button type="button" className="btn-quiet !min-h-8 !px-2" onClick={onClose} aria-label="关闭">
            <X className="h-4 w-4" />
          </button>
        </header>

        <label className="mb-4 block">
          <span className="label">片名</span>
          <input className="field" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="例如：午夜短信" />
        </label>

        <div className="mb-4">
          <span className="label">画幅</span>
          <div className="flex gap-2">
            {[
              ["9:16", "竖屏 9:16"],
              ["16:9", "横屏 16:9"],
              ["1:1", "方屏 1:1"],
            ].map(([value, label]) => (
              <button
                key={value}
                type="button"
                className={`rounded-xl border px-4 py-2 text-sm font-semibold ${
                  aspect === value
                    ? "border-[var(--projector)] bg-[var(--projector)]/15 text-[var(--navy)]"
                    : "border-[var(--line)] bg-white text-[var(--muted)]"
                }`}
                onClick={() => setAspect(value)}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        <label className="mb-4 block">
          <span className="label">源文本</span>
          <textarea
            className="field min-h-56 resize-y"
            value={source}
            onChange={(e) => setSource(e.target.value)}
            placeholder={"支持对白格式：林夏：别回那通电话。\n\n空行分段即场次。"}
          />
        </label>

        {err ? <p className="mb-3 text-sm text-[var(--danger)]">{err}</p> : null}

        <footer className="flex justify-end gap-2">
          <button type="button" className="btn-secondary" onClick={onClose}>
            取消
          </button>
          <button
            type="button"
            className="btn-primary !border-[var(--projector)] !bg-[var(--projector)] !text-[var(--navy)]"
            disabled={busy || !title || source.length < 20}
            onClick={submit}
          >
            {busy ? "创建中…" : "创建并拆解"}
          </button>
        </footer>
      </div>
    </div>
  );
}
