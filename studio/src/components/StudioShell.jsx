import {
  ArrowLeft,
  Box,
  Check,
  Clapperboard,
  Image as ImageIcon,
  KeyRound,
  Loader2,
  RefreshCw,
  Scissors,
  ScrollText,
  Users,
} from "lucide-react";
import { ScriptStep } from "./steps/ScriptStep";
import { EntityStep } from "./steps/EntityStep";
import { StoryboardStep } from "./steps/StoryboardStep";
import { EditStep } from "./steps/EditStep";

const STEP_ICONS = {
  script: ScrollText,
  character: Users,
  scene: ImageIcon,
  prop: Box,
  storyboard: Clapperboard,
  edit: Scissors,
};

function stepCounts(bundle) {
  if (!bundle) {
    return { script: "0 集", character: "0", scene: "0", prop: "0", storyboard: "0 镜", edit: "未开始" };
  }
  const ents = (bundle.entities || []).filter((e) => !e.deletedAt);
  const shots = (bundle.shots || []).filter((s) => !s.deletedAt);
  const successful = shots.filter((s) => s.status === "success").length;
  const episodes = bundle.episodes || [];
  const confirmed = episodes.filter((e) => e.status === "confirmed").length;
  return {
    script: `${confirmed}/${episodes.length} 集定稿`,
    character: String(ents.filter((e) => e.kind === "character").length),
    scene: String(ents.filter((e) => e.kind === "scene").length),
    prop: String(ents.filter((e) => e.kind === "prop").length),
    storyboard: `${successful}/${shots.length} 镜`,
    edit: (bundle.edits || []).some((e) => e.outputPath) ? "已成片" : "未成片",
  };
}

function stepDone(bundle, key) {
  if (!bundle) return false;
  const counts = stepCounts(bundle);
  if (key === "script") return (bundle.episodes || []).some((e) => e.status === "confirmed");
  if (key === "character") return Number(counts.character) > 0;
  if (key === "scene") return Number(counts.scene) > 0;
  if (key === "prop") return Number(counts.prop) > 0;
  if (key === "storyboard") return (bundle.shots || []).some((s) => !s.deletedAt);
  if (key === "edit") return (bundle.edits || []).some((e) => e.outputPath);
  return false;
}

export function StudioShell({
  projectId,
  bundle,
  loading,
  step,
  setStep,
  config,
  busyMsg,
  setBusyMsg,
  onBack,
  onRefresh,
  onBundle,
  onNeedKeys,
}) {
  const project = bundle?.project || {};
  const counts = stepCounts(bundle);
  const caps = config?.capabilities || {};
  const steps = (config?.six_steps || []).map((s) => ({
    key: s.id,
    label: s.label,
    note: s.note || "",
    icon: STEP_ICONS[s.id] || Clapperboard,
  }));
  const activeMeta = steps.find((s) => s.key === step) || steps[0] || { key: step, label: step, note: "", icon: Clapperboard };
  const keysMissing = !(caps.deepseek && caps.seedream && caps.seedance);

  const common = {
    projectId,
    bundle,
    config,
    setBusyMsg,
    onBundle,
    onRefresh,
    onNeedKeys,
  };

  if (loading && !bundle) {
    return (
      <div className="flex min-h-screen items-center justify-center text-sm text-[var(--muted)]">
        <Loader2 className="mr-2 h-4 w-4 animate-spin" /> 正在开机片场…
      </div>
    );
  }

  return (
    <main className="min-h-screen lg:h-screen lg:overflow-hidden">
      <div className="grid min-h-screen lg:h-screen lg:grid-cols-[92px_1fr]">
        <aside className="border-r border-[var(--line)] bg-[#0a0b10] lg:h-screen">
          <div className="flex gap-1 overflow-x-auto p-2 lg:h-full lg:flex-col lg:overflow-y-auto lg:py-4">
            {steps.map((item, index) => {
              const Icon = item.icon;
              const active = item.key === step;
              const done = stepDone(bundle, item.key);
              return (
                <button
                  key={item.key}
                  type="button"
                  onClick={() => setStep(item.key)}
                  className={`flex min-w-[72px] flex-col items-center gap-2 rounded-2xl px-2 py-3 text-center transition lg:min-w-0 ${
                    active ? "bg-white/[.06]" : "hover:bg-white/[.03]"
                  }`}
                >
                  <span
                    className={`relative flex h-10 w-10 items-center justify-center rounded-full border text-sm ${
                      active
                        ? "border-transparent bg-[var(--gradient)] text-white shadow-[0_0_20px_rgba(124,108,255,.45)]"
                        : done
                          ? "border-[var(--ok)]/40 bg-[var(--ok)]/15 text-[var(--ok)]"
                          : "border-white/10 bg-white/[.03] text-white/45"
                    }`}
                  >
                    {done && !active ? <Check className="h-4 w-4" /> : <Icon className="h-4 w-4" />}
                    <span className="timecode absolute -right-1 -top-1 rounded-full bg-black/70 px-1 text-[8px] text-white/50">
                      {index + 1}
                    </span>
                  </span>
                  <span className="min-w-0">
                    <span className={`block text-xs font-semibold ${active ? "text-white" : "text-white/70"}`}>
                      {item.label}
                    </span>
                    <span className="mt-0.5 block truncate text-[9px] text-white/35">{counts[item.key]}</span>
                  </span>
                </button>
              );
            })}
          </div>
        </aside>

        <section className="relative min-w-0 lg:h-screen lg:overflow-hidden">
          {(busyMsg || loading) && (
            <div className="absolute inset-x-0 top-16 z-20 flex items-center justify-center gap-2 bg-[#7c6cff]/90 px-4 py-2 text-sm text-white">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              {busyMsg || "加载中…"}
            </div>
          )}
          <header className="flex h-16 items-center justify-between border-b border-[var(--line)] bg-[#0c0e14]/90 px-4 backdrop-blur md:px-6">
            <div className="min-w-0">
              <button
                type="button"
                onClick={onBack}
                className="inline-flex items-center gap-1.5 text-xs text-white/45 hover:text-white"
              >
                <ArrowLeft className="h-3.5 w-3.5" /> 返回工坊
              </button>
              <div className="mt-0.5 flex flex-wrap items-center gap-2">
                <h1 className="truncate text-lg font-semibold">{project.title || projectId}</h1>
                <span className="rounded-full border border-white/10 bg-white/[.04] px-2 py-0.5 text-[10px] text-white/55">
                  {project.genre || "题材未设"}
                </span>
                <span className="rounded-full border border-white/10 bg-white/[.04] px-2 py-0.5 text-[10px] text-white/55">
                  {project.ratio || "9:16"}
                </span>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <div className="hidden text-[10px] text-white/35 sm:block">
                DeepSeek {caps.deepseek ? "就绪" : "未配置"} · Seedream {caps.seedream ? "✓" : "—"} · Seedance{" "}
                {caps.seedance ? "✓" : "—"}
              </div>
              {keysMissing ? (
                <button type="button" className="btn-secondary !min-h-9" onClick={() => onNeedKeys?.()}>
                  <KeyRound className="h-3.5 w-3.5" /> 配置密钥
                </button>
              ) : null}
              <button type="button" className="btn-secondary !min-h-9" onClick={onRefresh} disabled={loading}>
                <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} /> 刷新
              </button>
            </div>
          </header>
          {keysMissing ? (
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[#f59e0b]/30 bg-[#f59e0b]/10 px-4 py-2.5 text-xs text-[#fde68a] md:px-6">
              <span>当前步骤可能需要 API Key。未配置时会报错，可一键跳转配置并立即生效。</span>
              <button type="button" className="btn-primary !min-h-8 !px-3" onClick={() => onNeedKeys?.()}>
                <KeyRound className="h-3.5 w-3.5" /> 一键配置
              </button>
            </div>
          ) : null}
          <div className="border-b border-[var(--line)] bg-black/20 px-4 py-2 md:px-6">
            <div className="label !mb-0">Stage {String(Math.max(0, steps.findIndex((s) => s.key === step)) + 1).padStart(2, "0")}</div>
            <h2 className="text-base font-semibold">{activeMeta.label}</h2>
          </div>
          <div className="scrollbar-thin min-h-[calc(100vh-7.5rem)] overflow-y-auto p-4 md:p-6 lg:h-[calc(100vh-7.5rem)]">
            {step === "script" && <ScriptStep {...common} />}
            {step === "character" && <EntityStep {...common} kind="character" />}
            {step === "scene" && <EntityStep {...common} kind="scene" />}
            {step === "prop" && <EntityStep {...common} kind="prop" />}
            {step === "storyboard" && <StoryboardStep {...common} />}
            {step === "edit" && <EditStep {...common} />}
          </div>
        </section>
      </div>
    </main>
  );
}
