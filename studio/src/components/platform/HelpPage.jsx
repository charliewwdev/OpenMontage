import { PageShell } from "./PageShell";

export function HelpPage({ config, onNeedKeys }) {
  const sections = config?.helpSections || [];
  const page = config?.pages?.help || {};

  return (
    <PageShell
      eyebrow={page.eyebrow || "Help"}
      title={page.title || "帮助中心"}
      description={page.description || "影视工坊使用说明与常见问题。"}
      actions={
        <button type="button" className="btn-secondary" onClick={() => onNeedKeys?.()}>
          配置密钥
        </button>
      }
    >
      <div className="space-y-3">
        {sections.map((section) => (
          <article key={section.title} className="panel p-5">
            <h3 className="text-base font-semibold">{section.title}</h3>
            <p className="mt-2 text-sm leading-7 text-[var(--muted)]">{section.body}</p>
          </article>
        ))}
      </div>
    </PageShell>
  );
}
