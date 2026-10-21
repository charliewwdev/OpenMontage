import { useEffect, useState } from "react";
import { Sparkles } from "lucide-react";
import { api } from "../api";

const LABELS = {
  "script-brief": "爽剧创作需求优化",
  "drama-script": "分集剧本生成",
  "drama-entity-still": "资产定妆图",
  "drama-shot-prompt": "影视分镜提示词",
  "portrait-idlock": "写真对标 · 首尾帧身份锁",
};

/**
 * Visible Skill expert chip for workshop steps.
 * Fetches experience summary from the skills catalog (cacheable, non-blocking).
 */
export function SkillExpertBadge({ skillId, title, accent = "#7c6cff", className = "" }) {
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
      title={`当前步骤由 Skill「${skillId}」驱动`}
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
        <span className="rounded-full bg-emerald-500/15 px-1.5 py-0.5 text-[10px] text-emerald-200/90">
          经验 {patches} · 命中 {hits}
        </span>
      ) : (
        <span className="text-[10px] text-white/35">工坊运行时已绑定</span>
      )}
    </div>
  );
}
