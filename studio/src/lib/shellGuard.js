/**
 * Best-effort UI deterrents for casual inspection.
 * Not real anti-tamper — anyone can bypass via browser settings.
 */

const WARNING_STYLE_TITLE = "color:#ef4444;font-size:42px;font-weight:800;font-family:sans-serif;";
const WARNING_STYLE_BODY = "color:#fca5a5;font-size:14px;line-height:1.6;font-family:sans-serif;";

export function printConsoleWarning() {
  try {
    // eslint-disable-next-line no-console
    console.log("%c⏹ 停止！", WARNING_STYLE_TITLE);
    // eslint-disable-next-line no-console
    console.log(
      "%c这是浏览器面向开发者的功能区。\n请勿在此粘贴或运行不明代码，也请勿试图反编译 / 抓取本站点资产。\n未经授权的抓取、逆向或滥用可能导致账号与访问权限被限制。",
      WARNING_STYLE_BODY,
    );
    // eslint-disable-next-line no-console
    console.log("%cOpenMontage · 请关闭开发者工具后继续创作。", "color:#a78bfa;font-size:12px;");
  } catch {
    /* ignore */
  }
}

function isTypingTarget(el) {
  if (!el || !(el instanceof Element)) return false;
  const tag = el.tagName;
  if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return true;
  if (el.isContentEditable) return true;
  return Boolean(el.closest("input, textarea, select, [contenteditable='true']"));
}

/**
 * Block common DevTools / view-source shortcuts (easily bypassed).
 * Returns a cleanup function.
 */
export function installShortcutBlocker() {
  const onKeyDown = (event) => {
    if (isTypingTarget(event.target)) return;
    const key = String(event.key || "").toLowerCase();
    const ctrl = event.ctrlKey || event.metaKey;
    const shift = event.shiftKey;
    const blocked =
      key === "f12" ||
      (ctrl && shift && (key === "i" || key === "j" || key === "c" || key === "k")) ||
      (ctrl && key === "u");
    if (!blocked) return;
    event.preventDefault();
    event.stopPropagation();
    printConsoleWarning();
  };
  window.addEventListener("keydown", onKeyDown, true);
  return () => window.removeEventListener("keydown", onKeyDown, true);
}

export function installShellGuard() {
  printConsoleWarning();
  const stopShortcuts = installShortcutBlocker();
  // Re-print if someone clears console (best-effort; not reliable).
  let timer = window.setInterval(() => {
    try {
      if (typeof console.clear === "function") {
        /* leave console alone periodically — only warn once at boot */
      }
    } catch {
      /* ignore */
    }
  }, 60_000);
  return () => {
    stopShortcuts();
    window.clearInterval(timer);
  };
}
