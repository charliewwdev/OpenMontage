import { useEffect, useMemo, useState } from "react";
import { CheckCircle2, Loader2, Search, Sparkles, Store, X } from "lucide-react";
import { api } from "../../api";
import { toast } from "../../lib/toast";
import { ModalOverlay } from "../ModalPortal";
import { PageShell } from "./PageShell";

import { tr, useLocale } from "../../lib/i18n";

const FALLBACK_SOURCES = [
  {
    id: "all",

    get label() {
      return tr("ui_skills_all_sources");
    }
  },
  {
    id: "official",

    get label() {
      return tr("ui_skills_official_picks");
    }
  },
  {
    id: "community",

    get label() {
      return tr("ui_skills_community");
    }
  },
];

const FALLBACK_CATS = [
  {
    id: "all",

    get label() {
      return tr("ui_skills_all_categories");
    }
  },
  {
    id: "text",

    get label() {
      return tr("ui_skills_text_writing");
    }
  },
  {
    id: "image",

    get label() {
      return tr("ui_skills_image_design");
    }
  },
  {
    id: "video",

    get label() {
      return tr("ui_skills_video_creation");
    }
  },
  {
    id: "audio",

    get label() {
      return tr("ui_skills_audio_music");
    }
  },
  {
    id: "film",

    get label() {
      return tr("ui_skills_film_production");
    }
  },
  {
    id: "business",

    get label() {
      return tr("ui_skills_marketing");
    }
  },
  {
    id: "productivity",

    get label() {
      return tr("ui_skills_productivity");
    }
  },
  {
    id: "other",

    get label() {
      return tr("ui_skills_other");
    }
  },
];

// Tag values are skill data (they match `skill.tags`); only the chip label is translated.
const ALL_TAGS = "全部标签";
const FALLBACK_TAGS = [
  ALL_TAGS,
  "短剧漫剧",
  "剧本创作",
  "分镜设计",
  "角色设计",
  "场景设计",
  "提示词",
  "镜头语言",
  "图片生成",
  "视频生成",
  "配音旁白",
  "优化改写",
  "Seedance",
  "创作工作流",
];
const TAG_LABEL_KEYS = {
  "全部标签": "ui_skills_all_tags",
  "短剧漫剧": "ui_skills_short_comic_dramas",
  "剧本创作": "ui_skills_script_writing",
  "分镜设计": "ui_skills_storyboard_design",
  "角色设计": "ui_skills_character_design",
  "场景设计": "ui_skills_scene_design",
  "提示词": "ui_skills_prompts",
  "镜头语言": "ui_skills_camera_language",
  "图片生成": "ui_skills_image_generation",
  "视频生成": "ui_skills_video_generation",
  "配音旁白": "ui_skills_voice_over_narration",
  "优化改写": "ui_skills_rewrite_polish",
  "创作工作流": "ui_skills_creative_workflow",
};

/** Server lists carry zh labels; prefer the translated built-in label for known ids. */
function labelById(fallbacks, item) {
  return fallbacks.find((entry) => entry.id === item.id)?.label ?? item.label;
}

function tagLabel(tag) {
  const key = TAG_LABEL_KEYS[tag];
  return key ? tr(key) : tag;
}

function Chip({ active, children, onClick }) {
  useLocale();
  return (
    <button type="button" className={`${active ? "chip-active" : "chip"} shrink-0`} onClick={onClick}>
      {children}
    </button>
  );
}

function skillPrompt(skill) {
  if (skill.prompt) return skill.prompt;
  return `请按 Skill「${skill.title}」${skill.slash || `/${skill.id}`} 的规则帮我创作：\n\n${(skill.summary || "").trim()}`;
}

function ctaLabel(skill) {
  const route = skill?.workshop?.route;
  if (route === "portrait") return tr("ui_skills_open_portrait_benchmark");
  if (route === "workshop") return tr("ui_skills_open_film_workshop");
  if (route === "agent") return tr("ui_skills_chat_creation");
  return tr("ui_skills_use_it");
}

export function SkillsPage({ config, onUsePrompt, onUseSkill }) {
  useLocale();
  const activate = (skill) => {
    if (onUseSkill) onUseSkill(skill);
    else onUsePrompt?.(skillPrompt(skill));
  };

  const page = config?.pages?.skills || {};
  const [skills, setSkills] = useState([]);
  const [sources, setSources] = useState(FALLBACK_SOURCES);
  const [categories, setCategories] = useState(FALLBACK_CATS);
  const [tagOptions, setTagOptions] = useState(FALLBACK_TAGS);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [source, setSource] = useState("all");
  const [category, setCategory] = useState("all");
  const [tag, setTag] = useState(ALL_TAGS);
  const [active, setActive] = useState(null);
  const [showSubmit, setShowSubmit] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [draft, setDraft] = useState({ title: "", summary: "", prompt: "", category: "other" });

  const refresh = async () => {
    setLoading(true);
    try {
      const data = await api("/api/platform/skills");
      setSkills(data.skills || []);
      if (data.sources?.length) setSources(data.sources);
      if (data.categories?.length) setCategories(data.categories);
      if (data.tags?.length) setTagOptions(data.tags);
    } catch (error) {
      toast.error(String(error.message || error));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void refresh();
  }, []);

  const filtered = useMemo(() => {
    const q = query.trim().toLocaleLowerCase("zh-CN");
    return skills.filter((s) => {
      if (source !== "all" && (s.source || "official") !== source) return false;
      if (category !== "all" && (s.category || "other") !== category) return false;
      if (tag !== ALL_TAGS && !(s.tags || []).includes(tag)) return false;
      if (!q) return true;
      const blob = `${s.title} ${s.summary} ${s.id} ${(s.tags || []).join(" ")} ${s.content || ""}`.toLocaleLowerCase(
        "zh-CN",
      );
      return blob.includes(q);
    });
  }, [skills, query, source, category, tag]);

  const officialCount = filtered.filter((s) => (s.source || "official") === "official").length;

  return (
    <PageShell
      eyebrow={page.eyebrow || "Skills"}
      title={page.title || tr("ui_skills_put_professional_methods_into_your_creation")}
      description={
        page.description ||
        tr("ui_skills_official_skills_are_bound_to_film")
      }
      actions={
        <>
          <button type="button" className="btn-secondary" onClick={() => setShowSubmit(true)}>{tr("ui_skills_submit_to_community")}</button>
          <button type="button" className="btn-secondary" onClick={() => void refresh()}>
            <Store className="h-3.5 w-3.5" />{" "}{tr("ui_skills_skill_store")}</button>
        </>
      }
    >
      <label className="relative mb-4 block">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--muted)]" />
        <input
          className="field !pl-10"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={tr("ui_skills_search_capabilities_or_skill_names")}
        />
      </label>

      <div className="mb-3 flex flex-wrap gap-2">
        {sources.map((item) => (
          <Chip key={item.id} active={source === item.id} onClick={() => setSource(item.id)}>
            {labelById(FALLBACK_SOURCES, item)}
          </Chip>
        ))}
      </div>
      <div className="mb-3 flex flex-wrap gap-2">
        {categories.map((item) => (
          <Chip key={item.id} active={category === item.id} onClick={() => setCategory(item.id)}>
            {labelById(FALLBACK_CATS, item)}
          </Chip>
        ))}
      </div>
      <div className="mb-6 flex flex-wrap gap-2">
        {tagOptions.map((item) => (
          <Chip key={item} active={tag === item} onClick={() => setTag(item)}>
            {tagLabel(item)}
          </Chip>
        ))}
      </div>

      <div className="mb-4 flex items-center gap-2 text-sm text-white/70">
        <CheckCircle2 className="h-4 w-4 text-[#60a5fa]" />
        <span className="font-medium">{tr("ui_skills_official_picks")}</span>
        <span className="rounded-full bg-[#60a5fa]/15 px-2 py-0.5 text-[11px] text-[#93c5fd]">{tr("ui_skills_available", {
            officialCount: officialCount
          })}</span>
      </div>

      {loading ? (
        <div className="panel flex items-center justify-center gap-2 py-20 text-sm text-[var(--muted)]">
          <Loader2 className="h-4 w-4 animate-spin" />{" "}{tr("ui_skills_loading_skills")}</div>
      ) : !filtered.length ? (
        <div className="panel py-20 text-center text-sm text-[var(--muted)]">{tr("ui_skills_no_matching_skills")}</div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {filtered.map((skill) => (
            <article
              key={skill.id}
              className="panel flex flex-col p-5 transition hover:-translate-y-0.5 hover:border-white/20"
            >
              <button type="button" className="flex flex-1 flex-col text-left" onClick={() => setActive(skill)}>
                <span
                  className="flex h-10 w-10 items-center justify-center rounded-xl text-sm font-bold text-white"
                  style={{ background: skill.accent || "var(--gradient)" }}
                >
                  {(skill.title || skill.id).slice(0, 1)}
                </span>
                <strong className="mt-3 block text-base">{skill.title}</strong>
                <span className="mt-1 font-mono text-[11px] text-white/35">{skill.slash || `/${skill.id}`}</span>
                <p className="mt-2 line-clamp-3 flex-1 text-sm leading-6 text-[var(--muted)]">{skill.summary}</p>
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {(skill.tags || []).slice(0, 4).map((t) => (
                    <span key={t} className="rounded-full bg-white/[.06] px-2 py-0.5 text-[10px] text-white/50">
                      {t}
                    </span>
                  ))}
                </div>
                {skill.experience?.totalHits > 0 || skill.experience?.learnedCount > 0 ? (
                  <div className="mt-3 rounded-lg border border-emerald-500/20 bg-emerald-500/10 px-2.5 py-1.5 text-[10px] text-emerald-100/90">{tr("ui_skills_learned_hits", {
                      0: skill.experience.patchCount || 0,
                      1: skill.experience.totalHits || 0
                    })}{skill.experience.learnedCount
                      ? ` ${tr("ui_skills_auto_learned", {
  learnedCount: skill.experience.learnedCount
})}`
                      : ""}
                  </div>
                ) : null}
              </button>
              <div className="mt-4 flex items-center justify-between gap-2 border-t border-white/5 pt-3">
                <span className="text-[11px] text-white/35">{tr("ui_skills_built_in_no_install_needed")}</span>
                <button
                  type="button"
                  className="btn-primary !min-h-8 !px-3 !text-xs"
                  onClick={() => activate(skill)}
                >
                  <Sparkles className="h-3 w-3" /> {ctaLabel(skill)}
                </button>
              </div>
            </article>
          ))}
        </div>
      )}

      {showSubmit ? (
        <ModalOverlay onClose={() => setShowSubmit(false)} className="bg-black/70">
          <div
            className="panel my-auto w-full max-w-lg space-y-3 p-5"
            onClick={(e) => e.stopPropagation()}
            onMouseDown={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold">{tr("ui_skills_submit_a_skill_local_community")}</h3>
              <button type="button" className="btn-ghost p-1" onClick={() => setShowSubmit(false)}>
                <X className="h-4 w-4" />
              </button>
            </div>
            <label>
              <span className="label">{tr("ui_skills_title")}</span>
              <input className="field" value={draft.title} onChange={(e) => setDraft({ ...draft, title: e.target.value })} />
            </label>
            <label>
              <span className="label">{tr("ui_skills_summary")}</span>
              <input className="field" value={draft.summary} onChange={(e) => setDraft({ ...draft, summary: e.target.value })} />
            </label>
            <label>
              <span className="label">{tr("ui_skills_category")}</span>
              <select className="field" value={draft.category} onChange={(e) => setDraft({ ...draft, category: e.target.value })}>
                {categories.filter((c) => c.id !== "all").map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span className="label">{tr("ui_skills_prompt_rules")}</span>
              <textarea
                className="field min-h-36"
                value={draft.prompt}
                onChange={(e) => setDraft({ ...draft, prompt: e.target.value })}
                placeholder={tr("ui_skills_write_reusable_creative_rules_or_prompts")}
              />
            </label>
            <div className="flex justify-end gap-2 pt-2">
              <button type="button" className="btn-secondary" onClick={() => setShowSubmit(false)}>{tr("ui_skills_cancel")}</button>
              <button
                type="button"
                className="btn-primary"
                disabled={submitting}
                onClick={async () => {
                  if (!draft.title.trim() || !draft.prompt.trim()) return toast.error(tr("ui_skills_please_enter_a_title_and_prompt"));
                  setSubmitting(true);
                  try {
                    await api("/api/platform/skills/community", {
                      method: "POST",
                      headers: { "Content-Type": "application/json" },
                      body: JSON.stringify(draft),
                    });
                    toast.success(tr("ui_skills_submitted_to_community"));
                    setShowSubmit(false);
                    setDraft({ title: "", summary: "", prompt: "", category: "other" });
                    setSource("community");
                    await refresh();
                  } catch (error) {
                    toast.error(String(error.message || error));
                  } finally {
                    setSubmitting(false);
                  }
                }}
              >
                {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : null}{tr("ui_skills_submit")}</button>
            </div>
          </div>
        </ModalOverlay>
      ) : null}

      {active ? (
        <ModalOverlay onClose={() => setActive(null)} className="bg-black/70">
          <div
            className="panel my-auto max-h-[85vh] w-full max-w-3xl overflow-hidden"
            onClick={(e) => e.stopPropagation()}
            onMouseDown={(e) => e.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-3 border-b border-white/10 p-5">
              <div>
                <div className="label">{active.slash || `/${active.id}`}</div>
                <h2 className="text-xl font-semibold">{active.title}</h2>
                <p className="mt-2 text-sm text-[var(--muted)]">{active.summary}</p>
              </div>
              <button type="button" className="btn-secondary !min-h-8 !px-2" onClick={() => setActive(null)}>
                <X className="h-4 w-4" />
              </button>
            </div>
            {(active.experience?.topFailures || []).length ? (
              <div className="border-b border-white/10 bg-black/20 px-5 py-3">
                <div className="text-[11px] font-semibold uppercase tracking-wide text-white/45">{tr("ui_skills_qa_lessons_accumulated_automatically")}</div>
                <ul className="mt-2 space-y-1.5">
                  {active.experience.topFailures.slice(0, 5).map((f) => (
                    <li key={f.id} className="rounded-lg border border-white/8 bg-white/[.03] px-2.5 py-1.5 text-[11px] text-white/70">
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-mono text-white/50">{f.id}</span>
                        <span className="text-emerald-300/80">×{f.hits || 0}</span>
                      </div>
                      {f.lastReason ? (
                        <p className="mt-1 line-clamp-2 text-white/55">{f.lastReason}</p>
                      ) : null}
                      {f.promptBoost ? (
                        <p className="mt-1 line-clamp-2 text-[#c4b5fd]/90">{f.promptBoost}</p>
                      ) : null}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
            <pre className="max-h-[50vh] overflow-auto whitespace-pre-wrap bg-black/30 p-5 text-xs leading-6 text-white/75">
              {active.content || tr("ui_skills_nothing_here_yet")}
            </pre>
            <div className="flex justify-end gap-2 border-t border-white/10 p-4">
              <button type="button" className="btn-secondary" onClick={() => setActive(null)}>{tr("ui_skills_close")}</button>
              <button
                type="button"
                className="btn-primary"
                onClick={() => {
                  activate(active);
                  setActive(null);
                }}
              >
                <Sparkles className="h-3.5 w-3.5" /> {ctaLabel(active)}
              </button>
            </div>
          </div>
        </ModalOverlay>
      ) : null}
    </PageShell>
  );
}
