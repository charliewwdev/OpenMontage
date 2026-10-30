import { useEffect, useMemo, useState } from "react";
import { ChevronDown, LogOut, Moon, PanelLeftClose, PanelLeftOpen, Sun } from "lucide-react";
import { api } from "../api";
import { resolveIcon } from "../lib/icons";
import { useLocale } from "../lib/i18n";

const THEME_KEY = "om.theme.v1";
const NAV_COLLAPSE_KEY = "om.nav.collapsed.v1";
const NAV_SECTIONS_KEY = "om.nav.sections.v1";

const NAV_GROUP_ORDER = ["stage", "create", "assets", "system"];
const NAV_GROUP_DEFAULT_OPEN = {
  stage: true,
  create: false,
  assets: true,
  system: false,
};

function readTheme() {
  try {
    return localStorage.getItem(THEME_KEY) === "light" ? "light" : "dark";
  } catch {
    return "dark";
  }
}

function readCollapsed() {
  try {
    return localStorage.getItem(NAV_COLLAPSE_KEY) === "1";
  } catch {
    return false;
  }
}

function readSectionOpen() {
  try {
    const raw = localStorage.getItem(NAV_SECTIONS_KEY);
    if (!raw) return { ...NAV_GROUP_DEFAULT_OPEN };
    return { ...NAV_GROUP_DEFAULT_OPEN, ...JSON.parse(raw) };
  } catch {
    return { ...NAV_GROUP_DEFAULT_OPEN };
  }
}

function applyTheme(theme) {
  if (typeof document === "undefined") return;
  document.documentElement.setAttribute("data-theme", theme);
  try {
    localStorage.setItem(THEME_KEY, theme);
  } catch {
    /* ignore */
  }
}

function fmtUsd(n) {
  const v = Number(n) || 0;
  if (v < 0.01 && v > 0) return `$${v.toFixed(4)}`;
  return `$${v.toFixed(2)}`;
}

function MiniSpark({ values = [] }) {
  const pts = values.length ? values : [0, 0, 0, 0];
  const max = Math.max(1, ...pts);
  const w = 44;
  const h = 16;
  const d = pts
    .map((v, i) => {
      const x = (i / Math.max(1, pts.length - 1)) * w;
      const y = h - (v / max) * (h - 2) - 1;
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)} ${y.toFixed(1)}`;
    })
    .join(" ");
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} className="shrink-0 opacity-80" aria-hidden>
      <path d={d} fill="none" stroke="var(--accent-2)" strokeWidth="1.6" strokeLinejoin="round" />
    </svg>
  );
}

function groupNavItems(nav) {
  const buckets = Object.fromEntries(NAV_GROUP_ORDER.map((id) => [id, []]));
  for (const item of nav) {
    const group = NAV_GROUP_ORDER.includes(item.group) ? item.group : "system";
    buckets[group].push(item);
  }
  return NAV_GROUP_ORDER.map((id) => ({ id, items: buckets[id] })).filter((g) => g.items.length);
}

export function PlatformShell({
  active = "workshop",
  brand,
  tagline,
  config,
  user,
  onNavigate,
  onLogout,
  onLogin,
  immersive = false,
  collapsed: collapsedProp,
  onCollapsedChange,
  children,
}) {
  const { t, locale, setLocale } = useLocale();
  const caps = config?.capabilities || {};
  const ready = caps.configured ?? 0;
  const nav = config?.nav?.length ? config.nav : [];
  const displayBrand = brand || t("shell_brand_name");
  const displayTagline = tagline || t("shell_brand_tagline");
  const displayName = user?.username || t("auth_page_guest");
  const [usageToday, setUsageToday] = useState(null);
  const [creditsBalance, setCreditsBalance] = useState(null);
  const [theme, setTheme] = useState(() => readTheme());
  const [collapsedLocal, setCollapsedLocal] = useState(() => readCollapsed());
  const [sectionOpen, setSectionOpen] = useState(() => readSectionOpen());
  const collapsed = typeof collapsedProp === "boolean" ? collapsedProp : collapsedLocal;

  const setCollapsed = (next) => {
    const value = typeof next === "function" ? next(collapsed) : Boolean(next);
    if (typeof collapsedProp !== "boolean") setCollapsedLocal(value);
    onCollapsedChange?.(value);
    try {
      localStorage.setItem(NAV_COLLAPSE_KEY, value ? "1" : "0");
    } catch {
      /* ignore */
    }
  };

  const navLabel = (item) => t(`shell_nav_${item.id}_label`, null, item.label || item.id);
  const groupLabel = (id) => t(`shell_nav_group_${id}`, null, id);

  const sections = useMemo(() => groupNavItems(nav), [nav]);

  useEffect(() => {
    const activeGroup = nav.find((item) => item.id === active)?.group;
    if (!activeGroup) return;
    setSectionOpen((prev) => {
      if (prev[activeGroup]) return prev;
      const next = { ...prev, [activeGroup]: true };
      try {
        localStorage.setItem(NAV_SECTIONS_KEY, JSON.stringify(next));
      } catch {
        /* ignore */
      }
      return next;
    });
  }, [active, nav]);

  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const [usage, credits] = await Promise.all([
          api("/api/settings/usage?range=today&log_limit=1"),
          api("/api/settings/credits"),
        ]);
        if (!cancelled) {
          setUsageToday(usage);
          setCreditsBalance(credits?.credits?.balance ?? 0);
        }
      } catch {
        /* sidebar summary is optional */
      }
    };
    void load();
    const id = window.setInterval(load, 60_000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, []);

  const toggleTheme = (event) => {
    event.stopPropagation();
    setTheme((current) => (current === "light" ? "dark" : "light"));
  };

  const toggleSection = (groupId) => {
    setSectionOpen((prev) => {
      const next = { ...prev, [groupId]: !prev[groupId] };
      try {
        localStorage.setItem(NAV_SECTIONS_KEY, JSON.stringify(next));
      } catch {
        /* ignore */
      }
      return next;
    });
  };

  const renderNavButton = (item) => {
    const Icon = resolveIcon(item.icon);
    const selected = active === item.id;
    const label = navLabel(item);
    const baseBtn = `flex w-full items-center rounded-lg text-left text-[12px] transition ${
      selected ? "nav-active text-white" : "text-white/70 hover:bg-white/[.04] hover:text-white"
    } ${collapsed ? "justify-center px-1.5 py-2" : "gap-2 px-2 py-1.5"}`;

    if (item.id === "usage") {
      const cost = usageToday?.hero?.cost_usd;
      const spark = usageToday?.trend?.cost_usd || usageToday?.trend?.requests || [];
      return (
        <button
          key={item.id}
          type="button"
          className={baseBtn}
          title={label}
          onClick={() => onNavigate?.(item.id, item)}
        >
          <Icon className={`h-3.5 w-3.5 shrink-0 ${selected ? "text-[var(--accent-soft)]" : ""}`} />
          {!collapsed ? (
            <>
              <span className="min-w-0 flex-1 truncate">{label}</span>
              <div className="flex shrink-0 flex-col items-end gap-0.5">
                <MiniSpark values={spark.slice(-8).map((v) => Number(v) || 0)} />
                <span className="text-[10px] tabular-nums text-white/50">
                  {t("shell_nav_usage_today", { cost: cost == null ? "—" : fmtUsd(cost) })}
                </span>
              </div>
            </>
          ) : null}
        </button>
      );
    }
    if (item.id === "credits") {
      return (
        <button
          key={item.id}
          type="button"
          className={baseBtn}
          title={label}
          onClick={() => onNavigate?.(item.id, item)}
        >
          <Icon className={`h-3.5 w-3.5 shrink-0 ${selected ? "text-[var(--accent-soft)]" : ""}`} />
          {!collapsed ? (
            <>
              <span className="min-w-0 flex-1 truncate">{label}</span>
              <span className="shrink-0 text-[10px] tabular-nums text-white/50">
                {creditsBalance == null ? "—" : creditsBalance}
              </span>
            </>
          ) : null}
        </button>
      );
    }
    return (
      <button
        key={item.id}
        type="button"
        className={baseBtn}
        title={label}
        onClick={() => onNavigate?.(item.id, item)}
      >
        <Icon className={`h-3.5 w-3.5 shrink-0 ${selected ? "text-[var(--accent-soft)]" : ""}`} />
        {!collapsed ? <span className="min-w-0 flex-1 truncate">{label}</span> : null}
      </button>
    );
  };

  return (
    <div className="flex min-h-screen bg-[var(--stage)] text-[var(--ink)]">
      <aside
        className={`sticky top-0 h-screen shrink-0 flex-col overflow-hidden border-r border-[var(--line)] bg-[#0a0b10] transition-[width] duration-200 ${
          collapsed ? "w-[56px]" : "w-[168px]"
        } ${immersive ? "hidden" : "hidden md:flex"}`}
      >
        <div className={`shrink-0 ${collapsed ? "px-1.5 py-2.5" : "px-2.5 py-3"}`}>
          <div className={`flex items-center ${collapsed ? "justify-center gap-1" : "gap-2"}`}>
            <span className="flex h-7 w-7 shrink-0 items-center justify-center overflow-hidden rounded-lg bg-[var(--gradient)] text-white shadow-[0_6px_16px_rgba(124,108,255,.22)]">
              <img src="/favicon.svg" alt="" className="h-7 w-7" width={28} height={28} />
            </span>
            {!collapsed ? (
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-1">
                  <div className="min-w-0 flex-1 truncate text-[12px] font-semibold tracking-wide">{displayBrand}</div>
                  <button
                    type="button"
                    className="shrink-0 rounded-md p-0.5 text-white/40 transition hover:bg-white/[.06] hover:text-white"
                    onClick={() => setCollapsed(true)}
                    title={t("shell_nav_collapse")}
                    aria-label={t("shell_nav_collapse")}
                  >
                    <PanelLeftClose className="h-3.5 w-3.5" />
                  </button>
                </div>
                <div className="truncate text-[10px] text-[var(--muted)]">{displayTagline}</div>
              </div>
            ) : (
              <button
                type="button"
                className="shrink-0 rounded-md p-0.5 text-white/45 transition hover:bg-white/[.06] hover:text-white"
                onClick={() => setCollapsed(false)}
                title={t("shell_nav_expand")}
                aria-label={t("shell_nav_expand")}
              >
                <PanelLeftOpen className="h-3.5 w-3.5" />
              </button>
            )}
          </div>
          {!collapsed ? (
            <div className="mt-2 flex rounded-md border border-[var(--line)] p-0.5 text-[10px]">
              <button
                type="button"
                className={`flex-1 rounded px-1.5 py-0.5 ${locale === "zh" ? "bg-white/10 text-white" : "text-white/45"}`}
                onClick={() => setLocale("zh")}
              >
                {t("shell_locale_zh")}
              </button>
              <button
                type="button"
                className={`flex-1 rounded px-1.5 py-0.5 ${locale === "en" ? "bg-white/10 text-white" : "text-white/45"}`}
                onClick={() => setLocale("en")}
              >
                {t("shell_locale_en")}
              </button>
            </div>
          ) : null}
        </div>

        <nav className={`scrollbar-thin min-h-0 flex-1 space-y-2 overflow-y-auto pb-2 ${collapsed ? "px-1" : "px-1.5"}`}>
          {sections.map((section) => {
            const open = collapsed || sectionOpen[section.id] !== false;
            return (
              <div key={section.id} className="space-y-0.5">
                {!collapsed ? (
                  <button
                    type="button"
                    className="flex w-full items-center gap-1 rounded-md px-2 py-1 text-[10px] font-medium uppercase tracking-wide text-white/35 transition hover:bg-white/[.04] hover:text-white/55"
                    onClick={() => toggleSection(section.id)}
                    aria-expanded={open}
                  >
                    <span className="min-w-0 flex-1 truncate text-left">{groupLabel(section.id)}</span>
                    <ChevronDown className={`h-3 w-3 shrink-0 transition ${open ? "" : "-rotate-90"}`} />
                  </button>
                ) : null}
                {open ? section.items.map((item) => renderNavButton(item)) : null}
              </div>
            );
          })}
        </nav>

        <div className={`shrink-0 border-t border-[var(--line)] bg-[#0a0b10] ${collapsed ? "p-1.5" : "p-2"}`}>
          <div className={`mb-1.5 flex w-full items-center rounded-lg border border-[var(--line)] bg-white/[.03] ${collapsed ? "justify-center px-1.5 py-1.5" : "gap-1.5 px-2 py-1.5"}`}>
            <button
              type="button"
              className={`flex min-w-0 flex-1 items-center text-left transition hover:opacity-95 ${collapsed ? "justify-center" : "gap-1.5"}`}
              onClick={() => onNavigate?.("keys")}
              title={displayName}
            >
              <span className="flex h-7 w-7 shrink-0 items-center justify-center overflow-hidden rounded-full bg-[var(--gradient)] text-[10px] font-bold">
                {user?.avatar ? <img src={user.avatar} alt="" className="h-full w-full object-cover" /> : "OM"}
              </span>
              {!collapsed ? (
                <div className="min-w-0 flex-1">
                  <div className="truncate text-[11px] font-semibold">{displayName}</div>
                  <div className="text-[10px] text-[var(--muted)]">{t("shell_nav_keys_ready", { ready })}</div>
                </div>
              ) : null}
            </button>
            {!collapsed ? (
              <button
                type="button"
                title={theme === "light" ? t("shell_nav_theme_to_dark") : t("shell_nav_theme_to_light")}
                className="shrink-0 rounded-lg p-1 text-white/45 hover:bg-white/[.06] hover:text-white"
                onClick={toggleTheme}
              >
                {theme === "light" ? <Sun className="h-3.5 w-3.5" /> : <Moon className="h-3.5 w-3.5" />}
              </button>
            ) : null}
          </div>
          {!collapsed ? (
            <>
              {user ? (
                <button
                  type="button"
                  className="mb-3 flex w-full items-center justify-center gap-1.5 rounded-lg px-2 py-1.5 text-[11px] text-white/45 hover:bg-white/[.04] hover:text-white"
                  onClick={() => onLogout?.()}
                >
                  <LogOut className="h-3 w-3" />
                  {t("auth_page_logout")}
                </button>
              ) : (
                <button
                  type="button"
                  className="btn-primary mb-3 w-full text-[12px]"
                  onClick={() => onLogin?.()}
                >
                  {t("auth_page_sign_in_cta")}
                </button>
              )}
              <p className="px-1 text-[10px] leading-5 text-white/30">{t("shell_nav_footer")}</p>
            </>
          ) : null}
        </div>
      </aside>

      <div className="min-w-0 flex-1">{children}</div>
    </div>
  );
}
