import { useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Eraser, FileText, ImagePlus, Loader2, Maximize2, Plus, RefreshCw, ShieldCheck, Sparkles, Trash2, Upload, X } from "lucide-react";
import { api } from "../../api";
import { requireCapability, toastMaybeKeys } from "../../lib/keys";
import { toast } from "../../lib/toast";
import { Lightbox } from "../Lightbox";

import { tr, useLocale } from "../../lib/i18n";

const CONFIG = {
  character: {
    get title() {
      return tr("ui_entity_character_looks");
    },

    eyebrow: "Cast bible",

    get empty() {
      return tr("ui_entity_characters_are_organized_automatically_after_the");
    },

    accent: "#8b7cf7"
  },
  scene: {
    get title() {
      return tr("ui_entity_empty_scenes");
    },

    eyebrow: "Location bible",

    get empty() {
      return tr("ui_entity_set_up_reusable_spaces_and_lighting");
    },

    accent: "#41a99e"
  },
  prop: {
    get title() {
      return tr("ui_entity_key_props");
    },

    eyebrow: "Prop bible",

    get empty() {
      return tr("ui_entity_keep_only_key_objects_that_must");
    },

    accent: "#d79833"
  },
};

export function EntityStep({
  projectId,
  bundle,
  kind,
  setBusyMsg,
  onBundle,
  onRefresh,
  onNeedKeys,
  onRequireAuth,
  readOnly = false,
  config: appConfig,
  focusEpisodeId,
}) {
  useLocale();
  const config = CONFIG[kind];
  const caps = appConfig?.capabilities || {};
  const focusEpisode = useMemo(
    () => (bundle?.episodes || []).find((e) => e.id === focusEpisodeId) || null,
    [bundle?.episodes, focusEpisodeId],
  );
  const allOfKind = useMemo(
    () => (bundle?.entities || []).filter((e) => e.kind === kind && !e.deletedAt),
    [bundle?.entities, kind],
  );
  const entities = useMemo(() => {
    if (!focusEpisode) return allOfKind;
    const n = Number(focusEpisode.episodeNumber);
    const scoped = allOfKind.filter((e) => {
      const nums = e.episodes;
      if (!Array.isArray(nums) || nums.length === 0) return true;
      return nums.some((x) => Number(x) === n);
    });
    // Fall back to series list when this episode has no tagged assets yet.
    return scoped.length ? scoped : allOfKind;
  }, [allOfKind, focusEpisode]);
  const focusNote = focusEpisode
    ? entities.length < allOfKind.length
      ? tr("ui_entity_focused_on_ep_related_to_this", {
    episodeNumber: focusEpisode.episodeNumber,
    length: entities.length,
    length2: allOfKind.length
  })
      : tr("ui_entity_focused_on_ep_showing_all_nothing", {
    episodeNumber: focusEpisode.episodeNumber,
    length: allOfKind.length
  })
    : "";
  const [showAdd, setShowAdd] = useState(false);
  // Default off: three-view sheets fight portrait/prop close-ups and often ignore wardrobe identity.
  const [threeView, setThreeView] = useState(false);
  const [workingIds, setWorkingIds] = useState(() => new Set());
  const [batching, setBatching] = useState(false);
  const [rechecking, setRechecking] = useState(false);
  const [form, setForm] = useState({ name: "", variant: "", description: "", category: "item" });
  const [promptByEntityId, setPromptByEntityId] = useState(() => ({}));

  const apply = (res) => {
    if (res?.bundle) onBundle?.(res.bundle);
    else onRefresh?.();
  };

  const setWorking = (id, on) => {
    setWorkingIds((prev) => {
      const next = new Set(prev);
      if (on) next.add(id);
      else next.delete(id);
      return next;
    });
  };

  const create = async () => {
    if (onRequireAuth && !onRequireAuth()) return;
    if (!form.name.trim() || !form.description.trim()) return toast.error(tr("ui_entity_name_and_visual_description_can_t"));
    try {
      const res = await api(`/api/projects/${encodeURIComponent(projectId)}/entities`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          kind,
          name: form.name,
          variant: kind === "character" ? form.variant || "默认造型" : "",
          description: form.description,
          category: kind === "prop" ? form.category : "",
        }),
      });
      setShowAdd(false);
      setForm({ name: "", variant: "", description: "", category: "item" });
      apply(res);
      toast.success(tr("ui_entity_asset_profile_added"));
    } catch (e) {
      toast.error(String(e.message || e));
    }
  };

  const update = async (entity, fields) => {
    if (onRequireAuth && !onRequireAuth()) return;
    try {
      const res = await api(`/api/projects/${encodeURIComponent(projectId)}/entities`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ entityId: entity.id, ...fields }),
      });
      apply(res);
    } catch (e) {
      toast.error(String(e.message || e));
    }
  };

  const remove = async (entity) => {
    if (onRequireAuth && !onRequireAuth()) return;
    if (!window.confirm(tr("ui_entity_delete", {
      name: entity.name
    }))) return;
    try {
      const res = await api(
        `/api/projects/${encodeURIComponent(projectId)}/entities?entityId=${encodeURIComponent(entity.id)}`,
        { method: "DELETE" },
      );
      apply(res);
    } catch (e) {
      toast.error(String(e.message || e));
    }
  };

  const generate = async (entity, redraw = false, silent = false) => {
    if (onRequireAuth && !onRequireAuth()) return;
    if (!requireCapability(caps, "seedream", onNeedKeys, tr("ui_entity_image_backend_seedream_comfyui"))) return;
    if (workingIds.has(entity.id) || entity.imageStatus === "generating") return;
    setWorking(entity.id, true);
    const backendLabel = caps.imageBackend === "comfyui" ? "ComfyUI" : "Seedream";
    if (!silent) setBusyMsg?.(tr("ui_entity_image_queued_background_pool_with_qa", {
      backendLabel: backendLabel
    }));
    try {
      const res = await api(`/api/projects/${encodeURIComponent(projectId)}/entities`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "generate",
          entityId: entity.id,
          threeView: kind !== "scene" && threeView,
          redraw,
          // Always force so Redis purge won't drop jobs when an older still already qaPass.
          force: true,
        }),
      });
      apply(res);
      // Async enqueue: poll project until imageStatus leaves "generating".
      if (res?.async || res?.image?.queued) {
        if (!silent) toast.success(tr("ui_entity_image_submitted_generating_in_the_background", {
          backendLabel: backendLabel
        }));
        const started = Date.now();
        while (Date.now() - started < 15 * 60 * 1000) {
          await new Promise((r) => setTimeout(r, 4000));
          const snap = await api(`/api/projects/${encodeURIComponent(projectId)}`);
          if (snap) apply({ bundle: snap });
          const row = (snap?.entities || []).find((e) => e.id === entity.id);
          if (!row || row.imageStatus === "generating") continue;
          const imgs = row.images || [];
          const last = imgs[imgs.length - 1];
          if (!silent) {
            if (row.imageStatus === "failed" || last?.qaPass === false) {
              toast.error(tr("ui_entity_qa_failed_2", {
                0: row.imageError || last?.qa?.reason || tr("ui_qa_reason_prompt_mismatch")
              }));
            } else {
              toast.success(tr("ui_entity_image_saved", {
                backendLabel: backendLabel,
                1: last?.qa?.skipped ? "" : tr("ui_qa_passed_suffix")
              }));
            }
          }
          break;
        }
      } else {
        const imgs = (res?.bundle?.entities || []).find((e) => e.id === entity.id)?.images || [];
        const last = imgs[imgs.length - 1];
        if (!silent) {
          if (last?.qaPass === false) {
            toast.error(tr("ui_entity_qa_failed_redraw_or_switch_the", {
              0: last?.qa?.reason || tr("ui_qa_reason_prompt_mismatch")
            }));
          } else {
            toast.success(tr("ui_entity_image_saved", {
              backendLabel: backendLabel,
              1: last?.qa?.skipped ? "" : tr("ui_qa_passed_suffix")
            }));
          }
        }
      }
    } catch (e) {
      if (!silent) toastMaybeKeys(e, onNeedKeys);
      throw e;
    } finally {
      setWorking(entity.id, false);
      if (!silent) setBusyMsg?.("");
    }
  };

  const batchGenerate = async () => {
    if (onRequireAuth && !onRequireAuth()) return;
    const missing = entities.filter((e) => !e.selectedImage);
    if (!missing.length) return toast.info(tr("ui_entity_every_asset_already_has_a_selected"));
    if (!window.confirm(tr("ui_entity_generate_assets_in_bulk", {
      length: missing.length
    }))) return;
    setBatching(true);
    setBusyMsg?.(tr("ui_entity_generating_images", {
      length: missing.length
    }));
    try {
      const results = await Promise.allSettled(missing.map((e) => generate(e, false, true)));
      const ok = results.filter((r) => r.status === "fulfilled").length;
      await onRefresh?.();
      toast.success(tr("ui_entity_bulk_generation_done", {
        ok: ok,
        length: missing.length
      }));
    } finally {
      setBatching(false);
      setBusyMsg?.("");
    }
  };

  const recheckAllQa = async ({ regenerateFailed = false } = {}) => {
    if (onRequireAuth && !onRequireAuth()) return;
    if (!entities.length) return toast.info(tr("ui_entity_no_assets"));
    const label = regenerateFailed ? tr("ui_entity_recheck_and_regenerate_failed_items") : tr("ui_entity_qa_all");
    if (!window.confirm(tr("ui_entity_run_on_the_current_dirty_images", {
      length: entities.length,
      title: config.title,
      label: label
    }))) return;
    setRechecking(true);
    setBusyMsg?.(tr("ui_entity_text", {
      label: label
    }));
    try {
      const res = await api(`/api/projects/${encodeURIComponent(projectId)}/entities`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "recheck-qa",
          entityIds: entities.map((e) => e.id),
          clearSoftPass: true,
          regenerateFailed: Boolean(regenerateFailed),
        }),
      });
      if (res?.async || res?.queued) {
        toast.success(tr("ui_entity_submitted_to_the_background_queue_refresh", {
          label: label
        }));
        apply(res);
        const started = Date.now();
        while (Date.now() - started < 20 * 60 * 1000) {
          await new Promise((r) => setTimeout(r, 5000));
          const snap = await api(`/api/projects/${encodeURIComponent(projectId)}`);
          if (snap) apply({ bundle: snap });
          const busy = (snap?.entities || []).some(
            (e) => entities.some((x) => x.id === e.id) && e.imageStatus === "generating",
          );
          if (!busy) break;
        }
        return;
      }
      apply(res);
      toast.success(
        tr("ui_entity_qa_done_passed", {
          0: res.pass || 0,
          1: res.total || 0
        }) +
          (res.cleared ? ` ${tr("ui_entity_soft_passes_cleared", {
  cleared: res.cleared
})}` : "") +
          (res.fail ? ` ${tr("ui_entity_failed", {
  fail: res.fail
})}` : ""),
      );
    } catch (e) {
      toastMaybeKeys(e, onNeedKeys);
      toast.error(String(e.message || e));
    } finally {
      setRechecking(false);
      setBusyMsg?.("");
    }
  };

  const loadPrompt = async (entity) => {
    if (promptByEntityId[entity.id]?.prompt) return promptByEntityId[entity.id];
    try {
      const res = await api(`/api/projects/${encodeURIComponent(projectId)}/entities`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "preview-prompt", entityId: entity.id }),
      });
      setPromptByEntityId((prev) => ({ ...prev, [entity.id]: res }));
      return res;
    } catch (e) {
      toast.error(String(e.message || e));
      return null;
    }
  };

  const upload = async (entity, file) => {
    if (!file) return;
    if (onRequireAuth && !onRequireAuth()) return;
    setWorking(entity.id, true);
    const reader = new FileReader();
    reader.onload = async () => {
      try {
        const res = await api(`/api/projects/${encodeURIComponent(projectId)}/entities`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ action: "upload", entityId: entity.id, dataUrl: reader.result }),
        });
        apply(res);
        toast.success(tr("ui_entity_image_saved_2"));
      } catch (e) {
        toast.error(String(e.message || e));
      } finally {
        setWorking(entity.id, false);
      }
    };
    reader.readAsDataURL(file);
  };

  const punchAlpha = async (entity) => {
    if (!entity?.selectedImage || !["character", "prop"].includes(entity.kind)) return;
    if (onRequireAuth && !onRequireAuth()) return;
    setWorking(entity.id, true);
    try {
      const res = await api(`/api/projects/${encodeURIComponent(projectId)}/entities`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "punch-alpha",
          entityId: entity.id,
          imageId: entity.selectedImageId,
        }),
      });
      apply(res);
      toast.success(res?.punched ? tr("ui_entity_background_removed") : tr("ui_entity_converted_to_png_backdrop_couldn_t"));
    } catch (e) {
      toast.error(String(e.message || e));
    } finally {
      setWorking(entity.id, false);
    }
  };

  const selectVersion = async (entity, imageId) => {
    try {
      const res = await api(`/api/projects/${encodeURIComponent(projectId)}/entities`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "select", entityId: entity.id, imageId }),
      });
      apply(res);
    } catch (e) {
      toast.error(String(e.message || e));
    }
  };

  const missingImages = entities.filter((e) => !e.selectedImage);

  return (
    <div className="mx-auto max-w-[1500px] space-y-5">
      <section className="panel flex flex-col gap-4 p-5 md:flex-row md:items-center md:justify-between md:p-6">
        <div>
          <div className="label">{config.eyebrow}</div>
          <h3 className="display-type text-2xl font-semibold">
            {config.title}
            {focusEpisode ? (
              <span className="ml-2 text-base font-normal text-white/45">{tr("ui_entity_ep", {
                  episodeNumber: focusEpisode.episodeNumber,
                  1: focusEpisode.title ? `「${focusEpisode.title}」` : ""
                })}</span>
            ) : null}
          </h3>
          <p className="mt-1 max-w-2xl text-sm text-[var(--muted)]">{tr("ui_entity_the_image_backend_follows_the_model")}</p>
          {focusNote ? <p className="mt-2 text-xs text-[var(--projector)]">{focusNote}</p> : null}
          {missingImages.length ? (
            <p className="mt-2 text-xs text-[#fbbf24]">{tr("ui_entity_still_have_no_image_so_shot", {
                length: missingImages.length,
                title: config.title
              })}</p>
          ) : null}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {kind !== "scene" ? (
            <label className="mr-2 flex items-center gap-2 text-xs text-[var(--muted)]">
              <input
                type="checkbox"
                checked={threeView}
                disabled={batching}
                onChange={(e) => setThreeView(e.target.checked)}
              />{tr("ui_entity_three_view_model_sheet")}</label>
          ) : null}
          <button
            type="button"
            className="btn-secondary"
            disabled={batching || rechecking}
            onClick={() => void recheckAllQa({ regenerateFailed: false })}
            title={tr("ui_entity_recheck_final_images_with_a_vision")}
          >
            {rechecking ? <Loader2 className="h-4 w-4 animate-spin" /> : <ShieldCheck className="h-4 w-4" />}{" "}{tr("ui_entity_qa_all")}</button>
          <button
            type="button"
            className="btn-secondary"
            disabled={batching || rechecking}
            onClick={() => void recheckAllQa({ regenerateFailed: true })}
            title={tr("ui_entity_regenerate_failed_items_automatically_after_recheck")}
          >
            {rechecking ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}{" "}{tr("ui_entity_recheck_and_regenerate")}</button>
          <button type="button" className="btn-secondary" disabled={batching || rechecking} onClick={() => void batchGenerate()}>
            {batching ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}{" "}{tr("ui_entity_fill_missing_images")}</button>
          <button type="button" className="btn-primary" disabled={batching || rechecking} onClick={() => setShowAdd(true)}>
            <Plus className="h-4 w-4" />{" "}{tr("ui_entity_add")}{kind === "character" ? tr("ui_entity_looks") : kind === "scene" ? tr("ui_entity_scenes") : tr("ui_entity_props")}
          </button>
        </div>
      </section>

      {!entities.length ? (
        <button
          type="button"
          className="panel flex w-full flex-col items-center border-dashed py-24 text-center hover:border-[var(--projector)]"
          disabled={batching}
          onClick={() => setShowAdd(true)}
        >
          <ImagePlus className="mb-4 h-10 w-10" style={{ color: config.accent }} />
          <strong>{config.empty}</strong>
          <span className="mt-2 text-sm text-[var(--muted)]">{tr("ui_entity_click_to_add_the_first_profile")}</span>
        </button>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {entities.map((entity) => (
            <EntityCard
              key={entity.id}
              entity={entity}
              accent={config.accent}
              working={workingIds.has(entity.id) || entity.imageStatus === "generating"}
              onGenerate={generate}
              onUpload={upload}
              onPunchAlpha={punchAlpha}
              onSelect={selectVersion}
              onUpdate={update}
              onDelete={remove}
              promptPayload={promptByEntityId[entity.id] || null}
              onLoadPrompt={loadPrompt}
            />
          ))}
        </div>
      )}

      {showAdd
        ? createPortal(
            <div
              className="fixed inset-0 z-[100] flex items-center justify-center bg-[#09101d]/80 p-3 backdrop-blur-md md:p-6"
              onMouseDown={() => setShowAdd(false)}
            >
              <section
                className="panel max-h-[calc(100dvh-1.5rem)] w-full max-w-4xl overflow-y-auto p-5 md:p-7"
                onMouseDown={(e) => e.stopPropagation()}
              >
                <header className="flex items-start justify-between gap-4">
                  <div>
                    <div className="label">New {kind}</div>
                    <h3 className="display-type text-2xl font-semibold">{tr("ui_entity_add_2", {
                        title: config.title
                      })}</h3>
                  </div>
                  <button type="button" className="btn-quiet !min-h-9 !px-2" onClick={() => setShowAdd(false)}>
                    <X className="h-4 w-4" />
                  </button>
                </header>
                <div className="mt-6 grid gap-4 md:grid-cols-2">
                  <label>
                    <span className="label">{tr("ui_entity_name")}</span>
                    <input className="field" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} autoFocus />
                  </label>
                  {kind === "character" ? (
                    <label>
                      <span className="label">{tr("ui_entity_look_stage")}</span>
                      <input
                        className="field"
                        value={form.variant}
                        onChange={(e) => setForm({ ...form, variant: e.target.value })}
                        placeholder={tr("ui_entity_default_look_rainy_night_look")}
                      />
                    </label>
                  ) : null}
                  {kind === "prop" ? (
                    <label>
                      <span className="label">{tr("ui_entity_category")}</span>
                      <select className="field" value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}>
                        <option value="item">{tr("ui_entity_item")}</option>
                        <option value="weapon">{tr("ui_entity_weapon")}</option>
                        <option value="vehicle">{tr("ui_entity_vehicle")}</option>
                        <option value="clothing">{tr("ui_entity_clothing")}</option>
                        <option value="accessory">{tr("ui_entity_accessory")}</option>
                      </select>
                    </label>
                  ) : null}
                  <label className="md:col-span-2">
                    <span className="label">{tr("ui_entity_stable_visual_description")}</span>
                    <textarea
                      className="field min-h-40 resize-y leading-6"
                      value={form.description}
                      onChange={(e) => setForm({ ...form, description: e.target.value })}
                      placeholder={tr("ui_entity_describe_material_color_silhouette_structure_and")}
                    />
                  </label>
                </div>
                <div className="mt-6 flex justify-end gap-2">
                  <button type="button" className="btn-secondary" onClick={() => setShowAdd(false)}>{tr("ui_entity_cancel")}</button>
                  <button type="button" className="btn-primary" onClick={() => void create()}>{tr("ui_entity_add_profile")}</button>
                </div>
              </section>
            </div>,
            document.body,
          )
        : null}
    </div>
  );
}

function EntityCard({ entity, accent, working, onGenerate, onUpload, onPunchAlpha, onSelect, onUpdate, onDelete, promptPayload, onLoadPrompt }) {
  useLocale();
  const uploadRef = useRef(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [cardTab, setCardTab] = useState("edit"); // edit | prompt
  const [promptBusy, setPromptBusy] = useState(false);
  const previewAlt = `${entity.name}${entity.variant ? ` / ${entity.variant}` : ""}`;
  const locked = working;
  const sel = entity.selectedImage;
  const qaSoft =
    sel?.qa?.skipped && String(sel?.qa?.reason || "") !== "qa_disabled"
      ? true
      : /qa_error|qa_exception|软通过|vision_/i.test(String(sel?.qa?.reason || ""));
  // Prefer selected still verdict over sticky entity.qaFailed from a later failed redraw.
  const qaFail = sel ? sel.qaPass !== true || qaSoft : Boolean(entity.qaFailed);

  const switchToPrompt = async () => {
    setCardTab("prompt");
    if (promptPayload?.prompt) return;
    setPromptBusy(true);
    try {
      await onLoadPrompt?.(entity);
    } finally {
      setPromptBusy(false);
    }
  };

  return (
    <>
      <article className="panel overflow-hidden">
        <div className="flex items-center justify-between gap-2 border-b border-white/5 px-3 pt-3">
          <div className="flex items-center gap-0.5 rounded-lg bg-white/5 p-0.5">
            <button
              type="button"
              className={`rounded-md px-2 py-0.5 text-[11px] ${
                cardTab === "edit" ? "bg-white/10 font-semibold text-white" : "text-white/45"
              }`}
              onClick={() => setCardTab("edit")}
            >{tr("ui_entity_profile")}</button>
            <button
              type="button"
              className={`inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-[11px] ${
                cardTab === "prompt" ? "bg-white/10 font-semibold text-white" : "text-white/45"
              }`}
              onClick={() => void switchToPrompt()}
            >
              <FileText className="h-3 w-3" />{" "}{tr("ui_entity_prompt")}</button>
          </div>
          <button
            type="button"
            className="btn-quiet !min-h-7 !px-1.5 hover:!text-[var(--danger)]"
            disabled={locked}
            onClick={() => void onDelete(entity)}
          >
            <Trash2 className="h-3.5 w-3.5" />
          </button>
        </div>

        {cardTab === "prompt" ? (
          <div className="space-y-3 p-4 text-sm">
            {promptBusy ? (
              <div className="flex items-center justify-center gap-2 py-10 text-[var(--muted)]">
                <Loader2 className="h-4 w-4 animate-spin" />{" "}{tr("ui_entity_loading_prompt")}</div>
            ) : (
              <>
                <div>
                  <div className="mb-1 text-[11px] text-[var(--muted)]">{tr("ui_entity_positive_prompt_that_will_be_sent")}</div>
                  <pre className="max-h-48 overflow-y-auto whitespace-pre-wrap rounded-xl border border-white/10 bg-black/40 p-3 text-[11px] leading-5 text-white/85">
                    {promptPayload?.prompt || tr("ui_entity_none")}
                  </pre>
                </div>
                {promptPayload?.negativePrompt ? (
                  <div>
                    <div className="mb-1 text-[11px] text-[var(--muted)]">{tr("ui_entity_negative_prompt")}</div>
                    <pre className="max-h-28 overflow-y-auto whitespace-pre-wrap rounded-xl border border-white/10 bg-black/40 p-3 text-[11px] leading-5 text-white/70">
                      {promptPayload.negativePrompt}
                    </pre>
                  </div>
                ) : null}
                {promptPayload?.selectedImagePrompt ? (
                  <div>
                    <div className="mb-1 text-[11px] text-[var(--muted)]">{tr("ui_entity_prompt_actually_used_for_the_current")}</div>
                    <pre className="max-h-36 overflow-y-auto whitespace-pre-wrap rounded-xl border border-amber-500/20 bg-amber-500/5 p-3 text-[11px] leading-5 text-amber-50/90">
                      {promptPayload.selectedImagePrompt}
                    </pre>
                  </div>
                ) : null}
              </>
            )}
          </div>
        ) : (
          <>
            <div
              className={`relative ${
                entity.kind === "character"
                  ? "aspect-[3/4]"
                  : entity.kind === "prop"
                    ? "aspect-square"
                    : "aspect-[4/3]"
              } ${entity.kind === "scene" ? "bg-black/40" : "asset-cutout-bg"}`}
            >
              {entity.selectedImage ? (
                <button
                  type="button"
                  className="relative h-full w-full cursor-zoom-in overflow-hidden"
                  onClick={() => setPreviewUrl(entity.selectedImage?.url || null)}
                >
                  <img
                    src={entity.selectedImage.url}
                    alt={previewAlt}
                    className="h-full w-full object-contain object-center"
                  />
                  <span className="pointer-events-none absolute bottom-3 right-3 flex items-center gap-1 rounded-md bg-[var(--navy)]/70 px-2 py-1 text-[10px] font-medium text-white/80">
                    <Maximize2 className="h-3 w-3" />{" "}{tr("ui_entity_full_size")}</span>
                </button>
              ) : (
                <div className="flex h-full flex-col items-center justify-center text-sm text-[var(--muted)]">
                  <ImagePlus className="mb-3 h-8 w-8" style={{ color: accent }} />{tr("ui_entity_no_final_image_yet")}</div>
              )}
              {working ? (
                <div className="absolute inset-0 flex items-center justify-center bg-[var(--navy)]/70 text-sm font-semibold text-white backdrop-blur-sm">
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />{tr("ui_entity_processing_image")}</div>
              ) : null}
              <span className="timecode absolute left-3 top-3 rounded-md bg-[var(--navy)]/85 px-2 py-1 text-[9px] text-white">
                {entity.kind.toUpperCase()} / {String(entity.images?.length || 0).padStart(2, "0")} VER
              </span>
              {qaFail ? (
                <span className="absolute right-3 top-3 rounded-md bg-rose-600/85 px-2 py-1 text-[9px] font-semibold text-white">{tr("ui_entity_qa_failed")}</span>
              ) : sel?.qaPass === true ? (
                <span className="absolute right-3 top-3 rounded-md bg-emerald-600/85 px-2 py-1 text-[9px] font-semibold text-white">{tr("ui_entity_qa_passed")}</span>
              ) : null}
            </div>
            <div className="p-4">
              <div className="min-w-0">
                <input
                  className="w-full border-0 bg-transparent p-0 font-semibold outline-none"
                  defaultValue={entity.name}
                  disabled={locked}
                  onBlur={(e) => {
                    if (e.target.value !== entity.name) void onUpdate(entity, { name: e.target.value });
                  }}
                />
                {entity.kind === "character" ? (
                  <input
                    className="mt-1 w-full border-0 bg-transparent p-0 text-xs text-[var(--muted)] outline-none"
                    defaultValue={entity.variant || ""}
                    disabled={locked}
                    onBlur={(e) => {
                      if (e.target.value !== (entity.variant || "")) void onUpdate(entity, { variant: e.target.value });
                    }}
                  />
                ) : null}
              </div>
              <textarea
                className={`mt-3 w-full resize-y rounded-lg border border-transparent bg-[var(--panel-muted)] p-2.5 text-xs leading-5 outline-none focus:border-[var(--projector)] ${
                  entity.kind === "character" ? "min-h-36" : "min-h-24"
                }`}
                defaultValue={entity.description || ""}
                disabled={locked}
                onBlur={(e) => {
                  if (e.target.value !== (entity.description || "")) void onUpdate(entity, { description: e.target.value });
                }}
              />
              {entity.images?.length > 0 ? (
                <div className="scrollbar-thin mt-3 flex gap-2 overflow-x-auto pb-1">
                  {entity.images.map((image, index) => (
                    <button
                      key={image.id}
                      type="button"
                      disabled={locked}
                      onClick={() => void onSelect(entity, image.id)}
                      className={`h-12 w-12 shrink-0 overflow-hidden rounded-lg border-2 ${
                        image.id === entity.selectedImageId
                          ? "border-[var(--projector)]"
                          : "border-transparent opacity-65 hover:opacity-100"
                      }`}
                    >
                      <img
                        src={image.url}
                        alt={tr("ui_entity_version", {
                          0: index + 1
                        })}
                        className="h-full w-full object-contain object-center bg-black/50"
                      />
                    </button>
                  ))}
                </div>
              ) : null}
              <div className="mt-4 grid grid-cols-2 gap-2">
                <button type="button" className="btn-primary" disabled={locked} onClick={() => void onGenerate(entity, false)}>
                  <Sparkles className="h-3.5 w-3.5" /> {entity.selectedImage ? tr("ui_entity_generate_new_version") : tr("ui_entity_generate_image")}
                </button>
                <button
                  type="button"
                  className="btn-secondary"
                  disabled={locked || !entity.selectedImage}
                  onClick={() => void onGenerate(entity, true)}
                >
                  <RefreshCw className="h-3.5 w-3.5" />{" "}{tr("ui_entity_redraw_from_reference")}</button>
                {["character", "prop"].includes(entity.kind) ? (
                  <button
                    type="button"
                    className="btn-secondary col-span-2"
                    disabled={locked || !entity.selectedImage}
                    onClick={() => void onPunchAlpha?.(entity)}
                    title={tr("ui_entity_key_a_seamless_light_backdrop_out")}
                  >
                    <Eraser className="h-3.5 w-3.5" />{" "}{tr("ui_entity_remove_background")}</button>
                ) : null}
                <button type="button" className="btn-secondary col-span-2" disabled={locked} onClick={() => uploadRef.current?.click()}>
                  <Upload className="h-3.5 w-3.5" />{" "}{tr("ui_entity_upload_local_image")}</button>
                <input
                  ref={uploadRef}
                  hidden
                  type="file"
                  accept="image/png,image/jpeg,image/webp"
                  onChange={(event) => {
                    const file = event.target.files?.[0];
                    if (file) void onUpload(entity, file);
                    event.target.value = "";
                  }}
                />
              </div>
            </div>
          </>
        )}
      </article>
      <Lightbox src={previewUrl} alt={previewAlt} onClose={() => setPreviewUrl(null)} />
    </>
  );
}
