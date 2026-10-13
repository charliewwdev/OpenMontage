import { useEffect, useMemo, useState } from "react";
import { Copy, ExternalLink, Lightbulb, RefreshCw } from "lucide-react";
import { api } from "../../api";
import { useLocale } from "../../lib/i18n";
import { toast } from "../../lib/toast";
import { PageShell } from "./PageShell";

export function InspirePage({ config, onUsePrompt }) {
  const { t } = useLocale();
  const prompts = config?.inspirePrompts || [];
  const page = config?.pages?.inspire || {};
  const [filter, setFilter] = useState("全部");
  const [pins, setPins] = useState([]);
  const [pinSource, setPinSource] = useState("");
  const [pinLoading, setPinLoading] = useState(false);

  const tags = useMemo(() => {
    const all = t("inspire.all");
    return [all, ...new Set(prompts.map((p) => p.tag))];
  }, [prompts, t]);

  const allLabel = t("inspire.all");
  const list = filter === allLabel || filter === "全部" ? prompts : prompts.filter((p) => p.tag === filter);

  const loadPins = async (refresh = false) => {
    setPinLoading(true);
    try {
      const data = await api(`/api/inspire/pins?limit=24${refresh ? "&refresh=true" : ""}`);
      setPins(data.items || []);
      setPinSource(data.source || "");
    } catch (err) {
      toast.error(String(err.message || err));
    } finally {
      setPinLoading(false);
    }
  };

  useEffect(() => {
    void loadPins(false);
  }, []);

  return (
    <PageShell
      eyebrow={page.eyebrow || "Inspiration"}
      title={page.title || "灵感广场"}
      description={page.description || "精选短剧开篇点子。"}
    >
      <div className="mb-8">
        <div className="mb-3 flex items-center justify-between gap-3">
          <div>
            <div className="text-sm font-semibold text-white">{t("inspire.productImages")}</div>
            <div className="text-xs text-white/40">
              {t("inspire.fromPinterest")}
              {pinSource ? ` · ${pinSource}` : ""}
            </div>
          </div>
          <button
            type="button"
            className="btn-secondary !min-h-9 !px-3"
            disabled={pinLoading}
            onClick={() => void loadPins(true)}
          >
            <RefreshCw className={`h-3.5 w-3.5 ${pinLoading ? "animate-spin" : ""}`} />
            {t("common.retry")}
          </button>
        </div>
        <div className="columns-2 gap-3 md:columns-3 xl:columns-4">
          {pins.map((pin) => (
            <a
              key={pin.id}
              href={pin.link || "https://www.pinterest.com/"}
              target="_blank"
              rel="noreferrer"
              className="mb-3 block break-inside-avoid overflow-hidden rounded-2xl border border-[var(--line)] bg-white/[.03] transition hover:border-[#7c6cff]/45"
            >
              <img src={pin.imageUrl} alt={pin.title || "pin"} className="w-full object-cover" loading="lazy" />
              <div className="flex items-start justify-between gap-2 px-3 py-2">
                <div className="min-w-0">
                  <div className="truncate text-xs text-white/80">{pin.title || "Pin"}</div>
                  <div className="truncate text-[10px] text-white/35">{pin.board}</div>
                </div>
                <ExternalLink className="mt-0.5 h-3 w-3 shrink-0 text-white/35" />
              </div>
            </a>
          ))}
        </div>
        {!pinLoading && !pins.length ? (
          <p className="text-sm text-white/40">{t("common.error")}</p>
        ) : null}
      </div>

      <div className="mb-4 flex flex-wrap gap-2">
        {tags.map((tag) => (
          <button
            key={tag}
            type="button"
            className={filter === tag ? "btn-primary !min-h-9 !px-3" : "btn-secondary !min-h-9 !px-3"}
            onClick={() => setFilter(tag)}
          >
            {tag}
          </button>
        ))}
      </div>
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {list.map((item) => (
          <article key={item.text} className="panel flex flex-col p-5">
            <span className="label">{item.tag}</span>
            <p className="mt-2 flex-1 text-sm leading-7 text-white/85">{item.text}</p>
            <div className="mt-4 flex gap-2">
              <button
                type="button"
                className="btn-secondary flex-1"
                onClick={async () => {
                  await navigator.clipboard.writeText(item.text);
                  toast.success(t("inspire.copied"));
                }}
              >
                <Copy className="h-3.5 w-3.5" /> {t("inspire.copy")}
              </button>
              <button type="button" className="btn-primary flex-1" onClick={() => onUsePrompt?.(item.text)}>
                <Lightbulb className="h-3.5 w-3.5" /> {t("inspire.create")}
              </button>
            </div>
          </article>
        ))}
      </div>
    </PageShell>
  );
}
