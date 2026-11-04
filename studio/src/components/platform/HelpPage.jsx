import { PageShell } from "./PageShell";

import { tr, useLocale } from "../../lib/i18n";

export function HelpPage({ config, onNeedKeys, onNavigate }) {
  useLocale();
  const sections = config?.helpSections || [];
  const page = config?.pages?.help || {};
  const extras = [
    {
      title: tr("ui_help_my_assets"),
      body: tr("ui_help_the_assets_tab_uploads_images_video"),
    },
    {
      title: tr("ui_help_viral_content_plaza"),
      body: tr("ui_help_start_with_the_beat_structure_of"),
    },
    {
      title: tr("ui_help_creation_hub_agent"),
      body: tr("ui_help_the_creation_hub_groups_tools_into"),
    },
    {
      title: tr("ui_help_works_channel_canvas"),
      body: tr("ui_help_the_works_channel_collects_exported_cuts"),
    },
  ];
  const all = [...sections, ...extras];

  return (
    <PageShell
      eyebrow={page.eyebrow || "Help"}
      title={page.title || tr("ui_help_help_center")}
      description={page.description || tr("ui_help_how_to_use_the_film_workshop")}
      actions={
        <div className="flex flex-wrap gap-2">
          <button type="button" className="btn-secondary" onClick={() => onNeedKeys?.()}>{tr("ui_help_set_up_keys")}</button>
          <button type="button" className="btn-secondary" onClick={() => onNavigate?.("assets")}>{tr("ui_help_my_assets")}</button>
        </div>
      }
    >
      <div className="space-y-3">
        {all.map((section) => (
          <article key={section.title} className="panel p-5">
            <h3 className="text-base font-semibold">{section.title}</h3>
            <p className="mt-2 text-sm leading-7 text-[var(--muted)]">{section.body}</p>
          </article>
        ))}
      </div>
    </PageShell>
  );
}
