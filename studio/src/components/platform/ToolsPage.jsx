import { resolveIcon } from "../../lib/icons";
import { PageShell } from "./PageShell";

export function ToolsPage({ config, onOpenTool }) {
  const tools = config?.tools || [];
  const page = config?.pages?.tools || {};

  return (
    <PageShell
      eyebrow={page.eyebrow || "Creation center"}
      title={page.title || "创作中心"}
      description={page.description || "多模态影视工具入口。"}
    >
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {tools.map((tool) => {
          const Icon = resolveIcon(tool.icon);
          return (
            <button
              key={tool.id}
              type="button"
              className="panel group p-5 text-left transition hover:-translate-y-0.5 hover:border-[#7c6cff]/45"
              onClick={() => onOpenTool?.(tool)}
            >
              <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-[var(--gradient)] text-white">
                <Icon className="h-5 w-5" />
              </span>
              <strong className="mt-4 block text-base">{tool.title}</strong>
              <p className="mt-1 text-sm text-[var(--muted)]">{tool.desc}</p>
            </button>
          );
        })}
      </div>
    </PageShell>
  );
}
