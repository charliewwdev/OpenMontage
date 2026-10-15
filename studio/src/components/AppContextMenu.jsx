import { useEffect, useMemo, useRef, useState } from "react";
import {
  Clapperboard,
  ClipboardPaste,
  Copy,
  ExternalLink,
  HelpCircle,
  KeyRound,
  LayoutDashboard,
  PanelLeft,
  RefreshCw,
  Sparkles,
  Tv,
} from "lucide-react";
import { useLocale } from "../lib/i18n";

const QUICK_NAV = [
  { id: "tv", icon: Tv },
  { id: "agent", icon: Sparkles },
  { id: "workshop", icon: Clapperboard },
  { id: "keys", icon: KeyRound },
  { id: "help", icon: HelpCircle },
];

function isEditableTarget(el) {
  if (!el || !(el instanceof Element)) return false;
  const tag = el.tagName;
  if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return true;
  if (el.isContentEditable) return true;
  return Boolean(el.closest("input, textarea, select, [contenteditable='true']"));
}

/**
 * Replaces the browser context menu with in-app shortcuts.
 * DevTools / view-source are still reachable via browser chrome — this is UX only.
 */
export function AppContextMenu({ onNavigate, sidebarCollapsed, onToggleSidebar }) {
  const { t } = useLocale();
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState({ x: 0, y: 0 });
  const [selection, setSelection] = useState("");
  const [editable, setEditable] = useState(false);
  const menuRef = useRef(null);
  const targetRef = useRef(null);

  const items = useMemo(() => {
    const list = [];
    if (selection) {
      list.push({ id: "copy-selection", label: t("shell_menu_copy_selection"), icon: Copy });
    }
    if (editable) {
      list.push({ id: "paste", label: t("shell_menu_paste"), icon: ClipboardPaste });
    }
    list.push({ id: "copy-url", label: t("shell_menu_copy_url"), icon: ExternalLink });
    list.push({ id: "reload", label: t("shell_menu_reload"), icon: RefreshCw });
    list.push({ id: "sep-1", sep: true });
    if (typeof onToggleSidebar === "function") {
      list.push({
        id: "toggle-sidebar",
        label: sidebarCollapsed ? t("shell_menu_toggle_sidebar_expand") : t("shell_menu_toggle_sidebar_collapse"),
        icon: PanelLeft,
      });
    }
    list.push({ id: "home", label: t("shell_menu_home"), icon: LayoutDashboard });
    for (const nav of QUICK_NAV) {
      list.push({
        id: `nav:${nav.id}`,
        label: t(`shell_nav_${nav.id}_label`),
        icon: nav.icon,
      });
    }
    return list;
  }, [selection, editable, sidebarCollapsed, onToggleSidebar, t]);

  useEffect(() => {
    const onContextMenu = (event) => {
      event.preventDefault();
      event.stopPropagation();
      const sel = String(window.getSelection?.()?.toString?.() || "").trim();
      setSelection(sel.slice(0, 500));
      setEditable(isEditableTarget(event.target));
      targetRef.current = event.target;
      const pad = 8;
      const mw = 220;
      const mh = 360;
      const x = Math.min(event.clientX, window.innerWidth - mw - pad);
      const y = Math.min(event.clientY, window.innerHeight - mh - pad);
      setPos({ x: Math.max(pad, x), y: Math.max(pad, y) });
      setOpen(true);
    };
    const onClose = () => setOpen(false);
    const onKey = (event) => {
      if (event.key === "Escape") setOpen(false);
    };
    window.addEventListener("contextmenu", onContextMenu, true);
    window.addEventListener("click", onClose, true);
    window.addEventListener("scroll", onClose, true);
    window.addEventListener("keydown", onKey, true);
    return () => {
      window.removeEventListener("contextmenu", onContextMenu, true);
      window.removeEventListener("click", onClose, true);
      window.removeEventListener("scroll", onClose, true);
      window.removeEventListener("keydown", onKey, true);
    };
  }, []);

  useEffect(() => {
    if (!open || !menuRef.current) return;
    const rect = menuRef.current.getBoundingClientRect();
    let { x, y } = pos;
    if (x + rect.width > window.innerWidth - 8) x = window.innerWidth - rect.width - 8;
    if (y + rect.height > window.innerHeight - 8) y = window.innerHeight - rect.height - 8;
    if (x !== pos.x || y !== pos.y) setPos({ x, y });
  }, [open, pos, items.length]);

  const run = async (id) => {
    setOpen(false);
    if (id === "copy-selection" && selection) {
      try {
        await navigator.clipboard.writeText(selection);
      } catch {
        /* ignore */
      }
      return;
    }
    if (id === "paste") {
      try {
        const text = await navigator.clipboard.readText();
        const el = targetRef.current;
        if (el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA")) {
          const input = el;
          const start = input.selectionStart ?? input.value.length;
          const end = input.selectionEnd ?? input.value.length;
          const next = `${input.value.slice(0, start)}${text}${input.value.slice(end)}`;
          const proto = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value")
            || Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, "value");
          proto?.set?.call(input, next);
          input.dispatchEvent(new Event("input", { bubbles: true }));
          const caret = start + text.length;
          input.setSelectionRange?.(caret, caret);
          input.focus?.();
        } else if (el?.isContentEditable) {
          document.execCommand?.("insertText", false, text);
        }
      } catch {
        /* clipboard permission may be denied */
      }
      return;
    }
    if (id === "copy-url") {
      try {
        await navigator.clipboard.writeText(window.location.href);
      } catch {
        /* ignore */
      }
      return;
    }
    if (id === "reload") {
      window.location.reload();
      return;
    }
    if (id === "toggle-sidebar") {
      onToggleSidebar?.();
      return;
    }
    if (id === "home") {
      onNavigate?.("workshop");
      return;
    }
    if (id.startsWith("nav:")) {
      onNavigate?.(id.slice(4));
    }
  };

  if (!open) return null;

  return (
    <div
      ref={menuRef}
      role="menu"
      className="fixed z-[9999] min-w-[200px] overflow-hidden rounded-xl border border-white/10 bg-[#12141c]/98 py-1 text-sm text-white shadow-[0_16px_48px_rgba(0,0,0,.55)] backdrop-blur"
      style={{ left: pos.x, top: pos.y }}
      onClick={(e) => e.stopPropagation()}
      onContextMenu={(e) => e.preventDefault()}
    >
      <div className="border-b border-white/8 px-3 py-1.5 text-[10px] uppercase tracking-wide text-white/35">
        {editable ? t("shell_menu_title_editable") : t("shell_menu_title")}
      </div>
      {items.map((item) => {
        if (item.sep) {
          return <div key={item.id} className="my-1 border-t border-white/8" />;
        }
        const Icon = item.icon;
        return (
          <button
            key={item.id}
            type="button"
            role="menuitem"
            className="flex w-full items-center gap-2.5 px-3 py-2 text-left text-white/80 hover:bg-[#7c6cff]/20 hover:text-white"
            onClick={() => void run(item.id)}
          >
            {Icon ? <Icon className="h-3.5 w-3.5 shrink-0 text-white/45" /> : null}
            <span className="truncate">{item.label}</span>
          </button>
        );
      })}
    </div>
  );
}
