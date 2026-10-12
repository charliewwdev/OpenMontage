import {
  ArrowLeft,
  Box,
  Clapperboard,
  Image as ImageIcon,
  LayoutGrid,
  Loader2,
  RefreshCw,
  Scissors,
  ScrollText,
  Users,
  Workflow,
} from "lucide-react";
import { DESKS, STEPS, deriveProjectView } from "../lib/projectModel";
import { ScriptStep } from "./steps/ScriptStep";
import { EntityStep } from "./steps/EntityStep";
import { StoryboardStep } from "./steps/StoryboardStep";
import { EditStep } from "./steps/EditStep";
import { CanvasDesk } from "./CanvasDesk";

const STEP_ICONS = {
  script: ScrollText,
  characters: Users,
  locations: ImageIcon,
  props: Box,
  storyboard: Clapperboard,
  edit: Scissors,
};

const DESK_ICONS = {
  director: Workflow,
  canvas: LayoutGrid,
  edit: Scissors,
};

export function StudioShell({
  project,
  bundle,
  loading,
  desk,
  setDesk,
  step,
  setStep,
  onBack,
  onRefresh,
  onBundle,
  pipeline,
  subgraphs,
  selectedSubgraph,
  setSelectedSubgraph,
  subgraphDoc,
  canvasSource,
  setCanvasSource,
  genState,
  onGenerate,
  caps,
}) {
  const view = deriveProjectView(bundle);

  if (loading && !bundle) {
    return (
      <div className="flex min-h-screen items-center justify-center text-sm text-[var(--muted)]">
        <Loader2 className="mr-2 h-4 w-4 animate-spin" /> 正在开机片场…
      </div>
    );
  }

  if (!bundle || !view) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4">
        <p>项目不存在或无法读取。</p>
        <button type="button" className="btn-secondary" onClick={onBack}>
          返回片库
        </button>
      </div>
    );
  }

  const activeStepMeta = STEPS.find((s) => s.id === step) || STEPS[0];
  const stepIndex = STEPS.findIndex((s) => s.id === step);

  return (
    <main className="min-h-screen bg-[var(--stage)] lg:h-screen lg:overflow-hidden">
      <div className="grid min-h-screen lg:h-screen lg:grid-cols-[270px_1fr]">
        <aside className="relative overflow-hidden bg-[var(--navy)] text-white lg:h-screen">
          <div className="absolute bottom-0 left-0 top-0 w-6 film-perforation opacity-60" />
          <div className="ml-6 flex h-full flex-col">
            <div className="border-b border-white/10 px-5 py-5">
              <div className="timecode mb-3 text-[10px] font-semibold tracking-[.16em] text-[var(--timecode)]">
                OpenMontage Drama
              </div>
              <button
                type="button"
                onClick={onBack}
                className="inline-flex items-center gap-2 text-xs font-semibold text-white/55 hover:text-white"
              >
                <ArrowLeft className="h-3.5 w-3.5" /> 返回片库
              </button>
              <h1 className="display-type mt-4 line-clamp-2 text-2xl font-semibold leading-tight">{view.title}</h1>
              <div className="timecode mt-2 text-[10px] text-[var(--timecode)]">
                LOCAL / {view.ratio} / {view.genre}
              </div>
            </div>

            <nav className="flex gap-1 overflow-x-auto p-3 lg:block lg:flex-1 lg:space-y-1 lg:overflow-y-auto" aria-label="制作步骤">
              {STEPS.map((s, index) => {
                const Icon = STEP_ICONS[s.id];
                const active = s.id === step && desk === "director";
                return (
                  <button
                    key={s.id}
                    type="button"
                    onClick={() => {
                      setStep(s.id);
                      setDesk(s.id === "edit" ? "edit" : "director");
                    }}
                    className={`group flex min-w-40 items-center gap-3 rounded-xl border px-3 py-3 text-left transition lg:w-full ${
                      active ? "border-[var(--projector)]/40 bg-[var(--projector)]/10" : "border-transparent hover:bg-white/5"
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
                        {s.label}
                      </span>
                      <span className="mt-0.5 block truncate text-[10px] text-white/38">
                        {s.note} · {view.counts[s.id]}
                      </span>
                    </span>
                  </button>
                );
              })}
            </nav>

            <div className="border-t border-white/10 p-4">
              <div className="flex items-center justify-between text-[10px] text-white/35">
                <span>{caps?.mode === "online" ? "在线能力已接入" : "离线拆解模式"}</span>
                <span className="h-1.5 w-1.5 rounded-full bg-[var(--projector)]" />
              </div>
              <div className="mt-1 text-[10px] text-white/35">
                {caps ? `${caps.configured}/${caps.total} keys` : "—"}
                {caps?.ffmpeg ? " · FFmpeg" : ""} · openmontage.dtok.io
              </div>
            </div>
          </div>
        </aside>

        <section className="min-w-0 lg:h-screen lg:overflow-hidden">
          <header className="flex h-16 items-center justify-between gap-3 border-b border-[var(--line)] bg-white/85 px-4 backdrop-blur md:px-7">
            <div className="min-w-0">
              <div className="label !mb-0">
                {desk === "director" ? `Stage ${String(stepIndex + 1).padStart(2, "0")}` : desk === "canvas" ? "Canvas" : "Edit room"}
              </div>
              <h2 className="display-type truncate text-xl font-semibold">
                {desk === "director" ? activeStepMeta.label : DESKS.find((d) => d.id === desk)?.label}
              </h2>
            </div>

            <div className="flex items-center gap-2">
              <div className="hidden items-center rounded-xl border border-[var(--line)] bg-white p-1 sm:flex">
                {DESKS.map((d) => {
                  const Icon = DESK_ICONS[d.id];
                  return (
                    <button
                      key={d.id}
                      type="button"
                      className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
                        desk === d.id ? "bg-[var(--navy)] text-white" : "text-[var(--muted)] hover:bg-[var(--panel-muted)]"
                      }`}
                      onClick={() => {
                        setDesk(d.id);
                        if (d.id === "edit") setStep("edit");
                        if (d.id === "director" && step === "edit") setStep("storyboard");
                      }}
                    >
                      <Icon className="h-3.5 w-3.5" />
                      {d.label}
                    </button>
                  );
                })}
              </div>
              <button type="button" className="btn-secondary !min-h-9" onClick={onRefresh} disabled={loading}>
                <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} /> 刷新
              </button>
            </div>
          </header>

          <div className="scrollbar-thin min-h-[calc(100vh-4rem)] overflow-y-auto p-4 md:p-7 lg:h-[calc(100vh-4rem)]">
            {desk === "canvas" ? (
              <CanvasDesk
                canvasSource={canvasSource}
                setCanvasSource={setCanvasSource}
                pipeline={pipeline}
                subgraphs={subgraphs}
                selectedSubgraph={selectedSubgraph}
                setSelectedSubgraph={setSelectedSubgraph}
                subgraphDoc={subgraphDoc}
                view={view}
                onSelectShot={() => {
                  setDesk("director");
                  setStep("storyboard");
                }}
              />
            ) : desk === "edit" || step === "edit" ? (
              <EditStep project={project} view={view} onBundle={onBundle} />
            ) : step === "script" ? (
              <ScriptStep project={project} view={view} onBundle={onBundle} />
            ) : step === "characters" || step === "locations" || step === "props" ? (
              <EntityStep kind={step} project={project} view={view} onBundle={onBundle} />
            ) : (
              <StoryboardStep
                project={project}
                view={view}
                onBundle={onBundle}
                onGenerate={onGenerate}
                genState={genState}
              />
            )}
          </div>
        </section>
      </div>
    </main>
  );
}
