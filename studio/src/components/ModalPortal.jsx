import { createPortal } from "react-dom";

/**
 * Render overlays on document.body so `position:fixed` uses the real viewport.
 * Auth modal works because it sits outside PlatformShell; in-page overlays must portal.
 * Ancestors with backdrop-filter (.yc-frame) otherwise trap fixed and "center" into the
 * middle of a tall frame — which looks like the dialog is glued to the bottom.
 */
export function ModalPortal({ children, open = true }) {
  if (!open || typeof document === "undefined") return null;
  return createPortal(children, document.body);
}

/** Full-viewport dimmed overlay — same centering model as AuthPage modal. */
export function ModalOverlay({
  children,
  onClose,
  className = "bg-[#09101d]/80 backdrop-blur-sm",
  zClass = "z-[200]",
  role = "presentation",
}) {
  return (
    <ModalPortal>
      <div
        className={`fixed inset-0 flex items-center justify-center overflow-y-auto px-4 py-8 ${zClass} ${className}`}
        style={{
          position: "fixed",
          inset: 0,
          width: "100vw",
          height: "100dvh",
          maxHeight: "100vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          margin: 0,
        }}
        role={role}
        aria-modal={role === "dialog" ? true : undefined}
        onMouseDown={(event) => {
          if (event.target === event.currentTarget) onClose?.();
        }}
      >
        {children}
      </div>
    </ModalPortal>
  );
}
