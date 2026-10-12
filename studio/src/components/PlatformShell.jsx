import {
  Clapperboard,
  Compass,
  Film,
  LayoutGrid,
  Library,
  Sparkles,
  Wand2,
  Workflow,
} from "lucide-react";

const NAV = [
  { id: "workshop", label: "影视工坊", note: "剧本到成片", icon: Film, available: true },
  { id: "agent", label: "创作 Agent", note: "一句话出片", icon: Sparkles, available: false },
  { id: "tools", label: "创作中心", note: "多模态工具", icon: Wand2, available: false },
  { id: "canvas", label: "有彩画布", note: "节点无限画布", icon: Workflow, available: false },
  { id: "assets", label: "个人资产", note: "云端素材库", icon: Library, available: false },
  { id: "inspire", label: "灵感广场", note: "作品与模板", icon: Compass, available: false },
];

export function PlatformShell({ active = "workshop", onNavigate, children }) {
  return (
    <div className="flex min-h-screen bg-[var(--stage)]">
      <aside className="hidden w-[220px] shrink-0 flex-col border-r border-[var(--line)] bg-white md:flex">
        <div className="border-b border-[var(--line)] px-4 py-5">
          <div className="flex items-center gap-2">
            <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-[var(--navy)] text-[var(--projector)]">
              <Clapperboard className="h-4 w-4" />
            </span>
            <div>
              <div className="text-sm font-semibold">OpenMontage</div>
              <div className="text-[10px] text-[var(--muted)]">对齐有彩视界在线版</div>
            </div>
          </div>
        </div>
        <nav className="flex-1 space-y-1 p-2">
          {NAV.map((item) => {
            const Icon = item.icon;
            const selected = active === item.id;
            return (
              <button
                key={item.id}
                type="button"
                className={`flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left transition ${
                  selected
                    ? "bg-[var(--navy)] text-white"
                    : item.available
                      ? "text-[var(--ink)] hover:bg-[var(--panel-muted)]"
                      : "text-[var(--muted)] opacity-70 hover:bg-[var(--panel-muted)]"
                }`}
                onClick={() => onNavigate?.(item.id, item)}
              >
                <Icon className="h-4 w-4 shrink-0" />
                <span className="min-w-0 flex-1">
                  <span className="block text-sm font-medium">{item.label}</span>
                  <span className={`block text-[10px] ${selected ? "text-white/55" : "text-[var(--muted)]"}`}>
                    {item.available ? item.note : `${item.note} · 建设中`}
                  </span>
                </span>
                {!item.available ? (
                  <LayoutGrid className="h-3 w-3 opacity-40" />
                ) : null}
              </button>
            );
          })}
        </nav>
        <div className="border-t border-[var(--line)] p-3 text-[10px] leading-5 text-[var(--muted)]">
          影视工坊已对齐六步生产线。Agent / 画布 / 素材库 / 灵感广场按在线版信息架构铺开，能力逐步接入 OpenMontage 多模型工具。
        </div>
      </aside>
      <div className="min-w-0 flex-1">{children}</div>
    </div>
  );
}
