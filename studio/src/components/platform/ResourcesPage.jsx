import { useMemo, useState } from "react";
import { resolveIcon } from "../../lib/icons";
import { PageShell } from "./PageShell";

const GROUPS = [
  { id: "all", label: "全部" },
  { id: "docs", label: "文档" },
  { id: "studio", label: "站内入口" },
  { id: "providers", label: "模型与工具" },
];

export function ResourcesPage({ config, onNavigate }) {
  const links = config?.resources || [];
  const page = config?.pages?.resources || {};
  const [group, setGroup] = useState("all");

  const visible = useMemo(() => {
    if (group === "all") return links;
    return links.filter((l) => (l.group || "docs") === group);
  }, [links, group]);

  return (
    <PageShell
      eyebrow={page.eyebrow || "Resources"}
      title={page.title || "资源导航"}
      description={page.description || "文档、站内入口、模型控制台与制作参考。"}
    >
      <div className="mb-2.5 flex flex-wrap gap-1.5">
        {GROUPS.map((g) => (
          <button key={g.id} type="button" className={group === g.id ? "chip-active" : "chip"} onClick={() => setGroup(g.id)}>
            {g.label}
          </button>
        ))}
      </div>
      <div className="grid gap-2 md:grid-cols-2">
        {visible.map((link) => {
          const Icon = resolveIcon(link.icon);
          return (
            <a
              key={link.title}
              href={link.external ? link.href : undefined}
              target={link.external ? "_blank" : undefined}
              rel={link.external ? "noreferrer" : undefined}
              className="panel flex items-start gap-3 p-3 transition hover:-translate-y-0.5 hover:border-[#7c6cff]/45"
              onClick={(e) => {
                if (!link.external) {
                  e.preventDefault();
                  onNavigate?.(link.href || "help");
                }
              }}
            >
              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-white/[.06]">
                <Icon className="h-4 w-4 text-[#a78bfa]" />
              </span>
              <span>
                <strong className="block text-[13px]">{link.title}</strong>
                <span className="mt-0.5 block text-[12px] text-[var(--muted)]">{link.desc}</span>
              </span>
            </a>
          );
        })}
      </div>
    </PageShell>
  );
}
