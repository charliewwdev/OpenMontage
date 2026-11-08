import { useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import {
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
  Loader2,
  Plus,
  ShieldCheck,
  Trash2,
  Pencil,
  Zap,
  ExternalLink,
  X,
} from "lucide-react";
import { api } from "../../api";
import { toast } from "../../lib/toast";
import { PageShell } from "./PageShell";

import { tr, useLocale } from "../../lib/i18n";

function fmtUsd(n) {
  const v = Number(n) || 0;
  if (v < 0.01) return `$${v.toFixed(4)}`;
  return `$${v.toFixed(2)}`;
}

function fmtNum(n) {
  return new Intl.NumberFormat("zh-CN").format(Number(n) || 0);
}

function fmtPct(rate) {
  return `${((Number(rate) || 0) * 100).toFixed(1)}%`;
}

function latencyBadge(ms) {
  const s = (Number(ms) || 0) / 1000;
  const label = `${s.toFixed(1)}s`;
  const color = s <= 5 ? "text-[var(--ok)]" : s <= 120 ? "text-amber-400" : "text-red-400";
  return <span className={`text-xs ${color}`}>{label}</span>;
}

function LineChart({ labels, series, height = 160 }) {
  useLocale();
  const width = 640;
  const pad = 24;
  const maxY = Math.max(1, ...series.flatMap((s) => s.data));
  const n = Math.max(1, labels.length);
  const toX = (i) => pad + (i * (width - pad * 2)) / Math.max(1, n - 1);
  const toY = (v) => height - pad - ((v || 0) / maxY) * (height - pad * 2);
  if (!labels.length) {
    return (<div className="flex h-40 items-center justify-center text-sm text-[var(--muted)]">{tr("ui_keys_settings_no_data")}</div>);
  }
  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="h-40 w-full">
      {[0.25, 0.5, 0.75, 1].map((p) => (
        <line
          key={p}
          x1={pad}
          x2={width - pad}
          y1={toY(maxY * p)}
          y2={toY(maxY * p)}
          stroke="currentColor"
          className="text-[var(--line)]"
          strokeWidth="1"
        />
      ))}
      {series.map((s) => {
        const d = s.data
          .map((v, i) => `${i === 0 ? "M" : "L"} ${toX(i)} ${toY(v)}`)
          .join(" ");
        return (
          <path key={s.name} d={d} fill="none" stroke={s.color} strokeWidth="2.5" strokeLinejoin="round" />
        );
      })}
    </svg>
  );
}

function ProviderEditor({ open, catalog, initial, onClose, onSave }) {
  useLocale();
  const presets = catalog || [];
  const [presetId, setPresetId] = useState(initial?.id || presets[0]?.id || "custom");
  const preset = presets.find((p) => p.id === presetId) || presets[0];
  const [apiKey, setApiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState(initial?.baseUrl || preset?.baseUrl || "");
  const [model, setModel] = useState(initial?.model || preset?.model || "");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    setPresetId(initial?.id || presets[0]?.id || "custom");
    setApiKey("");
    setBaseUrl(initial?.baseUrl || "");
    setModel(initial?.model || "");
  }, [open, initial, presets]);

  useEffect(() => {
    if (initial) return;
    const p = presets.find((x) => x.id === presetId);
    if (!p) return;
    setBaseUrl(p.baseUrl || "");
    setModel(p.model || "");
  }, [presetId, initial, presets]);

  if (!open) return null;

  const submit = async () => {
    if (!preset) return;
    setSaving(true);
    try {
      const payload = { LLM_PROVIDER: preset.id };
      if (preset.baseEnv) payload[preset.baseEnv] = baseUrl;
      if (preset.modelEnv) payload[preset.modelEnv] = model;
      if (apiKey.trim()) payload[preset.keyEnv] = apiKey.trim();
      else if (!initial?.configured) {
        toast.error(tr("ui_keys_settings_please_enter_an_api_key"));
        setSaving(false);
        return;
      }
      await onSave(payload);
      onClose();
    } finally {
      setSaving(false);
    }
  };

  return createPortal(
    <div
      className="fixed inset-0 z-[200] grid place-items-center bg-black/60 p-4"
      style={{ left: 0, top: 0, right: 0, bottom: 0 }}
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="panel w-full max-w-lg space-y-4 p-5 shadow-float" role="dialog" aria-modal="true">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold">{initial ? tr("ui_keys_settings_edit_provider") : tr("ui_keys_settings_add_provider")}</h3>
          <button type="button" className="btn-ghost p-1" onClick={onClose}>
            <X className="h-4 w-4" />
          </button>
        </div>
        {!initial ? (
          <label>
            <span className="label">{tr("ui_keys_settings_preset")}</span>
            <select className="field" value={presetId} onChange={(e) => setPresetId(e.target.value)}>
              {presets.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.label}
                </option>
              ))}
            </select>
          </label>
        ) : (
          <div className="text-sm text-[var(--muted)]">{initial.label}</div>
        )}
        <label>
          <span className="label">API Key {initial?.configured ? tr("ui_keys_settings_configured_3", {
            masked: initial.masked
          }) : ""}</span>
          <input
            className="field"
            type="password"
            autoComplete="off"
            placeholder={initial?.configured ? tr("ui_keys_settings_leave_empty_to_keep_the_current") : preset?.placeholder || "sk-..."}
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
          />
        </label>
        {preset?.kind !== "cursor" ? (
          <label>
            <span className="label">Base URL</span>
            <input className="field" value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} />
          </label>
        ) : null}
        <label>
          <span className="label">Model</span>
          {(preset?.models || []).length ? (
            <div className="space-y-2">
              <select
                className="field"
                value={(preset.models || []).some((m) => m.id === model) ? model : "__custom__"}
                onChange={(e) => {
                  const v = e.target.value;
                  if (v === "__custom__") return;
                  setModel(v);
                }}
              >
                {(preset.models || []).map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.label || m.id}
                  </option>
                ))}
                <option value="__custom__">{tr("ui_keys_settings_custom_model_id")}</option>
              </select>
              {!(preset.models || []).some((m) => m.id === model) ? (
                <input
                  className="field"
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                  placeholder={tr("ui_keys_settings_custom_model_id_2")}
                />
              ) : null}
            </div>
          ) : (
            <input className="field" value={model} onChange={(e) => setModel(e.target.value)} />
          )}
        </label>
        {preset?.hint ? <p className="text-[11px] leading-4 text-white/45">{preset.hint}</p> : null}
        {preset?.docs ? (
          <a className="text-xs text-[#a5b4fc] hover:underline" href={preset.docs} target="_blank" rel="noreferrer">{tr("ui_keys_settings_open_provider_docs_console")}</a>
        ) : null}
        <div className="flex justify-end gap-2 pt-2">
          <button type="button" className="btn-secondary" onClick={onClose}>{tr("ui_keys_settings_cancel")}</button>
          <button type="button" className="btn-primary" disabled={saving} onClick={() => void submit()}>
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : null}{tr("ui_keys_settings_save_and_enable")}</button>
        </div>
      </div>
    </div>,
    document.body,
  );
}

function SectionLabel({ children }) {
  useLocale();
  return <p className="mb-2 mt-1 text-[11px] uppercase tracking-[0.08em] text-white/35">{children}</p>;
}

function ProvidersTab({ status, catalog, onUpdated, testing, onTest }) {
  useLocale();
  const providers = status?.llmProviders || catalog || [];
  const active = status?.llmBackend || status?.llmProvider || "";
  const [editor, setEditor] = useState(null);
  const [busyId, setBusyId] = useState("");

  const savePayload = async (payload) => {
    const data = await api("/api/settings/keys", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    onUpdated?.(data);
    toast.success(tr("ui_keys_settings_saved"));
    return data;
  };

  const freePoolOn = Boolean(status?.llmFreePool) || status?.llmProvider === "auto";
  const imageFreePoolOn = (status?.imageBackendPref || "auto").toLowerCase() === "auto";

  const enable = async (p) => {
    if (!p.configured) {
      setEditor(p);
      return;
    }
    setBusyId(p.id);
    try {
      // Free tiers join the shared free pool (all free usable). Paid pins a single provider.
      if (p.freeTier) {
        await savePayload({ LLM_PROVIDER: "auto", STUDIO_FREE_FIRST: "1" });
      } else {
        await savePayload({ LLM_PROVIDER: p.id });
      }
    } catch (e) {
      toast.error(String(e.message || e));
    } finally {
      setBusyId("");
    }
  };

  const switchModel = async (p, nextModel) => {
    if (!p?.modelEnv || !nextModel || nextModel === p.model) return;
    setBusyId(p.id);
    try {
      const payload = { [p.modelEnv]: nextModel };
      if (p.freeTier && freePoolOn) {
        payload.LLM_PROVIDER = "auto";
        payload.STUDIO_FREE_FIRST = "1";
      } else {
        payload.LLM_PROVIDER = p.id;
      }
      await savePayload(payload);
    } catch (e) {
      toast.error(String(e.message || e));
    } finally {
      setBusyId("");
    }
  };

  const clearKey = async (p) => {
    if (!p.keyEnv) return;
    setBusyId(p.id);
    try {
      await savePayload({ [p.keyEnv]: "" });
      toast.success(tr("ui_keys_settings_cleared", {
        label: p.label
      }));
    } catch (e) {
      toast.error(String(e.message || e));
    } finally {
      setBusyId("");
    }
  };

  const freeFirst = (list) =>
    [...list].sort((a, b) => Number(Boolean(b.freeTier)) - Number(Boolean(a.freeTier)));
  const configuredProviders = freeFirst(providers.filter((p) => p.configured));
  const otherProviders = freeFirst(providers.filter((p) => !p.configured));
  const volcConfigured = Boolean(status?.volcengine?.configured);
  const comfyConfigured = Boolean(status?.comfyui?.configured);
  const nvidiaConfigured = Boolean(status?.nvidia?.configured);
  const hfConfigured = Boolean(status?.hf?.configured);
  const cfImageConfigured = Boolean(status?.cloudflareImage?.configured);
  const hasConfigured =
    configuredProviders.length > 0 ||
    volcConfigured ||
    comfyConfigured ||
    nvidiaConfigured ||
    hfConfigured ||
    cfImageConfigured;

  const renderLlmCard = (p) => {
    const inFreePool = Boolean(p.freeTier && p.configured && freePoolOn);
    const isActive = inFreePool || active === p.id;
    const initials = String(p.label || p.id || "?")
      .replace(/[^A-Za-z0-9\u4e00-\u9fa5]/g, "")
      .slice(0, 2)
      .toUpperCase();
    return (
      <article key={p.id} className={`provider-card group ${isActive ? "provider-card-active" : ""}`}>
        <div className="provider-card-icon">{initials || "AI"}</div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="truncate text-[15px] font-semibold tracking-tight">{p.label}</h3>
            {inFreePool ? (
              <span className="provider-badge-active">{tr("ui_keys_settings_free_pool_enabled")}</span>
            ) : isActive ? (
              <span className="provider-badge-active">{tr("ui_keys_settings_in_use")}</span>
            ) : null}
            {p.freeTier ? (
              <span className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-[11px] text-emerald-300">{tr("ui_keys_settings_free_tier_badge")}</span>
            ) : null}
            {!p.configured ? (
              <span className="rounded-full border border-[var(--line)] px-2 py-0.5 text-[11px] text-[var(--muted)]">{tr("ui_keys_settings_not_configured")}</span>
            ) : null}
          </div>
          <div className="mt-1 flex min-w-0 flex-wrap items-center gap-x-2 gap-y-0.5 text-xs text-[var(--muted)]">
            {p.docs ? (
              <a
                href={p.docs}
                target="_blank"
                rel="noreferrer"
                className="truncate hover:text-[var(--ink)]"
                title={p.baseUrl || p.docs}
              >
                {p.baseUrl || p.docs}
              </a>
            ) : (
              <span className="truncate">{p.baseUrl || tr("ui_keys_settings_no_endpoint_configured")}</span>
            )}
            <span>·</span>
            <span>{p.model || "—"}</span>
            {p.configured ? (
              <>
                <span>·</span>
                <span>Key {p.masked}</span>
              </>
            ) : null}
          </div>
          {p.hint ? <p className="mt-1 text-[11px] leading-4 text-white/40">{p.hint}</p> : null}
          {p.configured && (p.models || []).length ? (
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <span className="text-[11px] text-white/35">{tr("ui_keys_settings_switch_model")}</span>
              <select
                className="field !min-h-[30px] !w-auto !max-w-[min(100%,280px)] !py-1 !text-xs"
                value={p.model || ""}
                disabled={busyId === p.id}
                onChange={(e) => void switchModel(p, e.target.value)}
              >
                {(p.models || []).map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.label || m.id}
                  </option>
                ))}
                {p.model && !(p.models || []).some((m) => m.id === p.model) ? (
                  <option value={p.model}>{tr("ui_keys_settings_current", {
                      model: p.model
                    })}</option>
                ) : null}
              </select>
            </div>
          ) : null}
        </div>

        <div className="provider-card-actions">
          <button
            type="button"
            className={`provider-icon-btn ${isActive ? "provider-icon-btn-done" : "provider-icon-btn-primary"}`}
            disabled={busyId === p.id || isActive}
            onClick={() => void enable(p)}
            title={isActive ? tr("ui_keys_settings_active") : tr("ui_keys_settings_enable")}
          >
            {busyId === p.id ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Zap className="h-3.5 w-3.5" />}
            <span className="hidden sm:inline">{isActive ? tr("ui_keys_settings_enabled") : tr("ui_keys_settings_enable")}</span>
          </button>
          <button type="button" className="provider-icon-btn" onClick={() => setEditor(p)} title={tr("ui_keys_settings_edit")}>
            <Pencil className="h-3.5 w-3.5" />
          </button>
          {p.docs ? (
            <a href={p.docs} target="_blank" rel="noreferrer" className="provider-icon-btn" title={tr("ui_keys_settings_docs")}>
              <ExternalLink className="h-3.5 w-3.5" />
            </a>
          ) : null}
          <button
            type="button"
            className="provider-icon-btn"
            disabled={busyId === p.id || !p.configured || (!inFreePool && active === p.id)}
            onClick={() => void clearKey(p)}
            title={
              !inFreePool && active === p.id
                ? tr("ui_keys_settings_switch_to_another_provider_before_clearing")
                : tr("ui_keys_settings_clear_key")
            }
          >
            <Trash2 className="h-3.5 w-3.5" />
          </button>
        </div>
      </article>
    );
  };

  const nvidiaSection = (
    <section className="provider-card !items-stretch !flex-col gap-3 sm:!flex-row sm:!items-center">
      <div className="provider-card-icon">N</div>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="text-[15px] font-semibold">{tr("ui_keys_settings_nvidia_open_source_images")}</h3>
          <span className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-[11px] text-emerald-300">{tr("ui_keys_settings_free_tier_badge")}</span>
          <span className="text-xs text-[var(--muted)]">{tr("ui_keys_settings_flux_schnell_klein_trial_quota")}</span>
          {nvidiaConfigured ? (
            <span className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-[11px] text-emerald-300">{tr("ui_keys_settings_configured")}</span>
          ) : (
            <span className="rounded-full border border-[var(--line)] px-2 py-0.5 text-[11px] text-[var(--muted)]">{tr("ui_keys_settings_not_configured")}</span>
          )}
          {nvidiaConfigured && imageFreePoolOn ? (
            <span className="provider-badge-active">{tr("ui_keys_settings_free_pool_enabled")}</span>
          ) : status?.imageBackend === "nvidia" ? (
            <span className="provider-badge-active">{tr("ui_keys_settings_used_for_images")}</span>
          ) : null}
        </div>
        <p className="mt-1 text-[11px] leading-4 text-white/40">
          {tr("ui_keys_settings_get_a_trial_key_at", { 0: " " })}
          <a className="text-[#a5b4fc] hover:underline" href="https://build.nvidia.com/settings" target="_blank" rel="noreferrer">
            build.nvidia.com
          </a>
          {tr("ui_keys_settings_after_saving_choose_flux_1_schnell", { 0: " " })}{" "}
          <a
            className="text-[#a5b4fc] hover:underline"
            href="https://github.com/charliewwdev/OpenMontage/blob/main/docs/FREE_GPU.md"
            target="_blank"
            rel="noreferrer"
          >
            FREE_GPU.md
          </a>
        </p>
        <div className="mt-3">
          <NvidiaKeyCard status={status} onUpdated={onUpdated} />
        </div>
      </div>
    </section>
  );

  const hfSection = (
    <section className="provider-card !items-stretch !flex-col gap-3 sm:!flex-row sm:!items-center">
      <div className="provider-card-icon">HF</div>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="text-[15px] font-semibold">{tr("ui_keys_settings_hf_images")}</h3>
          <span className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-[11px] text-emerald-300">{tr("ui_keys_settings_free_tier_badge")}</span>
          {hfConfigured ? (
            <span className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-[11px] text-emerald-300">{tr("ui_keys_settings_configured")}</span>
          ) : (
            <span className="rounded-full border border-[var(--line)] px-2 py-0.5 text-[11px] text-[var(--muted)]">{tr("ui_keys_settings_not_configured")}</span>
          )}
          {hfConfigured && imageFreePoolOn ? (
            <span className="provider-badge-active">{tr("ui_keys_settings_free_pool_enabled")}</span>
          ) : status?.imageBackend === "hf" ? (
            <span className="provider-badge-active">{tr("ui_keys_settings_used_for_images")}</span>
          ) : null}
        </div>
        <p className="mt-1 text-[11px] leading-4 text-white/40">
          {tr("ui_keys_settings_hf_images_hint")}{" "}
          <a className="text-[#a5b4fc] hover:underline" href="https://huggingface.co/settings/tokens" target="_blank" rel="noreferrer">
            huggingface.co/settings/tokens
          </a>
        </p>
        <div className="mt-3">
          <HfKeyCard status={status} onUpdated={onUpdated} />
        </div>
      </div>
    </section>
  );

  const cfImageSection = (
    <section className="provider-card !items-stretch !flex-col gap-3 sm:!flex-row sm:!items-center">
      <div className="provider-card-icon">CF</div>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="text-[15px] font-semibold">{tr("ui_keys_settings_cf_images")}</h3>
          <span className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-[11px] text-emerald-300">{tr("ui_keys_settings_free_tier_badge")}</span>
          {cfImageConfigured ? (
            <span className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-[11px] text-emerald-300">{tr("ui_keys_settings_configured")}</span>
          ) : (
            <span className="rounded-full border border-[var(--line)] px-2 py-0.5 text-[11px] text-[var(--muted)]">{tr("ui_keys_settings_not_configured")}</span>
          )}
          {cfImageConfigured && imageFreePoolOn ? (
            <span className="provider-badge-active">{tr("ui_keys_settings_free_pool_enabled")}</span>
          ) : status?.imageBackend === "cloudflare" ? (
            <span className="provider-badge-active">{tr("ui_keys_settings_used_for_images")}</span>
          ) : null}
        </div>
        <p className="mt-1 text-[11px] leading-4 text-white/40">{tr("ui_keys_settings_cf_images_hint")}</p>
        <div className="mt-3">
          <CfImageKeyCard status={status} onUpdated={onUpdated} />
        </div>
      </div>
    </section>
  );

  const volcSection = (
    <section className="provider-card !items-stretch !flex-col gap-3 sm:!flex-row sm:!items-center">
      <div className="provider-card-icon">{tr("ui_keys_settings_v")}</div>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="text-[15px] font-semibold">{tr("ui_keys_settings_volcengine_ark")}</h3>
          <span className="text-xs text-[var(--muted)]">{tr("ui_keys_settings_seedream_images_seedance_video")}</span>
          {volcConfigured ? (
            <span className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-[11px] text-emerald-300">{tr("ui_keys_settings_configured")}</span>
          ) : (
            <span className="rounded-full border border-[var(--line)] px-2 py-0.5 text-[11px] text-[var(--muted)]">{tr("ui_keys_settings_not_configured")}</span>
          )}
          {status?.imageBackend === "seedream" ? <span className="provider-badge-active">{tr("ui_keys_settings_used_for_images")}</span> : null}
          {status?.videoBackend === "seedance" ? <span className="provider-badge-active">{tr("ui_keys_settings_used_for_video")}</span> : null}
        </div>
        <div className="mt-3">
          <VolcCard status={status} onUpdated={onUpdated} />
        </div>
      </div>
    </section>
  );

  const comfySection = (
    <section className="provider-card !items-stretch !flex-col gap-3 sm:!flex-row sm:!items-start">
      <div className="provider-card-icon">C</div>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="text-[15px] font-semibold">ComfyUI</h3>
          <span className="text-xs text-[var(--muted)]">{tr("ui_keys_settings_local_lan_zhichuan_cloud_rental_images")}</span>
          {status?.comfyui?.reachable ? (
            <span className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-[11px] text-emerald-300">{tr("ui_keys_settings_connected", {
                0: status.comfyui.deviceName ? ` · ${status.comfyui.deviceName}` : ""
              })}</span>
          ) : comfyConfigured ? (
            <span className="rounded-full border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-[11px] text-amber-300">{tr("ui_keys_settings_configured_not_connected")}</span>
          ) : (
            <span className="rounded-full border border-[var(--line)] px-2 py-0.5 text-[11px] text-[var(--muted)]">{tr("ui_keys_settings_not_configured")}</span>
          )}
          {status?.imageBackend === "comfyui" ? <span className="provider-badge-active">{tr("ui_keys_settings_used_for_images")}</span> : null}
          {status?.videoBackend === "comfyui" ? <span className="provider-badge-active">{tr("ui_keys_settings_used_for_video")}</span> : null}
        </div>
        <p className="mt-1 text-[11px] leading-4 text-white/40">{tr("ui_keys_settings_local")}{" "}<code className="text-white/55">http://127.0.0.1:8188</code>{tr("ui_keys_settings_a_cloud_studio_needs_your_local", {
            0: " "
          })}<a className="text-[#a5b4fc] hover:underline" href="https://gpuhome.cc/market" target="_blank" rel="noreferrer">{tr("ui_keys_settings_gpu_marketplace")}</a>{tr("ui_keys_settings_and_enter_its_custom_service_address", {
            0: " "
          })}</p>
        <p className="mt-1.5 text-[11px] leading-4 text-white/40">
          {tr("ui_keys_settings_comfy_colab_hint")}{" "}
          <a
            className="text-[#a5b4fc] hover:underline"
            href="https://github.com/charliewwdev/OpenMontage/blob/main/docs/COMFY_COLAB.md"
            target="_blank"
            rel="noreferrer"
          >
            COMFY_COLAB.md
          </a>
        </p>
        <div className="mt-2 flex flex-wrap gap-2">
          <a
            className="btn-secondary !h-8 !px-3 !text-[12px]"
            href="https://colab.research.google.com/github/charliewwdev/OpenMontage/blob/main/notebooks/comfyui_openmontage_colab.ipynb"
            target="_blank"
            rel="noreferrer"
          >
            {tr("ui_keys_settings_open_comfy_colab")}
          </a>
        </div>
        <div className="mt-3">
          <ComfyCard status={status} onUpdated={onUpdated} />
        </div>
      </div>
    </section>
  );

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-[var(--muted)]">{tr("ui_keys_settings_configured_providers_are_pinned_to_the")}</p>
        <div className="flex gap-2">
          <button type="button" className="btn-secondary" disabled={testing} onClick={onTest}>
            {testing ? <Loader2 className="h-4 w-4 animate-spin" /> : <ShieldCheck className="h-4 w-4" />}{tr("ui_keys_settings_test_connection")}</button>
          <button type="button" className="provider-add-btn" onClick={() => setEditor({ add: true })}>
            <Plus className="h-4 w-4" />{" "}{tr("ui_keys_settings_add_provider")}</button>
        </div>
      </div>

      {hasConfigured ? (
        <div className="space-y-3">
          <SectionLabel>{tr("ui_keys_settings_configured")}</SectionLabel>
          {configuredProviders.length ? (
            <div className="space-y-2.5">{configuredProviders.map(renderLlmCard)}</div>
          ) : null}
          {volcConfigured || comfyConfigured || nvidiaConfigured || hfConfigured || cfImageConfigured ? (
            <div className="space-y-2.5">
              <SectionLabel>{tr("ui_keys_settings_media_images_video")}</SectionLabel>
              {nvidiaConfigured ? nvidiaSection : null}
              {cfImageConfigured ? cfImageSection : null}
              {hfConfigured ? hfSection : null}
              {volcConfigured ? volcSection : null}
              {comfyConfigured ? comfySection : null}
            </div>
          ) : null}
        </div>
      ) : null}

      {otherProviders.length ? (
        <div className="space-y-2.5">
          <SectionLabel>{tr("ui_keys_settings_text_models_not_configured")}</SectionLabel>
          {otherProviders.map(renderLlmCard)}
        </div>
      ) : null}

      {!volcConfigured || !comfyConfigured || !nvidiaConfigured || !hfConfigured || !cfImageConfigured ? (
        <div className="space-y-2.5">
          <SectionLabel>{tr("ui_keys_settings_media_not_configured")}</SectionLabel>
          {!nvidiaConfigured ? nvidiaSection : null}
          {!cfImageConfigured ? cfImageSection : null}
          {!hfConfigured ? hfSection : null}
          {!volcConfigured ? volcSection : null}
          {!comfyConfigured ? comfySection : null}
        </div>
      ) : null}

      <ProviderEditor
        open={Boolean(editor)}
        catalog={providers}
        initial={editor?.add ? null : editor}
        onClose={() => setEditor(null)}
        onSave={savePayload}
      />
    </div>
  );
}

function NvidiaKeyCard({ status, onUpdated }) {
  useLocale();
  const [key, setKey] = useState("");
  const [saving, setSaving] = useState(false);
  const configured = status?.nvidia?.configured;
  const save = async () => {
    if (!key.trim()) {
      toast.error(tr("ui_keys_settings_please_enter_an_nvidia_api_key"));
      return;
    }
    setSaving(true);
    try {
      const data = await api("/api/settings/keys", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          NVIDIA_API_KEY: key.trim(),
          NVIDIA_IMAGE_MODEL: "flux-3-image-klein",
          STUDIO_IMAGE_BACKEND: "auto",
          STUDIO_FREE_FIRST: "1",
        }),
      });
      setKey("");
      onUpdated?.(data);
      toast.success(tr("ui_keys_settings_nvidia_key_saved"));
    } catch (e) {
      toast.error(String(e.message || e));
    } finally {
      setSaving(false);
    }
  };
  return (
    <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
      <input
        className="field sm:flex-1"
        type="password"
        autoComplete="off"
        placeholder={configured ? tr("ui_keys_settings_configured_paste_a_new_key_to", {
          0: status?.nvidia?.masked || ""
        }) : tr("ui_keys_settings_paste_nvapi_key")}
        value={key}
        onChange={(e) => setKey(e.target.value)}
      />
      <button type="button" className="btn-secondary !min-h-[38px] !px-3 text-xs" disabled={saving || !key.trim()} onClick={() => void save()}>
        {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : null}{tr("ui_keys_settings_save")}</button>
    </div>
  );
}

function HfKeyCard({ status, onUpdated }) {
  useLocale();
  const [key, setKey] = useState("");
  const [saving, setSaving] = useState(false);
  const configured = status?.hf?.configured;
  const save = async () => {
    if (!key.trim()) {
      toast.error(tr("ui_keys_settings_please_enter_hf_token"));
      return;
    }
    setSaving(true);
    try {
      const data = await api("/api/settings/keys", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          HF_TOKEN: key.trim(),
          HF_IMAGE_MODEL: "black-forest-labs/FLUX.1-schnell",
          STUDIO_IMAGE_BACKEND: "auto",
          STUDIO_FREE_FIRST: "1",
        }),
      });
      setKey("");
      onUpdated?.(data);
      toast.success(tr("ui_keys_settings_hf_token_saved"));
    } catch (e) {
      toast.error(String(e.message || e));
    } finally {
      setSaving(false);
    }
  };
  return (
    <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
      <input
        className="field sm:flex-1"
        type="password"
        autoComplete="off"
        placeholder={configured ? tr("ui_keys_settings_configured_paste_a_new_key_to", {
          0: status?.hf?.masked || ""
        }) : "hf_…"}
        value={key}
        onChange={(e) => setKey(e.target.value)}
      />
      <button type="button" className="btn-secondary !min-h-[38px] !px-3 text-xs" disabled={saving || !key.trim()} onClick={() => void save()}>
        {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : null}{tr("ui_keys_settings_save")}</button>
    </div>
  );
}

function CfImageKeyCard({ status, onUpdated }) {
  useLocale();
  const [accountId, setAccountId] = useState("");
  const [token, setToken] = useState("");
  const [saving, setSaving] = useState(false);
  const configured = status?.cloudflareImage?.configured;
  const save = async () => {
    if (!accountId.trim() || !token.trim()) {
      toast.error(tr("ui_keys_settings_please_enter_cf_creds"));
      return;
    }
    setSaving(true);
    try {
      const data = await api("/api/settings/keys", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          CF_ACCOUNT_ID: accountId.trim(),
          CF_API_TOKEN: token.trim(),
          CF_IMAGE_MODEL: "@cf/black-forest-labs/flux-1-schnell",
          STUDIO_IMAGE_BACKEND: "auto",
          STUDIO_FREE_FIRST: "1",
        }),
      });
      setAccountId("");
      setToken("");
      onUpdated?.(data);
      toast.success(tr("ui_keys_settings_cf_creds_saved"));
    } catch (e) {
      toast.error(String(e.message || e));
    } finally {
      setSaving(false);
    }
  };
  return (
    <div className="flex flex-col gap-2">
      <input
        className="field"
        autoComplete="off"
        placeholder={configured ? tr("ui_keys_settings_cf_account_configured", {
          0: status?.cloudflareImage?.accountId || ""
        }) : "CF_ACCOUNT_ID"}
        value={accountId}
        onChange={(e) => setAccountId(e.target.value)}
      />
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
        <input
          className="field sm:flex-1"
          type="password"
          autoComplete="off"
          placeholder={configured ? tr("ui_keys_settings_configured_paste_a_new_key_to", {
            0: status?.cloudflareImage?.masked || ""
          }) : "CF_API_TOKEN"}
          value={token}
          onChange={(e) => setToken(e.target.value)}
        />
        <button
          type="button"
          className="btn-secondary !min-h-[38px] !px-3 text-xs"
          disabled={saving || !accountId.trim() || !token.trim()}
          onClick={() => void save()}
        >
          {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
          {tr("ui_keys_settings_save")}
        </button>
      </div>
    </div>
  );
}

function VolcCard({ status, onUpdated }) {
  useLocale();
  const [key, setKey] = useState("");
  const [saving, setSaving] = useState(false);
  const [editing, setEditing] = useState(false);
  const configured = status?.volcengine?.configured;
  const masked = status?.volcengine?.masked || "";
  const canSave = Boolean(key.trim());

  useEffect(() => {
    if (!configured) setEditing(true);
    else setEditing(false);
  }, [configured]);

  const save = async () => {
    if (!key.trim()) {
      toast.error(configured ? tr("ui_keys_settings_paste_a_new_key_before_saving") : tr("ui_keys_settings_please_enter_a_volcengine_api_key"));
      return;
    }
    setSaving(true);
    try {
      const data = await api("/api/settings/keys", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ VOLCENGINE_API_KEY: key.trim() }),
      });
      setKey("");
      setEditing(false);
      onUpdated?.(data);
      toast.success(configured ? tr("ui_keys_settings_volcengine_key_updated") : tr("ui_keys_settings_volcengine_key_saved"));
    } catch (e) {
      toast.error(String(e.message || e));
    } finally {
      setSaving(false);
    }
  };

  if (configured && !editing) {
    return (
      <div className="flex flex-wrap items-center gap-2">
        <span className="rounded-lg border border-emerald-500/25 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-200">{tr("ui_keys_settings_configured_2", {
            0: masked || "Key"
          })}</span>
        <button
          type="button"
          className="provider-icon-btn"
          title={tr("ui_keys_settings_edit_key")}
          aria-label={tr("ui_keys_settings_edit_key")}
          onClick={() => {
            setKey("");
            setEditing(true);
          }}
        >
          <Pencil className="h-3.5 w-3.5" />
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
      <input
        className="field sm:flex-1"
        type="password"
        autoComplete="off"
        placeholder={configured ? tr("ui_keys_settings_paste_a_new_key_to_replace") : tr("ui_keys_settings_paste_volcengine_ark_api_key")}
        value={key}
        onChange={(e) => setKey(e.target.value)}
      />
      <button
        type="button"
        className="provider-icon-btn provider-icon-btn-primary !min-h-[38px] !px-3"
        disabled={saving || !canSave}
        onClick={() => void save()}
      >
        {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
        {configured ? tr("ui_keys_settings_update_key") : tr("ui_keys_settings_save")}
      </button>
      {configured ? (
        <button
          type="button"
          className="btn-secondary !min-h-[38px] !px-3 text-xs"
          disabled={saving}
          onClick={() => {
            setKey("");
            setEditing(false);
          }}
        >{tr("ui_keys_settings_cancel")}</button>
      ) : null}
    </div>
  );
}

function shortenUrl(url) {
  const raw = String(url || "").trim();
  if (!raw) return "";
  try {
    const u = new URL(raw);
    const host = u.host || raw;
    if (host.length <= 42) return host;
    return `${host.slice(0, 18)}…${host.slice(-14)}`;
  } catch {
    if (raw.length <= 42) return raw;
    return `${raw.slice(0, 18)}…${raw.slice(-14)}`;
  }
}

const COMFY_LOCAL_PRESETS = [
  {
    get label() {
      return tr("ui_keys_settings_local_8188");
    },

    url: "http://127.0.0.1:8188"
  },
  { label: "localhost", url: "http://localhost:8188" },
];

function ComfyCard({ status, onUpdated }) {
  useLocale();
  const comfy = status?.comfyui || {};
  const [serverUrl, setServerUrl] = useState(comfy.serverUrl || "");
  const [imageUrl, setImageUrl] = useState(comfy.imageUrl || "");
  const [videoUrl, setVideoUrl] = useState(comfy.videoUrl || "");
  const [checkpoint, setCheckpoint] = useState(comfy.checkpoint || "");
  const [videoModel, setVideoModel] = useState(comfy.videoModel || "");
  const [apiKey, setApiKey] = useState("");
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [editing, setEditing] = useState(!comfy.configured);

  useEffect(() => {
    setServerUrl(comfy.serverUrl || "");
    setImageUrl(comfy.imageUrl || "");
    setVideoUrl(comfy.videoUrl || "");
    setCheckpoint(comfy.checkpoint || "");
    setVideoModel(comfy.videoModel || "");
    setEditing(!comfy.configured);
  }, [comfy.serverUrl, comfy.imageUrl, comfy.videoUrl, comfy.checkpoint, comfy.videoModel, comfy.configured]);

  const savedUrl = (comfy.serverUrl || "").replace(/\/$/, "");
  const draftUrl = serverUrl.trim().replace(/\/$/, "");
  const dirty =
    draftUrl !== savedUrl ||
    imageUrl.trim().replace(/\/$/, "") !== (comfy.imageUrl || "").replace(/\/$/, "") ||
    videoUrl.trim().replace(/\/$/, "") !== (comfy.videoUrl || "").replace(/\/$/, "") ||
    Boolean(apiKey.trim());
  const canSave = dirty;

  const save = async (extra = {}) => {
    const url = String((extra.serverUrl ?? serverUrl) || comfy.serverUrl || "")
      .trim()
      .replace(/\/$/, "");
    const ckpt = (extra.checkpoint ?? checkpoint).trim();
    const vmodel = (extra.videoModel ?? videoModel).trim();
    const img = String((extra.imageUrl ?? imageUrl) || comfy.imageUrl || "")
      .trim()
      .replace(/\/$/, "");
    const vid = String((extra.videoUrl ?? videoUrl) || comfy.videoUrl || "")
      .trim()
      .replace(/\/$/, "");
    setSaving(true);
    try {
      const payload = {
        COMFYUI_SERVER_URL: url,
        COMFYUI_IMAGE_SERVER_URL: img,
        COMFYUI_VIDEO_SERVER_URL: vid,
      };
      if ("checkpoint" in extra || ckpt) payload.COMFYUI_CHECKPOINT = ckpt;
      if ("videoModel" in extra || vmodel) payload.COMFYUI_VIDEO_MODEL = vmodel;
      if (apiKey.trim()) {
        payload.COMFY_API_KEY = apiKey.trim();
        setApiKey("");
      }
      const data = await api("/api/settings/keys", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      onUpdated?.(data);
      if (url) setEditing(false);
      toast.success(url ? tr("ui_keys_settings_comfyui_saved") : tr("ui_keys_settings_comfyui_url_cleared"));
      return data;
    } catch (e) {
      toast.error(String(e.message || e));
      return null;
    } finally {
      setSaving(false);
    }
  };

  const test = async () => {
    setTesting(true);
    try {
      if (editing && dirty) {
        await save();
      }
      const data = await api("/api/settings/keys/test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: "{}",
      });
      onUpdated?.(data);
      const r = data?.results?.comfyui;
      if (r?.ok) {
        const vid = (r.videoModels || []).length;
        toast.success(
          vid
            ? tr("ui_keys_settings_comfyui_connected_images_video_model", {
            0: r.checkpointCount || 0,
            vid: vid
          })
            : tr("ui_keys_settings_comfyui_connected_image_models_no_video", {
            0: r.checkpointCount || 0
          }),
        );
      } else {
        toast.error(r?.error || tr("ui_keys_settings_comfyui_connection_failed"));
      }
    } catch (e) {
      toast.error(String(e.message || e));
    } finally {
      setTesting(false);
    }
  };

  const checkpoints = comfy.checkpoints || [];
  const videoModels = comfy.videoModels || [];
  const hasUrl = Boolean(savedUrl || draftUrl);
  const isLocal =
    /^(https?:\/\/)?(127\.0\.0\.1|localhost)(:\d+)?\/?$/i.test(savedUrl || draftUrl) ||
    (savedUrl || draftUrl).includes("127.0.0.1") ||
    (savedUrl || draftUrl).includes("localhost");

  return (
    <div className="space-y-3">
      {comfy.configured && !editing ? (
        <div className="flex flex-wrap items-center gap-2">
          <span
            className="max-w-full truncate rounded-lg border border-emerald-500/25 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-200"
            title={savedUrl}
          >{tr("ui_keys_settings_configured_2", {
              0: shortenUrl(savedUrl)
            })}{isLocal ? ` ${tr("ui_keys_settings_local_2")}` : ""}
          </span>
          <button
            type="button"
            className="provider-icon-btn"
            title={tr("ui_keys_settings_edit_url_and_models")}
            aria-label={tr("ui_keys_settings_edit_url_and_models")}
            onClick={() => {
              setServerUrl(savedUrl);
              setEditing(true);
              setShowAdvanced(Boolean(comfy.imageUrl || comfy.videoUrl));
            }}
          >
            <Pencil className="h-3.5 w-3.5" />
          </button>
          <button
            type="button"
            className="btn-secondary !min-h-[38px] !px-3 text-xs"
            disabled={testing || !hasUrl}
            onClick={() => void test()}
          >
            {testing ? <Loader2 className="h-4 w-4 animate-spin" /> : <ShieldCheck className="h-3.5 w-3.5" />}{tr("ui_keys_settings_test_connection")}</button>
          {comfy.docs ? (
            <a className="btn-secondary !min-h-[38px] !px-3 text-xs" href={comfy.docs} target="_blank" rel="noreferrer">{tr("ui_keys_settings_comfyui_docs")}</a>
          ) : null}
        </div>
      ) : (
        <div className="space-y-2">
          <div className="flex flex-wrap gap-1.5">
            {COMFY_LOCAL_PRESETS.map((preset) => (
              <button
                key={preset.url}
                type="button"
                className="rounded-full border border-white/15 bg-white/[0.04] px-2.5 py-1 text-[11px] text-white/70 transition hover:border-[#7c6cff]/50 hover:text-white"
                onClick={() => {
                  setServerUrl(preset.url);
                  setEditing(true);
                }}
              >
                {preset.label}
              </button>
            ))}
          </div>
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <input
              className="field sm:flex-1"
              type="url"
              autoComplete="off"
              placeholder={tr("ui_keys_settings_local_http_127_0_0_1")}
              value={serverUrl}
              onChange={(e) => setServerUrl(e.target.value)}
            />
            <button
              type="button"
              className="provider-icon-btn provider-icon-btn-primary !min-h-[38px] !px-3"
              disabled={saving || !canSave}
              onClick={() => void save()}
            >
              {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              {comfy.configured ? tr("ui_keys_settings_update") : tr("ui_keys_settings_save")}
            </button>
            {comfy.configured ? (
              <button
                type="button"
                className="btn-secondary !min-h-[38px] !px-3 text-xs"
                disabled={saving}
                onClick={() => {
                  setServerUrl(savedUrl);
                  setImageUrl(comfy.imageUrl || "");
                  setVideoUrl(comfy.videoUrl || "");
                  setApiKey("");
                  setEditing(false);
                }}
              >{tr("ui_keys_settings_cancel")}</button>
            ) : null}
            <button
              type="button"
              className="btn-secondary !min-h-[38px] !px-3 text-xs"
              disabled={testing || !draftUrl}
              onClick={() => void test()}
            >
              {testing ? <Loader2 className="h-4 w-4 animate-spin" /> : <ShieldCheck className="h-3.5 w-3.5" />}{tr("ui_keys_settings_test_connection")}</button>
          </div>
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <span className="text-[11px] text-white/35">{tr("ui_keys_settings_image_model")}</span>
        {checkpoints.length ? (
          <select
            className="field !min-h-[30px] !w-auto !max-w-[min(100%,320px)] !py-1 !text-xs"
            value={checkpoint || checkpoints[0]}
            disabled={saving}
            onChange={(e) => {
              setCheckpoint(e.target.value);
              void save({ checkpoint: e.target.value });
            }}
          >
            {checkpoints.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        ) : (
          <input
            className="field !min-h-[30px] !max-w-[min(100%,320px)] !py-1 !text-xs"
            placeholder={tr("ui_keys_settings_e_g_realvisxl_qwen_image_3")}
            value={checkpoint}
            disabled={saving}
            onChange={(e) => setCheckpoint(e.target.value)}
            onBlur={() => {
              if (checkpoint.trim() && checkpoint.trim() !== (comfy.checkpoint || "")) {
                void save({ checkpoint: checkpoint.trim() });
              }
            }}
          />
        )}
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <span className="text-[11px] text-white/35">{tr("ui_keys_settings_video_model")}</span>
        {videoModels.length ? (
          <select
            className="field !min-h-[30px] !w-auto !max-w-[min(100%,320px)] !py-1 !text-xs"
            value={videoModel || videoModels[0]}
            disabled={saving}
            onChange={(e) => {
              setVideoModel(e.target.value);
              void save({ videoModel: e.target.value });
            }}
          >
            {videoModels.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
        ) : (
          <input
            className="field !min-h-[30px] !max-w-[min(100%,320px)] !py-1 !text-xs"
            placeholder={tr("ui_keys_settings_e_g_minimax_hailuo_02_h3")}
            value={videoModel}
            disabled={saving}
            onChange={(e) => setVideoModel(e.target.value)}
            onBlur={() => {
              if (videoModel.trim() && videoModel.trim() !== (comfy.videoModel || "")) {
                void save({ videoModel: videoModel.trim() });
              }
            }}
          />
        )}
      </div>

      <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
        <span className="shrink-0 text-[11px] text-white/35">Comfy Org API Key</span>
        {comfy.apiKeyConfigured && !apiKey ? (
          <span className="rounded-lg border border-emerald-500/25 bg-emerald-500/10 px-2.5 py-1.5 text-xs text-emerald-200">{tr("ui_keys_settings_configured_2", {
              0: comfy.apiKeyMasked || "Key"
            })}</span>
        ) : null}
        <input
          className="field sm:flex-1 !min-h-[34px] !py-1 !text-xs"
          type="password"
          autoComplete="off"
          placeholder={comfy.apiKeyConfigured ? tr("ui_keys_settings_paste_a_new_key_to_replace_2") : tr("ui_keys_settings_optional_platform_comfy_org_api_key")}
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
        />
        {apiKey.trim() ? (
          <button
            type="button"
            className="provider-icon-btn provider-icon-btn-primary !min-h-[34px] !px-3 text-xs"
            disabled={saving}
            onClick={() => void save()}
          >
            {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}{tr("ui_keys_settings_save_key")}</button>
        ) : null}
      </div>

      <button
        type="button"
        className="text-[11px] text-white/40 underline-offset-2 hover:text-white/70 hover:underline"
        onClick={() => setShowAdvanced((v) => !v)}
      >
        {showAdvanced ? tr("ui_keys_settings_hide_advanced") : tr("ui_keys_settings_advanced_separate_image_video_urls")}
      </button>
      {showAdvanced ? (
        <div className="grid gap-2 sm:grid-cols-2">
          <label className="space-y-1">
            <span className="text-[11px] text-white/35">{tr("ui_keys_settings_image_url_optional")}</span>
            <input
              className="field !min-h-[34px] !py-1 !text-xs"
              type="url"
              placeholder={tr("ui_keys_settings_defaults_to_the_main_url")}
              value={imageUrl}
              onChange={(e) => setImageUrl(e.target.value)}
            />
          </label>
          <label className="space-y-1">
            <span className="text-[11px] text-white/35">{tr("ui_keys_settings_video_url_optional")}</span>
            <input
              className="field !min-h-[34px] !py-1 !text-xs"
              type="url"
              placeholder={tr("ui_keys_settings_defaults_to_the_main_url")}
              value={videoUrl}
              onChange={(e) => setVideoUrl(e.target.value)}
            />
          </label>
          {editing || dirty ? (
            <button
              type="button"
              className="provider-icon-btn provider-icon-btn-primary !min-h-[34px] !px-3 text-xs sm:col-span-2 sm:w-fit"
              disabled={saving || !canSave}
              onClick={() => void save()}
            >
              {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}{tr("ui_keys_settings_save_advanced_urls")}</button>
          ) : null}
        </div>
      ) : null}

      {comfy.error ? <p className="text-[11px] text-amber-300/90">{comfy.error}</p> : null}
    </div>
  );
}

function buildPageItems(page, pageCount) {
  if (pageCount <= 7) {
    return Array.from({ length: pageCount }, (_, i) => i + 1);
  }
  const items = new Set([1, pageCount, page, page - 1, page + 1, page - 2, page + 2]);
  const sorted = [...items].filter((n) => n >= 1 && n <= pageCount).sort((a, b) => a - b);
  const out = [];
  for (let i = 0; i < sorted.length; i += 1) {
    if (i > 0 && sorted[i] - sorted[i - 1] > 1) out.push("…");
    out.push(sorted[i]);
  }
  return out;
}

function LogsPager({ meta, pageSize, onPageChange, onPageSizeChange, loading }) {
  useLocale();
  const page = meta?.page || 1;
  const pageCount = meta?.pageCount || 1;
  const total = meta?.total || 0;
  const limit = meta?.limit || pageSize;
  const offset = meta?.offset || 0;
  const from = total ? offset + 1 : 0;
  const to = Math.min(offset + limit, total);
  const items = buildPageItems(page, pageCount);

  return (
    <div className="flex flex-col gap-3 border-t border-[var(--line)] px-3 py-3 sm:flex-row sm:items-center sm:justify-between">
      <div className="text-xs text-[var(--muted)]">
        {total ? (
          <>{tr("ui_keys_settings_showing")}{" "}<span className="tabular-nums text-white/80">{from}</span>–
                        <span className="tabular-nums text-white/80">{to}</span>{" "}{tr("ui_keys_settings_of", {
              0: " "
            })}<span className="tabular-nums text-white/80">{fmtNum(total)}</span>{" "}{tr("ui_keys_settings_entries")}</>
        ) : (
          tr("ui_keys_settings_no_records")
        )}
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <label className="flex items-center gap-1.5 text-xs text-[var(--muted)]">{tr("ui_keys_settings_per_page")}<select
            className="field !w-auto !py-1 !text-xs"
            value={pageSize}
            disabled={loading}
            onChange={(e) => onPageSizeChange?.(Number(e.target.value) || 20)}
          >
            {[10, 20, 50, 100].map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
        </label>
        <div className="flex items-center gap-1">
          <button
            type="button"
            className="btn-secondary !px-2 !py-1"
            disabled={loading || page <= 1}
            onClick={() => onPageChange?.(1)}
            title={tr("ui_keys_settings_first")}
            aria-label={tr("ui_keys_settings_first")}
          >
            <ChevronsLeft className="h-3.5 w-3.5" />
          </button>
          <button
            type="button"
            className="btn-secondary !px-2 !py-1"
            disabled={loading || page <= 1}
            onClick={() => onPageChange?.(page - 1)}
            title={tr("ui_keys_settings_previous")}
            aria-label={tr("ui_keys_settings_previous")}
          >
            <ChevronLeft className="h-3.5 w-3.5" />
          </button>
          {items.map((item, idx) =>
            item === "…" ? (
              <span key={`e-${idx}`} className="px-1 text-xs text-[var(--muted)]">
                …
              </span>
            ) : (
              <button
                key={item}
                type="button"
                className={`min-w-[2rem] rounded-md px-2 py-1 text-xs tabular-nums ${
                  item === page ? "bg-white/15 text-white" : "text-[var(--muted)] hover:bg-white/8 hover:text-white"
                }`}
                disabled={loading || item === page}
                onClick={() => onPageChange?.(item)}
              >
                {item}
              </button>
            ),
          )}
          <button
            type="button"
            className="btn-secondary !px-2 !py-1"
            disabled={loading || page >= pageCount}
            onClick={() => onPageChange?.(page + 1)}
            title={tr("ui_keys_settings_next")}
            aria-label={tr("ui_keys_settings_next")}
          >
            <ChevronRight className="h-3.5 w-3.5" />
          </button>
          <button
            type="button"
            className="btn-secondary !px-2 !py-1"
            disabled={loading || page >= pageCount}
            onClick={() => onPageChange?.(pageCount)}
            title={tr("ui_keys_settings_last")}
            aria-label={tr("ui_keys_settings_last")}
          >
            <ChevronsRight className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
    </div>
  );
}

export function UsageSettings() {
  useLocale();
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState(null);
  const [subTab, setSubTab] = useState("logs");
  const [range, setRange] = useState("7d");
  const [kind, setKind] = useState("all");
  const [provider, setProvider] = useState("");
  const [model, setModel] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);

  const load = async () => {
    setLoading(true);
    try {
      const offset = Math.max(0, (page - 1) * pageSize);
      const qs = new URLSearchParams({
        range,
        kind,
        provider,
        model,
        log_limit: String(pageSize),
        log_offset: String(offset),
      });
      const res = await api(`/api/settings/usage?${qs}`);
      setData(res);
      const meta = res?.logsMeta;
      if (meta?.page && meta.page !== page) {
        setPage(meta.page);
      }
    } catch (e) {
      toast.error(String(e.message || e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    setPage(1);
  }, [range, kind, provider, model, pageSize]);

  useEffect(() => {
    void load();
  }, [range, kind, provider, model, page, pageSize]);

  const hero = data?.hero || {};
  const trend = data?.trend || { buckets: [], requests: [], tokens_in: [], tokens_out: [], cost_usd: [] };
  const logsMeta = data?.logsMeta || { total: 0, page: 1, pageCount: 1, offset: 0, limit: pageSize };

  return (
    <PageShell eyebrow="Settings" title={tr("ui_keys_settings_usage")} description={tr("ui_keys_settings_see_call_counts_tokens_cost_and")}>
      <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-3">
        <div className="usage-seg">
          {[
            ["today", tr("ui_keys_settings_today")],
            ["7d", tr("ui_keys_settings_last_7_days")],
            ["30d", tr("ui_keys_settings_last_30_days")],
          ].map(([id, label]) => (
            <button key={id} type="button" className={range === id ? "active" : ""} onClick={() => setRange(id)}>
              {label}
            </button>
          ))}
        </div>
        <select className="field !w-auto !py-1.5" value={kind} onChange={(e) => setKind(e.target.value)}>
          <option value="all">{tr("ui_keys_settings_all_types")}</option>
          <option value="text">{tr("ui_keys_settings_text")}</option>
          <option value="image">{tr("ui_keys_settings_image")}</option>
          <option value="video">{tr("ui_keys_settings_video")}</option>
        </select>
        <select className="field !w-auto !py-1.5" value={provider} onChange={(e) => setProvider(e.target.value)}>
          <option value="">{tr("ui_keys_settings_all_providers")}</option>
          {(data?.filters?.providers || []).map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </select>
        <select className="field !w-auto !py-1.5" value={model} onChange={(e) => setModel(e.target.value)}>
          <option value="">{tr("ui_keys_settings_all_models")}</option>
          {(data?.filters?.models || []).map((m) => (
            <option key={m} value={m}>
              {m}
            </option>
          ))}
        </select>
        <button type="button" className="btn-secondary" onClick={() => void load()}>{tr("ui_keys_settings_refresh")}</button>
      </div>

      {loading && !data ? (
        <div className="panel flex items-center gap-2 px-5 py-10 text-sm text-[var(--muted)]">
          <Loader2 className="h-4 w-4 animate-spin" />{" "}{tr("ui_keys_settings_loading_usage")}</div>
      ) : (
        <>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
            {[
              [tr("ui_keys_settings_total_requests"), fmtNum(hero.requests)],
              [tr("ui_keys_settings_tokens_actually_used"), fmtNum(hero.tokens)],
              [tr("ui_keys_settings_cache_hit_rate"), fmtPct(hero.cache_hit_rate)],
              [tr("ui_keys_settings_estimated_cost"), fmtUsd(hero.cost_usd)],
              [tr("ui_keys_settings_success_rate"), fmtPct(hero.success_rate)],
            ].map(([label, value]) => (
              <div key={label} className="usage-hero">
                <div className="text-[11px] uppercase tracking-[0.08em] text-[var(--muted)]">{label}</div>
                <div className="mt-1.5 text-2xl font-semibold tracking-tight">{value}</div>
              </div>
            ))}
          </div>

          <div className="grid gap-4 xl:grid-cols-2">
            <section className="panel p-4">
              <div className="label">{tr("ui_keys_settings_request_trend")}</div>
              <LineChart
                labels={trend.buckets || []}
                series={[{ name: "requests", data: trend.requests || [], color: "#7c6cff" }]}
              />
            </section>
            <section className="panel p-4">
              <div className="mb-1 flex flex-wrap gap-3 text-[11px] text-[var(--muted)]">
                <span className="text-sky-400">{tr("ui_keys_settings_input")}</span>
                <span className="text-emerald-400">{tr("ui_keys_settings_output")}</span>
                <span className="text-orange-400">{tr("ui_keys_settings_cache_write")}</span>
                <span className="text-violet-400">{tr("ui_keys_settings_cache_hit")}</span>
                <span className="text-rose-400">{tr("ui_keys_settings_cost")}</span>
              </div>
              <div className="label">{tr("ui_keys_settings_token_cost_trend")}</div>
              <LineChart
                labels={trend.buckets || []}
                series={[
                  { name: "in", data: trend.tokens_in || [], color: "#38bdf8" },
                  { name: "out", data: trend.tokens_out || [], color: "#34d399" },
                  { name: "cw", data: trend.cache_write || [], color: "#fb923c" },
                  { name: "cr", data: trend.cache_read || [], color: "#a78bfa" },
                  {
                    name: "cost",
                    data: (trend.cost_usd || []).map((v) => Number(v) * 100000),
                    color: "#fb7185",
                  },
                ]}
              />
            </section>
          </div>

          <div className="usage-seg">
            {[
              ["logs", tr("ui_keys_settings_request_log")],
              ["providers", tr("ui_keys_settings_provider")],
              ["models", tr("ui_keys_settings_model")],
            ].map(([id, label]) => (
              <button key={id} type="button" className={subTab === id ? "active" : ""} onClick={() => setSubTab(id)}>
                {label}
              </button>
            ))}
          </div>

          {subTab === "logs" ? (
            <div className="panel overflow-hidden">
              <div className="overflow-x-auto">
                <table className="min-w-full text-left text-sm">
                  <thead className="text-xs text-[var(--muted)]">
                    <tr>
                      {[tr("ui_keys_settings_time"), tr("ui_keys_settings_provider"), tr("ui_keys_settings_model"), tr("ui_keys_settings_type"), "Token", tr("ui_keys_settings_cost_2"), tr("ui_keys_settings_duration"), tr("ui_keys_settings_status")].map((h) => (
                        <th key={h} className="px-3 py-2 font-medium">
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {(data?.logs || []).map((row, idx) => (
                      <tr key={`${row.ts}-${idx}`} className="border-t border-[var(--line)]">
                        <td className="px-3 py-2 whitespace-nowrap text-xs">{String(row.ts || "").replace("T", " ").slice(0, 19)}</td>
                        <td className="px-3 py-2">{row.provider}</td>
                        <td className="px-3 py-2">{row.model}</td>
                        <td className="px-3 py-2">{row.kind}</td>
                        <td className="px-3 py-2 text-xs">
                          {fmtNum(row.tokens_in)}→{fmtNum(row.tokens_out)}
                        </td>
                        <td className="px-3 py-2">{fmtUsd(row.cost_usd)}</td>
                        <td className="px-3 py-2">{latencyBadge(row.latency_ms)}</td>
                        <td className="px-3 py-2">
                          {row.ok ? (
                            <span className="inline-flex items-center gap-1 text-[var(--ok)]">
                              <CheckCircle2 className="h-3.5 w-3.5" /> {row.status}
                            </span>
                          ) : (
                            <span className="text-red-400">{row.status}</span>
                          )}
                        </td>
                      </tr>
                    ))}
                    {!data?.logs?.length ? (
                      <tr>
                        <td colSpan={8} className="px-3 py-8 text-center text-[var(--muted)]">{tr("ui_keys_settings_no_requests_yet")}</td>
                      </tr>
                    ) : null}
                  </tbody>
                </table>
              </div>
              <LogsPager
                meta={logsMeta}
                pageSize={pageSize}
                loading={loading}
                onPageChange={(next) => setPage(Math.max(1, next))}
                onPageSizeChange={(size) => {
                  setPageSize(size);
                  setPage(1);
                }}
              />
            </div>
          ) : null}

          {subTab === "providers" ? (
            <div className="panel overflow-x-auto">
              <table className="min-w-full text-left text-sm">
                <thead className="text-xs text-[var(--muted)]">
                  <tr>
                    {[tr("ui_keys_settings_provider"), tr("ui_keys_settings_requests"), tr("ui_keys_settings_succeeded"), tr("ui_keys_settings_failed"), tr("ui_keys_settings_success_rate"), "Token", tr("ui_keys_settings_cost_2"), tr("ui_keys_settings_avg_latency")].map((h) => (
                      <th key={h} className="px-3 py-2 font-medium">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {(data?.byProvider || []).map((row) => (
                    <tr key={row.provider} className="border-t border-[var(--line)]">
                      <td className="px-3 py-2">{row.provider}</td>
                      <td className="px-3 py-2">{row.requests}</td>
                      <td className="px-3 py-2">{row.ok}</td>
                      <td className="px-3 py-2">{row.fail}</td>
                      <td className="px-3 py-2">{fmtPct(row.success_rate)}</td>
                      <td className="px-3 py-2">{fmtNum(row.tokens)}</td>
                      <td className="px-3 py-2">{fmtUsd(row.cost_usd)}</td>
                      <td className="px-3 py-2">{latencyBadge(row.avg_latency_ms)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}

          {subTab === "models" ? (
            <div className="panel overflow-x-auto">
              <table className="min-w-full text-left text-sm">
                <thead className="text-xs text-[var(--muted)]">
                  <tr>
                    {[tr("ui_keys_settings_model"), tr("ui_keys_settings_provider"), tr("ui_keys_settings_requests"), tr("ui_keys_settings_input_tokens"), tr("ui_keys_settings_output_tokens"), tr("ui_keys_settings_cost_2"), tr("ui_keys_settings_avg_latency")].map((h) => (
                      <th key={h} className="px-3 py-2 font-medium">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {(data?.byModel || []).map((row) => (
                    <tr key={`${row.provider}-${row.model}`} className="border-t border-[var(--line)]">
                      <td className="px-3 py-2">{row.model}</td>
                      <td className="px-3 py-2">{row.provider}</td>
                      <td className="px-3 py-2">{row.requests}</td>
                      <td className="px-3 py-2">{fmtNum(row.tokens_in)}</td>
                      <td className="px-3 py-2">{fmtNum(row.tokens_out)}</td>
                      <td className="px-3 py-2">{fmtUsd(row.cost_usd)}</td>
                      <td className="px-3 py-2">{latencyBadge(row.avg_latency_ms)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            ) : null}
        </>
      )}
      </div>
    </PageShell>
  );
}

export function KeysSettings({ config, onUpdated }) {
  const { locale } = useLocale();
  const catalog = config?.llmProviders || [];
  const [loading, setLoading] = useState(true);
  const [testing, setTesting] = useState(false);
  const [status, setStatus] = useState(null);

  const refresh = async () => {
    setLoading(true);
    try {
      const data = await api("/api/settings/keys");
      setStatus(data.keys);
      onUpdated?.(data);
    } catch (error) {
      toast.error(String(error.message || error));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void refresh();
  }, []);

  const onKeysUpdated = (data) => {
    setStatus(data.keys);
    onUpdated?.(data);
    window.dispatchEvent(new CustomEvent("studio-keys-changed"));
  };

  const test = async () => {
    setTesting(true);
    try {
      const data = await api("/api/settings/keys/test", { method: "POST" });
      const llm = data.results?.llm || data.results?.deepseek;
      if (llm?.ok) toast.success(tr("ui_keys_settings_text_model_available", {
        0: data.keys?.llmBackend || "llm"
      }));
      else toast.error(llm?.error || tr("ui_keys_settings_check_failed"));
      setStatus(data.keys);
      onUpdated?.(data);
    } catch (error) {
      toast.error(String(error.message || error));
    } finally {
      setTesting(false);
    }
  };

  const activeLabel = useMemo(() => {
    const list = status?.llmProviders || catalog;
    const id = status?.llmBackend;
    return list.find((p) => p.id === id)?.label || id || tr("ui_keys_settings_not_enabled");
  }, [status, catalog, locale]);

  return (
    <PageShell
      eyebrow="Settings"
      title={tr("ui_keys_settings_model_settings")}
      description={tr("ui_keys_settings_manage_text_and_media_providers_current", {
        activeLabel: activeLabel
      })}
    >
      {loading && !status ? (
        <div className="panel flex items-center gap-2 px-5 py-10 text-sm text-[var(--muted)]">
          <Loader2 className="h-4 w-4 animate-spin" />{" "}{tr("ui_keys_settings_loading_settings")}</div>
      ) : (
        <ProvidersTab
          status={status}
          catalog={catalog}
          onUpdated={onKeysUpdated}
          testing={testing}
          onTest={() => void test()}
        />
      )}
    </PageShell>
  );
}
