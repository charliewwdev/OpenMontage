import { useEffect, useMemo, useState } from "react";
import { api } from "../../api";
import { Lightbox } from "../Lightbox";

const LABELS = {
  character: { title: "角色台", empty: "定稿剧本后将自动同步角色档案", three: true },
  scene: { title: "场景台", empty: "定稿剧本后将自动同步场景档案", three: false },
  prop: { title: "道具台", empty: "定稿剧本后将自动同步道具档案", three: true },
};

export function EntityStep({ projectId, bundle, kind, setBusyMsg, onBundle, onRefresh }) {
  const meta = LABELS[kind];
  const entities = useMemo(
    () =>
      (bundle?.entities || [])
        .filter((e) => e.kind === kind && !e.deletedAt)
        .sort((a, b) => (a.name || "").localeCompare(b.name || "", "zh")),
    [bundle?.entities, kind],
  );
  const [activeId, setActiveId] = useState("");
  const [lightbox, setLightbox] = useState(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

  const active = entities.find((e) => e.id === activeId) || entities[0];

  useEffect(() => {
    if (!active) {
      setActiveId("");
      setName("");
      setDescription("");
      return;
    }
    setActiveId(active.id);
    setName(active.name || "");
    setDescription(active.description || "");
  }, [active?.id, kind]);

  const selectEntity = (ent) => {
    setActiveId(ent.id);
    setName(ent.name || "");
    setDescription(ent.description || "");
  };

  const apply = (res) => {
    if (res?.bundle) onBundle?.(res.bundle);
    else onRefresh?.();
  };

  const saveMeta = async () => {
    if (!active) return;
    setBusyMsg("保存档案…");
    try {
      const res = await api(`/api/projects/${encodeURIComponent(projectId)}/entities`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ entityId: active.id, name, description }),
      });
      apply(res);
    } catch (e) {
      window.alert(String(e.message || e));
    } finally {
      setBusyMsg("");
    }
  };

  const generate = async (opts = {}) => {
    if (!active) return;
    setBusyMsg(opts.redraw ? "参考重绘…" : opts.threeView ? "三视图出图…" : "出图中…");
    const t0 = performance.now();
    try {
      const res = await api(`/api/projects/${encodeURIComponent(projectId)}/entities`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "generate",
          entityId: active.id,
          threeView: Boolean(opts.threeView),
          redraw: Boolean(opts.redraw),
        }),
      });
      apply(res);
      setBusyMsg(`完成（${((performance.now() - t0) / 1000).toFixed(1)}s）`);
      setTimeout(() => setBusyMsg(""), 1500);
    } catch (e) {
      setBusyMsg("");
      window.alert(String(e.message || e));
    }
  };

  const batch = async () => {
    const ids = entities.filter((e) => !e.selectedImageId).map((e) => e.id);
    if (!ids.length) {
      window.alert("没有缺少图片的档案");
      return;
    }
    setBusyMsg(`批量出图 ${ids.length} 项…`);
    try {
      const res = await api(`/api/projects/${encodeURIComponent(projectId)}/entities`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "batch", entityIds: ids, threeView: meta.three }),
      });
      apply(res);
    } catch (e) {
      window.alert(String(e.message || e));
    } finally {
      setBusyMsg("");
    }
  };

  const selectVersion = async (imageId) => {
    setBusyMsg("切换版本…");
    try {
      const res = await api(`/api/projects/${encodeURIComponent(projectId)}/entities`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "select", entityId: active.id, imageId }),
      });
      apply(res);
    } catch (e) {
      window.alert(String(e.message || e));
    } finally {
      setBusyMsg("");
    }
  };

  const upload = async (file) => {
    if (!active || !file) return;
    const reader = new FileReader();
    reader.onload = async () => {
      setBusyMsg("上传中…");
      try {
        const res = await api(`/api/projects/${encodeURIComponent(projectId)}/entities`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            action: "upload",
            entityId: active.id,
            dataUrl: reader.result,
          }),
        });
        apply(res);
      } catch (e) {
        window.alert(String(e.message || e));
      } finally {
        setBusyMsg("");
      }
    };
    reader.readAsDataURL(file);
  };

  const softDelete = async () => {
    if (!active || !window.confirm(`软删除「${active.name}」？`)) return;
    setBusyMsg("删除…");
    try {
      const res = await api(
        `/api/projects/${encodeURIComponent(projectId)}/entities?entityId=${encodeURIComponent(active.id)}`,
        { method: "DELETE" },
      );
      apply(res);
      setActiveId("");
    } catch (e) {
      window.alert(String(e.message || e));
    } finally {
      setBusyMsg("");
    }
  };

  const createNew = async () => {
    const n = window.prompt(`新建${meta.title.replace("台", "")}名称`);
    if (!n?.trim()) return;
    setBusyMsg("创建档案…");
    try {
      const res = await api(`/api/projects/${encodeURIComponent(projectId)}/entities`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ kind, name: n.trim(), description: "" }),
      });
      apply(res);
      if (res.entity) selectEntity(res.entity);
    } catch (e) {
      window.alert(String(e.message || e));
    } finally {
      setBusyMsg("");
    }
  };

  const images = active?.images || [];
  const selected = active?.selectedImage;

  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="display-type text-3xl">{meta.title}</h2>
          <p className="mt-1 text-sm text-[var(--muted)]">出图 · 三视图 · 版本切换 · 上传 · 批量补齐 · 参考重绘</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button type="button" className="btn-ghost" onClick={() => void createNew()}>
            新建
          </button>
          <button type="button" className="btn-primary" onClick={() => void batch()}>
            批量补齐缺图
          </button>
        </div>
      </header>

      <div className="grid gap-4 lg:grid-cols-[260px_1fr]">
        <aside className="panel max-h-[70vh] overflow-auto p-2">
          {entities.map((ent) => (
            <button
              key={ent.id}
              type="button"
              className={`mb-1 flex w-full items-center gap-2 rounded-lg px-2 py-2 text-left ${
                active?.id === ent.id ? "bg-[var(--panel-muted)]" : "hover:bg-[var(--panel-muted)]"
              }`}
              onClick={() => selectEntity(ent)}
            >
              <div className="h-10 w-10 shrink-0 overflow-hidden rounded-md bg-[var(--line)]">
                {ent.selectedImage?.url ? (
                  <img src={ent.selectedImage.url} alt="" className="h-full w-full object-cover" />
                ) : null}
              </div>
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-medium">{ent.name}</div>
                <div className="truncate text-[11px] text-[var(--muted)]">
                  {ent.images?.length || 0} 版本{ent.selectedImageId ? " · 已出图" : " · 缺图"}
                </div>
              </div>
            </button>
          ))}
          {!entities.length && <p className="px-2 py-8 text-center text-xs text-[var(--muted)]">{meta.empty}</p>}
        </aside>

        <section className="panel space-y-4 p-4">
          {active ? (
            <>
              <div className="grid gap-3 md:grid-cols-2">
                <label className="text-xs text-[var(--muted)]">
                  名称
                  <input className="field mt-1" value={name} onChange={(e) => setName(e.target.value)} />
                </label>
                <div className="flex items-end gap-2">
                  <button type="button" className="btn-ghost" onClick={() => void saveMeta()}>
                    保存档案
                  </button>
                  <button type="button" className="btn-ghost text-[var(--danger)]" onClick={() => void softDelete()}>
                    软删除
                  </button>
                </div>
              </div>
              <label className="block text-xs text-[var(--muted)]">
                描述 / 出图提示
                <textarea
                  className="field mt-1 min-h-[90px]"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                />
              </label>

              <div className="flex flex-wrap gap-2">
                <button type="button" className="btn-primary" onClick={() => void generate()}>
                  Seedream 出图
                </button>
                {meta.three ? (
                  <button type="button" className="btn-ghost" onClick={() => void generate({ threeView: true })}>
                    三视图
                  </button>
                ) : null}
                <button
                  type="button"
                  className="btn-ghost"
                  disabled={!selected}
                  onClick={() => void generate({ redraw: true })}
                >
                  参考重绘
                </button>
                <label className="btn-ghost cursor-pointer">
                  本地上传
                  <input
                    type="file"
                    accept="image/*"
                    className="hidden"
                    onChange={(e) => void upload(e.target.files?.[0])}
                  />
                </label>
              </div>

              <div
                className="relative flex min-h-[280px] items-center justify-center overflow-hidden rounded-xl bg-[var(--panel-muted)]"
                onClick={() => selected?.url && setLightbox(selected.url)}
              >
                {selected?.url ? (
                  <img src={selected.url} alt={active.name} className="max-h-[420px] cursor-zoom-in object-contain" />
                ) : (
                  <span className="text-sm text-[var(--muted)]">尚未出图</span>
                )}
              </div>

              {images.length > 0 && (
                <div>
                  <p className="mb-2 text-xs text-[var(--muted)]">版本条（点击选用）</p>
                  <div className="flex flex-wrap gap-2">
                    {images.map((img, i) => (
                      <button
                        key={img.id}
                        type="button"
                        className={`h-16 w-16 overflow-hidden rounded-lg border-2 ${
                          img.id === active.selectedImageId
                            ? "border-[var(--projector)]"
                            : "border-transparent opacity-80 hover:opacity-100"
                        }`}
                        onClick={() => void selectVersion(img.id)}
                        title={`版本 ${i + 1}`}
                      >
                        <img src={img.url} alt="" className="h-full w-full object-cover" />
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </>
          ) : (
            <p className="py-16 text-center text-sm text-[var(--muted)]">{meta.empty}</p>
          )}
        </section>
      </div>

      <Lightbox src={lightbox} onClose={() => setLightbox(null)} />
    </div>
  );
}
