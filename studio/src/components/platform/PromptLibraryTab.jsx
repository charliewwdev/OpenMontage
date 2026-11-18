import { useEffect, useMemo, useRef, useState } from "react";
import { BookmarkPlus, Clapperboard, Copy, ExternalLink, Languages, Loader2, Search, X } from "lucide-react";
import { api } from "../../api";
import { toast } from "../../lib/toast";
import { getLocale, pickLocale, tr, useLocale } from "../../lib/i18n";

const PAGE_SIZE = 24;
const STAGES = ["script", "character", "scene", "prop", "storyboard", "voice", "edit"];
const CREDITS_FALLBACK = "https://github.com/charliewwdev/OpenMontage/blob/main/prompts/library/ATTRIBUTION.md";
const HIDDEN_TAGS = new Set(["VBench"]);

export function stageLabel(stage) {
  return STAGES.includes(stage) ? tr(`ui_prompt_library_stage_${stage}`) : stage;
}

export function modelLabel(model) {
  return model === "generic" ? tr("ui_prompt_library_model_generic") : model;
}

/** Text shown for an entry in the given language, falling back to the other side. */
export function entryText(item, lang) {
  if (!item) return "";
  return lang === "en" ? item.prompt_en || item.prompt_zh || "" : item.prompt_zh || item.prompt_en || "";
}

/** The AI-assisted marker belongs to the side that was translated, not the original. */
export function showsAiTranslation(item, lang) {
  if (!item?.aiTranslated) return false;
  return (item.lang_origin || "en") !== lang;
}

function Chip({ active, children, onClick }) {
  return (
    <button type="button" className={`${active ? "chip-active" : "chip"} shrink-0 whitespace-nowrap`} onClick={onClick}>
      {children}
    </button>
  );
}

function PromptCard({ item, uiLang, authed, onTag, onUseInNewProject, onRequireAuth }) {
  useLocale();
  const [lang, setLang] = useState(uiLang);
  const [saving, setSaving] = useState(false);
  useEffect(() => setLang(uiLang), [uiLang]);
  const text = entryText(item, lang);
  const title = pickLocale(item.title) || item.id;
  const other = lang === "en" ? "zh" : "en";
  const src = item.source || {};
  const tags = (item.tags || []).filter((t) => !HIDDEN_TAGS.has(t) && t !== "基础例句" && t !== "原创");

  const save = async () => {
    if (!authed) {
      // The shell's sign-in prompt shows its own toast; only explain when there is no shell handler.
      if (onRequireAuth) onRequireAuth();
      else toast.info(tr("ui_prompt_library_login_to_save"));
      return;
    }
    setSaving(true);
    try {
      await api("/api/platform/prompts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title,
          text,
          category: "template",
          origin: {
            libraryId: item.id,
            source: src.name || "",
            sourceUrl: src.url || "",
            license: item.license || "",
            licenseUrl: item.license_url || "",
            attribution: item.attribution || "",
          },
        }),
      });
      toast.success(tr("ui_prompt_library_saved"));
    } catch (error) {
      toast.error(String(error.message || error));
    } finally {
      setSaving(false);
    }
  };

  return (
    <article className="panel flex flex-col p-5" data-prompt-id={item.id}>
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="label">{stageLabel(item.stage)}</span>
        {item.model && item.model !== "generic" ? <span className="label">{item.model}</span> : null}
        {item.basicExample ? (
          <span
            className="rounded-full border border-amber-300/30 bg-amber-300/10 px-2 py-0.5 text-[11px] text-amber-200"
            title={tr("ui_prompt_library_basic_example_hint")}
          >
            {tr("ui_prompt_library_basic_example")}
          </span>
        ) : null}
        {item.original ? (
          <span className="rounded-full border border-[#8b7cff]/30 bg-[#8b7cff]/10 px-2 py-0.5 text-[11px] text-[#c4bbff]">
            {tr("ui_prompt_library_original")}
          </span>
        ) : null}
        {showsAiTranslation(item, lang) ? (
          <span
            className="rounded-full border border-sky-300/30 bg-sky-300/10 px-2 py-0.5 text-[11px] text-sky-200"
            title={tr("ui_prompt_library_ai_translated_hint")}
          >
            {tr("ui_prompt_library_ai_translated")}
          </span>
        ) : null}
      </div>
      <div className="mt-2 flex items-start justify-between gap-2">
        <h3 className="text-sm font-semibold text-white">{title}</h3>
        <button
          type="button"
          className="inline-flex shrink-0 items-center gap-1 text-[11px] text-white/45 hover:text-white/75"
          onClick={() => setLang(other)}
          title={other === "en" ? tr("ui_prompt_library_show_en") : tr("ui_prompt_library_show_zh")}
        >
          <Languages className="h-3 w-3" aria-hidden />
          {other === "en" ? tr("ui_prompt_library_show_en") : tr("ui_prompt_library_show_zh")}
        </button>
      </div>
      <p className="mt-2 line-clamp-6 flex-1 whitespace-pre-line text-sm leading-7 text-white/80" lang={lang === "en" ? "en" : "zh-CN"}>
        {text}
      </p>
      {tags.length ? (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {tags.slice(0, 6).map((t) => (
            <button
              key={t}
              type="button"
              className="rounded-full bg-white/[0.06] px-2 py-0.5 text-[11px] text-white/55 hover:bg-white/10 hover:text-white/80"
              onClick={() => onTag?.(t)}
            >
              #{t}
            </button>
          ))}
        </div>
      ) : null}
      <div className="mt-4 grid grid-cols-2 gap-2">
        <button
          type="button"
          className="btn-secondary whitespace-nowrap"
          onClick={async () => {
            try {
              await navigator.clipboard.writeText(text);
              toast.success(tr("ui_assets_copied"));
            } catch (error) {
              toast.error(String(error.message || error));
            }
          }}
        >
          <Copy className="h-3.5 w-3.5" /> {tr("ui_assets_copy")}
        </button>
        <button
          type="button"
          className="btn-secondary whitespace-nowrap"
          disabled={saving}
          title={authed ? undefined : tr("ui_prompt_library_login_to_save")}
          onClick={() => void save()}
        >
          {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <BookmarkPlus className="h-3.5 w-3.5" />}{" "}
          {tr("ui_prompt_library_save")}
        </button>
        <button type="button" className="btn-primary col-span-2" onClick={() => onUseInNewProject?.(text, item)}>
          <Clapperboard className="h-3.5 w-3.5" /> {tr("ui_prompt_library_use_in_new_project")}
        </button>
      </div>
      <p className="mt-3 border-t border-white/[0.06] pt-2 text-[10px] leading-5 text-white/40">
        {tr("ui_prompt_library_source")}:{" "}
        {src.url ? (
          <a className="underline-offset-2 hover:text-white/70 hover:underline" href={src.url} target="_blank" rel="noreferrer noopener">
            {src.name}
          </a>
        ) : (
          src.name
        )}
        {" · "}
        {tr("ui_prompt_library_license")}:{" "}
        {item.license_url ? (
          <a className="underline-offset-2 hover:text-white/70 hover:underline" href={item.license_url} target="_blank" rel="noreferrer noopener">
            {item.license}
          </a>
        ) : (
          item.license
        )}
        {item.attribution ? <span className="block">{item.attribution}</span> : null}
      </p>
    </article>
  );
}

export function PromptLibraryTab({ authed = false, onRequireAuth, onUseInNewProject }) {
  useLocale();
  const uiLang = getLocale() === "en" ? "en" : "zh";
  const [meta, setMeta] = useState(null);
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [nextOffset, setNextOffset] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("");
  const [subcategory, setSubcategory] = useState("");
  const [model, setModel] = useState("");
  const [stage, setStage] = useState("");
  const [source, setSource] = useState("");
  const [tag, setTag] = useState("");
  const reqId = useRef(0);

  useEffect(() => {
    api("/api/platform/prompts/library/meta")
      .then(setMeta)
      .catch((error) => toast.error(String(error.message || error)));
  }, []);

  const fetchPage = async (offset, append) => {
    const id = ++reqId.current;
    if (append) setLoadingMore(true);
    else setLoading(true);
    try {
      const q = new URLSearchParams({ limit: String(PAGE_SIZE), offset: String(offset) });
      if (query.trim()) q.set("q", query.trim());
      if (category) q.set("category", category);
      if (subcategory) q.set("subcategory", subcategory);
      if (model) q.set("model", model);
      if (stage) q.set("stage", stage);
      if (source) q.set("source", source);
      if (tag) q.append("tag", tag);
      const data = await api(`/api/platform/prompts/library?${q.toString()}`);
      if (id !== reqId.current) return;
      const batch = data.items || [];
      setItems((prev) => (append ? [...prev, ...batch] : batch));
      setTotal(Number(data.total) || 0);
      setHasMore(Boolean(data.hasMore));
      setNextOffset(data.nextOffset ?? null);
    } catch (error) {
      if (id === reqId.current) toast.error(String(error.message || error));
    } finally {
      if (id === reqId.current) {
        setLoading(false);
        setLoadingMore(false);
      }
    }
  };

  useEffect(() => {
    const timer = setTimeout(() => void fetchPage(0, false), query ? 280 : 0);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query, category, subcategory, model, stage, source, tag]);

  const categories = meta?.categories || [];
  const subcats = useMemo(
    () => categories.find((c) => c.key === category)?.subcategories || [],
    [categories, category],
  );
  const filtered = Boolean(query || category || subcategory || model || stage || source || tag);
  const clearFilters = () => {
    setQuery("");
    setCategory("");
    setSubcategory("");
    setModel("");
    setStage("");
    setSource("");
    setTag("");
  };

  return (
    <>
      <div className="mb-4 flex flex-col gap-1 text-xs text-[var(--muted)] sm:flex-row sm:items-center sm:justify-between">
        <span>{tr("ui_prompt_library_intro")}</span>
        <a
          className="inline-flex shrink-0 items-center gap-1 text-[#8b7cff] hover:underline"
          href={meta?.creditsUrl || CREDITS_FALLBACK}
          target="_blank"
          rel="noreferrer noopener"
        >
          {tr("ui_prompt_library_credits")} <ExternalLink className="h-3 w-3" aria-hidden />
        </a>
      </div>

      <div className="mb-3 overflow-x-auto pb-1 [scrollbar-width:thin]">
        <div className="flex w-max items-center gap-2 pr-2">
          <Chip active={!category} onClick={() => { setCategory(""); setSubcategory(""); }}>
            {tr("ui_prompt_library_all")}
          </Chip>
          {categories.map((c) => (
            <Chip key={c.key} active={category === c.key} onClick={() => { setCategory(c.key); setSubcategory(""); }}>
              {c.emoji ? `${c.emoji} ` : ""}
              {pickLocale(c)} <span className="opacity-50">{c.count}</span>
            </Chip>
          ))}
        </div>
      </div>

      {subcats.length ? (
        <div className="mb-3 overflow-x-auto pb-1 [scrollbar-width:thin]">
          <div className="flex w-max items-center gap-2 pr-2">
            <Chip active={!subcategory} onClick={() => setSubcategory("")}>{tr("ui_prompt_library_all")}</Chip>
            {subcats.map((s) => (
              <Chip key={s.key} active={subcategory === s.key} onClick={() => setSubcategory(s.key)}>
                {pickLocale(s) || s.key} <span className="opacity-50">{s.count}</span>
              </Chip>
            ))}
          </div>
        </div>
      ) : null}

      <div className="mb-5 flex flex-col gap-3 lg:flex-row lg:items-center">
        <label className="relative min-w-0 flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--muted)]" />
          <input
            className="field !pl-10"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={tr("ui_prompt_library_search")}
            aria-label={tr("ui_prompt_library_search")}
          />
        </label>
        <div className="flex flex-wrap items-center gap-2">
          <select className="field !w-auto" value={stage} onChange={(e) => setStage(e.target.value)} aria-label={tr("ui_prompt_library_all_stages")}>
            <option value="">{tr("ui_prompt_library_all_stages")}</option>
            {(meta?.stages || STAGES).map((s) => (
              <option key={s} value={s}>{stageLabel(s)}</option>
            ))}
          </select>
          <select className="field !w-auto" value={model} onChange={(e) => setModel(e.target.value)} aria-label={tr("ui_prompt_library_all_models")}>
            <option value="">{tr("ui_prompt_library_all_models")}</option>
            {(meta?.models || []).map((m) => (
              <option key={m} value={m}>{modelLabel(m)}</option>
            ))}
          </select>
          <select className="field !w-auto" value={source} onChange={(e) => setSource(e.target.value)} aria-label={tr("ui_prompt_library_all_sources")}>
            <option value="">{tr("ui_prompt_library_all_sources")}</option>
            <option value="original">{tr("ui_prompt_library_source_original")}</option>
            <option value="third-party">{tr("ui_prompt_library_source_third_party")}</option>
          </select>
        </div>
      </div>

      <div className="mb-3 flex flex-wrap items-center gap-2 text-xs text-[var(--muted)]">
        <span>{tr("ui_prompt_library_count", { total })}</span>
        {tag ? (
          <button type="button" className="chip-active inline-flex items-center gap-1" onClick={() => setTag("")}>
            {tr("ui_prompt_library_tag_filter", { tag })} <X className="h-3 w-3" aria-hidden />
          </button>
        ) : null}
        {filtered ? (
          <button type="button" className="text-white/45 hover:text-white/75" onClick={clearFilters}>
            {tr("ui_prompt_library_clear_filters")}
          </button>
        ) : null}
      </div>

      {loading && !items.length ? (
        <div className="panel flex items-center justify-center gap-2 py-20 text-sm text-[var(--muted)]">
          <Loader2 className="h-4 w-4 animate-spin" /> {tr("ui_prompt_library_loading")}
        </div>
      ) : !items.length ? (
        <div className="panel py-20 text-center text-sm text-[var(--muted)]">{tr("ui_prompt_library_empty")}</div>
      ) : (
        <>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {items.map((item) => (
              <PromptCard
                key={item.id}
                item={item}
                uiLang={uiLang}
                authed={authed}
                onTag={setTag}
                onRequireAuth={onRequireAuth}
                onUseInNewProject={onUseInNewProject}
              />
            ))}
          </div>
          {hasMore ? (
            <div className="mt-6 flex justify-center">
              <button
                type="button"
                className="btn-secondary"
                disabled={loadingMore}
                onClick={() => void fetchPage(nextOffset ?? items.length, true)}
              >
                {loadingMore ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null} {tr("ui_prompt_library_load_more")}
              </button>
            </div>
          ) : null}
        </>
      )}
    </>
  );
}
