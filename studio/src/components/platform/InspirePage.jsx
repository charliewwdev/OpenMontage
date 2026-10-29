import { useEffect, useMemo, useRef, useState } from "react";
import { Copy, Flame, Lightbulb, RefreshCw, Search, Sparkles, X } from "lucide-react";
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

function ScenarioCard({ item, expanded, onToggle, onUsePrompt, onStartPortrait, t }) {
  const why = Array.isArray(item.whyItWorks) ? item.whyItWorks : [];
  const beats = Array.isArray(item.beats) ? item.beats : [];

  return (
    <article className="panel flex flex-col gap-3 border border-[var(--line)] bg-gradient-to-br from-[#ff5a3d]/08 to-transparent p-4">
      <button type="button" className="w-full text-left" onClick={onToggle}>
        <div className="flex flex-wrap items-center gap-2">
          <span className="rounded-full bg-[#ff5a3d]/20 px-2 py-0.5 text-[10px] font-medium text-[#ff8f6b]">
            {item.platform}
          </span>
          <span className="rounded-full bg-white/[.06] px-2 py-0.5 text-[10px] text-white/50">
            {item.duration}
          </span>
          {item.genre ? (
            <span className="rounded-full bg-white/[.06] px-2 py-0.5 text-[10px] text-white/50">
              {item.genre}
            </span>
          ) : null}
        </div>
        <div className="mt-2 text-sm font-semibold text-white">{item.title}</div>
        <p className="mt-1 text-xs leading-5 text-white/55">{item.hook}</p>
      </button>

      {expanded ? (
        <div className="space-y-3 border-t border-[var(--line)] pt-3">
          {why.length ? (
            <div>
              <div className="mb-1 text-[11px] font-medium uppercase tracking-wide text-white/35">
                {t("inspire_scenario_why")}
              </div>
              <ul className="space-y-1 text-xs leading-5 text-white/70">
                {why.map((line) => (
                  <li key={line}>· {line}</li>
                ))}
              </ul>
            </div>
          ) : null}
          {beats.length ? (
            <div>
              <div className="mb-1 text-[11px] font-medium uppercase tracking-wide text-white/35">
                {t("inspire_scenario_beats")}
              </div>
              <ol className="space-y-1.5 text-xs leading-5 text-white/75">
                {beats.map((beat) => (
                  <li key={`${beat.t}-${beat.action}`}>
                    <span className="font-medium text-[#ff8f6b]">{beat.t}</span>
                    <span className="text-white/40"> · </span>
                    {beat.action}
                  </li>
                ))}
              </ol>
            </div>
          ) : null}
          {item.styleNotes ? (
            <p className="text-[11px] leading-5 text-white/40">{item.styleNotes}</p>
          ) : null}
          {item.referenceNote ? (
            <p className="text-[10px] leading-4 text-white/30">{item.referenceNote}</p>
          ) : null}
        </div>
      ) : null}

      <div className="mt-auto flex gap-2">
        <button
          type="button"
          className="btn-secondary flex-1 !min-h-9"
          onClick={async () => {
            await navigator.clipboard.writeText(item.prompt || "");
            toast.success(t("inspire_toast_copied"));
          }}
        >
          <Copy className="h-3.5 w-3.5" /> {t("inspire_action_copy")}
        </button>
        <button
          type="button"
          className="btn-primary flex-1 !min-h-9"
          onClick={() => {
            if (item.workflow === "portrait-match" && onStartPortrait) {
              onStartPortrait(item);
              return;
            }
            onUsePrompt?.(item.prompt);
          }}
        >
          <Lightbulb className="h-3.5 w-3.5" /> {t("inspire_action_create")}
        </button>
      </div>
    </article>
  );
}

export function InspirePage({ config, onUsePrompt, onStartPortrait }) {
  const { t } = useLocale();
  const prompts = config?.inspirePrompts || [];
  const platforms = config?.inspirePlatforms || [];
  const scenarios = config?.viralScenarios || [];
  const page = config?.pages?.inspire || {};
  const [promptFilter, setPromptFilter] = useState("全部");
  const [scenarioFilter, setScenarioFilter] = useState("全部");
  const [expandedId, setExpandedId] = useState(scenarios[0]?.id || null);
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

  const scenarioPlatforms = useMemo(() => {
    const all = t("inspire_filter_all");
    return [all, ...new Set(scenarios.map((s) => s.platform).filter(Boolean))];
  }, [scenarios, t]);

  const allLabel = t("inspire_filter_all");
  const promptList =
    promptFilter === allLabel || promptFilter === "全部"
      ? prompts
      : prompts.filter((p) => p.tag === promptFilter);

  const scenarioList =
    scenarioFilter === allLabel || scenarioFilter === "全部"
      ? scenarios
      : scenarios.filter((s) => s.platform === scenarioFilter);

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
      eyebrow={page.eyebrow || "Viral Content"}
      title={page.title || "爆款内容广场"}
      description={
        page.description ||
        "先看各大平台真实短视频爆款长什么样（节拍结构），再选平台套路一键带入创作。"
      }
    >
      {scenarios.length ? (
        <div className="mb-4">
          <div className="mb-0.5 text-[13px] font-semibold text-white">{t("inspire_scenarios_title")}</div>
          <p className="mb-2 text-[11px] leading-4 text-white/40">{t("inspire_scenarios_hint")}</p>
          <div className="mb-2.5 flex flex-wrap gap-1.5">
            {scenarioPlatforms.map((tag) => (
              <button
                key={tag}
                type="button"
                className={
                  scenarioFilter === tag ? "btn-primary !min-h-9 !px-3" : "btn-secondary !min-h-9 !px-3"
                }
                onClick={() => setScenarioFilter(tag)}
              >
                {tag}
              </button>
            ))}
          </div>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {scenarioList.map((item) => (
              <ScenarioCard
                key={item.id}
                item={item}
                expanded={expandedId === item.id}
                onToggle={() => setExpandedId((cur) => (cur === item.id ? null : item.id))}
                onUsePrompt={onUsePrompt}
                onStartPortrait={onStartPortrait}
                t={t}
              />
            ))}
          </div>
        </div>
      ) : null}

      {platforms.length ? (
        <div className="mb-4">
          <div className="mb-2 text-[13px] font-semibold text-white">{t("inspire_platforms_title")}</div>
          <div className="mb-2 grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
            {platforms.map((item) => (
              <article
                key={item.id}
                className="panel flex flex-col gap-2 border border-[var(--line)] bg-gradient-to-br from-white/[.04] to-transparent p-3"
              >
                <div className="flex items-center gap-2">
                  <span className="inline-flex h-7 w-7 items-center justify-center rounded-full bg-[#ff5a3d]/15 text-[#ff8f6b]">
                    <Flame className="h-3.5 w-3.5" />
                  </span>
                  <div>
                    <div className="text-[13px] font-semibold text-white">{item.label}</div>
                    <div className="text-[11px] text-white/45">{item.blurb}</div>
                  </div>
                </div>
                <div className="mt-auto flex gap-2">
                  <button
                    type="button"
                    className="btn-secondary flex-1 !min-h-9"
                    onClick={async () => {
                      await navigator.clipboard.writeText(item.prompt);
                      toast.success(t("inspire_toast_copied"));
                    }}
                  >
                    <Copy className="h-3.5 w-3.5" /> {t("inspire_action_copy")}
                  </button>
                  <button
                    type="button"
                    className="btn-primary flex-1 !min-h-9"
                    onClick={() => onUsePrompt?.(item.prompt)}
                  >
                    <Lightbulb className="h-3.5 w-3.5" /> {t("inspire_action_create")}
                  </button>
                </div>
              </article>
            ))}
          </div>
        </div>
      ) : null}

      <div className="mb-4">
        <div className="mb-0.5 text-[13px] font-semibold text-white">{t("inspire_wall_title")}</div>
        <p className="mb-2.5 text-[11px] leading-4 text-white/40">{t("inspire_wall_hint")}</p>
        <div className="mb-2.5 flex flex-wrap items-center gap-2">
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
          <p className="py-10 text-center text-sm text-white/40">{t("inspire_empty_pins")}</p>
        ) : null}
      </div>

      <div className="mb-2 text-[13px] font-semibold text-white">{t("inspire_prompts_title")}</div>
      <div className="mb-2.5 flex flex-wrap gap-1.5">
        {promptTags.map((tag) => (
          <button
            key={tag}
            type="button"
            className={promptFilter === tag ? "btn-primary !min-h-8 !px-2.5" : "btn-secondary !min-h-8 !px-2.5"}
            onClick={() => setPromptFilter(tag)}
          >
            {tag}
          </button>
        ))}
      </div>
      <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
        {promptList.map((item) => (
          <article key={item.text} className="panel flex flex-col p-3">
            <span className="label">{item.tag}</span>
            <p className="mt-1.5 flex-1 text-[12px] leading-5 text-white/85">{item.text}</p>
            <div className="mt-2.5 flex gap-1.5">
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
                alt={selected.title || "viral reference"}
                className="max-h-[70vh] w-full rounded-xl object-contain"
              />
            </div>
            <div className="flex min-h-0 flex-col gap-4 border-t border-[var(--line)] p-4 md:border-l md:border-t-0 md:p-5">
              <div>
                <div className="text-sm font-semibold text-white">
                  {selected.title || t("inspire_detail_title")}
                </div>
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
                <p className="mt-3 text-xs text-white/35">{t("inspire_learn_hint")}</p>
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
                  <Lightbulb className="h-3.5 w-3.5" /> 用这个提示词打造
                </button>
              </div>
            </div>
          </div>
        </ModalOverlay>
      ) : null}
    </PageShell>
  );
}
