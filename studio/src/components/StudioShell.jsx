import {
  ArrowLeft,
  Box,
  Clapperboard,
  Image as ImageIcon,
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

const STEPS = [
  { key: "script", label: "剧本", note: "故事与分集", icon: ScrollText },
  { key: "character", label: "角色", note: "人物与造型", icon: Users },
  { key: "scene", label: "场景", note: "空间与光线", icon: ImageIcon },
  { key: "prop", label: "道具", note: "关键物件", icon: Box },
  { key: "storyboard", label: "分镜", note: "镜头与视频", icon: Clapperboard },
  { key: "edit", label: "剪辑", note: "排序与成片", icon: Scissors },
];

function stepCounts(bundle) {
  if (!bundle) {
    return { script: "0 集", character: "0", scene: "0", prop: "0", storyboard: "0 镜", edit: "未开始" };
  }
  const ents = (bundle.entities || []).filter((e) => !e.deletedAt);
  const shots = (bundle.shots || []).filter((s) => !s.deletedAt);
  const successful = shots.filter((s) => s.status === "success").length;
  return {
    script: `${(bundle.episodes || []).length} 集`,
    character: String(ents.filter((e) => e.kind === "character").length),
    scene: String(ents.filter((e) => e.kind === "scene").length),
    prop: String(ents.filter((e) => e.kind === "prop").length),
    storyboard: `${successful}/${shots.length} 镜`,
    edit: (bundle.edits || []).some((e) => e.outputPath) ? "已成片" : "未成片",
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
  const activeMeta = STEPS.find((s) => s.key === step) || STEPS[0];

  const common = {
    projectId,
    bundle,
    config,
    setBusyMsg,
    onBundle,
    onRefresh,
  };

  if (loading && !bundle) {
    return (
      <div className="flex min-h-screen items-center justify-center text-sm text-[var(--muted)]">
        <Loader2 className="mr-2 h-4 w-4 animate-spin" /> 正在开机片场…
      </div>
    );
  }

  return (
    <main className="min-h-screen bg-[var(--stage)] lg:h-screen lg:overflow-hidden">
      <div className="grid min-h-screen lg:h-screen lg:grid-cols-[270px_1fr]">
        <aside className="relative overflow-hidden bg-[var(--navy)] text-white lg:h-screen">
          <div className="absolute bottom-0 left-0 top-0 w-6 film-perforation opacity-60" />
          <div className="ml-6 flex h-full flex-col">
            <div className="border-b border-white/10 px-5 py-5">
              <div className="timecode mb-3 text-[10px] font-semibold tracking-[.16em] text-[var(--timecode)]">
                影视工坊 · OpenMontage
              </div>
              <button
                type="button"
                onClick={onBack}
                className="inline-flex items-center gap-2 text-xs font-semibold text-white/55 hover:text-white"
              >
                <ArrowLeft className="h-3.5 w-3.5" /> 返回片库
              </button>
              <h1 className="display-type mt-4 line-clamp-2 text-2xl font-semibold leading-tight">
                {project.title || projectId}
              </h1>
              <div className="timecode mt-2 text-[10px] text-[var(--timecode)]">
                LOCAL / {project.ratio || "9:16"} / {project.genre || "—"}
              </div>
            </div>
            <nav className="flex gap-1 overflow-x-auto p-3 lg:block lg:flex-1 lg:space-y-1 lg:overflow-y-auto" aria-label="制作步骤">
              {STEPS.map((item, index) => {
                const Icon = item.icon;
                const active = item.key === step;
                return (
                  <button
                    key={item.key}
                    type="button"
                    onClick={() => setStep(item.key)}
                    className={`group flex min-w-40 items-center gap-3 rounded-xl border px-3 py-3 text-left transition lg:w-full ${
                      active
                        ? "border-[var(--projector)]/40 bg-[var(--projector)]/10"
                        : "border-transparent hover:bg-white/5"
                    }`}
                  >
                    <span
                      className={`timecode flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-xs ${
                        active ? "bg-[var(--projector)] text-[var(--navy)]" : "bg-white/8 text-white/45"
                      }`}
                    >
                      {String(index + 1).padStart(2, "0")}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className={`flex items-center gap-1.5 text-sm font-semibold ${active ? "text-white" : "text-white/75"}`}>
                        <Icon className="h-3.5 w-3.5" />
                        {item.label}
                      </span>
                      <span className="mt-0.5 block truncate text-[10px] text-white/38">
                        {item.note} · {counts[item.key]}
                      </span>
                    </span>
                  </button>
                );
              })}
            </nav>
            <div className="border-t border-white/10 p-4">
              <div className="flex items-center justify-between text-[10px] text-white/35">
                <span>DeepSeek {caps.deepseek ? "就绪" : "未配置"}</span>
                <span className={`h-1.5 w-1.5 rounded-full ${caps.deepseek ? "bg-[var(--projector)]" : "bg-white/25"}`} />
              </div>
              <div className="mt-1 text-[10px] text-white/35">
                Seedream {caps.seedream ? "✓" : "—"} · Seedance {caps.seedance ? "✓" : "—"} · 无登录积分
              </div>
            </div>
          </div>
        </aside>

        <section className="relative min-w-0 lg:h-screen lg:overflow-hidden">
          {(busyMsg || loading) && (
            <div className="absolute inset-x-0 top-16 z-20 flex items-center justify-center gap-2 bg-[var(--navy)]/90 px-4 py-2 text-sm text-white">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              {busyMsg || "加载中…"}
            </div>
          )}
          <header className="flex h-16 items-center justify-between border-b border-[var(--line)] bg-white/85 px-4 backdrop-blur md:px-7">
            <div>
              <div className="label !mb-0">
                Stage {String(STEPS.findIndex((s) => s.key === step) + 1).padStart(2, "0")}
              </div>
              <h2 className="display-type text-xl font-semibold">{activeMeta.label}</h2>
            </div>
            <button type="button" className="btn-secondary !min-h-9" onClick={onRefresh} disabled={loading}>
              <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} /> 刷新
            </button>
          </header>
          <div className="scrollbar-thin min-h-[calc(100vh-4rem)] overflow-y-auto p-4 md:p-7 lg:h-[calc(100vh-4rem)]">
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
