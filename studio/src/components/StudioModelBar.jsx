import { useEffect, useEffectEvent, useMemo, useRef, useState } from "react";
import { Check, ChevronDown, Image as ImageIcon, Mic2, ShieldCheck, Video } from "lucide-react";
import { api } from "../api";
import { toast } from "../lib/toast";
import { useLocale } from "../lib/i18n";

function groupModels(list) {
  const groups = [];
  const index = new Map();
  for (const item of list || []) {
    const g = item.group || item.backend || "Other";
    if (!index.has(g)) {
      index.set(g, groups.length);
      groups.push({ name: g, items: [] });
    }
    groups[index.get(g)].items.push(item);
  }
  return groups;
}

function resolveImageValue(keys) {
  const pref = (keys?.imageBackendPref || "auto").toLowerCase();
  if (pref === "auto" || !pref) return "auto";
  if (pref === "seedream") {
    const mid = keys?.seedreamModel || keys?.volcengine?.seedreamModel || "";
    return mid ? `seedream:${mid}` : "seedream:";
  }
  if (pref === "comfyui") {
    const ckpt = keys?.comfyui?.checkpoint || "";
    return ckpt ? `comfyui:${ckpt}` : "comfyui:";
  }
  if (pref === "nvidia") {
    const mid = keys?.nvidia?.model || "flux-3-image-klein";
    return `nvidia:${mid}`;
  }
  return pref;
}

function resolveVideoValue(keys) {
  const pref = (keys?.videoBackendPref || "auto").toLowerCase();
  if (pref === "auto" || !pref) return "auto";
  if (pref === "seedance") {
    const mid = keys?.seedanceModel || keys?.volcengine?.seedanceModel || "";
    return mid ? `seedance:${mid}` : "seedance:";
  }
  if (pref === "comfyui") {
    const mid =
      keys?.comfyui?.videoModel ||
      (keys?.comfyui?.videoModels || [])[0] ||
      "MiniMax-Hailuo-02 / H3";
    return `comfyui:${mid}`;
  }
  return pref;
}

function resolveAudioValue(keys) {
  const pref = (keys?.ttsBackendPref || "auto").toLowerCase();
  const model = keys?.ttsModel || "";
  if (pref === "auto" || !pref) return "auto";
  if (pref === "edge") return model && model !== "multi" ? `edge:${model}` : "edge:multi";
  if (pref === "openai") return model ? `openai:${model}` : "openai:gpt-4o-mini-tts";
  if (pref === "indextts") return model ? `indextts:${model}` : "indextts:IndexTTS2";
  return pref;
}

function labelFor(models, value, fallback) {
  if (!value || value === "auto") return fallback;
  const hit = (models || []).find((m) => m.id === value);
  if (hit?.label) return hit.label;
  const parts = String(value).split(":");
  return parts[1] || parts[0] || fallback;
}

/**
 * Compact image/video model switcher for Studio header.
 * Lists concrete models from Keys settings (Seedream / Seedance / ComfyUI).
 */
export function StudioModelBar({ config, onChanged }) {
  const { t } = useLocale();
  const caps = config?.capabilities || {};
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [keys, setKeys] = useState(null);
  const rootRef = useRef(null);

  const load = async () => {
    try {
      const data = await api("/api/settings/keys");
      setKeys(data?.keys || null);
    } catch {
      setKeys(null);
    }
  };

  useEffect(() => {
    void load();
    const onKeys = () => void load();
    window.addEventListener("studio-keys-changed", onKeys);
    return () => window.removeEventListener("studio-keys-changed", onKeys);
  }, [caps.imageBackend, caps.videoBackend]);

  // Header has overflow-hidden ancestors, so a fixed inset backdrop cannot receive
  // clicks on the page body — listen on document instead.
  const onDocPointerDown = useEffectEvent((event) => {
    if (!open) return;
    const root = rootRef.current;
    if (root && event.target instanceof Node && root.contains(event.target)) return;
    setOpen(false);
  });

  const onDocKeyDown = useEffectEvent((event) => {
    if (!open) return;
    if (event.key === "Escape") setOpen(false);
  });

  useEffect(() => {
    if (!open) return;
    document.addEventListener("pointerdown", onDocPointerDown, true);
    document.addEventListener("keydown", onDocKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onDocPointerDown, true);
      document.removeEventListener("keydown", onDocKeyDown);
    };
  }, [open]);

  const imageModels = useMemo(() => {
    if (keys?.imageModels?.length) return keys.imageModels;
    // Fallback from platform config until keys reload
    const list = [];
    for (const m of config?.seedreamModels || []) {
      if (!m?.id) continue;
      list.push({
        id: `seedream:${m.id}`,
        backend: "seedream",
        model: m.id,
        label: m.name || m.id,
        group: "Seedream",
      });
    }
    return list;
  }, [keys, config?.seedreamModels]);

  const videoModels = useMemo(() => {
    if (keys?.videoModels?.length) return keys.videoModels;
    const list = [];
    for (const m of config?.seedanceModels || []) {
      if (!m?.id) continue;
      list.push({
        id: `seedance:${m.id}`,
        backend: "seedance",
        model: m.id,
        label: m.name || m.id,
        group: "Seedance",
      });
    }
    return list;
  }, [keys, config?.seedanceModels]);

  const audioModels = keys?.audioModels || [];
  const imageGroups = useMemo(() => groupModels(imageModels), [imageModels]);
  const videoGroups = useMemo(() => groupModels(videoModels), [videoModels]);
  const audioGroups = useMemo(() => groupModels(audioModels), [audioModels]);

  const imageValue = resolveImageValue(keys);
  const videoValue = resolveVideoValue(keys);
  const audioValue = resolveAudioValue(keys);
  const mediaQa = keys?.mediaQa !== false;

  const imageTrigger = labelFor(imageModels, imageValue === "auto" ? "" : imageValue, t("studio_model_auto"));
  const videoTrigger = labelFor(videoModels, videoValue === "auto" ? "" : videoValue, t("studio_model_auto"));
  const audioTrigger = labelFor(audioModels, audioValue === "auto" ? "" : audioValue, t("studio_model_auto"));

  const save = async (payload) => {
    setBusy(true);
    try {
      const data = await api("/api/settings/keys", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      setKeys(data?.keys || null);
      onChanged?.(data);
      toast.success(t("studio_model_saved"));
    } catch (error) {
      toast.error(String(error.message || error));
    } finally {
      setBusy(false);
    }
  };

  const onPickImage = (raw) => {
    if (raw === "auto") {
      void save({ STUDIO_IMAGE_BACKEND: "auto" });
      return;
    }
    const idx = raw.indexOf(":");
    const backend = idx >= 0 ? raw.slice(0, idx) : raw;
    const model = idx >= 0 ? raw.slice(idx + 1) : "";
    if (backend === "seedream") {
      void save({
        STUDIO_IMAGE_BACKEND: "seedream",
        ...(model ? { SEEDREAM_MODEL: model } : {}),
      });
      return;
    }
    if (backend === "nvidia") {
      void save({
        STUDIO_IMAGE_BACKEND: "nvidia",
        ...(model ? { NVIDIA_IMAGE_MODEL: model } : {}),
      });
      return;
    }
    if (backend === "comfyui") {
      const videoStillAuto = (keys?.videoBackendPref || "auto") === "auto";
      void save({
        STUDIO_IMAGE_BACKEND: "comfyui",
        // Keep explicit ckpt; Qwen Image 3 needs COMFY_API_KEY (Partner Node).
        ...(model ? { COMFYUI_CHECKPOINT: model } : {}),
        // Don't leave video on auto→Seedance while the user already chose Comfy for stills.
        ...(videoStillAuto ? { STUDIO_VIDEO_BACKEND: "comfyui" } : {}),
      });
    }
  };

  const onPickVideo = (raw) => {
    if (raw === "auto") {
      void save({ STUDIO_VIDEO_BACKEND: "auto" });
      return;
    }
    const idx = raw.indexOf(":");
    const backend = idx >= 0 ? raw.slice(0, idx) : raw;
    const model = idx >= 0 ? raw.slice(idx + 1) : "";
    if (backend === "seedance") {
      void save({
        STUDIO_VIDEO_BACKEND: "seedance",
        ...(model ? { SEEDANCE_MODEL: model } : {}),
      });
      return;
    }
    if (backend === "comfyui") {
      const imageStillAuto = (keys?.imageBackendPref || "auto") === "auto";
      void save({
        STUDIO_VIDEO_BACKEND: "comfyui",
        ...(model ? { COMFYUI_VIDEO_MODEL: model } : {}),
        ...(imageStillAuto
          ? {
              STUDIO_IMAGE_BACKEND: "comfyui",
              ...(keys?.comfyui?.checkpoint
                ? { COMFYUI_CHECKPOINT: keys.comfyui.checkpoint }
                : {}),
            }
          : {}),
      });
    }
  };

  const onPickAudio = (raw) => {
    if (raw === "auto") {
      void save({ STUDIO_TTS_BACKEND: "auto", STUDIO_TTS_MODEL: "multi" });
      return;
    }
    const idx = raw.indexOf(":");
    const backend = idx >= 0 ? raw.slice(0, idx) : raw;
    const model = idx >= 0 ? raw.slice(idx + 1) : "";
    void save({
      STUDIO_TTS_BACKEND: backend,
      ...(model ? { STUDIO_TTS_MODEL: model } : {}),
    });
  };

  const activeImageLabel =
    imageValue === "auto"
      ? `${t("studio_model_auto")} · ${keys?.imageBackend || caps.imageBackend || "—"}`
      : labelFor(imageModels, imageValue, keys?.imageBackend || "—");
  const activeVideoLabel =
    videoValue === "auto"
      ? `${t("studio_model_auto")} · ${keys?.videoBackend || caps.videoBackend || "—"}`
      : labelFor(videoModels, videoValue, keys?.videoBackend || "—");
  const activeAudioLabel =
    audioValue === "auto"
      ? `${t("studio_model_auto")} · Edge`
      : labelFor(audioModels, audioValue, keys?.ttsBackendPref || "—");

  const imageLabel = imageValue === "auto" ? t("studio_model_auto") : imageTrigger;
  const videoLabel = videoValue === "auto" ? t("studio_model_auto") : videoTrigger;
  const audioLabel = audioValue === "auto" ? t("studio_model_auto") : audioTrigger;
  const triggerTitle = `${t("studio_model_switcher_title")}: ${imageLabel} / ${videoLabel} / ${audioLabel}`;

  return (
    <div className="relative shrink-0" ref={rootRef}>
      <button
        type="button"
        className="btn-secondary !min-h-9 w-auto max-w-none shrink-0 gap-1.5 !px-2.5 text-[11px] whitespace-nowrap"
        aria-expanded={open}
        aria-haspopup="dialog"
        onClick={() => {
          setOpen((v) => {
            if (!v) void load();
            return !v;
          });
        }}
        title={triggerTitle}
      >
        <ImageIcon className="h-3.5 w-3.5 shrink-0 opacity-70" />
        <span>{imageLabel}</span>
        <span className="text-white/25">/</span>
        <Video className="h-3.5 w-3.5 shrink-0 opacity-70" />
        <span>{videoLabel}</span>
        <span className="text-white/25">/</span>
        <Mic2 className="h-3.5 w-3.5 shrink-0 opacity-70" />
        <span>{audioLabel}</span>
        <ChevronDown className="h-3 w-3 shrink-0 opacity-50" />
      </button>

      {open ? (
          <div
            className="absolute right-0 top-full z-50 mt-2 w-[340px] rounded-2xl border border-white/10 bg-[#12141c] p-3 shadow-[0_20px_60px_rgba(0,0,0,.55)]"
            role="dialog"
            aria-label={t("studio_model_switcher_title")}
          >
            <div className="mb-2 text-[11px] font-semibold text-white/80">{t("studio_model_switcher_title")}</div>
            <p className="mb-3 text-[10px] leading-4 text-white/40">{t("studio_model_switcher_hint")}</p>

            <div className="mb-3 block">
              <span className="label !mb-1">{t("studio_model_image_label")}</span>
              <div className="max-h-64 overflow-y-auto rounded-xl border border-white/10 bg-black/30 p-1" role="listbox" aria-label={t("studio_model_image_label")}>
                <button
                  type="button"
                  disabled={busy}
                  className={`flex w-full items-center justify-between rounded-lg px-2 py-1.5 text-left text-sm hover:bg-white/10 ${imageValue === "auto" ? "bg-white/10" : ""}`}
                  onClick={() => onPickImage("auto")}
                >
                  <span>{t("studio_model_auto")}</span>
                  {imageValue === "auto" ? <Check className="h-3.5 w-3.5" /> : null}
                </button>
                {imageGroups.map((g) => (
                  <div key={g.name} className="mt-1">
                    <div className="px-2 py-1 text-[10px] font-medium text-white/40">{g.name}</div>
                    {g.items.map((m) => (
                      <button
                        key={m.id}
                        type="button"
                        disabled={busy}
                        className={`flex w-full items-center justify-between rounded-lg px-2 py-1.5 text-left text-sm hover:bg-white/10 ${imageValue === m.id ? "bg-white/10" : ""}`}
                        onClick={() => onPickImage(m.id)}
                      >
                        <span className="truncate">{m.label}</span>
                        {imageValue === m.id ? <Check className="h-3.5 w-3.5 shrink-0" /> : null}
                      </button>
                    ))}
                  </div>
                ))}
              </div>
              <span className="mt-1 block text-[10px] text-white/35">
                {t("studio_model_active")}: {activeImageLabel}
              </span>
            </div>

            <label className="mb-3 block">
              <span className="label !mb-1">{t("studio_model_video_label")}</span>
              <select
                className="field !py-2 text-sm"
                disabled={busy}
                value={videoValue}
                onChange={(e) => onPickVideo(e.target.value)}
              >
                <option value="auto">{t("studio_model_auto")}</option>
                {videoGroups.map((g) => (
                  <optgroup key={g.name} label={g.name}>
                    {g.items.map((m) => (
                      <option key={m.id} value={m.id}>
                        {m.label}
                      </option>
                    ))}
                  </optgroup>
                ))}
              </select>
              <span className="mt-1 block text-[10px] text-white/35">
                {t("studio_model_active")}: {activeVideoLabel}
              </span>
            </label>

            <label className="mb-3 block">
              <span className="label !mb-1">{t("studio_model_audio_label")}</span>
              <select
                className="field !py-2 text-sm"
                disabled={busy}
                value={audioModels.some((m) => m.id === audioValue) || audioValue === "auto" ? audioValue : "auto"}
                onChange={(e) => onPickAudio(e.target.value)}
              >
                <option value="auto">{t("studio_model_auto")}</option>
                {audioGroups.map((g) => (
                  <optgroup key={g.name} label={g.name}>
                    {g.items.map((m) => (
                      <option key={m.id} value={m.id}>
                        {m.label}
                      </option>
                    ))}
                  </optgroup>
                ))}
              </select>
              <span className="mt-1 block text-[10px] text-white/35">
                {t("studio_model_active")}: {activeAudioLabel}
                {audioValue.startsWith("indextts:") && keys?.indextts && !keys.indextts.configured
                  ? ` · ${t("studio_model_indextts_need_url")}`
                  : ""}
              </span>
            </label>

            {!imageModels.length && !videoModels.length ? (
              <p className="mb-3 text-[10px] leading-4 text-amber-300/80">{t("studio_model_empty_hint")}</p>
            ) : null}

            <button
              type="button"
              disabled={busy}
              className={`flex w-full items-center justify-between rounded-xl border px-3 py-2.5 text-left text-xs transition ${
                mediaQa
                  ? "border-[var(--ok)]/35 bg-[var(--ok)]/10 text-white/85"
                  : "border-white/10 bg-white/[.03] text-white/55"
              }`}
              onClick={() => void save({ STUDIO_MEDIA_QA: mediaQa ? "0" : "1" })}
            >
              <span className="inline-flex items-center gap-2">
                <ShieldCheck className="h-3.5 w-3.5" />
                {t("studio_model_qa_toggle")}
              </span>
              {mediaQa ? <Check className="h-3.5 w-3.5 text-[var(--ok)]" /> : null}
            </button>
            <p className="mt-1.5 text-[10px] leading-4 text-white/35">{t("studio_model_qa_hint")}</p>
          </div>
      ) : null}
    </div>
  );
}
