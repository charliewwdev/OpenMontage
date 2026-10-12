import { useEffect, useMemo, useState } from "react";
import { ImagePlus, Plus, Save, Sparkles, Users } from "lucide-react";
import { api } from "../../api";

const CONFIG = {
  characters: {
    title: "角色造型",
    eyebrow: "Cast bible",
    empty: "剧本拆解后会自动整理角色；也可以手动补充造型描述。",
    entity: "character",
    accent: "#56c7c1",
  },
  locations: {
    title: "空镜场景",
    eyebrow: "Location bible",
    empty: "在这里建立可重复使用的空间与光线设定。",
    entity: "location",
    accent: "#3d8f9c",
  },
  props: {
    title: "关键道具",
    eyebrow: "Prop bible",
    empty: "只保留跨镜头需要维持一致的关键物件。",
    entity: "prop",
    accent: "#d79833",
  },
};

function itemList(view, kind) {
  if (kind === "characters") return view.characters;
  if (kind === "locations") return view.locations;
  return view.props;
}

function itemBlurb(item) {
  return item.appearance || item.description || item.look || item.visual || item.summary || "暂无视觉描述";
}

function mediaUrl(project, rel) {
  if (!rel) return null;
  return `/api/media/${encodeURIComponent(project)}/${rel.split("/").map(encodeURIComponent).join("/")}`;
}

export function EntityStep({ kind, project, view, onBundle }) {
  const config = CONFIG[kind];
  const items = useMemo(() => itemList(view, kind), [view, kind]);
  const [selectedId, setSelectedId] = useState(items[0]?.id || null);
  const [draft, setDraft] = useState("");
  const [name, setName] = useState("");
  const [status, setStatus] = useState("");
  const [saving, setSaving] = useState(false);
  const [showAdd, setShowAdd] = useState(false);
  const [newName, setNewName] = useState("");
  const [newDesc, setNewDesc] = useState("");

  const selected = items.find((i) => i.id === selectedId) || items[0] || null;
  const preview = mediaUrl(project, selected?.selected_image || selected?.reference_image);

  useEffect(() => {
    if (!selected) {
      setDraft("");
      setName("");
      return;
    }
    setSelectedId(selected.id);
    setName(selected.name || selected.id || "");
    setDraft(itemBlurb(selected));
  }, [selected?.id, items.length]);

  const save = async () => {
    if (!selected) return;
    setSaving(true);
    setStatus("");
    try {
      const item = {
        ...selected,
        id: selected.id || `${config.entity}_${Date.now()}`,
        name,
        display_name: name,
      };
      if (config.entity === "character") item.appearance = draft;
      else item.description = draft;
      await api("/api/project/bible/upsert", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ project, entity: config.entity, item }),
      });
      const bundle = await api(`/api/project/bundle?name=${encodeURIComponent(project)}`);
      onBundle?.(bundle);
      setStatus("已保存到素材档案");
    } catch (e) {
      setStatus(String(e.message || e));
    } finally {
      setSaving(false);
    }
  };

  const generateRef = async () => {
    if (!selected) return;
    setSaving(true);
    setStatus("");
    try {
      await save();
      const res = await api("/api/project/entity/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ project, entity: config.entity, item_id: selected.id }),
      });
      onBundle?.(res.bundle);
      setStatus("定妆 / 参考板已生成");
    } catch (e) {
      setStatus(String(e.message || e));
    } finally {
      setSaving(false);
    }
  };

  const add = async () => {
    if (!newName.trim() || !newDesc.trim()) return;
    setSaving(true);
    try {
      const item = {
        id: `${config.entity}_${Date.now()}`,
        name: newName.trim(),
        display_name: newName.trim(),
      };
      if (config.entity === "character") item.appearance = newDesc.trim();
      else item.description = newDesc.trim();
      await api("/api/project/bible/upsert", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ project, entity: config.entity, item }),
      });
      const bundle = await api(`/api/project/bundle?name=${encodeURIComponent(project)}`);
      onBundle?.(bundle);
      setShowAdd(false);
      setNewName("");
      setNewDesc("");
      setSelectedId(item.id);
      setStatus("素材档案已添加");
    } catch (e) {
      setStatus(String(e.message || e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="label">{config.eyebrow}</div>
          <h3 className="display-type text-2xl font-semibold">{config.title}</h3>
          <p className="mt-1 text-sm text-[var(--muted)]">{config.empty}</p>
        </div>
        <button type="button" className="btn-primary" onClick={() => setShowAdd(true)}>
          <Plus className="h-4 w-4" /> 添加
        </button>
      </div>

      {items.length === 0 ? (
        <div className="panel flex flex-col items-center border-dashed py-20 text-center">
          <Users className="mb-3 h-10 w-10" style={{ color: config.accent }} />
          <strong className="display-type text-lg">档案还是空的</strong>
          <p className="mt-2 max-w-md text-sm text-[var(--muted)]">{config.empty}</p>
        </div>
      ) : (
        <div className="grid gap-4 xl:grid-cols-[280px_minmax(0,1fr)]">
          <div className="panel max-h-[70vh] space-y-1 overflow-y-auto p-2 scrollbar-thin">
            {items.map((item) => {
              const thumb = mediaUrl(project, item.selected_image || item.reference_image);
              return (
                <button
                  key={item.id}
                  type="button"
                  className={`flex w-full items-start gap-3 rounded-xl px-3 py-3 text-left transition ${
                    selected?.id === item.id ? "bg-[var(--panel-muted)]" : "hover:bg-[var(--panel-muted)]/70"
                  }`}
                  onClick={() => setSelectedId(item.id)}
                >
                  <div
                    className="flex h-14 w-11 shrink-0 items-center justify-center overflow-hidden rounded-xl border border-[var(--line)] bg-white"
                    style={{ boxShadow: `inset 0 0 0 2px ${config.accent}22` }}
                  >
                    {thumb ? <img src={thumb} alt="" className="h-full w-full object-cover" /> : <ImagePlus className="h-4 w-4 text-[var(--muted)]" />}
                  </div>
                  <div className="min-w-0">
                    <div className="truncate text-sm font-semibold">{item.name || item.id}</div>
                    <div className="mt-1 line-clamp-2 text-[11px] leading-4 text-[var(--muted)]">{itemBlurb(item)}</div>
                  </div>
                </button>
              );
            })}
          </div>

          {selected ? (
            <div className="space-y-4">
              <div className="panel overflow-hidden">
                <div className="flex aspect-[3/4] max-h-[360px] items-center justify-center bg-[var(--navy)]">
                  {preview ? (
                    <img src={preview} alt={selected.name} className="h-full w-full object-contain" />
                  ) : (
                    <div className="px-6 text-center text-sm text-white/45">尚未生成参考板</div>
                  )}
                </div>
              </div>
              <div className="panel p-5 md:p-6">
                <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <div className="timecode text-[10px] text-[var(--muted)]">{selected.id}</div>
                    <h4 className="display-type text-xl font-semibold">{selected.name || "未命名"}</h4>
                  </div>
                  <div className="flex gap-2">
                    <button type="button" className="btn-secondary" disabled={saving} onClick={generateRef}>
                      <Sparkles className="h-4 w-4" />
                      生成参考板
                    </button>
                    <button type="button" className="btn-primary" disabled={saving} onClick={save}>
                      <Save className="h-4 w-4" />
                      {saving ? "保存中…" : "保存"}
                    </button>
                  </div>
                </div>
                <label className="mb-4 block">
                  <span className="label">名称</span>
                  <input className="field" value={name} onChange={(e) => setName(e.target.value)} />
                </label>
                <label className="block">
                  <span className="label">视觉描述</span>
                  <textarea className="field min-h-40 resize-y leading-7" value={draft} onChange={(e) => setDraft(e.target.value)} />
                </label>
                {status ? <p className="mt-3 text-xs text-[var(--muted)]">{status}</p> : null}
              </div>
            </div>
          ) : null}
        </div>
      )}

      {showAdd ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-[rgba(16,24,39,.5)] p-4" onClick={() => setShowAdd(false)}>
          <div className="panel w-full max-w-lg p-6" onClick={(e) => e.stopPropagation()}>
            <h4 className="display-type text-xl font-semibold">添加{config.title}</h4>
            <label className="mt-4 block">
              <span className="label">名称</span>
              <input className="field" value={newName} onChange={(e) => setNewName(e.target.value)} />
            </label>
            <label className="mt-3 block">
              <span className="label">视觉描述</span>
              <textarea className="field min-h-32 resize-y" value={newDesc} onChange={(e) => setNewDesc(e.target.value)} />
            </label>
            <div className="mt-4 flex justify-end gap-2">
              <button type="button" className="btn-secondary" onClick={() => setShowAdd(false)}>
                取消
              </button>
              <button type="button" className="btn-primary" disabled={saving} onClick={add}>
                确认添加
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
