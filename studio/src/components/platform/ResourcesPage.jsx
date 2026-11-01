import { useMemo, useState } from "react";
import { resolveIcon } from "../../lib/icons";
import { useLocale } from "../../lib/i18n";
import { PageShell } from "./PageShell";

export function ResourcesPage({ config, onNavigate }) {
  const { t } = useLocale();
  const links = config?.resources || [];
  const page = config?.pages?.resources || {};
  const [group, setGroup] = useState("all");

  const groups = useMemo(
    () => [
      { id: "all", label: t("resources_filter_all") },
      { id: "docs", label: t("resources_filter_docs") },
      { id: "studio", label: t("resources_filter_studio") },
      { id: "providers", label: t("resources_filter_providers") },
    ],
    [t],
  );

  const visible = useMemo(() => {
    if (group === "all") return links;
    return links.filter((l) => (l.group || "docs") === group);
  }, [links, group]);

  return (
    <PageShell
      eyebrow={page.eyebrow || "Resources"}
      title={page.title || t("resources_page_title")}
      description={page.description || t("resources_page_description")}
    >
      <div className="mb-4 flex flex-wrap gap-2">
        {groups.map((g) => (
          <button key={g.id} type="button" className={group === g.id ? "chip-active" : "chip"} onClick={() => setGroup(g.id)}>
            {g.label}
          </button>
        ))}
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        {visible.map((link) => {
          const Icon = resolveIcon(link.icon);
          return (
            <a
              key={link.title}
              href={link.external ? link.href : undefined}
              target={link.external ? "_blank" : undefined}
              rel={link.external ? "noreferrer" : undefined}
              className="panel flex items-start gap-4 p-5 transition hover:-translate-y-0.5 hover:border-[#7c6cff]/45"
              onClick={(e) => {
                if (!link.external) {
                  e.preventDefault();
                  onNavigate?.(link.href || "help");
                }
              }}
            >
              <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-white/[.06]">
                <Icon className="h-5 w-5 text-[#a78bfa]" />
              </span>
              <span>
                <strong className="block">{link.title}</strong>
                <span className="mt-1 block text-sm text-[var(--muted)]">{link.desc}</span>
              </span>
            </a>
          );
        })}
      </div>
    </PageShell>
  );
}
