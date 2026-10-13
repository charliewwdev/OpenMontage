import {
  Clapperboard,
  Compass,
  Film,
  HelpCircle,
  Library,
  Sparkles,
  Tv,
  Trophy,
  Wand2,
  Workflow,
  FolderKanban,
  CreditCard,
  Gift,
  BookOpen,
  Moon,
} from "lucide-react";

const NAV = [
  { id: "assets", label: "个人资产", icon: FolderKanban, available: false },
  { id: "skills", label: "Skill 专家", icon: BookOpen, available: false },
  { id: "tools", label: "创作中心", icon: Wand2, available: false },
  { id: "agent", label: "创作 Agent", icon: Sparkles, available: false },
  { id: "workshop", label: "影视工坊", icon: Film, available: true },
  { id: "canvas", label: "无限画布", icon: Workflow, available: false },
  { id: "inspire", label: "灵感广场", icon: Compass, available: false },
  { id: "tv", label: "作品频道", icon: Tv, available: false },
  { id: "cup", label: "创作挑战", icon: Trophy, available: false },
  { id: "nav", label: "资源导航", icon: Library, available: false },
  { id: "help", label: "帮助中心", icon: HelpCircle, available: false },
  { id: "credits", label: "积分充值", icon: CreditCard, available: false },
  { id: "refer", label: "推荐计划", icon: Gift, available: false },
];

export function PlatformShell({ active = "workshop", brand = "OpenMontage", onNavigate, children }) {
  return (
    <div className="flex min-h-screen bg-[var(--stage)] text-[var(--ink)]">
      <aside className="hidden w-[220px] shrink-0 flex-col border-r border-[var(--line)] bg-[#0a0b10] md:flex">
        <div className="px-4 py-5">
          <div className="flex items-center gap-2.5">
            <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-[var(--gradient)] text-white shadow-[0_0_24px_rgba(124,108,255,.35)]">
              <Clapperboard className="h-4 w-4" />
            </span>
            <div>
              <div className="text-sm font-semibold tracking-wide">{brand}</div>
              <div className="text-[10px] text-[var(--muted)]">影视工坊 · 本地生产</div>
            </div>
          </div>
        </div>

        <nav className="scrollbar-thin flex-1 space-y-0.5 overflow-y-auto px-2 pb-4">
          {NAV.map((item) => {
            const Icon = item.icon;
            const selected = active === item.id;
            return (
              <button
                key={item.id}
                type="button"
                className={`flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm transition ${
                  selected
                    ? "nav-active text-white"
                    : item.available
                      ? "text-white/70 hover:bg-white/[.04] hover:text-white"
                      : "text-white/35 hover:bg-white/[.03] hover:text-white/55"
                }`}
                onClick={() => onNavigate?.(item.id, item)}
              >
                <Icon className={`h-4 w-4 shrink-0 ${selected ? "text-[#b7acff]" : ""}`} />
                <span className="min-w-0 flex-1 truncate">{item.label}</span>
                {!item.available ? (
                  <span className="rounded-md bg-white/[.06] px-1.5 py-0.5 text-[9px] text-white/35">soon</span>
                ) : null}
              </button>
            );
          })}
        </nav>

        <div className="border-t border-[var(--line)] p-3">
          <div className="mb-3 flex items-center gap-2 rounded-xl border border-[var(--line)] bg-white/[.03] px-3 py-2.5">
            <span className="flex h-8 w-8 items-center justify-center rounded-full bg-[var(--gradient)] text-xs font-bold">
              OM
            </span>
            <div className="min-w-0 flex-1">
              <div className="truncate text-xs font-semibold">本地工坊</div>
              <div className="text-[10px] text-[var(--muted)]">无积分 · 密钥自备</div>
            </div>
            <Moon className="h-3.5 w-3.5 text-white/35" />
          </div>
          <p className="px-1 text-[10px] leading-5 text-white/30">
            影视工坊已接通六步生产线；其余入口陆续开放。
          </p>
        </div>
      </aside>

      <div className="min-w-0 flex-1">{children}</div>
    </div>
  );
}
