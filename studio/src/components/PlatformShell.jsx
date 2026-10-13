import { Clapperboard, Moon } from "lucide-react";
import { resolveIcon } from "../lib/icons";

export function PlatformShell({ active = "workshop", brand, tagline, config, onNavigate, children }) {
  const caps = config?.capabilities || {};
  const ready = caps.configured ?? 0;
  const nav = config?.nav?.length ? config.nav : [];
  const displayBrand = brand || config?.brand || "OpenMontage";
  const displayTagline = tagline || config?.tagline || "影视工坊 · 本地生产";

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
            className="mb-3 flex w-full items-center gap-2 rounded-xl border border-[var(--line)] bg-white/[.03] px-3 py-2.5 text-left transition hover:border-[#7c6cff]/40"
            onClick={() => onNavigate?.("keys")}
          >
            <span className="flex h-8 w-8 items-center justify-center rounded-full bg-[var(--gradient)] text-xs font-bold">
              OM
            </span>
            <div className="min-w-0 flex-1">
              <div className="truncate text-xs font-semibold">本地工坊</div>
              <div className="text-[10px] text-[var(--muted)]">密钥 {ready}/3 · 点击配置</div>
            </div>
            <Moon className="h-3.5 w-3.5 text-white/35" />
          </button>
          <p className="px-1 text-[10px] leading-5 text-white/30">六步生产线已接通；侧栏模块均可进入。</p>
        </div>
      </aside>

      <div className="min-w-0 flex-1">{children}</div>
    </div>
  );
}
