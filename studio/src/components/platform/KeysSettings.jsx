import { useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import {
  CheckCircle2,
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
  const width = 640;
  const pad = 24;
  const maxY = Math.max(1, ...series.flatMap((s) => s.data));
  const n = Math.max(1, labels.length);
  const toX = (i) => pad + (i * (width - pad * 2)) / Math.max(1, n - 1);
  const toY = (v) => height - pad - ((v || 0) / maxY) * (height - pad * 2);
  if (!labels.length) {
    return (
      <div className="flex h-40 items-center justify-center text-sm text-[var(--muted)]">暂无数据</div>
    );
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
        toast.error("请填写 API Key");
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
          <h3 className="text-lg font-semibold">{initial ? "编辑供应商" : "添加供应商"}</h3>
          <button type="button" className="btn-ghost p-1" onClick={onClose}>
            <X className="h-4 w-4" />
          </button>
        </div>
        {!initial ? (
          <label>
            <span className="label">预设</span>
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
          <span className="label">API Key {initial?.configured ? `· 已配置 ${initial.masked}` : ""}</span>
          <input
            className="field"
            type="password"
            autoComplete="off"
            placeholder={initial?.configured ? "留空则保留现有 Key" : preset?.placeholder || "sk-..."}
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
                <option value="__custom__">自定义模型 ID…</option>
              </select>
              {!(preset.models || []).some((m) => m.id === model) ? (
                <input
                  className="field"
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                  placeholder="自定义模型 ID"
                />
              ) : null}
            </div>
          ) : (
            <input className="field" value={model} onChange={(e) => setModel(e.target.value)} />
          )}
        </label>
        {preset?.hint ? <p className="text-[11px] leading-4 text-white/45">{preset.hint}</p> : null}
        {preset?.docs ? (
          <a className="text-xs text-[#a5b4fc] hover:underline" href={preset.docs} target="_blank" rel="noreferrer">
            打开渠道文档 / 控制台
          </a>
        ) : null}
        <div className="flex justify-end gap-2 pt-2">
          <button type="button" className="btn-secondary" onClick={onClose}>
            取消
          </button>
          <button type="button" className="btn-primary" disabled={saving} onClick={() => void submit()}>
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
            保存并启用
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
}

function ProvidersTab({ status, catalog, onUpdated, testing, onTest }) {
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
    toast.success("已保存");
    return data;
  };

  const enable = async (p) => {
    if (!p.configured) {
      setEditor(p);
      return;
    }
    setBusyId(p.id);
    try {
      await savePayload({ LLM_PROVIDER: p.id });
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
      await savePayload({
        LLM_PROVIDER: p.id,
        [p.modelEnv]: nextModel,
      });
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
      toast.success(`已清空 ${p.label}`);
    } catch (e) {
      toast.error(String(e.message || e));
    } finally {
      setBusyId("");
    }
  };

  const configuredProviders = providers.filter((p) => p.configured);
  const otherProviders = providers.filter((p) => !p.configured);

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-[var(--muted)]">
          文本模型在下方卡片（铅笔=改 Key）；火山 / ComfyUI 单独成块。已保存的 Key 仍在服务端，不会因页面改版丢失。
        </p>
        <div className="flex gap-2">
          <button type="button" className="btn-secondary" disabled={testing} onClick={onTest}>
            {testing ? <Loader2 className="h-4 w-4 animate-spin" /> : <ShieldCheck className="h-4 w-4" />}
            检测连通
          </button>
          <button type="button" className="provider-add-btn" onClick={() => setEditor({ add: true })}>
            <Plus className="h-4 w-4" /> 添加供应商
          </button>
        </div>
      </div>

      <div className="space-y-2.5">
        {[...configuredProviders, ...otherProviders].map((p, idx) => {
          const isActive = active === p.id;
          const showUnconfiguredLabel = idx === configuredProviders.length && otherProviders.length > 0;
          const initials = String(p.label || p.id || "?")
            .replace(/[^A-Za-z0-9\u4e00-\u9fa5]/g, "")
            .slice(0, 2)
            .toUpperCase();
          return (
            <div key={p.id}>
            {showUnconfiguredLabel ? (
              <p className="mb-2 mt-3 text-[11px] uppercase tracking-[0.08em] text-white/35">未配置</p>
            ) : null}
            <article className={`provider-card group ${isActive ? "provider-card-active" : ""}`}>
              <div className="provider-card-icon">{initials || "AI"}</div>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="truncate text-[15px] font-semibold tracking-tight">{p.label}</h3>
                  {isActive ? <span className="provider-badge-active">使用中</span> : null}
                  {!p.configured ? (
                    <span className="rounded-full border border-[var(--line)] px-2 py-0.5 text-[11px] text-[var(--muted)]">
                      未配置
                    </span>
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
                    <span className="truncate">{p.baseUrl || "未配置接口地址"}</span>
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
                    <span className="text-[11px] text-white/35">切换模型</span>
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
                        <option value={p.model}>{p.model}（当前）</option>
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
                  title={isActive ? "当前启用" : "启用"}
                >
                  {busyId === p.id ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Zap className="h-3.5 w-3.5" />}
                  <span className="hidden sm:inline">{isActive ? "已启用" : "启用"}</span>
                </button>
                <button type="button" className="provider-icon-btn" onClick={() => setEditor(p)} title="编辑">
                  <Pencil className="h-3.5 w-3.5" />
                </button>
                {p.docs ? (
                  <a href={p.docs} target="_blank" rel="noreferrer" className="provider-icon-btn" title="文档">
                    <ExternalLink className="h-3.5 w-3.5" />
                  </a>
                ) : null}
                <button
                  type="button"
                  className="provider-icon-btn"
                  disabled={busyId === p.id || !p.configured || isActive}
                  onClick={() => void clearKey(p)}
                  title={isActive ? "请先切换到其他供应商再清空" : "清空 Key"}
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>
            </article>
            </div>
          );
        })}
      </div>

      <section className="provider-card !items-stretch !flex-col gap-3 sm:!flex-row sm:!items-center">
        <div className="provider-card-icon">火</div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-[15px] font-semibold">火山方舟</h3>
            <span className="text-xs text-[var(--muted)]">Seedream 出图 · Seedance 出片</span>
            {status?.volcengine?.configured ? (
              <span className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-[11px] text-emerald-300">
                已配置 {status.volcengine.masked}
              </span>
            ) : (
              <span className="rounded-full border border-[var(--line)] px-2 py-0.5 text-[11px] text-[var(--muted)]">
                未配置
              </span>
            )}
          </div>
          <div className="mt-3">
            <VolcCard status={status} onUpdated={onUpdated} />
          </div>
        </div>
      </section>

      <section className="provider-card !items-stretch !flex-col gap-3 sm:!flex-row sm:!items-center">
        <div className="provider-card-icon">川</div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-[15px] font-semibold">智川云 GPU · ComfyUI</h3>
            <span className="text-xs text-[var(--muted)]">出图 + 出片（MiniMax H3；优先于火山 Seedream / Seedance）</span>
            {status?.comfyui?.reachable ? (
              <span className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-[11px] text-emerald-300">
                已连通{status.comfyui.deviceName ? ` · ${status.comfyui.deviceName}` : ""}
              </span>
            ) : status?.comfyui?.configured ? (
              <span className="rounded-full border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-[11px] text-amber-300">
                已配置未连通
              </span>
            ) : (
              <span className="rounded-full border border-[var(--line)] px-2 py-0.5 text-[11px] text-[var(--muted)]">
                未配置
              </span>
            )}
            {status?.imageBackend === "comfyui" ? (
              <span className="provider-badge-active">出图使用中</span>
            ) : null}
            {status?.videoBackend === "comfyui" ? (
              <span className="provider-badge-active">出片使用中</span>
            ) : null}
          </div>
          <p className="mt-1 text-[11px] leading-4 text-white/40">
            ①{" "}
            <a className="text-[#a5b4fc] hover:underline" href="https://gpuhome.cc/market" target="_blank" rel="noreferrer">
              算力市场
            </a>{" "}
            租 GPU（建议 3090/4090）→ ② 镜像选 ComfyUI → ③{" "}
            <a
              className="text-[#a5b4fc] hover:underline"
              href={status?.comfyui?.portsDocs || "https://docs.gpuhome.cc/docs/instance/open-ports.html"}
              target="_blank"
              rel="noreferrer"
            >
              开放端口
            </a>{" "}
            （勿用 22/8888/8188，用平台给的「自定义服务」地址）→ ④ 填到下方并检测连通。文本模型仍用上方「智川云 Token」。
          </p>
          <div className="mt-3">
            <ComfyCard status={status} onUpdated={onUpdated} />
          </div>
        </div>
      </section>

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

function VolcCard({ status, onUpdated }) {
  const [key, setKey] = useState("");
  const [saving, setSaving] = useState(false);
  const configured = status?.volcengine?.configured;
  const canSave = Boolean(key.trim());

  const save = async () => {
    if (!key.trim()) {
      toast.error(configured ? "已保存。若要更换，请粘贴新 Key 后再保存" : "请填写火山 API Key");
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
      onUpdated?.(data);
      toast.success(configured ? "火山 Key 已更新" : "火山 Key 已保存");
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
        placeholder={configured ? "已保存，仅更换时粘贴新 Key" : "粘贴火山方舟 API Key"}
        value={key}
        onChange={(e) => setKey(e.target.value)}
      />
      {canSave || !configured ? (
        <button
          type="button"
          className="provider-icon-btn provider-icon-btn-primary !min-h-[38px] !px-3"
          disabled={saving || !canSave}
          onClick={() => void save()}
        >
          {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
          {configured ? "更新 Key" : "保存"}
        </button>
      ) : (
        <span className="inline-flex min-h-[38px] items-center px-1 text-xs text-emerald-300/90">Key 已保存</span>
      )}
    </div>
  );
}

function ComfyCard({ status, onUpdated }) {
  const comfy = status?.comfyui || {};
  const [serverUrl, setServerUrl] = useState(comfy.serverUrl || "");
  const [checkpoint, setCheckpoint] = useState(comfy.checkpoint || "");
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);

  useEffect(() => {
    setServerUrl(comfy.serverUrl || "");
    setCheckpoint(comfy.checkpoint || "");
  }, [comfy.serverUrl, comfy.checkpoint]);

  const savedUrl = (comfy.serverUrl || "").replace(/\/$/, "");
  const draftUrl = serverUrl.trim().replace(/\/$/, "");
  const dirty = draftUrl !== savedUrl;
  const canSave = dirty; // allow clear (empty) when previously configured

  const save = async (extra = {}) => {
    const url = (extra.serverUrl ?? serverUrl).trim().replace(/\/$/, "");
    const ckpt = (extra.checkpoint ?? checkpoint).trim();
    setSaving(true);
    try {
      const payload = { COMFYUI_SERVER_URL: url };
      if (ckpt) payload.COMFYUI_CHECKPOINT = ckpt;
      const data = await api("/api/settings/keys", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      onUpdated?.(data);
      toast.success(url ? "ComfyUI 已保存" : "已清空 ComfyUI 地址");
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
      if (serverUrl.trim() && serverUrl.trim().replace(/\/$/, "") !== (comfy.serverUrl || "")) {
        await save();
      }
      const data = await api("/api/settings/keys/test", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
      onUpdated?.(data);
      const r = data?.results?.comfyui;
      if (r?.ok) {
        const vid = (r.videoModels || []).length;
        toast.success(
          vid
            ? `ComfyUI 连通 · 出图 ${r.checkpointCount || 0} · 出片 H3 就绪`
            : `ComfyUI 连通 · 出图模型 ${r.checkpointCount || 0} 个（未检测到 MiniMax H3 出片权重）`,
        );
      } else {
        toast.error(r?.error || "ComfyUI 连通失败");
      }
    } catch (e) {
      toast.error(String(e.message || e));
    } finally {
      setTesting(false);
    }
  };

  const checkpoints = comfy.checkpoints || [];

  return (
    <div className="space-y-2">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
        <input
          className="field sm:flex-1"
          type="url"
          autoComplete="off"
          placeholder="粘贴智川云「自定义服务」地址，如 https://xxx.gpuhome.cc"
          value={serverUrl}
          onChange={(e) => setServerUrl(e.target.value)}
        />
        {canSave || !comfy.configured ? (
          <button
            type="button"
            className="provider-icon-btn provider-icon-btn-primary !min-h-[38px] !px-3"
            disabled={saving || !canSave}
            onClick={() => void save()}
          >
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
            {comfy.configured ? "更新地址" : "保存"}
          </button>
        ) : (
          <span className="inline-flex min-h-[38px] items-center px-1 text-xs text-emerald-300/90">地址已保存</span>
        )}
        <button type="button" className="btn-secondary !min-h-[38px] !px-3 text-xs" disabled={testing || !serverUrl.trim()} onClick={() => void test()}>
          {testing ? <Loader2 className="h-4 w-4 animate-spin" /> : <ShieldCheck className="h-3.5 w-3.5" />}
          检测连通
        </button>
        {comfy.docs ? (
          <a className="btn-secondary !min-h-[38px] !px-3 text-xs" href={comfy.docs} target="_blank" rel="noreferrer">
            ComfyUI 文档
          </a>
        ) : null}
      </div>
      {checkpoints.length ? (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-[11px] text-white/35">Checkpoint</span>
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
        </div>
      ) : null}
      {comfy.error ? <p className="text-[11px] text-amber-300/90">{comfy.error}</p> : null}
    </div>
  );
}

export function UsageSettings() {
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState(null);
  const [subTab, setSubTab] = useState("logs");
  const [range, setRange] = useState("7d");
  const [kind, setKind] = useState("all");
  const [provider, setProvider] = useState("");
  const [model, setModel] = useState("");

  const load = async () => {
    setLoading(true);
    try {
      const qs = new URLSearchParams({
        range,
        kind,
        provider,
        model,
        log_limit: "120",
      });
      const res = await api(`/api/settings/usage?${qs}`);
      setData(res);
    } catch (e) {
      toast.error(String(e.message || e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, [range, kind, provider, model]);

  const hero = data?.hero || {};
  const trend = data?.trend || { buckets: [], requests: [], tokens_in: [], tokens_out: [], cost_usd: [] };

  return (
    <PageShell eyebrow="Settings" title="用量统计" description="查看调用次数、Token、费用与请求日志。">
      <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-3">
        <div className="usage-seg">
          {[
            ["today", "今日"],
            ["7d", "近 7 天"],
            ["30d", "近 30 天"],
          ].map(([id, label]) => (
            <button key={id} type="button" className={range === id ? "active" : ""} onClick={() => setRange(id)}>
              {label}
            </button>
          ))}
        </div>
        <select className="field !w-auto !py-1.5" value={kind} onChange={(e) => setKind(e.target.value)}>
          <option value="all">全部类型</option>
          <option value="text">文本</option>
          <option value="image">出图</option>
          <option value="video">出片</option>
        </select>
        <select className="field !w-auto !py-1.5" value={provider} onChange={(e) => setProvider(e.target.value)}>
          <option value="">全部供应商</option>
          {(data?.filters?.providers || []).map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </select>
        <select className="field !w-auto !py-1.5" value={model} onChange={(e) => setModel(e.target.value)}>
          <option value="">全部模型</option>
          {(data?.filters?.models || []).map((m) => (
            <option key={m} value={m}>
              {m}
            </option>
          ))}
        </select>
        <button type="button" className="btn-secondary" onClick={() => void load()}>
          刷新
        </button>
      </div>

      {loading && !data ? (
        <div className="panel flex items-center gap-2 px-5 py-10 text-sm text-[var(--muted)]">
          <Loader2 className="h-4 w-4 animate-spin" /> 加载用量…
        </div>
      ) : (
        <>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
            {[
              ["总请求数", fmtNum(hero.requests)],
              ["真实消耗 Tokens", fmtNum(hero.tokens)],
              ["缓存命中率", fmtPct(hero.cache_hit_rate)],
              ["估算费用", fmtUsd(hero.cost_usd)],
              ["成功率", fmtPct(hero.success_rate)],
            ].map(([label, value]) => (
              <div key={label} className="usage-hero">
                <div className="text-[11px] uppercase tracking-[0.08em] text-[var(--muted)]">{label}</div>
                <div className="mt-1.5 text-2xl font-semibold tracking-tight">{value}</div>
              </div>
            ))}
          </div>

          <div className="grid gap-4 xl:grid-cols-2">
            <section className="panel p-4">
              <div className="label">请求趋势</div>
              <LineChart
                labels={trend.buckets || []}
                series={[{ name: "requests", data: trend.requests || [], color: "#7c6cff" }]}
              />
            </section>
            <section className="panel p-4">
              <div className="mb-1 flex flex-wrap gap-3 text-[11px] text-[var(--muted)]">
                <span className="text-sky-400">● 输入</span>
                <span className="text-emerald-400">● 输出</span>
                <span className="text-orange-400">● 缓存创建</span>
                <span className="text-violet-400">● 缓存命中</span>
                <span className="text-rose-400">● 费用</span>
              </div>
              <div className="label">Token / 费用趋势</div>
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
              ["logs", "请求日志"],
              ["providers", "供应商"],
              ["models", "模型"],
            ].map(([id, label]) => (
              <button key={id} type="button" className={subTab === id ? "active" : ""} onClick={() => setSubTab(id)}>
                {label}
              </button>
            ))}
          </div>

          {subTab === "logs" ? (
            <div className="panel overflow-x-auto">
              <table className="min-w-full text-left text-sm">
                <thead className="text-xs text-[var(--muted)]">
                  <tr>
                    {["时间", "供应商", "模型", "类型", "Token", "费用", "耗时", "状态"].map((h) => (
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
                      <td colSpan={8} className="px-3 py-8 text-center text-[var(--muted)]">
                        暂无请求记录
                      </td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </div>
          ) : null}

          {subTab === "providers" ? (
            <div className="panel overflow-x-auto">
              <table className="min-w-full text-left text-sm">
                <thead className="text-xs text-[var(--muted)]">
                  <tr>
                    {["供应商", "请求", "成功", "失败", "成功率", "Token", "费用", "均延迟"].map((h) => (
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
                    {["模型", "供应商", "请求", "输入 Token", "输出 Token", "费用", "均延迟"].map((h) => (
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
  };

  const test = async () => {
    setTesting(true);
    try {
      const data = await api("/api/settings/keys/test", { method: "POST" });
      const llm = data.results?.llm || data.results?.deepseek;
      if (llm?.ok) toast.success(`文本模型可用（${data.keys?.llmBackend || "llm"}）`);
      else toast.error(llm?.error || "检测失败");
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
    return list.find((p) => p.id === id)?.label || id || "未启用";
  }, [status, catalog]);

  return (
    <PageShell
      eyebrow="Settings"
      title="模型配置"
      description={`管理文本与媒体供应商。当前文本后端：${activeLabel}`}
    >
      {loading && !status ? (
        <div className="panel flex items-center gap-2 px-5 py-10 text-sm text-[var(--muted)]">
          <Loader2 className="h-4 w-4 animate-spin" /> 读取配置…
        </div>
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
