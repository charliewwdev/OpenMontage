import { useEffect, useRef, useState } from "react";
import { Eraser, FileText, ImagePlus, Loader2, Maximize2, RefreshCw, Sparkles, Upload, X } from "lucide-react";
import { api } from "../api";
import { requireCapability, toastMaybeKeys } from "../lib/keys";
import { toast } from "../lib/toast";
import { Lightbox } from "./Lightbox";
import { ModalOverlay } from "./ModalPortal";

const KIND_LABEL = {
  character: "角色",
  scene: "场景",
  prop: "道具",
};

const ROLE_LABEL = {
  protagonist: "主角",
  lead: "主角",
  main: "主角",
  supporting: "配角",
  side: "配角",
  antagonist: "反派",
  villain: "反派",
  extra: "群演",
  npc: "配角",
};

function roleBadge(entity) {
  const raw = String(entity?.metadata?.role || entity?.role || entity?.category || "").trim();
  if (!raw) return entity?.kind === "character" ? "角色" : "";
  return ROLE_LABEL[raw.toLowerCase()] || raw;
}

/**
 * Asset inspector: open from the workspace rail to view /
 * regenerate / upload without leaving the segment desk.
 */
export function AssetDetailModal({
  entity,
  projectId,
  config,
  onClose,
  onBundle,
  onRefresh,
  onNeedKeys,
}) {
  const caps = config?.capabilities || {};
  const uploadRef = useRef(null);
  const promptCacheRef = useRef(new Map());
  const [working, setWorking] = useState(false);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [name, setName] = useState(entity?.name || "");
  const [variant, setVariant] = useState(entity?.variant || "");
  const [description, setDescription] = useState(entity?.description || "");
  const [voiceDescription, setVoiceDescription] = useState(entity?.metadata?.voiceDescription || "");
  const [detailTab, setDetailTab] = useState("edit"); // edit | prompt
  const [promptBusy, setPromptBusy] = useState(false);
  const [promptPayload, setPromptPayload] = useState(null);
  const [descExpanded, setDescExpanded] = useState(false);

  const loadPrompt = async (entityId, { force = false } = {}) => {
    if (!entityId || !projectId) return null;
    if (!force) {
      const cached = promptCacheRef.current.get(entityId);
      if (cached) {
        setPromptPayload(cached);
        return cached;
      }
    }
    setPromptBusy(true);
    try {
      const res = await api(`/api/projects/${encodeURIComponent(projectId)}/entities`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "preview-prompt", entityId }),
      });
      promptCacheRef.current.set(entityId, res);
      setPromptPayload(res);
      return res;
    } catch (e) {
      toast.error(String(e.message || e));
      return null;
    } finally {
      setPromptBusy(false);
    }
  };

  useEffect(() => {
    if (!entity?.id) return;
    setName(entity.name || "");
    setVariant(entity.variant || "");
    setDescription(entity.description || "");
    setVoiceDescription(entity.metadata?.voiceDescription || "");
    setPreviewUrl(null);
    setDescExpanded(false);
    const cached = promptCacheRef.current.get(entity.id);
    if (cached) {
      setPromptPayload(cached);
      setPromptBusy(false);
    } else if (detailTab === "prompt") {
      void loadPrompt(entity.id);
    } else {
      setPromptPayload(null);
    }
    // Keep current tab (edit/prompt) when switching characters — no forced reload UX.
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only rebind fields on entity id swap
  }, [entity?.id]);

  useEffect(() => {
    if (!entity?.id) return;
    setDescription(entity.description || "");
    setVoiceDescription(entity.metadata?.voiceDescription || "");
    setName(entity.name || "");
    setVariant(entity.variant || "");
  }, [entity?.name, entity?.variant, entity?.description, entity?.metadata?.voiceDescription, entity?.id]);

  if (!entity) return null;

  const apply = (res) => {
    if (res?.bundle) onBundle?.(res.bundle);
    else onRefresh?.();
  };

  const live = entity;
  const badge = roleBadge(live);
  const voiceText = voiceDescription || live.metadata?.voiceDescription || "";

  const invalidatePromptCache = (entityId = live.id) => {
    if (entityId) promptCacheRef.current.delete(entityId);
  };

  const patch = async (fields) => {
    try {
      const res = await api(`/api/projects/${encodeURIComponent(projectId)}/entities`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ entityId: live.id, ...fields }),
      });
      if ("description" in fields || "name" in fields || "variant" in fields || "metadata" in fields) {
        invalidatePromptCache(live.id);
      }
      apply(res);
    } catch (e) {
      toast.error(String(e.message || e));
    }
  };

  const generate = async (redraw = false) => {
    if (!requireCapability(caps, "seedream", onNeedKeys, "出图后端（Seedream / ComfyUI）")) return;
    setWorking(true);
    try {
      const res = await api(`/api/projects/${encodeURIComponent(projectId)}/entities`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "generate",
          entityId: live.id,
          redraw: Boolean(redraw),
          force: true,
        }),
      });
      invalidatePromptCache(live.id);
      apply(res);
      const imgs = (res?.bundle?.entities || []).find((e) => e.id === live.id)?.images || [];
      const last = imgs[imgs.length - 1];
      if (last?.qaPass === false) {
        toast.error(`质检未通过：${last?.qa?.reason || "与提示词不符"}`);
      } else {
        toast.success(redraw ? "参考重绘已保存" : "图片已保存");
      }
    } catch (e) {
      toastMaybeKeys(e, onNeedKeys);
      toast.error(String(e.message || e));
    } finally {
      setWorking(false);
    }
  };

  const selectImage = async (imageId) => {
    try {
      const res = await api(`/api/projects/${encodeURIComponent(projectId)}/entities`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "select", entityId: live.id, imageId }),
      });
      invalidatePromptCache(live.id);
      apply(res);
    } catch (e) {
      toast.error(String(e.message || e));
    }
  };

  const upload = async (file) => {
    if (!file) return;
    setWorking(true);
    try {
      const reader = new FileReader();
      const dataUrl = await new Promise((resolve, reject) => {
        reader.onload = () => resolve(reader.result);
        reader.onerror = reject;
        reader.readAsDataURL(file);
      });
      const res = await api(`/api/projects/${encodeURIComponent(projectId)}/entities`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "upload", entityId: live.id, dataUrl }),
      });
      invalidatePromptCache(live.id);
      apply(res);
      toast.success("已上传并设为定稿图");
    } catch (e) {
      toast.error(String(e.message || e));
    } finally {
      setWorking(false);
    }
  };

  const punchAlpha = async () => {
    if (!thumb || !["character", "prop"].includes(live.kind)) return;
    setWorking(true);
    try {
      const res = await api(`/api/projects/${encodeURIComponent(projectId)}/entities`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "punch-alpha",
          entityId: live.id,
          imageId: selected?.id || live.selectedImageId,
        }),
      });
      apply(res);
      toast.success(res?.punched ? "已抠成透明底" : "已转 PNG（底板色过深或非无缝，未能自动抠除）");
    } catch (e) {
      toast.error(String(e.message || e));
    } finally {
      setWorking(false);
    }
  };

  const showPromptTab = async () => {
    setDetailTab("prompt");
    await loadPrompt(live.id);
  };

  const selected =
    (live.images || []).find((i) => i.id === live.selectedImageId) || live.selectedImage || null;
  const thumb = live.selectedImage?.url || selected?.url || "";
  const kindLabel = KIND_LABEL[live.kind] || live.kind;
  const title = `${live.name}${live.variant ? ` / ${live.variant}` : ""}`;
  const qaPass = selected?.qaPass === true;
  const qaReason = selected?.qa?.reason || live.qaFailReason || "";
  const longDesc = (description || "").trim();
  const descNeedsCollapse = longDesc.length > 160;
  const descShown = !descNeedsCollapse || descExpanded ? longDesc : `${longDesc.slice(0, 160)}…`;

  return (
    <>
      <ModalOverlay onClose={onClose} role="dialog" zClass="z-[190]">
        <div
          className="relative my-auto w-full max-w-3xl overflow-hidden rounded-2xl border border-white/10 bg-[#0c0e14] shadow-2xl"
          onMouseDown={(e) => e.stopPropagation()}
        >
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-white/10 px-4 py-3">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <span className="rounded-full bg-white/10 px-2 py-0.5 text-[10px] uppercase tracking-wider text-white/55">
                  {kindLabel}
                </span>
                {badge && live.kind === "character" ? (
                  <span className="rounded-full bg-[#7c6cff]/25 px-2 py-0.5 text-[10px] font-semibold text-[#c4b5fd]">
                    {badge}
                  </span>
                ) : null}
              </div>
              <h3 className="mt-1 truncate text-lg font-semibold text-white">{title}</h3>
            </div>
            <div className="flex items-center gap-2">
              <div className="flex items-center gap-0.5 rounded-lg bg-white/5 p-0.5">
                <button
                  type="button"
                  className={`rounded-md px-2.5 py-1 text-xs ${
                    detailTab === "edit" ? "bg-white/10 font-semibold text-white" : "text-white/45 hover:text-white/70"
                  }`}
                  onClick={() => setDetailTab("edit")}
                >
                  资料
                </button>
                <button
                  type="button"
                  className={`inline-flex items-center gap-1 rounded-md px-2.5 py-1 text-xs ${
                    detailTab === "prompt" ? "bg-white/10 font-semibold text-white" : "text-white/45 hover:text-white/70"
                  }`}
                  onClick={() => void showPromptTab()}
                >
                  <FileText className="h-3 w-3" /> 提示词
                </button>
              </div>
              <button type="button" className="btn-quiet !min-h-8 !px-2 text-white/70" onClick={onClose} aria-label="关闭">
                <X className="h-4 w-4" />
              </button>
            </div>
          </div>

          {detailTab === "prompt" ? (
            <div className="scrollbar-thin max-h-[min(82dvh,860px)] space-y-3 overflow-y-auto p-4 text-sm">
              {promptBusy && !promptPayload ? (
                <div className="flex items-center justify-center gap-2 py-12 text-white/50">
                  <Loader2 className="h-4 w-4 animate-spin" /> 加载提示词…
                </div>
              ) : (
                <>
                  {promptBusy ? (
                    <div className="flex items-center gap-2 text-[11px] text-white/40">
                      <Loader2 className="h-3 w-3 animate-spin" /> 更新提示词…
                    </div>
                  ) : null}
                  <div>
                    <div className="mb-1 text-[11px] font-medium text-white/40">将提交给大模型的正向提示词</div>
                    <pre className="whitespace-pre-wrap rounded-xl border border-white/10 bg-black/40 p-3 text-[12px] leading-5 text-white/85">
                      {promptPayload?.prompt || "（无）"}
                    </pre>
                  </div>
                  {promptPayload?.negativePrompt ? (
                    <div>
                      <div className="mb-1 text-[11px] font-medium text-white/40">负向提示词</div>
                      <pre className="whitespace-pre-wrap rounded-xl border border-white/10 bg-black/40 p-3 text-[12px] leading-5 text-white/70">
                        {promptPayload.negativePrompt}
                      </pre>
                    </div>
                  ) : null}
                  {promptPayload?.selectedImagePrompt ? (
                    <div>
                      <div className="mb-1 text-[11px] font-medium text-white/40">当前定稿图实际使用的提示词</div>
                      <pre className="whitespace-pre-wrap rounded-xl border border-amber-500/20 bg-amber-500/5 p-3 text-[12px] leading-5 text-amber-50/90">
                        {promptPayload.selectedImagePrompt}
                      </pre>
                    </div>
                  ) : null}
                  {promptPayload?.selectedImageQa?.reason ? (
                    <div className="rounded-lg border border-white/10 bg-white/[.03] px-3 py-2 text-[11px] text-white/55">
                      定稿质检：{promptPayload.selectedQaPass ? "通过" : "未过"} · {promptPayload.selectedImageQa.reason}
                    </div>
                  ) : null}
                </>
              )}
            </div>
          ) : (
            <div className="grid max-h-[min(82dvh,860px)] gap-0 overflow-y-auto md:grid-cols-[minmax(0,1.05fr)_minmax(280px,0.95fr)]">
              <div
                className={`relative min-h-[240px] md:min-h-[360px] ${
                  entity.kind === "scene" ? "bg-black/50" : "asset-cutout-bg"
                }`}
              >
                {thumb ? (
                  <button
                    type="button"
                    className="relative h-full w-full cursor-zoom-in"
                    onClick={() => setPreviewUrl(thumb)}
                  >
                    <img
                      src={thumb}
                      alt={title}
                      className="h-full max-h-[420px] w-full object-contain object-center"
                    />
                    <span className="pointer-events-none absolute bottom-3 right-3 flex items-center gap-1 rounded-md bg-black/55 px-2 py-1 text-[10px] font-medium text-white/80">
                      <Maximize2 className="h-3 w-3" /> 大图
                    </span>
                  </button>
                ) : (
                  <div className="flex h-full min-h-[240px] flex-col items-center justify-center text-sm text-white/40">
                    <ImagePlus className="mb-3 h-8 w-8 text-[#7c6cff]" />
                    尚无定稿图
                  </div>
                )}
                {working ? (
                  <div className="absolute inset-0 flex items-center justify-center bg-[#0c0e14]/75 text-sm font-semibold text-white backdrop-blur-sm">
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    正在处理图片…
                  </div>
                ) : null}
              </div>

              <div className="space-y-3 border-t border-white/10 p-4 md:border-l md:border-t-0">
                {selected ? (
                  <div
                    className={`rounded-lg border px-2.5 py-1.5 text-[11px] ${
                      qaPass
                        ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-200"
                        : "border-rose-500/30 bg-rose-500/10 text-rose-200"
                    }`}
                    title={qaReason}
                  >
                    {qaPass ? "质检通过" : `质检未过${qaReason ? ` · ${String(qaReason).slice(0, 80)}` : ""}`}
                  </div>
                ) : null}

                <div className="flex flex-wrap items-center gap-2">
                  <h4 className="text-xl font-semibold text-white">{live.name || "未命名"}</h4>
                  {badge && live.kind === "character" ? (
                    <span className="rounded-full bg-[#7c6cff]/25 px-2 py-0.5 text-[11px] font-semibold text-[#c4b5fd]">
                      {badge}
                    </span>
                  ) : null}
                  {live.variant ? (
                    <span className="rounded-full border border-white/10 px-2 py-0.5 text-[11px] text-white/50">
                      {live.variant}
                    </span>
                  ) : null}
                </div>

                <div>
                  <div className="label !mb-1">形象描述</div>
                  <p className="text-sm leading-6 text-white/75">{descShown || "尚未填写形象描述"}</p>
                  {descNeedsCollapse ? (
                    <button
                      type="button"
                      className="mt-1 text-xs font-medium text-[#a78bfa] hover:underline"
                      onClick={() => setDescExpanded((v) => !v)}
                    >
                      {descExpanded ? "收起" : "展开全部"}
                    </button>
                  ) : null}
                </div>

                {live.kind === "character" ? (
                  <div>
                    <div className="label !mb-1">角色音色</div>
                    {voiceText ? (
                      <p className="text-sm leading-6 text-white/70">{voiceText}</p>
                    ) : (
                      <p className="text-sm text-white/35">暂无音色描述（解析剧本时若有会写入）</p>
                    )}
                  </div>
                ) : null}

                <details className="rounded-xl border border-white/10 bg-white/[.02] p-3">
                  <summary className="cursor-pointer text-xs font-medium text-white/55">编辑档案</summary>
                  <div className="mt-3 space-y-3">
                    <label className="block">
                      <span className="label">名称</span>
                      <input
                        className="field"
                        value={name}
                        disabled={working}
                        onChange={(e) => setName(e.target.value)}
                        onBlur={() => {
                          if (name.trim() && name !== live.name) void patch({ name: name.trim() });
                        }}
                      />
                    </label>
                    {live.kind === "character" ? (
                      <label className="block">
                        <span className="label">造型</span>
                        <input
                          className="field"
                          value={variant}
                          disabled={working}
                          onChange={(e) => setVariant(e.target.value)}
                          onBlur={() => {
                            if (variant !== (live.variant || "")) void patch({ variant });
                          }}
                        />
                      </label>
                    ) : null}
                    <label className="block">
                      <span className="label">形象描述</span>
                      <textarea
                        className="field min-h-28 resize-y text-sm leading-6"
                        value={description}
                        disabled={working}
                        onChange={(e) => setDescription(e.target.value)}
                        onBlur={() => {
                          if (description !== (live.description || "")) void patch({ description });
                        }}
                      />
                    </label>
                    {live.kind === "character" ? (
                      <label className="block">
                        <span className="label">角色音色</span>
                        <textarea
                          className="field min-h-20 resize-y text-sm leading-6"
                          value={voiceDescription}
                          disabled={working}
                          placeholder="例如：少女音偏清亮，喘息中带沙哑…"
                          onChange={(e) => setVoiceDescription(e.target.value)}
                          onBlur={() => {
                            const next = voiceDescription.trim();
                            const prev = String(live.metadata?.voiceDescription || "").trim();
                            if (next !== prev) {
                              void patch({
                                metadata: { ...(live.metadata || {}), voiceDescription: next },
                              });
                            }
                          }}
                        />
                      </label>
                    ) : null}
                  </div>
                </details>

                {(live.images || []).length ? (
                  <div>
                    <div className="label mb-1.5">版本 · {(live.images || []).length}</div>
                    <div className="scrollbar-thin flex gap-2 overflow-x-auto pb-1">
                      {(live.images || []).map((image, index) => (
                        <button
                          key={image.id}
                          type="button"
                          disabled={working}
                          onClick={() => void selectImage(image.id)}
                          className={`relative h-14 w-14 shrink-0 overflow-hidden rounded-lg border-2 ${
                            image.id === live.selectedImageId
                              ? "border-[#7c6cff]"
                              : "border-transparent opacity-65 hover:opacity-100"
                          }`}
                          title={`版本 ${index + 1}${image.qaPass === false ? " · 质检未过" : ""}`}
                        >
                          <img
                            src={image.url}
                            alt={`版本 ${index + 1}`}
                            className="h-full w-full object-contain object-center bg-black/50"
                          />
                          {image.qaPass === false ? (
                            <span className="absolute inset-x-0 bottom-0 bg-rose-600/80 text-center text-[8px] text-white">未过</span>
                          ) : null}
                        </button>
                      ))}
                    </div>
                  </div>
                ) : null}

                <div className="grid grid-cols-2 gap-2 pt-1">
                  <button type="button" className="btn-primary" disabled={working} onClick={() => void generate(false)}>
                    <Sparkles className="h-3.5 w-3.5" /> {thumb ? "生成新版本" : "生成图片"}
                  </button>
                  <button type="button" className="btn-secondary" disabled={working || !thumb} onClick={() => void generate(true)}>
                    <RefreshCw className="h-3.5 w-3.5" /> 参考重绘
                  </button>
                  {["character", "prop"].includes(live.kind) ? (
                    <button
                      type="button"
                      className="btn-secondary col-span-2"
                      disabled={working || !thumb}
                      onClick={() => void punchAlpha()}
                      title="把无缝浅色底板键控成透明 PNG"
                    >
                      <Eraser className="h-3.5 w-3.5" /> 抠透明底
                    </button>
                  ) : null}
                  <button
                    type="button"
                    className="btn-secondary col-span-2"
                    disabled={working}
                    onClick={() => uploadRef.current?.click()}
                  >
                    <Upload className="h-3.5 w-3.5" /> 上传本地图
                  </button>
                  <input
                    ref={uploadRef}
                    hidden
                    type="file"
                    accept="image/png,image/jpeg,image/webp"
                    onChange={(event) => {
                      const file = event.target.files?.[0];
                      if (file) void upload(file);
                      event.target.value = "";
                    }}
                  />
                </div>
              </div>
            </div>
          )}
        </div>
      </ModalOverlay>

      <Lightbox src={previewUrl} alt={title} onClose={() => setPreviewUrl(null)} />
    </>
  );
}
