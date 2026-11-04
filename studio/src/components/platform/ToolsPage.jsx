import { useState } from "react";
import { ArrowUp, Clapperboard, Film, Mic2, Palette, PenLine, Sparkles, Workflow } from "lucide-react";
import { PageShell } from "./PageShell";

import { tr, useLocale } from "../../lib/i18n";

const ICONS = {
  text: PenLine,
  visual: Palette,
  audio: Mic2,
  video: Film,
  workshop: Clapperboard,
  canvas: Workflow,
};

const DEFAULT_CATEGORIES = [
  {
    id: "text",

    get title() {
      return tr("ui_tools_text_creation");
    },

    get desc() {
      return tr("ui_tools_ai_scripts_short_drama_scripts_film");
    },

    accent: "from-[#1d4ed8] to-[#60a5fa]",
    nav: "workshop",
    step: "script"
  },
  {
    id: "visual",

    get title() {
      return tr("ui_tools_visual_creation");
    },

    get desc() {
      return tr("ui_tools_concept_design_character_art_scene_painting");
    },

    accent: "from-[#9d174d] to-[#f472b6]",
    nav: "workshop",
    step: "character"
  },
  {
    id: "audio",

    get title() {
      return tr("ui_tools_audio_creation");
    },

    get desc() {
      return tr("ui_tools_voice_synthesis_sound_design_background_music");
    },

    accent: "from-[#c2410c] to-[#fb923c]",
    nav: "help"
  },
  {
    id: "video",

    get title() {
      return tr("ui_tools_video_creation");
    },

    get desc() {
      return tr("ui_tools_ai_video_generation_motion_storyboards_compositing");
    },

    accent: "from-[#047857] to-[#34d399]",
    nav: "workshop",
    step: "storyboard"
  },
  {
    id: "workshop",

    get title() {
      return tr("ui_tools_film_workshop");
    },

    get desc() {
      return tr("ui_tools_professional_scenario_workflows_for_short_dramas");
    },

    accent: "from-[#4c1d95] to-[#8b5cf6]",
    nav: "workshop"
  },
  {
    id: "canvas",

    get title() {
      return tr("ui_tools_canvas_creation");
    },

    get desc() {
      return tr("ui_tools_visual_workflow_builder_connect_multiple_ai");
    },

    accent: "from-[#a16207] to-[#fbbf24]",
    nav: "canvas"
  },
];

const DEFAULT_WORKFLOW = {
  get title() {
    return tr("ui_tools_the_complete_ai_short_drama_workflow");
  },

  get description() {
    return tr("ui_tools_direct_your_ai_production_the_platform");
  },

  steps: [
    {
      get title() {
        return tr("ui_tools_script");
      },

      get desc() {
        return tr("ui_tools_ai_writes_a_shooting_script_with");
      }
    },
    {
      get title() {
        return tr("ui_tools_casting");
      },

      get desc() {
        return tr("ui_tools_ai_generates_virtual_character_looks_and");
      }
    },
    {
      get title() {
        return tr("ui_tools_shoot");
      },

      get desc() {
        return tr("ui_tools_ai_image_to_video_brings_still");
      }
    },
    {
      get title() {
        return tr("ui_tools_voice");
      },

      get desc() {
        return tr("ui_tools_ai_generates_background_music_sound_effects");
      }
    },
    {
      get title() {
        return tr("ui_tools_edit");
      },

      get desc() {
        return tr("ui_tools_cut_the_material_into_a_complete");
      }
    },
  ]
};

export function ToolsPage({ config, onOpenTool, onNavigate, onStartCreate }) {
  useLocale();
  const page = config?.pages?.tools || {};
  const hub = config?.toolHub || {};
  const categories = hub.categories?.length ? hub.categories : DEFAULT_CATEGORIES;
  const workflow = hub.workflow || DEFAULT_WORKFLOW;
  const [prompt, setPrompt] = useState("");

  const openCategory = (cat) => {
    if (cat.nav === "workshop") {
      onOpenTool?.({ nav: "workshop", step: cat.step });
      return;
    }
    onNavigate?.(cat.nav);
  };

  const startCreate = () => {
    const text = prompt.trim();
    if (!text) return;
    onStartCreate?.(text);
  };

  return (
    <PageShell
      eyebrow={page.eyebrow || "Creation center"}
      title={page.title || tr("ui_tools_ai_creation_hub")}
      description={page.description || tr("ui_tools_describe_your_idea_directly_or_pick")}
    >
      {/* Hero band — 对齐有彩顶部氛围条 */}
      <div className="relative mb-6 overflow-hidden rounded-2xl border border-white/10">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_20%_20%,rgba(124,108,255,.35),transparent_50%),radial-gradient(ellipse_at_80%_0%,rgba(56,189,248,.2),transparent_45%),linear-gradient(135deg,#0b1020,#12182c_55%,#1a1030)]" />
        <div className="relative px-5 py-10 md:px-8 md:py-14">
          <div className="label !mb-2 !text-white/50">OPENMONTAGE</div>
          <h2 className="max-w-xl text-2xl font-semibold text-white md:text-3xl">{tr("ui_tools_from_a_one_line_idea_to")}</h2>
          <p className="mt-2 max-w-lg text-sm text-white/60">{tr("ui_tools_text_visual_audio_video_workshop_canvas")}</p>
        </div>
      </div>

      {/* Prompt composer */}
      <section className="panel mb-8 p-5 md:p-6">
        <div className="mb-3 flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-[#a78bfa]" />
          <h3 className="text-base font-semibold">{tr("ui_tools_say_your_idea_and_turn_it")}</h3>
          <span className="rounded-full bg-[#7c6cff]/15 px-2 py-0.5 text-[10px] text-[#c4b5fd]">{tr("ui_tools_creation_agent")}</span>
        </div>
        <p className="mb-4 text-sm text-[var(--muted)]">{tr("ui_tools_describe_your_idea_the_agent_calls")}</p>
        <label className="block">
          <span className="sr-only">{tr("ui_tools_describe_what_you_want_to_create")}</span>
          <textarea
            className="field min-h-[120px] resize-y !py-3"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder={tr("ui_tools_e_g_a_summer_poster_for")}
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                e.preventDefault();
                startCreate();
              }
            }}
          />
        </label>
        <div className="mt-3 flex justify-end">
          <button type="button" className="btn-primary" disabled={!prompt.trim()} onClick={startCreate}>
            <ArrowUp className="h-3.5 w-3.5" />{" "}{tr("ui_tools_start_creating")}</button>
        </div>
      </section>

      {/* Category cards 2×3 */}
      <div className="mb-10 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {categories.map((cat) => {
          const Icon = ICONS[cat.id] || Sparkles;
          return (
            <button
              key={cat.id}
              type="button"
              className={`relative overflow-hidden rounded-2xl border border-white/10 bg-gradient-to-br ${cat.accent || "from-[#312e81] to-[#7c6cff]"} p-5 text-left text-white shadow-lg transition hover:-translate-y-0.5 hover:brightness-110`}
              onClick={() => openCategory(cat)}
            >
              <Icon className="mb-6 h-7 w-7 opacity-90" />
              <strong className="block text-lg">{cat.title}</strong>
              <p className="mt-2 text-sm leading-6 text-white/80">{cat.desc}</p>
            </button>
          );
        })}
      </div>

      {/* Workflow */}
      <section className="mb-8">
        <h3 className="text-lg font-semibold">{workflow.title}</h3>
        <p className="mt-2 max-w-3xl text-sm text-[var(--muted)]">{workflow.description}</p>
        <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          {(workflow.steps || []).map((step, index) => {
            const stepMap = {
              定剧本: "script",
              选演员: "character",
              拍画面: "storyboard",
              做配音: "audio",
              剪成片: "edit",
            };
            const workshopStep = stepMap[step.title] || step.step;
            return (
              <button
                key={step.title}
                type="button"
                className="panel p-4 text-left transition hover:-translate-y-0.5 hover:border-white/20"
                onClick={() => onOpenTool?.({ nav: "workshop", step: workshopStep })}
              >
                <div className="mb-3 flex h-8 w-8 items-center justify-center rounded-full bg-[var(--gradient)] text-sm font-bold text-white">
                  {index + 1}
                </div>
                <strong className="block text-sm">{step.title}</strong>
                <p className="mt-2 text-xs leading-5 text-[var(--muted)]">{step.desc}</p>
              </button>
            );
          })}
        </div>
      </section>

      {/* Workshop CTA */}
      <section className="overflow-hidden rounded-2xl border border-white/10 bg-gradient-to-r from-[#1e1b4b] via-[#312e81] to-[#4c1d95] p-6 md:flex md:items-center md:justify-between md:gap-6">
        <div>
          <h3 className="text-lg font-semibold text-white">{tr("ui_tools_film_creation_workshop")}</h3>
          <p className="mt-2 text-sm text-white/70">{tr("ui_tools_from_script_to_final_cut_ai")}</p>
          <p className="mt-1 text-xs text-white/45">{tr("ui_tools_ai_scripts_one_click_assets_smart")}</p>
        </div>
        <button
          type="button"
          className="btn-primary mt-4 shrink-0 md:mt-0"
          onClick={() => onOpenTool?.({ nav: "workshop" })}
        >{tr("ui_tools_open_film_workshop")}</button>
      </section>
    </PageShell>
  );
}
