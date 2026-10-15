import { useEffect, useMemo, useRef, useState } from "react";
import { Copy, Lightbulb, RefreshCw, Search, Sparkles, X } from "lucide-react";
import { api } from "../../api";
import { useLocale } from "../../lib/i18n";
import { toast } from "../../lib/toast";
import { ModalOverlay } from "../ModalPortal";
import { PageShell } from "./PageShell";

const DEFAULT_CATS = [
  { id: "all", label: "全部" },
  { id: "character", label: "角色" },
  { id: "scene", label: "场景" },
  { id: "prop", label: "道具" },
  { id: "style", label: "风格" },
  { id: "storyboard", label: "分镜" },
];

const MEDIA_TYPES = [
  { id: "all", label: "全部" },
  { id: "image", label: "图片" },
];

const PAGE_SIZE = 96;

function PinCard({ pin, prompt, onOpen, onDead }) {
  const [ready, setReady] = useState(false);
  const key = `${pin.id}-${pin.imageUrl}`;

  return (
    <button
      type="button"
      onClick={() => (ready ? onOpen(pin) : undefined)}
      tabIndex={ready ? 0 : -1}
      aria-hidden={!ready}
      className={
        ready
          ? "group mb-3 block w-full break-inside-avoid overflow-hidden rounded-2xl border border-[var(--line)] bg-white/[.03] text-left transition hover:border-[#7c6cff]/45"
          : "pointer-events-none absolute h-0 w-0 overflow-hidden opacity-0"
      }
    >
      <div className="relative overflow-hidden">
        <img
          src={pin.imageUrl}
          alt=""
          className="w-full object-cover transition duration-500 group-hover:scale-[1.03]"
          loading="eager"
          decoding="async"
          onLoad={() => setReady(true)}
          onError={() => onDead(key)}
        />
        {ready && prompt ? (
          <span className="absolute left-2 top-2 rounded-full bg-[#7c6cff]/95 px-2 py-0.5 text-[10px] font-medium text-white shadow">
            含提示词
          </span>
        ) : null}
      </div>
    </button>
  );
}

export function InspirePage({ config, onUsePrompt }) {
  const { t } = useLocale();
  const prompts = config?.inspirePrompts || [];
  const page = config?.pages?.inspire || {};
  const [promptFilter, setPromptFilter] = useState("全部");
  const [category, setCategory] = useState("all");
  const [mediaType, setMediaType] = useState("all");
  const [search, setSearch] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [pins, setPins] = useState([]);
  const [categories, setCategories] = useState(DEFAULT_CATS);
  const [pinLoading, setPinLoading] = useState(false);
  const [selected, setSelected] = useState(null);
  const configRef = useRef(config);
  configRef.current = config;

  const promptTags = useMemo(() => {
    const all = t("inspire_filter_all");
    return [all, ...new Set(prompts.map((p) => p.tag))];
  }, [prompts, t]);

  const allLabel = t("inspire_filter_all");
  const promptList =
    promptFilter === allLabel || promptFilter === "全部"
      ? prompts
      : prompts.filter((p) => p.tag === promptFilter);

  const loadPins = async ({
    refresh = false,
    nextCategory = category,
    nextMedia = mediaType,
    nextSearch = search,
    append = false,
    offset = 0,
  } = {}) => {
    setPinLoading(true);
    try {
      const q = new URLSearchParams({
        limit: String(PAGE_SIZE),
        offset: String(offset),
        category: nextCategory || "all",
        mediaType: nextMedia || "all",
      });
      if (nextSearch?.trim()) q.set("q", nextSearch.trim());
      if (refresh) q.set("refresh", "true");
      const data = await api(`/api/inspire/pins?${q.toString()}`);
      const batch = (data.items || []).filter((item) => String(item?.imageUrl || "").trim());
      setPins((prev) => (append ? [...prev, ...batch] : batch));
      const cfg = configRef.current;
      if (Array.isArray(data.categories) && data.categories.length) {
        setCategories(data.categories);
      } else if (cfg?.pinterest?.categories?.length) {
        setCategories(cfg.pinterest.categories);
      }
    } catch (err) {
      toast.error(String(err.message || err));
    } finally {
      setPinLoading(false);
    }
  };

  useEffect(() => {
    const timer = setTimeout(() => {
      setSearch(searchInput);
      void loadPins({
        refresh: false,
        nextCategory: category,
        nextMedia: mediaType,
        nextSearch: searchInput,
        offset: 0,
      });
    }, searchInput ? 320 : 0);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchInput, category, mediaType]);

  const pinPrompt = (pin) => (pin?.prompt || pin?.description || pin?.title || "").trim();

  return (
    <PageShell
      eyebrow={page.eyebrow || "Inspiration"}
      title={page.title || "灵感广场"}
      description={page.description || "探索影视灵感素材，学习提示词技巧；点击卡片查看完整创作提示词。"}
    >
      <div className="mb-8">
        <div className="mb-4 flex flex-wrap items-center gap-3">
          <label className="relative min-w-[220px] flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-white/35" />
            <input
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="搜索提示词或文件名..."
              className="w-full rounded-xl border border-[var(--line)] bg-white/[.04] py-2.5 pl-10 pr-3 text-sm text-white outline-none placeholder:text-white/30 focus:border-[#7c6cff]/55"
            />
          </label>
          <button
            type="button"
            className="btn-secondary !min-h-10 !px-3"
            disabled={pinLoading}
            onClick={() =>
              void loadPins({
                refresh: true,
                nextCategory: category,
                nextMedia: mediaType,
                nextSearch: searchInput,
                offset: 0,
              })
            }
          >
            <RefreshCw className={`h-3.5 w-3.5 ${pinLoading ? "animate-spin" : ""}`} />
            {t("common_action_retry")}
          </button>
        </div>

        <div className="mb-3 flex flex-wrap gap-2">
          {MEDIA_TYPES.map((item) => {
            const selectedMedia = mediaType === item.id;
            return (
              <button
                key={item.id}
                type="button"
                className={selectedMedia ? "btn-primary !min-h-9 !px-3" : "btn-secondary !min-h-9 !px-3"}
                onClick={() => setMediaType(item.id)}
              >
                {item.label}
              </button>
            );
          })}
        </div>

        <div className="mb-4 flex flex-wrap gap-2">
          {categories.map((cat) => {
            const id = cat.id || cat;
            const label = cat.label || cat.id || cat;
            const selectedCat = category === id;
            return (
              <button
                key={id}
                type="button"
                className={selectedCat ? "btn-primary !min-h-9 !px-3" : "btn-secondary !min-h-9 !px-3"}
                onClick={() => setCategory(id)}
              >
                {label}
              </button>
            );
          })}
        </div>

        <div className="relative columns-2 gap-3 sm:columns-3 xl:columns-4 2xl:columns-5">
          {pins.map((pin) => {
            const prompt = pinPrompt(pin);
            const key = `${pin.id}-${pin.imageUrl}`;
            return (
              <PinCard
                key={key}
                pin={pin}
                prompt={prompt}
                onOpen={setSelected}
                onDead={(deadKey) => {
                  setPins((prev) => prev.filter((p) => `${p.id}-${p.imageUrl}` !== deadKey));
                }}
              />
            );
          })}
        </div>

        {pinLoading && !pins.length ? (
          <p className="py-10 text-center text-sm text-white/40">{t("common_state_loading")}</p>
        ) : null}
        {!pinLoading && !pins.length ? (
          <p className="py-10 text-center text-sm text-white/40">没有找到匹配的灵感，试试换个关键词或分类。</p>
        ) : null}
      </div>

      <div className="mb-3 text-sm font-semibold text-white">{t("inspire_prompts_title")}</div>
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
                  toast.success(t("inspire_toast_copied"));
                }}
              >
                <Copy className="h-3.5 w-3.5" /> {t("inspire_action_copy")}
              </button>
              <button type="button" className="btn-primary flex-1" onClick={() => onUsePrompt?.(item.text)}>
                <Lightbulb className="h-3.5 w-3.5" /> {t("inspire_action_create")}
              </button>
            </div>
          </article>
        ))}
      </div>

      {selected ? (
        <ModalOverlay
          onClose={() => setSelected(null)}
          className="bg-[#09101d]/80 backdrop-blur-sm"
          role="dialog"
        >
          <div
            className="panel relative my-auto grid max-h-[92vh] w-full max-w-5xl overflow-hidden md:grid-cols-[1.2fr_0.9fr]"
            onMouseDown={(e) => e.stopPropagation()}
          >
            <button
              type="button"
              className="absolute right-3 top-3 z-10 rounded-full bg-black/40 p-1.5 text-white/80 hover:bg-black/60"
              onClick={() => setSelected(null)}
              aria-label="关闭"
            >
              <X className="h-4 w-4" />
            </button>
            <div className="flex items-center justify-center bg-black/30 p-3 md:p-5">
              <img
                src={selected.imageUrl}
                alt={selected.title || "inspiration"}
                className="max-h-[70vh] w-full rounded-xl object-contain"
              />
            </div>
            <div className="flex min-h-0 flex-col gap-4 border-t border-[var(--line)] p-4 md:border-l md:border-t-0 md:p-5">
              <div>
                <div className="text-sm font-semibold text-white">{selected.title || "灵感详情"}</div>
              </div>

              <div className="min-h-0 flex-1 rounded-2xl border border-[var(--line)] bg-white/[.03] p-4">
                <div className="mb-2 flex items-center justify-between gap-2">
                  <div className="flex items-center gap-1.5 text-sm font-medium text-white">
                    <Sparkles className="h-3.5 w-3.5 text-[#7c6cff]" />
                    创作提示词
                  </div>
                  <button
                    type="button"
                    className="btn-secondary !min-h-8 !px-2.5 !text-xs"
                    onClick={async () => {
                      const text = pinPrompt(selected);
                      if (!text) return;
                      await navigator.clipboard.writeText(text);
                      toast.success(t("inspire_toast_copied"));
                    }}
                  >
                    <Copy className="h-3 w-3" /> 复制
                  </button>
                </div>
                <div className="max-h-[36vh] overflow-y-auto whitespace-pre-wrap text-sm leading-7 text-white/85">
                  {pinPrompt(selected) || "暂无提示词"}
                </div>
                <p className="mt-3 text-xs text-white/35">学习这个提示词，创作属于你的作品</p>
              </div>

              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  className="btn-primary flex-1"
                  onClick={() => {
                    const text = pinPrompt(selected);
                    if (!text) return;
                    setSelected(null);
                    onUsePrompt?.(text);
                  }}
                >
                  <Lightbulb className="h-3.5 w-3.5" /> 用这个提示词创作
                </button>
              </div>
            </div>
          </div>
        </ModalOverlay>
      ) : null}
    </PageShell>
  );
}
