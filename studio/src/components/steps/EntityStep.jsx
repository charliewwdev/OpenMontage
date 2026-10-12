import { useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { ImagePlus, Loader2, Maximize2, Plus, RefreshCw, Sparkles, Trash2, Upload, X } from "lucide-react";
import { api } from "../../api";
import { toast } from "../../lib/toast";
import { Lightbox } from "../Lightbox";

const CONFIG = {
  character: {
    title: "角色造型",
    eyebrow: "Cast bible",
    empty: "剧本生成后会自动整理角色；也可以手动添加造型。",
    accent: "#8b7cf7",
  },
  scene: {
    title: "空镜场景",
    eyebrow: "Location bible",
    empty: "在这里建立可重复使用的空间与光线设定。",
    accent: "#41a99e",
  },
  prop: {
    title: "关键道具",
    eyebrow: "Prop bible",
    empty: "只保留跨镜头需要维持一致的关键物件。",
    accent: "#d79833",
  },
};

export function EntityStep({ projectId, bundle, kind, setBusyMsg, onBundle, onRefresh }) {
  const config = CONFIG[kind];
  const entities = useMemo(
    () => (bundle?.entities || []).filter((e) => e.kind === kind && !e.deletedAt),
    [bundle?.entities, kind],
  );
  const [showAdd, setShowAdd] = useState(false);
  const [threeView, setThreeView] = useState(kind !== "scene");
  const [workingIds, setWorkingIds] = useState(() => new Set());
  const [batching, setBatching] = useState(false);
  const [form, setForm] = useState({ name: "", variant: "", description: "", category: "item" });

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
    if (!form.name.trim() || !form.description.trim()) return toast.error("名称和视觉描述不能为空");
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
      toast.success("素材档案已添加");
    } catch (e) {
      toast.error(String(e.message || e));
    }
  };

  const update = async (entity, fields) => {
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
    if (!window.confirm(`删除「${entity.name}」？`)) return;
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
    if (workingIds.has(entity.id)) return;
    setWorking(entity.id, true);
    if (!silent) setBusyMsg?.("Seedream 出图…");
    try {
      const res = await api(`/api/projects/${encodeURIComponent(projectId)}/entities`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "generate",
          entityId: entity.id,
          threeView: kind !== "scene" && threeView,
          redraw,
        }),
      });
      apply(res);
      if (!silent) toast.success("Seedream 图片已保存");
    } catch (e) {
      if (!silent) toast.error(String(e.message || e));
      throw e;
    } finally {
      setWorking(entity.id, false);
      if (!silent) setBusyMsg?.("");
    }
  };

  const batchGenerate = async () => {
    const missing = entities.filter((e) => !e.selectedImage);
    if (!missing.length) return toast.info("所有素材都已有选定图片");
    if (!window.confirm(`批量生成 ${missing.length} 个素材？`)) return;
    setBatching(true);
    setBusyMsg?.(`批量出图 ${missing.length}…`);
    try {
      const results = await Promise.allSettled(missing.map((e) => generate(e, false, true)));
      const ok = results.filter((r) => r.status === "fulfilled").length;
      await onRefresh?.();
      toast.success(`批量生成完成：${ok}/${missing.length}`);
    } finally {
      setBatching(false);
      setBusyMsg?.("");
    }
  };

  const upload = async (entity, file) => {
    if (!file) return;
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
        toast.success("图片已保存");
      } catch (e) {
        toast.error(String(e.message || e));
      } finally {
        setWorking(entity.id, false);
      }
    };
    reader.readAsDataURL(file);
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

  return (
    <div className="mx-auto max-w-[1500px] space-y-5">
      <section className="panel flex flex-col gap-4 p-5 md:flex-row md:items-center md:justify-between md:p-6">
        <div>
          <div className="label">{config.eyebrow}</div>
          <h3 className="display-type text-2xl font-semibold">{config.title}</h3>
          <p className="mt-1 max-w-2xl text-sm text-[var(--muted)]">
            Seedream 出图写入本地媒体目录；所有版本可回看和切换。
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {kind !== "scene" ? (
            <label className="mr-2 flex items-center gap-2 text-xs text-[var(--muted)]">
              <input
                type="checkbox"
                checked={threeView}
                disabled={batching}
                onChange={(e) => setThreeView(e.target.checked)}
              />
              三视图设定稿
            </label>
          ) : null}
          <button type="button" className="btn-secondary" disabled={batching} onClick={() => void batchGenerate()}>
            {batching ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />} 批量补齐图片
          </button>
          <button type="button" className="btn-primary" disabled={batching} onClick={() => setShowAdd(true)}>
            <Plus className="h-4 w-4" /> 添加{kind === "character" ? "造型" : kind === "scene" ? "场景" : "道具"}
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
          <span className="mt-2 text-sm text-[var(--muted)]">点击添加第一份档案。</span>
        </button>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {entities.map((entity) => (
            <EntityCard
              key={entity.id}
              entity={entity}
              accent={config.accent}
              working={workingIds.has(entity.id)}
              onGenerate={generate}
              onUpload={upload}
              onSelect={selectVersion}
              onUpdate={update}
              onDelete={remove}
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
                    <h3 className="display-type text-2xl font-semibold">添加{config.title}</h3>
                  </div>
                  <button type="button" className="btn-quiet !min-h-9 !px-2" onClick={() => setShowAdd(false)}>
                    <X className="h-4 w-4" />
                  </button>
                </header>
                <div className="mt-6 grid gap-4 md:grid-cols-2">
                  <label>
                    <span className="label">名称</span>
                    <input className="field" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} autoFocus />
                  </label>
                  {kind === "character" ? (
                    <label>
                      <span className="label">造型阶段</span>
                      <input
                        className="field"
                        value={form.variant}
                        onChange={(e) => setForm({ ...form, variant: e.target.value })}
                        placeholder="默认造型 / 雨夜造型"
                      />
                    </label>
                  ) : null}
                  {kind === "prop" ? (
                    <label>
                      <span className="label">分类</span>
                      <select className="field" value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}>
                        <option value="item">物品</option>
                        <option value="weapon">武器</option>
                        <option value="vehicle">载具</option>
                        <option value="clothing">服装</option>
                        <option value="accessory">饰品</option>
                      </select>
                    </label>
                  ) : null}
                  <label className="md:col-span-2">
                    <span className="label">稳定视觉描述</span>
                    <textarea
                      className="field min-h-40 resize-y leading-6"
                      value={form.description}
                      onChange={(e) => setForm({ ...form, description: e.target.value })}
                      placeholder="描述材质、颜色、轮廓、结构和识别细节…"
                    />
                  </label>
                </div>
                <div className="mt-6 flex justify-end gap-2">
                  <button type="button" className="btn-secondary" onClick={() => setShowAdd(false)}>
                    取消
                  </button>
                  <button type="button" className="btn-primary" onClick={() => void create()}>
                    添加档案
                  </button>
                </div>
              </section>
            </div>,
            document.body,
          )
        : null}
    </div>
  );
}

function EntityCard({ entity, accent, working, onGenerate, onUpload, onSelect, onUpdate, onDelete }) {
  const uploadRef = useRef(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const previewAlt = `${entity.name}${entity.variant ? ` / ${entity.variant}` : ""}`;
  const locked = working;

  return (
    <>
      <article className="panel overflow-hidden">
        <div className="relative aspect-[4/3] bg-[#e8ebef]">
          {entity.selectedImage ? (
            <button
              type="button"
              className="group relative h-full w-full cursor-zoom-in overflow-hidden"
              onClick={() => setPreviewUrl(entity.selectedImage?.url || null)}
            >
              <img
                src={entity.selectedImage.url}
                alt={previewAlt}
                className="h-full w-full object-contain transition-transform duration-300 group-hover:scale-[1.02]"
              />
              <span className="absolute bottom-3 right-3 flex items-center gap-1.5 rounded-full bg-[var(--navy)]/80 px-2.5 py-1.5 text-[10px] font-semibold text-white opacity-0 backdrop-blur-sm transition-opacity group-hover:opacity-100">
                <Maximize2 className="h-3 w-3" /> 查看大图
              </span>
            </button>
          ) : (
            <div className="flex h-full flex-col items-center justify-center text-sm text-[var(--muted)]">
              <ImagePlus className="mb-3 h-8 w-8" style={{ color: accent }} />
              尚无定稿图
            </div>
          )}
          {working ? (
            <div className="absolute inset-0 flex items-center justify-center bg-[var(--navy)]/70 text-sm font-semibold text-white backdrop-blur-sm">
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              正在处理图片…
            </div>
          ) : null}
          <span className="timecode absolute left-3 top-3 rounded-md bg-[var(--navy)]/85 px-2 py-1 text-[9px] text-white">
            {entity.kind.toUpperCase()} / {String(entity.images?.length || 0).padStart(2, "0")} VER
          </span>
        </div>
        <div className="p-4">
          <div className="flex items-start gap-2">
            <div className="min-w-0 flex-1">
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
            <button
              type="button"
              className="btn-quiet !min-h-7 !px-1.5 hover:!text-[var(--danger)]"
              disabled={locked}
              onClick={() => void onDelete(entity)}
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
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
                  <img src={image.url} alt={`版本 ${index + 1}`} className="h-full w-full object-cover" />
                </button>
              ))}
            </div>
          ) : null}
          <div className="mt-4 grid grid-cols-2 gap-2">
            <button type="button" className="btn-primary" disabled={locked} onClick={() => void onGenerate(entity, false)}>
              <Sparkles className="h-3.5 w-3.5" /> {entity.selectedImage ? "生成新版本" : "生成图片"}
            </button>
            <button
              type="button"
              className="btn-secondary"
              disabled={locked || !entity.selectedImage}
              onClick={() => void onGenerate(entity, true)}
            >
              <RefreshCw className="h-3.5 w-3.5" /> 参考重绘
            </button>
            <button type="button" className="btn-secondary col-span-2" disabled={locked} onClick={() => uploadRef.current?.click()}>
              <Upload className="h-3.5 w-3.5" /> 上传本地图
            </button>
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
      </article>
      <Lightbox src={previewUrl} alt={previewAlt} onClose={() => setPreviewUrl(null)} />
    </>
  );
}
