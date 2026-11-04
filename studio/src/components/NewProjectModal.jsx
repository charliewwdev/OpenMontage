import { useState } from "react";
import { X } from "lucide-react";
import { api } from "../api";
import { ModalOverlay } from "./ModalPortal";

import { tr, useLocale } from "../lib/i18n";

export function NewProjectModal({ open, onClose, onCreated }) {
  useLocale();
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
    <ModalOverlay onClose={onClose} className="bg-[rgba(16,24,39,.55)]">
      <div
        className="panel my-auto max-h-[90vh] w-full max-w-2xl overflow-y-auto p-6 shadow-float"
        onClick={(e) => e.stopPropagation()}
        onMouseDown={(e) => e.stopPropagation()}
      >
        <header className="mb-5 flex items-start justify-between gap-4">
          <div>
            <div className="label !mb-1">New production</div>
            <h2 className="display-type text-2xl font-semibold">{tr("ui_new_project_new_project")}</h2>
            <p className="mt-1 text-sm text-[var(--muted)]">{tr("ui_new_project_paste_a_novel_or_script_to")}</p>
          </div>
          <button type="button" className="btn-quiet !min-h-8 !px-2" onClick={onClose} aria-label={tr("ui_new_project_close")}>
            <X className="h-4 w-4" />
          </button>
        </header>

        <label className="mb-4 block">
          <span className="label">{tr("ui_new_project_title")}</span>
          <input className="field" value={title} onChange={(e) => setTitle(e.target.value)} placeholder={tr("ui_new_project_e_g_midnight_text_message")} />
        </label>

        <div className="mb-4">
          <span className="label">{tr("ui_new_project_frame")}</span>
          <div className="flex gap-2">
            {[
              ["9:16", tr("ui_new_project_portrait_9_16")],
              ["16:9", tr("ui_new_project_landscape_16_9")],
              ["1:1", tr("ui_new_project_square_1_1")],
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
          <span className="label">{tr("ui_new_project_source_text")}</span>
          <textarea
            className="field min-h-56 resize-y"
            value={source}
            onChange={(e) => setSource(e.target.value)}
            placeholder={tr("ui_new_project_dialogue_format_supported_lin_xia_don")}
          />
        </label>

        {err ? <p className="mb-3 text-sm text-[var(--danger)]">{err}</p> : null}

        <footer className="flex justify-end gap-2">
          <button type="button" className="btn-secondary" onClick={onClose}>{tr("ui_new_project_cancel")}</button>
          <button
            type="button"
            className="btn-primary !border-[var(--projector)] !bg-[var(--projector)] !text-[var(--navy)]"
            disabled={busy || !title || source.length < 20}
            onClick={submit}
          >
            {busy ? tr("ui_new_project_creating") : tr("ui_new_project_create_and_split")}
          </button>
        </footer>
      </div>
    </ModalOverlay>
  );
}
