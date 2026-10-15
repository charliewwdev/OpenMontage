/**
 * Soft client-side deterrence only — DevTools / view-source cannot be truly blocked in a browser.
 * Shows a red console banner and intercepts common shortcuts + native context menu (handled elsewhere).
 */

const BANNER_SHOWN_KEY = "om.guard.banner.v1";

function paintConsoleBanner() {
  try {
    // eslint-disable-next-line no-console
    console.log(
      "%c停止 Stop",
      "color:#ff3b30;font-size:42px;font-weight:800;text-shadow:0 0 8px rgba(255,59,48,.35)",
    );
    // eslint-disable-next-line no-console
    console.log(
      "%c此为面向开发者的浏览器功能。\\n请勿在此粘贴不明代码，勿试图反编译或篡改 OpenMontage 前端。\\nThis is a browser feature for developers. Do not paste untrusted code or attempt to reverse-engineer the app.",
      "color:#ff3b30;font-size:13px;line-height:1.55;font-weight:600",
    );
    // eslint-disable-next-line no-console
    console.log(
      "%cUnauthorized inspection / decompilation is prohibited. Session activity may be audited.",
      "color:#ff6961;font-size:12px",
    );
  } catch {
    /* ignore */
  }
}

function isEditableTarget(el) {
  if (!el || !(el instanceof Element)) return false;
  const tag = el.tagName;
  if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return true;
  if (el.isContentEditable) return true;
  return Boolean(el.closest("input, textarea, select, [contenteditable='true']"));
}

function shouldBlockShortcut(event) {
  const key = event.key;
  const upper = key.length === 1 ? key.toUpperCase() : key;
  // F12
  if (key === "F12") return true;
  // Ctrl/Cmd + Shift + I/J/C
  if ((event.ctrlKey || event.metaKey) && event.shiftKey && ["I", "J", "C"].includes(upper)) return true;
  // Ctrl/Cmd + U (view source)
  if ((event.ctrlKey || event.metaKey) && !event.shiftKey && upper === "U") return true;
  // Ctrl/Cmd + S often used to save page source
  if ((event.ctrlKey || event.metaKey) && !event.shiftKey && upper === "S" && !isEditableTarget(event.target)) {
    return true;
  }
  return false;
}

export function installClientGuard() {
  if (typeof window === "undefined") return () => {};

  paintConsoleBanner();

  // Re-print when the console is opened (best-effort; not reliable across browsers).
  let bannerTimer = null;
  const bumpBanner = () => {
    try {
      if (sessionStorage.getItem(BANNER_SHOWN_KEY) === "1") return;
      sessionStorage.setItem(BANNER_SHOWN_KEY, "1");
    } catch {
      /* ignore */
    }
    paintConsoleBanner();
  };
  bannerTimer = window.setInterval(() => {
    const widthGap = Math.abs(window.outerWidth - window.innerWidth) > 160;
    const heightGap = Math.abs(window.outerHeight - window.innerHeight) > 160;
    if (widthGap || heightGap) bumpBanner();
  }, 2500);

  const onKeyDown = (event) => {
    if (!shouldBlockShortcut(event)) return;
    event.preventDefault();
    event.stopPropagation();
    paintConsoleBanner();
  };

  window.addEventListener("keydown", onKeyDown, true);

  return () => {
    window.removeEventListener("keydown", onKeyDown, true);
    if (bannerTimer) window.clearInterval(bannerTimer);
  };
}
