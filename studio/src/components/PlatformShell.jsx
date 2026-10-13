import { Clapperboard, LogOut, Moon } from "lucide-react";
import { resolveIcon } from "../lib/icons";
import { useLocale } from "../lib/i18n";

export function PlatformShell({
  active = "workshop",
  brand,
  tagline,
  config,
  user,
  onNavigate,
  onLogout,
  children,
}) {
  const { t, locale, setLocale } = useLocale();
  const caps = config?.capabilities || {};
  const ready = caps.configured ?? 0;
  const nav = config?.nav?.length ? config.nav : [];
  const displayBrand = brand || config?.brand || t("app.brand");
  const displayTagline = tagline || config?.tagline || t("app.tagline");
  const displayName = user?.username || t("nav.localWorkshop");

  return (
    <div className="flex min-h-screen bg-[var(--stage)] text-[var(--ink)]">
      <aside className="hidden w-[220px] shrink-0 flex-col border-r border-[var(--line)] bg-[#0a0b10] md:flex">
        <div className="px-4 py-5">
          <div className="flex items-center gap-2.5">
            <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-[var(--gradient)] text-white shadow-[0_0_24px_rgba(124,108,255,.35)]">
              <Clapperboard className="h-4 w-4" />
            </span>
            <div>
              <div className="text-sm font-semibold tracking-wide">{displayBrand}</div>
              <div className="text-[10px] text-[var(--muted)]">{displayTagline}</div>
            </div>
          </div>
          <div className="mt-3 flex rounded-lg border border-[var(--line)] p-0.5 text-[10px]">
            <button
              type="button"
              className={`flex-1 rounded-md px-2 py-1 ${locale === "zh" ? "bg-white/10 text-white" : "text-white/45"}`}
              onClick={() => setLocale("zh")}
            >
              {t("lang.zh")}
            </button>
            <button
              type="button"
              className={`flex-1 rounded-md px-2 py-1 ${locale === "en" ? "bg-white/10 text-white" : "text-white/45"}`}
              onClick={() => setLocale("en")}
            >
              {t("lang.en")}
            </button>
          </div>
        </div>

        <nav className="scrollbar-thin flex-1 space-y-0.5 overflow-y-auto px-2 pb-4">
          {nav.map((item) => {
            const Icon = resolveIcon(item.icon);
            const selected = active === item.id;
            return (
              <button
                key={item.id}
                type="button"
                className={`flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm transition ${
                  selected ? "nav-active text-white" : "text-white/70 hover:bg-white/[.04] hover:text-white"
                }`}
                onClick={() => onNavigate?.(item.id, item)}
              >
                <Icon className={`h-4 w-4 shrink-0 ${selected ? "text-[#b7acff]" : ""}`} />
                <span className="min-w-0 flex-1 truncate">{item.label}</span>
              </button>
            );
          })}
        </nav>

        <div className="border-t border-[var(--line)] p-3">
          <button
            type="button"
            className="mb-2 flex w-full items-center gap-2 rounded-xl border border-[var(--line)] bg-white/[.03] px-3 py-2.5 text-left transition hover:border-[#7c6cff]/40"
            onClick={() => onNavigate?.("keys")}
          >
            <span className="flex h-8 w-8 items-center justify-center overflow-hidden rounded-full bg-[var(--gradient)] text-xs font-bold">
              {user?.avatar ? <img src={user.avatar} alt="" className="h-full w-full object-cover" /> : "OM"}
            </span>
            <div className="min-w-0 flex-1">
              <div className="truncate text-xs font-semibold">{displayName}</div>
              <div className="text-[10px] text-[var(--muted)]">{t("nav.keysReady", { ready })}</div>
            </div>
            <Moon className="h-3.5 w-3.5 text-white/35" />
          </button>
          {user ? (
            <button
              type="button"
              className="mb-3 flex w-full items-center justify-center gap-1.5 rounded-lg px-2 py-1.5 text-[11px] text-white/45 hover:bg-white/[.04] hover:text-white"
              onClick={() => onLogout?.()}
            >
              <LogOut className="h-3 w-3" />
              {t("auth.logout")}
            </button>
          ) : null}
          <p className="px-1 text-[10px] leading-5 text-white/30">{t("nav.footer")}</p>
        </div>
      </aside>

      <div className="min-w-0 flex-1">{children}</div>
    </div>
  );
}
