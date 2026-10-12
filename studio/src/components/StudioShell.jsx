import { STEPS } from "../config/options";
import { ScriptStep } from "./steps/ScriptStep";
import { EntityStep } from "./steps/EntityStep";
import { StoryboardStep } from "./steps/StoryboardStep";
import { EditStep } from "./steps/EditStep";

function stepCounts(bundle) {
  const eps = bundle?.episodes || [];
  const ents = (bundle?.entities || []).filter((e) => !e.deletedAt);
  const shots = (bundle?.shots || []).filter((s) => !s.deletedAt);
  return {
    script: eps.length,
    character: ents.filter((e) => e.kind === "character").length,
    scene: ents.filter((e) => e.kind === "scene").length,
    prop: ents.filter((e) => e.kind === "prop").length,
    storyboard: shots.length,
    edit: (bundle?.edits || []).length,
  };
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
}) {
  const project = bundle?.project || {};
  const counts = stepCounts(bundle);
  const caps = config?.capabilities || {};

  const common = {
    projectId,
    bundle,
    config,
    setBusyMsg,
    onBundle,
    onRefresh,
  };

  return (
    <div className="flex min-h-full">
      <aside className="flex w-[220px] shrink-0 flex-col border-r border-[var(--line)] bg-[var(--navy)] text-white">
        <div className="border-b border-white/10 px-4 py-4">
          <button type="button" className="text-xs text-white/60 hover:text-white" onClick={onBack}>
            ← 片库
          </button>
          <h1 className="display-type mt-2 line-clamp-2 text-lg leading-snug">{project.title || projectId}</h1>
          <p className="mt-1 text-[11px] text-white/50">
            {project.genre} · {project.ratio}
          </p>
        </div>
        <nav className="flex-1 space-y-1 p-2">
          {STEPS.map((s, i) => {
            const active = step === s.key;
            return (
              <button
                key={s.key}
                type="button"
                className={`flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left transition ${
                  active ? "bg-white/12 text-white" : "text-white/65 hover:bg-white/6 hover:text-white"
                }`}
                onClick={() => setStep(s.key)}
              >
                <span className="timecode text-[11px] text-[var(--projector)]">{String(i + 1).padStart(2, "0")}</span>
                <span className="flex-1">
                  <span className="block text-sm font-medium">{s.label}</span>
                  <span className="block text-[11px] opacity-60">{s.note}</span>
                </span>
                <span className="timecode rounded-md bg-white/10 px-1.5 py-0.5 text-[10px]">{counts[s.key] || 0}</span>
              </button>
            );
          })}
        </nav>
        <div className="border-t border-white/10 p-3 text-[11px] text-white/45">
          <div>DeepSeek {caps.deepseek ? "✓" : "—"}</div>
          <div>Seedream {caps.seedream ? "✓" : "—"}</div>
          <div>Seedance {caps.seedance ? "✓" : "—"}</div>
          <button type="button" className="mt-2 text-[var(--projector)] hover:underline" onClick={onRefresh}>
            刷新状态
          </button>
        </div>
      </aside>

      <main className="relative flex min-w-0 flex-1 flex-col">
        {(loading || busyMsg) && (
          <div className="absolute inset-x-0 top-0 z-20 flex items-center justify-center gap-2 bg-[var(--navy)]/90 px-4 py-2 text-sm text-white">
            <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-[var(--projector)]" />
            {busyMsg || "加载中…"}
          </div>
        )}
        <div className="flex-1 overflow-auto p-4 md:p-6">
          {step === "script" && <ScriptStep {...common} />}
          {step === "character" && <EntityStep {...common} kind="character" />}
          {step === "scene" && <EntityStep {...common} kind="scene" />}
          {step === "prop" && <EntityStep {...common} kind="prop" />}
          {step === "storyboard" && <StoryboardStep {...common} />}
          {step === "edit" && <EditStep {...common} />}
        </div>
      </main>
    </div>
  );
}
