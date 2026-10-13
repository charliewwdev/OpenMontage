import { useEffect, useMemo, useState } from "react";
import { Copy, ExternalLink, Lightbulb, Loader2, RefreshCw } from "lucide-react";
import { api } from "../../api";
import { useLocale } from "../../lib/i18n";
import { toast } from "../../lib/toast";
import { PageShell } from "./PageShell";

const DEFAULT_CATS = [
  { id: "all", label: "全部" },
  { id: "character", label: "角色" },
  { id: "scene", label: "场景" },
  { id: "prop", label: "道具" },
  { id: "style", label: "风格" },
  { id: "storyboard", label: "分镜" },
];

const PAGE_SIZE = 48;

export function InspirePage({ config, onUsePrompt }) {
  const { t } = useLocale();
  const prompts = config?.inspirePrompts || [];
  const page = config?.pages?.inspire || {};
  const [promptFilter, setPromptFilter] = useState("全部");
  const [category, setCategory] = useState("all");
  const [pins, setPins] = useState([]);
  const [categories, setCategories] = useState(DEFAULT_CATS);
  const [pinSource, setPinSource] = useState("");
  const [pinTotal, setPinTotal] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [nextOffset, setNextOffset] = useState(null);
  const [pinLoading, setPinLoading] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);

  const promptTags = useMemo(() => {
    const all = t("inspire.all");
    return [all, ...new Set(prompts.map((p) => p.tag))];
  }, [prompts, t]);

  const allLabel = t("inspire.all");
  const promptList =
    promptFilter === allLabel || promptFilter === "全部"
      ? prompts
      : prompts.filter((p) => p.tag === promptFilter);

  const loadPins = async ({ refresh = false, nextCategory = category, append = false, offset = 0 } = {}) => {
    if (append) setLoadingMore(true);
    else setPinLoading(true);
    try {
      const q = new URLSearchParams({
        limit: String(PAGE_SIZE),
        offset: String(offset),
        category: nextCategory || "all",
      });
      if (refresh) q.set("refresh", "true");
      const data = await api(`/api/inspire/pins?${q.toString()}`);
      const batch = data.items || [];
      setPins((prev) => (append ? [...prev, ...batch] : batch));
      setPinSource(data.source || "");
      setPinTotal(data.total || batch.length);
      setHasMore(Boolean(data.hasMore));
      setNextOffset(data.nextOffset ?? null);
      if (Array.isArray(data.categories) && data.categories.length) {
        setCategories(data.categories);
      } else if (config?.pinterest?.categories?.length) {
        setCategories(config.pinterest.categories);
      }
    } catch (err) {
      toast.error(String(err.message || err));
    } finally {
      setPinLoading(false);
      setLoadingMore(false);
    }
  };

  useEffect(() => {
    void loadPins({ refresh: false, nextCategory: "all", offset: 0 });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <PageShell
      eyebrow={page.eyebrow || "Inspiration"}
      title={page.title || "灵感广场"}
      description={page.description || "从 Pinterest 抓取的影视灵感素材，可按角色 / 场景 / 道具浏览，支持分页加载。"}
    >
      <div className="mb-8">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="text-sm font-semibold text-white">{t("inspire.productImages")}</div>
            <div className="text-xs text-white/40">
              {t("inspire.fromPinterest")}
              {pinSource ? ` · ${pinSource}` : ""}
              {pinTotal ? ` · 已显示 ${pins.length}/${pinTotal}` : ""}
            </div>
          </div>
          <button
            type="button"
            className="btn-secondary !min-h-9 !px-3"
            disabled={pinLoading}
            onClick={() => void loadPins({ refresh: true, nextCategory: category, offset: 0 })}
          >
            <RefreshCw className={`h-3.5 w-3.5 ${pinLoading ? "animate-spin" : ""}`} />
            {t("common.retry")}
          </button>
        </div>

        <div className="mb-4 flex flex-wrap gap-2">
          {categories.map((cat) => {
            const id = cat.id || cat;
            const label = cat.label || cat.id || cat;
            const selected = category === id;
            return (
              <button
                key={id}
                type="button"
                className={selected ? "btn-primary !min-h-9 !px-3" : "btn-secondary !min-h-9 !px-3"}
                onClick={() => {
                  setCategory(id);
                  void loadPins({ refresh: false, nextCategory: id, offset: 0 });
                }}
              >
                {label}
              </button>
            );
          })}
        </div>

        <div className="columns-2 gap-3 sm:columns-3 xl:columns-4 2xl:columns-5">
          {pins.map((pin) => (
            <a
              key={`${pin.id}-${pin.imageUrl}`}
              href={pin.link || "https://www.pinterest.com/"}
              target="_blank"
              rel="noreferrer"
              className="group mb-3 block break-inside-avoid overflow-hidden rounded-2xl border border-[var(--line)] bg-white/[.03] transition hover:border-[#7c6cff]/45"
            >
              <div className="relative overflow-hidden bg-black/20">
                <img
                  src={pin.imageUrl}
                  alt={pin.title || "pin"}
                  className="w-full object-cover transition duration-500 group-hover:scale-[1.03]"
                  loading="lazy"
                />
                <div className="pointer-events-none absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/75 via-black/20 to-transparent p-3 opacity-0 transition group-hover:opacity-100">
                  <div className="line-clamp-2 text-xs text-white/90">{pin.title || "Pin"}</div>
                </div>
              </div>
              <div className="flex items-start justify-between gap-2 px-3 py-2">
                <div className="min-w-0">
                  <div className="truncate text-xs text-white/80">{pin.title || "Pin"}</div>
                  <div className="truncate text-[10px] text-white/35">
                    {pin.category || "style"} · {pin.board}
                  </div>
                </div>
                <ExternalLink className="mt-0.5 h-3 w-3 shrink-0 text-white/35" />
              </div>
            </a>
          ))}
        </div>

        {pinLoading && !pins.length ? (
          <p className="text-sm text-white/40">{t("common.loading")}</p>
        ) : null}
        {!pinLoading && !pins.length ? (
          <p className="text-sm text-white/40">{t("common.error")}</p>
        ) : null}

        {hasMore ? (
          <div className="mt-6 flex justify-center">
            <button
              type="button"
              className="btn-secondary"
              disabled={loadingMore}
              onClick={() =>
                void loadPins({
                  refresh: false,
                  nextCategory: category,
                  append: true,
                  offset: nextOffset ?? pins.length,
                })
              }
            >
              {loadingMore ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}
              加载更多
            </button>
          </div>
        ) : null}
      </div>

      <div className="mb-3 text-sm font-semibold text-white">{t("inspire.prompts") || "开篇点子"}</div>
      <div className="mb-4 flex flex-wrap gap-2">
        {promptTags.map((tag) => (
          <button
            key={tag}
            type="button"
            className={promptFilter === tag ? "btn-primary !min-h-9 !px-3" : "btn-secondary !min-h-9 !px-3"}
            onClick={() => setPromptFilter(tag)}
          >
            {tag}
          </button>
        ))}
      </div>
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {promptList.map((item) => (
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
