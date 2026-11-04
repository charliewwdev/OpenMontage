import { useEffect, useMemo, useState } from "react";
import { Clapperboard, Loader2, Play, Search } from "lucide-react";
import { api } from "../../api";
import { toast } from "../../lib/toast";
import { PageShell } from "./PageShell";

import { tr, useLocale } from "../../lib/i18n";

export function TvPage({ onOpenProject }) {
  useLocale();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState("latest");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const data = await api("/api/platform/exports");
        if (!cancelled) setItems(data.exports || data.items || []);
      } catch (error) {
        if (!cancelled) toast.error(String(error.message || error));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const visible = useMemo(() => {
    const q = query.trim().toLocaleLowerCase("zh-CN");
    // Only playable successful finals (API already filters; keep client guard).
    let list = items.filter((item) => {
      const url = String(item.url || item.outputUrl || "").trim();
      if (!url) return false;
      if (!q) return true;
      return `${item.projectTitle} ${item.filename} ${item.episodeId} ${item.projectId}`
        .toLocaleLowerCase("zh-CN")
        .includes(q);
    });
    list = [...list].sort((a, b) => {
      const ta = new Date(a.updatedAt || 0).getTime();
      const tb = new Date(b.updatedAt || 0).getTime();
      return sort === "oldest" ? ta - tb : tb - ta;
    });
    return list;
  }, [items, query, sort]);

  return (
    <PageShell
      eyebrow="TV"
      title={tr("ui_tv_works_channel")}
      description={tr("ui_tv_shows_only_successfully_exported_cuts_with")}
    >
      <div className="mb-4 flex flex-wrap items-center gap-2">
        {[
          ["latest", tr("ui_tv_newest")],
          ["oldest", tr("ui_tv_oldest")],
        ].map(([value, label]) => (
          <button key={value} type="button" className={sort === value ? "chip-active" : "chip"} onClick={() => setSort(value)}>
            {label}
          </button>
        ))}
        <label className="relative min-w-[200px] flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--muted)]" />
          <input className="field !pl-10" value={query} onChange={(e) => setQuery(e.target.value)} placeholder={tr("ui_tv_search_cuts_or_projects")} />
        </label>
      </div>

      {loading ? (
        <div className="panel flex items-center justify-center gap-2 py-20 text-sm text-[var(--muted)]">
          <Loader2 className="h-4 w-4 animate-spin" />{" "}{tr("ui_tv_loading_cuts")}</div>
      ) : !visible.length ? (
        <div className="panel flex flex-col items-center justify-center gap-4 py-20 text-center">
          <Clapperboard className="h-8 w-8 text-[var(--muted)]" />
          <p className="text-sm text-[var(--muted)]">
            {items.length ? tr("ui_tv_no_matching_cuts") : tr("ui_tv_no_exported_cuts_yet_they_appear")}
          </p>
          <p className="max-w-md text-xs text-white/35">{tr("ui_tv_walk_the_welcome_project_through_storyboard")}</p>
        </div>
      ) : (
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {visible.map((item) => {
            const url = item.url || item.outputUrl || "";
            const key = `${item.projectId}-${item.filename || item.episodeId || url}`;
            return (
              <article key={key} className="panel overflow-hidden">
                <div className="flex aspect-video items-center justify-center bg-black/40">
                  {url ? (
                    <video src={url} className="h-full w-full object-cover" controls preload="metadata" />
                  ) : (
                    <Play className="h-8 w-8 text-white/40" />
                  )}
                </div>
                <div className="p-4">
                  <strong className="block truncate">{item.projectTitle || item.projectId}</strong>
                  <p className="mt-1 truncate text-xs text-[var(--muted)]">{item.filename || item.episodeId || tr("ui_tv_cut")}</p>
                  <button type="button" className="btn-secondary mt-3 w-full" onClick={() => onOpenProject?.(item.projectId)}>{tr("ui_tv_open_project")}</button>
                </div>
              </article>
            );
          })}
        </div>
      )}
    </PageShell>
  );
}
