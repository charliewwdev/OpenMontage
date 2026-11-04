import { useEffect, useState } from "react";
import { Sparkles } from "lucide-react";
import { api } from "../api";

import { tr, useLocale } from "../lib/i18n";

const LABELS = {
  get "script-brief"() {
    return tr("ui_skill_expert_badge_hit_drama_brief_optimization");
  },

  get "drama-script"() {
    return tr("ui_skill_expert_badge_episode_script_generation");
  },

  get "drama-entity-still"() {
    return tr("ui_skill_expert_badge_asset_look_images");
  },

  get "drama-shot-prompt"() {
    return tr("ui_skill_expert_badge_film_storyboard_prompts");
  },

  get "portrait-idlock"() {
    return tr("ui_skill_expert_badge_portrait_benchmark_first_last_frame_identity");
  }
};

/**
 * Visible Skill expert chip for workshop steps.
 * Fetches experience summary from the skills catalog (cacheable, non-blocking).
 */
export function SkillExpertBadge({ skillId, title, accent = "#7c6cff", className = "" }) {
  useLocale();
  const [exp, setExp] = useState(null);
  const label = title || LABELS[skillId] || skillId;

  useEffect(() => {
    if (!skillId) return undefined;
    let cancelled = false;
    (async () => {
      try {
        const data = await api("/api/platform/skills");
        const hit = (data.skills || []).find((s) => s.id === skillId);
        if (!cancelled) setExp(hit?.experience || null);
      } catch {
        if (!cancelled) setExp(null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [skillId]);

  if (!skillId) return null;

  const patches = exp?.patchCount || 0;
  const hits = exp?.totalHits || 0;

  return (
    <div
      className={`inline-flex max-w-full flex-wrap items-center gap-1.5 rounded-lg border border-white/10 bg-white/[.04] px-2.5 py-1.5 text-[11px] text-white/75 ${className}`}
      title={tr("ui_skill_expert_badge_this_step_is_driven_by_skill", {
        skillId: skillId
      })}
    >
      <span
        className="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-md"
        style={{ background: `${accent}33`, color: accent }}
      >
        <Sparkles className="h-3 w-3" />
      </span>
      <span className="font-medium text-white/90">{label}</span>
      <span className="font-mono text-[10px] text-white/35">/{skillId}</span>
      {patches > 0 || hits > 0 ? (
        <span className="rounded-full bg-emerald-500/15 px-1.5 py-0.5 text-[10px] text-emerald-200/90">{tr("ui_skill_expert_badge_experience_hits", {
            patches: patches,
            hits: hits
          })}</span>
      ) : (
        <span className="text-[10px] text-white/35">{tr("ui_skill_expert_badge_bound_to_workshop_runtime")}</span>
      )}
    </div>
  );
}
