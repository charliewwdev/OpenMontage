import { ModalOverlay } from "./ModalPortal";

import { tr, useLocale } from "../lib/i18n";

export function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = tr("ui_confirm_dialog_confirm"),
  cancelLabel = tr("ui_confirm_dialog_cancel"),
  danger,
  onConfirm,
  onCancel,
  maxWidthClass = "max-w-md",
}) {
  useLocale();
  if (!open) return null;
  return (
    <ModalOverlay onClose={onCancel} className="bg-black/45" zClass="z-[200]">
      <div
        className={`panel my-auto w-full ${maxWidthClass} p-5`}
        role="dialog"
        aria-modal="true"
        onMouseDown={(e) => e.stopPropagation()}
      >
        <h3 className="display-type text-xl">{title}</h3>
        <div className="mt-2 text-sm text-[var(--muted)] whitespace-pre-wrap">{message}</div>
        <div className="mt-5 flex justify-end gap-2">
          <button type="button" className="btn-ghost" onClick={onCancel}>
            {cancelLabel}
          </button>
          <button type="button" className={danger ? "btn-danger" : "btn-primary"} onClick={onConfirm}>
            {confirmLabel}
          </button>
        </div>
      </div>
    </ModalOverlay>
  );
}
