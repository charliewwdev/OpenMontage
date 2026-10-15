import { ModalOverlay } from "./ModalPortal";

export function ConfirmDialog({ open, title, message, confirmLabel = "确认", danger, onConfirm, onCancel }) {
  if (!open) return null;
  return (
    <ModalOverlay onClose={onCancel} className="bg-black/45" zClass="z-[200]">
      <div
        className="panel my-auto w-full max-w-md p-5"
        role="dialog"
        aria-modal="true"
        onMouseDown={(e) => e.stopPropagation()}
      >
        <h3 className="display-type text-xl">{title}</h3>
        <p className="mt-2 text-sm text-[var(--muted)]">{message}</p>
        <div className="mt-5 flex justify-end gap-2">
          <button type="button" className="btn-ghost" onClick={onCancel}>
            取消
          </button>
          <button type="button" className={danger ? "btn-danger" : "btn-primary"} onClick={onConfirm}>
            {confirmLabel}
          </button>
        </div>
      </div>
    </ModalOverlay>
  );
}
