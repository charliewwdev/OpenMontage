import { useEffect, useMemo, useRef, useState } from "react";
import { ArrowLeft, Clapperboard, KeyRound, Loader2, Plus, RotateCcw, Sparkles, Upload, Wand2 } from "lucide-react";
import { api } from "../api";
import { requireGithubStar } from "../lib/githubStar";
import { requireCapability, toastMaybeKeys } from "../lib/keys";
import { toast } from "../lib/toast";
import { AspectRatioPicker } from "./project-settings/AspectRatioPicker";
import { GenrePicker } from "./project-settings/GenrePicker";
import { VideoStylePicker } from "./project-settings/VideoStylePicker";

import { tr, useLocale } from "../lib/i18n";

export function CreateProjectPage({ config, entryMode = null, onBack, onCreated, onNeedKeys }) {
  useLocale();
  const genres = config?.genres || [];
  const styles = config?.styles || [];
  const ratios = config?.ratios;
  const creationSteps = config?.creationSteps || [];
  const defaults = config?.defaults || {};
  const defaultStyle = useMemo(() => styles[0], [styles]);
  const isUpload = entryMode?.mode === "upload" || entryMode?.id === "upload";
  const preset = entryMode?.preset || {};
  const fileRef = useRef(null);

  const [creating, setCreating] = useState(false);
  const [autoRunning, setAutoRunning] = useState(false);
  const [optimizingBrief, setOptimizingBrief] = useState(false);
  const [parsing, setParsing] = useState(false);
  const [uploadName, setUploadName] = useState("");
  const [briefHistory, setBriefHistory] = useState([]);
  const [form, setForm] = useState({
    title: "",
    brief: "",
    genre: preset.genre || defaults.genre || genres[0] || "",
    visualStyle: defaultStyle?.promptValue || defaultStyle?.generationPrompt || defaults.visualStyle || "",
    ratio: preset.ratio || defaults.ratio || ratios?.[0]?.value || "",
  });
  const formLocked = optimizingBrief || creating || parsing || autoRunning;
  const caps = config?.capabilities || {};

  useEffect(() => {
    if (!entryMode) return;
    setForm((current) => ({
      ...current,
      genre: entryMode.preset?.genre || current.genre,
      ratio: entryMode.preset?.ratio || current.ratio,
    }));
  }, [entryMode?.id]);

  const onPickScript = async (file) => {
    if (!file) return;
    setParsing(true);
    try {
      const body = new FormData();
      body.append("file", file);
      const res = await api("/api/projects/parse-script", { method: "POST", body });
      const text = (res.text || "").trim();
      if (!text) throw new Error(tr("ui_create_project_couldn_t_extract_text_from_the"));
      setUploadName(file.name);
      setForm((current) => ({
        ...current,
        title: current.title || String(res.title || file.name.replace(/\.[^.]+$/, "")).slice(0, 40),
        brief: text.slice(0, 100000),
      }));
      toast.success(tr("ui_create_project_imported_2", {
        name: file.name
      }));
    } catch (error) {
      toast.error(String(error.message || error));
    } finally {
      setParsing(false);
    }
  };

  const optimizeBrief = async () => {
    if (!(await requireGithubStar())) return;
    if (!requireCapability(config?.capabilities, "deepseek", onNeedKeys, tr("ui_create_project_text_llm_key"))) return;
    if (!form.brief.trim()) return toast.error(tr("ui_create_project_write_a_one_sentence_story_idea"));
    if (!form.genre.trim()) return toast.error(tr("ui_create_project_pick_a_genre_or_enter_a"));
    if (!form.visualStyle.trim()) return toast.error(tr("ui_create_project_pick_a_visual_style"));
    const requestInput = { ...form };
    setOptimizingBrief(true);
    try {
      const result = await api("/api/script-brief", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(requestInput),
      });
      const optimizedBrief = (result.brief || "").trim();
      if (!optimizedBrief) throw new Error(tr("ui_create_project_ai_didn_t_return_a_usable"));
      if (optimizedBrief !== requestInput.brief.trim()) {
        setBriefHistory((current) => [...current, requestInput.brief].slice(-10));
        setForm((current) => ({ ...current, brief: optimizedBrief }));
        toast.success(tr("ui_create_project_brief_polished_keep_editing_or_restore"));
      } else {
        toast.info(tr("ui_create_project_the_current_brief_is_already_complete"));
      }
    } catch (error) {
      toastMaybeKeys(error, onNeedKeys);
    } finally {
      setOptimizingBrief(false);
    }
  };

  const restoreBrief = () => {
    if (formLocked) return;
    const previousBrief = briefHistory.at(-1);
    if (previousBrief === undefined) return;
    setForm((current) => ({ ...current, brief: previousBrief }));
    setBriefHistory((current) => current.slice(0, -1));
    toast.success(tr("ui_create_project_restored_the_previous_brief"));
  };

  const create = async () => {
    if (optimizingBrief || autoRunning) return;
    if (!form.title.trim()) return toast.error(tr("ui_create_project_give_the_project_a_name_first"));
    if (!form.genre.trim()) return toast.error(tr("ui_create_project_pick_a_genre_or_enter_a"));
    if (!form.visualStyle.trim()) return toast.error(tr("ui_create_project_pick_a_visual_style"));
    setCreating(true);
    try {
      const bundle = await api("/api/projects", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      onCreated?.(bundle.project?.id);
    } catch (error) {
      toast.error(String(error.message || error));
    } finally {
      setCreating(false);
    }
  };

  const createAndAutoProduce = async () => {
    if (optimizingBrief || creating) return;
    if (!form.title.trim()) return toast.error(tr("ui_create_project_give_the_project_a_name_first"));
    if (!form.brief.trim()) return toast.error(tr("ui_create_project_write_a_one_sentence_idea_or"));
    if (!form.genre.trim()) return toast.error(tr("ui_create_project_pick_a_genre_or_enter_a"));
    if (!form.visualStyle.trim()) return toast.error(tr("ui_create_project_pick_a_visual_style"));
    if (!(await requireGithubStar())) return;
    if (!requireCapability(caps, "deepseek", onNeedKeys, tr("ui_create_project_text_llm_key"))) return;
    if (!caps.seedream || !caps.seedance) {
      toast.error(tr("ui_create_project_the_full_pipeline_needs_seedream_seedance"));
      onNeedKeys?.();
      return;
    }
    setAutoRunning(true);
    try {
      const res = await api("/api/auto-produce", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...form,
          episodeCount: 1,
          maxShots: 24,
          maxCharacters: 6,
          maxScenes: 4,
          forceIllustration: false,
          resolution: "720p",
        }),
      });
      toast.success(tr("ui_create_project_one_click_pipeline_started_producing_in"));
      onCreated?.(res.projectId);
    } catch (error) {
      toastMaybeKeys(error, onNeedKeys);
    } finally {
      setAutoRunning(false);
    }
  };

  return (
    <main className="min-h-screen p-2 md:p-3">
      <div className="yc-frame mx-0 w-full max-w-none p-3 md:p-4">
      <header className="overflow-hidden rounded-[22px] border border-white/10 bg-[linear-gradient(135deg,#15182a_0%,#1a1240_45%,#0d1b3a_100%)] text-white shadow-float">
        <div className="grid lg:grid-cols-[1fr_360px]">
          <div className="p-6 md:p-9">
            <button
              type="button"
              onClick={onBack}
              className="inline-flex items-center gap-2 text-xs font-semibold text-white/55 transition hover:text-white"
            >
              <ArrowLeft className="h-4 w-4" />{" "}{tr("ui_create_project_back_to_film_workshop")}</button>
            <div className="mt-10 flex items-center gap-3 text-xs font-bold uppercase tracking-[.2em] text-white/45">
              <Clapperboard className="h-4 w-4 text-[#b7acff]" /> New production
            </div>
            <h1 className="mt-3 text-4xl font-semibold md:text-5xl">
              {isUpload ? tr("ui_create_project_new_project_from_script") : entryMode?.id === "formal" ? tr("ui_create_project_drama_project") : tr("ui_create_project_new_project")}
            </h1>
            <p className="mt-4 max-w-3xl text-sm leading-7 text-white/60 md:text-base">
              {isUpload
                ? tr("ui_create_project_supports_txt_md_docx_after_import")
                : tr("ui_create_project_first_settle_the_story_direction_and")}
            </p>
          </div>
          <div className="relative border-t border-white/10 bg-black/20 p-6 lg:border-l lg:border-t-0 md:p-8">
            <div className="timecode text-[10px] text-[#b7acff]">PROJECT SETUP / 01</div>
            <p className="mt-4 text-sm leading-7 text-white/65">{tr("ui_create_project_this_is_your_working_draft_so")}</p>
            <ol className="mt-6 space-y-2 text-sm text-white/70">
              {creationSteps.map((step, i) => (
                <li key={step} className="flex gap-3 border-b border-white/10 py-2">
                  <span className="timecode text-[10px] text-[#b7acff]">{String(i + 1).padStart(2, "0")}</span>
                  {step}
                </li>
              ))}
            </ol>
          </div>
        </div>
      </header>

      {!config?.capabilities?.deepseek ? (
        <section className="mt-4 flex flex-col gap-3 rounded-2xl border border-[#f59e0b]/40 bg-[linear-gradient(90deg,rgba(245,158,11,.16),rgba(239,68,68,.1))] px-4 py-4 md:flex-row md:items-center md:justify-between md:px-5">
          <div className="text-sm text-white/85">
            <strong className="block">{tr("ui_create_project_ai_brief_polishing_needs_a_text")}</strong>
            <span className="mt-1 block text-white/60">{tr("ui_create_project_you_can_create_the_project_now")}</span>
          </div>
          <button type="button" className="btn-primary shrink-0" onClick={() => onNeedKeys?.()}>
            <KeyRound className="h-4 w-4" />{" "}{tr("ui_create_project_set_up_keys")}</button>
        </section>
      ) : null}

      <div className="mt-6 grid gap-6 xl:grid-cols-[minmax(0,1fr)_340px]">
        <div className="space-y-6">
          {isUpload ? (
            <section className="panel p-5 md:p-7">
              <div className="label">Script upload</div>
              <h2 className="display-type text-2xl font-semibold">{tr("ui_create_project_upload_script_file")}</h2>
              <p className="mt-1 text-sm leading-6 text-[var(--muted)]">{tr("ui_create_project_txt_markdown_word_docx_the_content")}</p>
              <input
                ref={fileRef}
                type="file"
                accept=".txt,.md,.markdown,.docx,text/plain,text/markdown,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                className="hidden"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  e.target.value = "";
                  void onPickScript(file);
                }}
              />
              <button
                type="button"
                className="btn-primary mt-5"
                disabled={formLocked}
                onClick={() => fileRef.current?.click()}
              >
                {parsing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
                {parsing ? tr("ui_create_project_parsing") : tr("ui_create_project_choose_file")}
              </button>
              {uploadName ? <p className="mt-3 text-xs text-[var(--muted)]">{tr("ui_create_project_imported", {
                  uploadName: uploadName
                })}</p> : null}
            </section>
          ) : null}
          <section className="panel p-5 md:p-7">
            <div className="label">Basic setup</div>
            <h2 className="display-type text-2xl font-semibold">{tr("ui_create_project_story_identity")}</h2>
            <p className="mt-1 text-sm leading-6 text-[var(--muted)]">{tr("ui_create_project_give_the_project_a_recognizable_name")}</p>
            <div className="mt-5 space-y-5">
              <label>
                <span className="label">{tr("ui_create_project_title")}</span>
                <input
                  className="field"
                  value={form.title}
                  onChange={(event) => setForm({ ...form, title: event.target.value })}
                  placeholder={tr("ui_create_project_e_g_the_last_bus_on")}
                  autoFocus
                  disabled={formLocked}
                />
              </label>
              <div>
                <span className="label">{tr("ui_create_project_genre")}</span>
                <GenrePicker
                  value={form.genre}
                  onChange={(genre) => setForm({ ...form, genre })}
                  disabled={formLocked}
                  genres={genres}
                />
              </div>
            </div>
          </section>

          <section className="panel p-5 md:p-7">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <div className="label">Story brief</div>
                <label htmlFor="project-brief" className="display-type block text-2xl font-semibold">{tr("ui_create_project_story_idea_original_story")}</label>
                <p className="mt-1 text-sm leading-6 text-[var(--muted)]">{tr("ui_create_project_write_one_sentence_a_detailed_outline")}</p>
              </div>
              <div className="flex flex-wrap justify-end gap-2">
                {briefHistory.length > 0 ? (
                  <button type="button" className="btn-secondary shrink-0" disabled={formLocked} onClick={restoreBrief}>
                    <RotateCcw className="h-4 w-4" />{tr("ui_create_project_restore_previous_version")}</button>
                ) : null}
                <button
                  type="button"
                  className="btn-secondary shrink-0"
                  disabled={!form.brief.trim() || !form.genre.trim() || !form.visualStyle.trim() || formLocked}
                  onClick={() => void optimizeBrief()}
                >
                  {optimizingBrief ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
                  {optimizingBrief ? tr("ui_create_project_polishing") : tr("ui_create_project_polish_brief_with_ai")}
                </button>
              </div>
            </div>
            <textarea
              id="project-brief"
              className="field mt-5 min-h-[420px] resize-y leading-7 md:min-h-[520px]"
              value={form.brief}
              onChange={(event) => setForm({ ...form, brief: event.target.value })}
              placeholder={tr("ui_create_project_describe_the_short_drama_you_want")}
              maxLength={100000}
              disabled={formLocked}
            />
            <div className="mt-3 flex flex-wrap items-center justify-between gap-3 text-xs text-[var(--muted)]">
              <span>{tr("ui_create_project_ai_keeps_the_characters_plot_points")}</span>
              <span className="timecode shrink-0">
                {form.brief.length} / 100000
              </span>
            </div>
          </section>

          <section className="panel p-5 md:p-7">
            <div className="label">Visual language</div>
            <h2 className="display-type text-2xl font-semibold">{tr("ui_create_project_visual_style")}</h2>
            <p className="mb-5 mt-1 text-sm leading-6 text-[var(--muted)]">{tr("ui_create_project_unifies_materials_color_lighting_and_composition")}</p>
            <VideoStylePicker
              value={form.visualStyle}
              onChange={(visualStyle) => setForm({ ...form, visualStyle })}
              disabled={formLocked}
              styles={styles}
              categories={config?.styleCategories}
            />
          </section>
        </div>

        <aside className="space-y-5 xl:sticky xl:top-6 xl:self-start">
          <section className="panel p-5">
            <div className="label">Frame</div>
            <h2 className="display-type text-xl font-semibold">{tr("ui_create_project_aspect_ratio")}</h2>
            <div className="mt-4">
              <AspectRatioPicker
                value={form.ratio}
                onChange={(ratio) => setForm({ ...form, ratio })}
                disabled={formLocked}
                ratios={ratios}
              />
            </div>
            <div className="panel-muted mt-4 p-4">
              <div className="timecode text-[10px] text-[var(--muted)]">PRODUCTION LOCK</div>
              <p className="mt-2 text-xs leading-6 text-[var(--muted)]">{tr("ui_create_project_the_frame_carries_through_characters_scenes")}</p>
            </div>
          </section>

          <section className="panel p-5">
            <div className="label">Ready</div>
            <h2 className="display-type text-xl font-semibold">{tr("ui_create_project_go_to_script_desk")}</h2>
            <p className="mt-2 text-sm leading-6 text-[var(--muted)]">{tr("ui_create_project_create_just_the_project_and_walk")}</p>
            <button type="button" className="btn-primary mt-5 w-full" disabled={formLocked} onClick={() => void createAndAutoProduce()}>
              {autoRunning ? <Loader2 className="h-4 w-4 animate-spin" /> : <Wand2 className="h-4 w-4" />}
              {autoRunning ? tr("ui_create_project_starting_pipeline") : tr("ui_create_project_one_click_full_production")}
            </button>
            <button type="button" className="btn-secondary mt-2 w-full" disabled={formLocked} onClick={() => void create()}>
              {creating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
              {creating ? tr("ui_create_project_creating") : tr("ui_create_project_create_project_only")}
            </button>
            <button type="button" className="btn-ghost mt-2 w-full" disabled={formLocked} onClick={onBack}>{tr("ui_create_project_cancel")}</button>
          </section>
        </aside>
      </div>
      </div>
    </main>
  );
}
