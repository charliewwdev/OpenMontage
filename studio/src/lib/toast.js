let host = null;

function ensureHost() {
  if (host || typeof document === "undefined") return host;
  host = document.createElement("div");
  host.className = "fixed bottom-6 left-1/2 z-[90] flex w-[min(420px,92vw)] -translate-x-1/2 flex-col gap-2";
  document.body.appendChild(host);
  return host;
}

export function toast(message, kind = "info") {
  const root = ensureHost();
  if (!root) {
    window.alert(message);
    return;
  }
  const el = document.createElement("div");
  const colors =
    kind === "error"
      ? "border-[var(--danger)]/40 bg-[#2a1216] text-[#fca5a5]"
      : kind === "success"
        ? "border-[var(--ok)]/40 bg-[#0f241c] text-[#6ee7b7]"
        : "border-[var(--line-strong)] bg-[var(--panel)] text-[var(--ink)]";
  el.className = `rounded-xl border px-4 py-3 text-sm shadow-float ${colors}`;
  el.textContent = message;
  root.appendChild(el);
  setTimeout(() => {
    el.remove();
  }, 3200);
}

toast.error = (m) => toast(m, "error");
toast.success = (m) => toast(m, "success");
toast.info = (m) => toast(m, "info");
