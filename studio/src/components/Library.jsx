import { useMemo, useRef, useState } from "react";
import {
  Clapperboard,
  FolderOpen,
  ImagePlus,
  KeyRound,
  Lock,
  Plus,
  RefreshCw,
  Search,
  Sparkles,
  Trash2,
  Unlock,
  Upload,
} from "lucide-react";
import { api } from "../api";
import { toast } from "../lib/toast";
import { ConfirmDialog } from "./ConfirmDialog";

import { tr, useLocale } from "../lib/i18n";

function progressSteps(project, stepCount = 7) {
  const p = project.progress || {};
  const flags = [
    (p.episodes?.total || 0) > 0,
    (p.characters?.total || 0) > 0,
    (p.scenes?.total || 0) > 0,
    (p.props?.total || 0) > 0,
    (p.shots?.total || 0) > 0,
    (p.audios?.total || 0) > 0 || (p.shots?.completed || 0) > 0,
    (p.shots?.completed || 0) > 0,
  ];
  return flags.slice(0, stepCount);
}

function ProjectCover({ project, className }) {
  useLocale();
  const [imgFailed, setImgFailed] = useState(false);
  const [videoFailed, setVideoFailed] = useState(false);
  const still =
    !imgFailed && (project.coverUrl || (project.coverPath ? `/api/media/${project.id}/${project.coverPath}` : ""));
  const video = !videoFailed ? project.coverVideoUrl || "" : "";

  if (still) {
    return (
      <img
        src={still}
        alt=""
        onError={() => setImgFailed(true)}
        className={className || "h-full w-full object-cover transition duration-500 group-hover:scale-[1.03]"}
      />
    );
  }
  if (video) {
    return (
      <video
        src={video}
        muted
        playsInline
        loop
        autoPlay
        preload="metadata"
        onError={() => setVideoFailed(true)}
        className={className || "h-full w-full object-cover transition duration-500 group-hover:scale-[1.03]"}
      />
    );
  }
  return (
    <div className="flex h-full flex-col items-center justify-center gap-2 text-white/25">
      <Clapperboard className="h-8 w-8" />
      <span className="text-[10px] text-white/30">{tr("ui_library_no_cover_material_yet")}</span>
    </div>
  );
}

function CoverEditorDialog({ project, formats, open, onClose, onSaved }) {
  useLocale();
  const fileRef = useRef(null);
  const [busy, setBusy] = useState(false);
  const [formatId, setFormatId] = useState(project?.coverFormatId || formats[0]?.id || "portrait_9_16");
  const [title, setTitle] = useState(project?.coverTitle || project?.title || "");
  const [locked, setLocked] = useState(Boolean(project?.coverLocked));

  if (!open || !project) return null;

  const preview =
    project.coverUrl ||
    (project.coverPath ? `/api/media/${project.id}/${project.coverPath}` : "") ||
    project.coverVideoUrl ||
    "";

  const patch = async (body) => {
    setBusy(true);
    try {
      await api(`/api/projects/${encodeURIComponent(project.id)}`, {
        method: "PATCH",
        body: JSON.stringify(body),
      });
      toast.success(tr("ui_library_cover_updated"));
      onSaved?.();
    } catch (e) {
      toast.error(String(e.message || e));
    } finally {
      setBusy(false);
    }
  };

  const fromVideo = () =>
    void patch({
      action: "cover-from-video",
      coverFormatId: formatId,
      coverTitle: title,
      force: true,
    });

  const onUpload = async (file) => {
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      const data = String(reader.result || "");
      const ext = (file.name.split(".").pop() || "jpg").toLowerCase();
      void patch({
        action: "cover-upload",
        data,
        ext,
        coverFormatId: formatId,
        coverLocked: true,
      });
    };
    reader.readAsDataURL(file);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4" onClick={onClose}>
      <div
        className="panel w-full max-w-lg overflow-hidden border border-white/15 bg-[var(--panel)] shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-[var(--line)] px-4 py-3">
          <div>
            <h3 className="text-sm font-semibold">{tr("ui_library_cover_design", {
                title: project.title
              })}</h3>
            <p className="mt-0.5 text-[11px] text-[var(--muted)]">{tr("ui_library_first_frame_grab_upload_multi_ratio")}</p>
          </div>
          <button type="button" className="btn-quiet !min-h-8 !px-2 text-xs" onClick={onClose}>{tr("ui_library_close")}</button>
        </div>
        <div className="grid gap-4 p-4 sm:grid-cols-[140px_1fr]">
          <div className="flex aspect-[9/16] max-h-52 items-center justify-center overflow-hidden rounded border border-white/10 bg-black/40 sm:aspect-auto sm:h-52">
            {preview ? (
              <img src={preview} alt="" className="max-h-full max-w-full object-contain" />
            ) : (
              <span className="text-[10px] text-white/30">{tr("ui_library_no_cover")}</span>
            )}
          </div>
          <div className="space-y-3 text-sm">
            <label className="block">
              <span className="mb-1 block text-[11px] text-[var(--muted)]">{tr("ui_library_cover_format")}</span>
              <select
                className="field"
                value={formatId}
                onChange={(e) => setFormatId(e.target.value)}
                disabled={busy}
              >
                {formats.map((f) => (
                  <option key={f.id} value={f.id}>
                    {f.label} ({f.ratio}){f.description ? ` · ${f.description}` : ""}
                  </option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="mb-1 block text-[11px] text-[var(--muted)]">{tr("ui_library_cover_title_optional")}</span>
              <input
                className="field"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder={project.title || tr("ui_library_title")}
                disabled={busy}
              />
            </label>
            <div className="flex flex-wrap gap-2">
              <button type="button" className="btn-primary !min-h-8 text-xs" disabled={busy} onClick={fromVideo}>
                <Clapperboard className="h-3.5 w-3.5" />{" "}{tr("ui_library_use_first_video_frame")}</button>
              <button
                type="button"
                className="btn-secondary !min-h-8 text-xs"
                disabled={busy}
                onClick={() => fileRef.current?.click()}
              >
                <Upload className="h-3.5 w-3.5" />{" "}{tr("ui_library_upload_cover")}</button>
              <button
                type="button"
                className="btn-quiet !min-h-8 text-xs"
                disabled={busy}
                onClick={() =>
                  void patch({
                    action: "cover-patch",
                    coverFormatId: formatId,
                    coverTitle: title,
                    coverLocked: locked,
                  })
                }
              >
                <ImagePlus className="h-3.5 w-3.5" />{" "}{tr("ui_library_apply_format")}</button>
              <button
                type="button"
                className="btn-quiet !min-h-8 text-xs"
                disabled={busy}
                onClick={() => {
                  const next = !locked;
                  setLocked(next);
                  void patch({ action: "cover-patch", coverLocked: next });
                }}
              >
                {locked ? <Lock className="h-3.5 w-3.5" /> : <Unlock className="h-3.5 w-3.5" />}
                {locked ? tr("ui_library_locked") : tr("ui_library_lock_cover")}
              </button>
            </div>
            <p className="text-[10px] leading-4 text-[var(--muted)]">{tr("ui_library_after_a_successful_render_the_first")}</p>
            <input
              ref={fileRef}
              type="file"
              accept="image/jpeg,image/png,image/webp"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0];
                e.target.value = "";
                void onUpload(f);
              }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

export function Library({
  projects,
  config,
  onOpen,
  onCreate,
  onDeleted,
  onRefresh,
  onNeedKeys,
  onRequireAuth,
  authed = false,
}) {
  useLocale();
  const [confirmId, setConfirmId] = useState(null);
  const [coverProjectId, setCoverProjectId] = useState(null);
  const [query, setQuery] = useState("");
  const caps = config?.capabilities || {};
  const keysReady = (caps.configured ?? 0) >= 1;
  const stepLabels = (config?.six_steps || []).map((s) => s.label);
  const entryCards = config?.entryCards || [];
  const coverFormats = config?.coverFormats?.length
    ? config.coverFormats
    : [
        { id: "portrait_9_16", label: tr("ui_library_portrait_cover"), ratio: "9:16" },
        { id: "landscape_16_9", label: tr("ui_library_landscape_cover"), ratio: "16:9" },
        { id: "square_1_1", label: tr("ui_library_square_cover"), ratio: "1:1" },
        { id: "social_4_5", label: tr("ui_library_social_cover"), ratio: "4:5" },
      ];
  const coverTarget = (projects || []).find((p) => p.id === coverProjectId);
  const hasRealProject = (projects || []).some((p) => !String(p.id || "").startsWith("welcome"));
  const onboardingSteps = [
    { n: "01", title: tr("ui_library_sign_in"), done: Boolean(authed) },
    { n: "02", title: tr("ui_library_configure_model_keys"), done: Boolean(authed) && keysReady },
    { n: "03", title: tr("ui_library_create_a_project_and_shoot"), done: Boolean(authed) && keysReady && hasRealProject },
  ];
  const onboardingDone = onboardingSteps.every((s) => s.done);

  const visible = useMemo(() => {
    const keyword = query.trim().toLocaleLowerCase("zh-CN");
    if (!keyword) return projects || [];
    return (projects || []).filter((project) =>
      `${project.title} ${project.genre}`.toLocaleLowerCase("zh-CN").includes(keyword),
    );
  }, [projects, query]);

  const remove = async (id) => {
    if (onRequireAuth && !onRequireAuth()) return;
    try {
      await api(`/api/projects/${encodeURIComponent(id)}`, { method: "DELETE" });
      onDeleted?.(id);
      toast.success(tr("ui_library_project_deleted"));
    } catch (e) {
      toast.error(String(e.message || e));
    } finally {
      setConfirmId(null);
    }
  };

  const target = (projects || []).find((p) => p.id === confirmId);

  return (
    <main className="min-h-screen p-2 md:p-3">
      <div className="yc-frame mx-0 min-h-[calc(100vh-2.5rem)] w-full max-w-none overflow-hidden p-3 md:p-4">
        <header className="relative overflow-hidden rounded-2xl border border-white/10 bg-[linear-gradient(135deg,#15182a_0%,#1a1240_45%,#0d1b3a_100%)] px-4 py-3 md:px-6 md:py-4">
          <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_80%_20%,rgba(124,108,255,.28),transparent_40%)]" />
          <div className="relative flex flex-wrap items-end justify-between gap-2">
            <div className="min-w-0">
              <div className="flex items-center gap-2 text-[11px] font-semibold text-white/55">
                <Clapperboard className="h-3.5 w-3.5 text-[#b7acff]" />{tr("ui_library_film_creation_workshop")}</div>
              <h1 className="mt-1 text-xl font-semibold tracking-tight md:text-2xl">{tr("ui_library_from_script_to_final_cut_ai")}</h1>
              <p className="mt-1 max-w-2xl text-xs text-white/55">{tr("ui_library_script_writing_script_lock_analysis_asset")}</p>
            </div>
          </div>
        </header>

        {!authed ? (
          <section className="mt-3 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-amber-500/35 bg-amber-500/10 px-3 py-2.5 md:px-4">
            <div className="min-w-0 text-xs leading-5 text-amber-50/90">
              <strong className="font-semibold text-amber-100">{tr("ui_library_browse_mode")}</strong>
              <span className="text-amber-100/70">{tr("ui_library_open_projects_to_view_progress_and", {
                  0: " "
                })}</span>
            </div>
            <button
              type="button"
              className="btn-primary !min-h-8 shrink-0 !px-3 text-xs"
              onClick={() => onRequireAuth?.()}
            >{tr("ui_library_sign_in_to_create")}</button>
          </section>
        ) : null}

        <section className="mt-3 rounded-xl border border-[#7c6cff]/35 bg-[linear-gradient(90deg,rgba(124,108,255,.18),rgba(79,140,255,.12))] px-3 py-2 md:px-4">
          <div className="flex flex-wrap items-center gap-2 text-xs text-white/80">
            <Sparkles className="h-3.5 w-3.5 shrink-0 text-[#c4b5fd]" />
            <span className="font-semibold">{tr("ui_library_pipeline_step_count", { count: stepLabels.length })}</span>
            <span className="text-white/35">|</span>
            {stepLabels.map((label, i) => (
              <span key={label} className="inline-flex items-center gap-1 text-white/70">
                <span className="timecode text-[10px] text-[#a5b4fc]">{i + 1}</span>
                {label}
                {i < stepLabels.length - 1 ? <span className="text-white/25">→</span> : null}
              </span>
            ))}
          </div>
        </section>

        <section className="mt-3 rounded-xl border border-white/10 bg-white/[.03] px-3 py-2.5 md:px-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="min-w-0">
              <strong className="text-sm text-white/90">
                {onboardingDone ? tr("ui_library_three_setup_steps_done") : tr("ui_library_three_setup_steps")}
              </strong>
              <p className="mt-0.5 text-[11px] text-white/50">
                {onboardingDone
                  ? tr("ui_library_keys_are_ready_create_a_new")
                  : tr("ui_library_keys_are_stored_per_account_and")}
              </p>
            </div>
            {!keysReady ? (
              <button type="button" className="btn-primary !min-h-8 shrink-0 !px-3 text-xs" onClick={() => onNeedKeys?.()}>
                <KeyRound className="h-3.5 w-3.5" />{" "}{tr("ui_library_configure_models")}</button>
            ) : (
              <button type="button" className="btn-secondary !min-h-8 shrink-0 !px-3 text-xs" onClick={() => onCreate?.("drama")}>
                <Plus className="h-3.5 w-3.5" />{" "}{tr("ui_library_new_project")}</button>
            )}
          </div>
          {!onboardingDone ? (
            <ol className="mt-2 grid gap-1.5 sm:grid-cols-3">
              {onboardingSteps.map((step) => (
                <li
                  key={step.n}
                  className={`rounded-lg border px-2.5 py-1.5 text-xs ${
                    step.done ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-100" : "border-white/10 text-white/55"
                  }`}
                >
                  <span className="timecode text-[10px] text-white/35">{step.n}</span>
                  <div className="mt-0.5 font-medium text-white/85">{step.title}</div>
                  <div className="text-[10px]">{step.done ? tr("ui_library_done") : tr("ui_library_to_do")}</div>
                </li>
              ))}
            </ol>
          ) : null}
        </section>

        <section className="mt-4">
          <div className="mb-2 flex items-end justify-between gap-3">
            <h2 className="text-base font-semibold">{tr("ui_library_choose_how_to_start")}</h2>
          </div>
          <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
            {entryCards.map((card) => (
              <button
                key={card.id}
                type="button"
                disabled={!card.available}
                onClick={() => {
                  if (!card.available) return toast.info(tr("ui_library_the_entry_is_under_construction_using", {
                    title: card.title
                  }));
                  onCreate?.(card.id, card);
                }}
                className={`group relative overflow-hidden rounded-xl bg-gradient-to-br p-3 text-left text-white shadow-float transition ${card.tone} ${
                  card.available ? "hover:-translate-y-0.5 hover:brightness-110" : "cursor-not-allowed opacity-70"
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <strong className="text-lg font-semibold leading-tight">
                    {card.title}
                    <span className="ml-1 text-base opacity-80">{card.badge}</span>
                  </strong>
                  {card.id === "upload" ? <Upload className="h-4 w-4 shrink-0 opacity-80" /> : <Plus className="h-4 w-4 shrink-0 opacity-80" />}
                </div>
                <p className="mt-2 line-clamp-2 text-xs text-white/85">{card.desc}</p>
                {!card.available ? (
                  <span className="mt-1.5 inline-block rounded-full bg-black/25 px-2 py-0.5 text-[10px]">{tr("ui_library_coming_soon")}</span>
                ) : null}
              </button>
            ))}
          </div>
        </section>

        <section className="mt-5">
          <div className="mb-3 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <h2 className="text-base font-semibold">{tr("ui_library_my_projects")}</h2>
              <p className="mt-0.5 text-xs text-[var(--muted)]">{tr("ui_library_providers", {
                  0: caps.configured ?? 0,
                  1: caps.total ?? 3,
                  2: caps.deepseek || caps.llmReady ? ` · LLM${caps.llmBackend && caps.llmBackend !== "none" ? `/${caps.llmBackend}` : ""}` : "",
                  3: caps.seedream ? " · Seedream" : "",
                  4: caps.seedance ? " · Seedance" : ""
                })}</p>
            </div>
            <div className="flex w-full flex-wrap items-center gap-2 sm:w-auto">
              <label className="relative w-full sm:w-72">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--muted)]" />
                <input
                  className="field !pl-10"
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder={tr("ui_library_search_project_names")}
                />
              </label>
              <button type="button" className="btn-secondary" onClick={onRefresh}>
                <RefreshCw className="h-3.5 w-3.5" />{" "}{tr("ui_library_refresh")}</button>
              <button type="button" className="btn-primary" onClick={onCreate}>
                <Plus className="h-4 w-4" />{" "}{tr("ui_library_new_project")}</button>
            </div>
          </div>

          {!projects?.length ? (
            <button
              type="button"
              onClick={onCreate}
              className="panel group flex w-full flex-col items-center border-dashed border-white/15 py-10 text-center hover:border-[#7c6cff]/50"
            >
              <FolderOpen className="mb-3 h-8 w-8 text-[#a78bfa]" />
              <strong className="text-lg">{tr("ui_library_no_projects_yet")}</strong>
              <span className="mt-2 text-sm text-[var(--muted)]">{tr("ui_library_start_your_first_work_from_the")}</span>
            </button>
          ) : visible.length === 0 ? (
            <div className="panel py-16 text-center text-sm text-[var(--muted)]">{tr("ui_library_no_matching_projects")}</div>
          ) : (
            <div className="grid gap-3 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5">
              {visible.map((project) => {
                const steps = progressSteps(project, stepLabels.length || 6);
                const doneCount = steps.filter(Boolean).length;
                return (
                  <article
                    key={project.id}
                    className="panel group overflow-hidden transition hover:-translate-y-0.5 hover:border-white/20"
                  >
                    <button type="button" className="w-full text-left" onClick={() => onOpen(project.id)}>
                      <div className="flex aspect-[16/9] items-center justify-center overflow-hidden bg-black/50">
                        <ProjectCover project={project} className="max-h-full max-w-full object-contain" />
                      </div>
                      <div className="p-3">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="rounded-full border border-white/10 bg-white/[.04] px-2 py-0.5 text-[10px] text-white/60">
                          {project.genre || tr("ui_library_uncategorized")}
                        </span>
                        <span className="rounded-full border border-white/10 bg-white/[.04] px-2 py-0.5 text-[10px] text-white/60">
                          {project.ratio || "9:16"}
                        </span>
                      </div>
                      <h3 className="mt-2 truncate text-base font-semibold">{project.title}</h3>
                      <p className="mt-1 line-clamp-2 min-h-8 text-xs leading-4 text-[var(--muted)]">
                        {project.synopsis || project.brief || tr("ui_library_no_script_yet")}
                      </p>
                      <div className="mt-3">
                        <div className="mb-2 flex items-center justify-between text-[10px] text-[var(--muted)]">
                          <span>{tr("ui_library_progress")}</span>
                          <span className="timecode text-[#a5b4fc]">
                            {doneCount}/{stepLabels.length || steps.length}
                          </span>
                        </div>
                        <div className="grid grid-cols-6 gap-1">
                          {steps.map((done, index) => (
                            <div
                              key={stepLabels[index] || index}
                              className={`h-1.5 rounded-full ${done ? "bg-[var(--ok)]" : "bg-white/10"}`}
                              title={stepLabels[index] || ""}
                            />
                          ))}
                        </div>
                      </div>
                      <div className="mt-4 flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-white/40">
                        <span>{tr("ui_library_ep", {
                            0: project.progress?.episodes?.total || 0
                          })}</span>
                        <span>{tr("ui_library_characters", {
                            0: project.progress?.characters?.total || 0
                          })}</span>
                        <span>{tr("ui_library_scenes", {
                            0: project.progress?.scenes?.total || 0
                          })}</span>
                        <span>{tr("ui_library_updated", {
                            0: " ",
                            1: project.updatedAt ? new Date(project.updatedAt).toLocaleDateString("zh-CN") : "—"
                          })}</span>
                      </div>
                      </div>
                    </button>
                    <div className="flex items-center justify-between border-t border-[var(--line)] bg-black/20 px-3 py-2">
                      <span className="timecode text-[10px] text-white/35">
                        {project.progress?.shots?.completed || 0}/{project.progress?.shots?.total || 0} SHOTS
                      </span>
                      <div className="flex items-center gap-1">
                        <button
                          type="button"
                          className="btn-quiet !min-h-8 !px-2 text-xs"
                          onClick={() => setCoverProjectId(project.id)}
                          title={tr("ui_library_cover_design_2")}
                        >
                          <ImagePlus className="h-3.5 w-3.5" />{" "}{tr("ui_library_cover")}</button>
                        <button
                          type="button"
                          className="btn-quiet !min-h-8 !px-2 text-xs hover:!text-[var(--danger)]"
                          onClick={() => setConfirmId(project.id)}
                        >
                          <Trash2 className="h-3.5 w-3.5" />{" "}{tr("ui_library_delete")}</button>
                      </div>
                    </div>
                  </article>
                );
              })}
            </div>
          )}
        </section>
      </div>

      <ConfirmDialog
        open={Boolean(confirmId)}
        title={tr("ui_library_delete_the_whole_project")}
        message={tr("ui_library_and_its_script_asset_profiles_shots", {
          0: target?.title || confirmId
        })}
        confirmLabel={tr("ui_library_delete_project")}
        danger
        onCancel={() => setConfirmId(null)}
        onConfirm={() => void remove(confirmId)}
      />

      <CoverEditorDialog
        open={Boolean(coverProjectId)}
        project={coverTarget}
        formats={coverFormats}
        onClose={() => setCoverProjectId(null)}
        onSaved={() => {
          onRefresh?.();
        }}
      />
    </main>
  );
}
