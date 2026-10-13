import { useEffect, useState } from "react";
import { Clapperboard, Loader2, Play } from "lucide-react";
import { api } from "../../api";
import { toast } from "../../lib/toast";
import { PageShell } from "./PageShell";

export function TvPage({ onOpenProject }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);

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

  return (
    <PageShell eyebrow="TV" title="影视工坊 TV" description="汇总各项目已导出的成片，方便回看与继续剪辑。">
      {loading ? (
        <div className="panel flex items-center justify-center gap-2 py-20 text-sm text-[var(--muted)]">
          <Loader2 className="h-4 w-4 animate-spin" /> 加载成片…
        </div>
      ) : !items.length ? (
        <div className="panel flex flex-col items-center justify-center gap-3 py-20 text-center">
          <Clapperboard className="h-8 w-8 text-[var(--muted)]" />
          <p className="text-sm text-[var(--muted)]">还没有导出成片。完成剪辑步骤后会出现在这里。</p>
        </div>
      ) : (
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {items.map((item) => {
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
                  <p className="mt-1 truncate text-xs text-[var(--muted)]">
                    {item.filename || item.episodeId || "成片"}
                  </p>
                  <button
                    type="button"
                    className="btn-secondary mt-3 w-full"
                    onClick={() => onOpenProject?.(item.projectId)}
                  >
                    打开项目
                  </button>
                </div>
              </article>
            );
          })}
        </div>
      )}
    </PageShell>
  );
}
