export function ConfirmDialog({ open, title, message, confirmLabel = "确认", danger, onConfirm, onCancel }) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/45 p-4">
      <div className="panel w-full max-w-md p-5" role="dialog" aria-modal="true">
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
    </div>
  );
}
