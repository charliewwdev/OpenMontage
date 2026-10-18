import { useEffect, useRef, useState } from "react";
import {
  CheckSquare,
  Copy,
  FileText,
  Filter,
  FolderOpen,
  Image as ImageIcon,
  Lightbulb,
  Loader2,
  Plus,
  Search,
  Trash2,
  Upload,
  Video,
  X,
} from "lucide-react";
import { api } from "../../api";
import { toast } from "../../lib/toast";
import { PageShell } from "./PageShell";
import { Lightbox } from "../Lightbox";
import { ModalOverlay } from "../ModalPortal";

const PAGE_SIZE = 60;

const KIND_FILTERS = [
  ["all", "全部"],
  ["image", "图片"],
  ["video", "视频"],
  ["audio", "音频"],
  ["doc", "文档"],
];

const SOURCE_FILTERS = [
  ["all", "全部来源"],
  ["upload", "📤 上传"],
  ["ai", "🤖 AI 生成"],
];

const SORT_FILTERS = [
  ["latest", "最新"],
  ["oldest", "最早"],
  ["hot", "最热"],
];

const PROMPT_SORTS = [
  ["default", "默认"],
  ["latest", "最新"],
  ["oldest", "最早"],
  ["name", "名称"],
];

const ASSET_CATS = [
  { id: "all", label: "全部分类" },
  { id: "character", label: "👤 角色" },
  { id: "scene", label: "🏞️ 场景" },
  { id: "prop", label: "💍 道具" },
  { id: "style", label: "🎨 风格" },
  { id: "storyboard", label: "🎬 分镜" },
  { id: "final", label: "🎞️ 成片" },
  { id: "music", label: "🎵 音乐" },
  { id: "voice", label: "🎙️ 语音" },
  { id: "audio", label: "🎧 音频" },
  { id: "sfx", label: "🔊 音效" },
  { id: "image", label: "🖼️ 图片" },
  { id: "video", label: "🎥 视频" },
  { id: "other", label: "📁 其他" },
];

const PROMPT_CATS = [
  { id: "all", label: "全部" },
  { id: "general", label: "通用" },
  { id: "style", label: "风格" },
  { id: "composition", label: "构图" },
  { id: "lighting", label: "光影" },
  { id: "character", label: "人物" },
  { id: "scene", label: "场景" },
  { id: "camera", label: "运镜" },
  { id: "quality", label: "画质" },
  { id: "audio", label: "音频" },
  { id: "text", label: "文本" },
  { id: "template", label: "模板" },
];

function readAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(new Error("read failed"));
    reader.readAsDataURL(file);
  });
}

function Chip({ active, children, onClick, className = "" }) {
  return (
    <button
      type="button"
      className={`${active ? "chip-active" : "chip"} shrink-0 whitespace-nowrap ${className}`}
      onClick={onClick}
    >
      {children}
    </button>
  );
}

function FilterRow({ children, scroll = false }) {
  if (scroll) {
    return (
      <div className="mb-3 overflow-x-auto pb-1 [scrollbar-width:thin] [-ms-overflow-style:auto]">
        <div className="flex w-max items-center gap-2 pr-2">{children}</div>
      </div>
    );
  }
  return <div className="mb-3 flex flex-wrap items-center gap-2">{children}</div>;
}

function SortLink({ active, children, onClick }) {
  return (
    <button
      type="button"
      className={`shrink-0 text-sm font-medium transition ${
        active ? "text-[#8b7cff]" : "text-white/45 hover:text-white/75"
      }`}
      onClick={onClick}
    >
      {children}
    </button>
  );
}

export function AssetsPage({ onUsePrompt }) {
  const [tab, setTab] = useState("assets");
  const [assets, setAssets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [query, setQuery] = useState("");
  const [kind, setKind] = useState("all");
  const [source, setSource] = useState("all");
  const [category, setCategory] = useState("all");
  const [health, setHealth] = useState("healthy");
  const [sort, setSort] = useState("latest");
  const [preview, setPreview] = useState(null);
  const [total, setTotal] = useState(0);
  const [brokenCount, setBrokenCount] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [nextOffset, setNextOffset] = useState(null);
  const [selectMode, setSelectMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState(() => new Set());
  const fileRef = useRef(null);
  const moreSentinelRef = useRef(null);

  const [prompts, setPrompts] = useState([]);
  const [promptCategory, setPromptCategory] = useState("all");
  const [promptQuery, setPromptQuery] = useState("");
  const [promptSort, setPromptSort] = useState("default");
  const [promptLoading, setPromptLoading] = useState(false);
  const [editor, setEditor] = useState(null);

  const refreshAssets = async ({ append = false, offset = 0 } = {}) => {
    if (append) setLoadingMore(true);
    else setLoading(true);
    try {
      const q = new URLSearchParams({
        limit: String(PAGE_SIZE),
        offset: String(offset),
        kind,
        source,
        category,
        sort,
        health,
      });
      if (query.trim()) q.set("q", query.trim());
      const data = await api(`/api/platform/assets?${q.toString()}`);
      const batch = data.assets || [];
      setAssets((prev) => (append ? [...prev, ...batch] : batch));
      setTotal(data.total || batch.length);
      setBrokenCount(Number(data.brokenCount) || 0);
      setHasMore(Boolean(data.hasMore));
      setNextOffset(data.nextOffset ?? null);
    } catch (error) {
      toast.error(String(error.message || error));
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  };

  const refreshPrompts = async () => {
    setPromptLoading(true);
    try {
      const sortKey = promptSort === "default" ? "latest" : promptSort;
      const q = new URLSearchParams({ category: promptCategory, sort: sortKey });
      if (promptQuery.trim()) q.set("q", promptQuery.trim());
      const data = await api(`/api/platform/prompts?${q.toString()}`);
      setPrompts(data.prompts || []);
    } catch (error) {
      toast.error(String(error.message || error));
    } finally {
      setPromptLoading(false);
    }
  };

  useEffect(() => {
    if (tab !== "assets") return;
    const timer = setTimeout(() => void refreshAssets({ offset: 0 }), query ? 280 : 0);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab, kind, source, category, health, sort, query]);

  useEffect(() => {
    if (tab !== "prompts") return;
    const timer = setTimeout(() => void refreshPrompts(), promptQuery ? 280 : 0);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab, promptCategory, promptSort, promptQuery]);

  useEffect(() => {
    if (tab !== "assets" || !hasMore || loadingMore) return;
    const node = moreSentinelRef.current;
    if (!node) return;
    const io = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          void refreshAssets({ append: true, offset: nextOffset ?? assets.length });
        }
      },
      { rootMargin: "240px" },
    );
    io.observe(node);
    return () => io.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab, hasMore, loadingMore, nextOffset, assets.length]);

  const onUploadFiles = async (fileList) => {
    const files = [...(fileList || [])];
    if (!files.length) return;
    setUploading(true);
    let ok = 0;
    try {
      for (const file of files) {
        const dataUrl = await readAsDataUrl(file);
        await api("/api/platform/assets/upload", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            dataUrl,
            filename: file.name,
            category: category === "all" ? "" : category,
          }),
        });
        ok += 1;
      }
      toast.success(`已上传 ${ok} 个素材`);
      setSource("upload");
      await refreshAssets({ offset: 0 });
    } catch (error) {
      toast.error(String(error.message || error));
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const toggleSelect = (id) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const deleteSelected = async () => {
    const picked = assets.filter((a) => selectedIds.has(a.id || `${a.projectId}-${a.path}`));
    if (!picked.length) return;
    if (!window.confirm(`确定删除选中的 ${picked.length} 个素材？`)) return;
    try {
      await api("/api/platform/assets", {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          items: picked.map((a) => ({ projectId: a.projectId, path: a.path })),
        }),
      });
      toast.success("已删除");
      setSelectedIds(new Set());
      setSelectMode(false);
      await refreshAssets({ offset: 0 });
    } catch (error) {
      toast.error(String(error.message || error));
    }
  };

  const savePrompt = async () => {
    if (!editor?.text?.trim()) return toast.error("请填写提示词内容");
    try {
      await api("/api/platform/prompts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(editor),
      });
      toast.success(editor.id ? "已更新提示词" : "已新建提示词");
      setEditor(null);
      await refreshPrompts();
    } catch (error) {
      toast.error(String(error.message || error));
    }
  };

  const removePrompt = async (id) => {
    if (!window.confirm("确定删除这条提示词？")) return;
    try {
      await api(`/api/platform/prompts/${encodeURIComponent(id)}`, { method: "DELETE" });
      toast.success("已删除");
      await refreshPrompts();
    } catch (error) {
      toast.error(String(error.message || error));
    }
  };

  return (
    <PageShell
      eyebrow="Library"
      title="个人资产"
      description="管理上传素材、AI 生成结果与个人提示词库，可筛选、批量删除并一键带入创作。"
    >
      <input
        ref={fileRef}
        type="file"
        accept="image/*,video/mp4,video/webm,audio/wav,audio/mpeg,.svg,.pdf,.txt,.md,.docx"
        multiple
        className="hidden"
        onChange={(e) => void onUploadFiles(e.target.files)}
      />

      {/* Row 1: 文件夹图标 + 素材/提示词 | 上传·选择 — 对齐有彩 */}
      <div className="mb-4 flex items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2">
          <FolderOpen className="h-4 w-4 shrink-0 text-white/40" aria-hidden />
          <Chip active={tab === "assets"} onClick={() => setTab("assets")}>
            素材
          </Chip>
          <Chip active={tab === "prompts"} onClick={() => setTab("prompts")}>
            提示词
          </Chip>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {tab === "assets" ? (
            <>
              {selectMode ? (
                <button
                  type="button"
                  className="btn-secondary !min-h-9 !px-3"
                  disabled={!selectedIds.size}
                  onClick={() => void deleteSelected()}
                >
                  <Trash2 className="h-3.5 w-3.5" />
                  删除 {selectedIds.size || ""}
                </button>
              ) : (
                <button
                  type="button"
                  className="btn-secondary !min-h-9 !px-3"
                  disabled={uploading}
                  onClick={() => fileRef.current?.click()}
                >
                  {uploading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Upload className="h-3.5 w-3.5" />}
                  上传
                </button>
              )}
              <button
                type="button"
                className={selectMode ? "btn-primary !min-h-9 !px-3" : "btn-secondary !min-h-9 !px-3"}
                onClick={() => {
                  setSelectMode((v) => !v);
                  setSelectedIds(new Set());
                }}
              >
                <CheckSquare className="h-3.5 w-3.5" />
                {selectMode ? "取消" : "选择"}
              </button>
            </>
          ) : (
            <button
              type="button"
              className="btn-primary !min-h-9 !px-3"
              onClick={() =>
                setEditor({
                  title: "",
                  text: "",
                  category: promptCategory === "all" ? "general" : promptCategory,
                })
              }
            >
              <Plus className="h-3.5 w-3.5" /> 新建
            </button>
          )}
        </div>
      </div>

      {tab === "assets" ? (
        <>
          {/* Row 2: 类型 */}
          <FilterRow scroll>
            {KIND_FILTERS.map(([value, label]) => (
              <Chip key={value} active={kind === value} onClick={() => setKind(value)}>
                {label}
              </Chip>
            ))}
          </FilterRow>

          {/* Row 3: 来源 */}
          <FilterRow scroll>
            {SOURCE_FILTERS.map(([value, label]) => (
              <Chip key={value} active={source === value} onClick={() => setSource(value)}>
                {label}
              </Chip>
            ))}
          </FilterRow>

          {/* Row 3b: 质量（默认隐藏损坏文件） */}
          <FilterRow scroll>
            {[
              ["healthy", "仅健康"],
              ["broken", `损坏${brokenCount ? ` ${brokenCount}` : ""}`],
              ["all", "全部含损坏"],
            ].map(([value, label]) => (
              <Chip key={value} active={health === value} onClick={() => setHealth(value)}>
                {label}
              </Chip>
            ))}
          </FilterRow>

          {/* Row 4: 分类横滑 */}
          <FilterRow scroll>
            {ASSET_CATS.map((cat) => (
              <Chip key={cat.id} active={category === cat.id} onClick={() => setCategory(cat.id)}>
                {cat.label}
              </Chip>
            ))}
          </FilterRow>

          {/* Row 5: 排序文字链 + 搜索 */}
          <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-center">
            <div className="flex shrink-0 items-center gap-3">
              <Filter className="h-3.5 w-3.5 text-white/35" aria-hidden />
              {SORT_FILTERS.map(([value, label]) => (
                <SortLink key={value} active={sort === value} onClick={() => setSort(value)}>
                  {label}
                </SortLink>
              ))}
            </div>
            <label className="relative min-w-0 flex-1">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--muted)]" />
              <input
                className="field !pl-10"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="搜索素材..."
              />
            </label>
          </div>

          {loading && !assets.length ? (
            <div className="panel flex items-center justify-center gap-2 py-20 text-sm text-[var(--muted)]">
              <Loader2 className="h-4 w-4 animate-spin" /> 加载资产…
            </div>
          ) : !assets.length ? (
            <div className="panel flex flex-col items-center justify-center gap-4 py-20 text-center">
              <p className="text-sm text-[var(--muted)]">还没有素材。上传参考图，或去影视工坊生成角色 / 导出成片。</p>
              <button type="button" className="btn-primary" disabled={uploading} onClick={() => fileRef.current?.click()}>
                <Upload className="h-3.5 w-3.5" /> 上传素材
              </button>
            </div>
          ) : (
            <>
              <div className="mb-3 text-xs text-white/35">共 {total} 个</div>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                {assets.map((item) => {
                  const id = item.id || `${item.projectId}-${item.path}`;
                  const selected = selectedIds.has(id);
                  const catLabel = ASSET_CATS.find((c) => c.id === item.category)?.label || item.category;
                  return (
                    <button
                      key={id}
                      type="button"
                      className={`panel relative overflow-hidden text-left transition hover:-translate-y-0.5 hover:border-white/20 ${
                        selected ? "border-[#7c6cff]/70 ring-1 ring-[#7c6cff]/40" : ""
                      }`}
                      onClick={() => {
                        if (selectMode) toggleSelect(id);
                        else setPreview(item);
                      }}
                    >
                      {selectMode ? (
                        <span
                          className={`absolute left-2 top-2 z-10 flex h-5 w-5 items-center justify-center rounded border text-[10px] ${
                            selected ? "border-[#7c6cff] bg-[#7c6cff] text-white" : "border-white/40 bg-black/50 text-transparent"
                          }`}
                        >
                          ✓
                        </span>
                      ) : null}
                      <div className="relative flex aspect-video items-center justify-center bg-[#11131a]">
                        {item.broken ? (
                          <div className="flex flex-col items-center gap-1 px-3 text-center text-[11px] text-[#f87171]">
                            <ImageIcon className="h-7 w-7 opacity-70" />
                            损坏 / 空文件
                          </div>
                        ) : item.kind === "video" ? (
                          <video
                            src={item.url}
                            className="max-h-full max-w-full object-contain object-center"
                            muted
                            playsInline
                            preload="metadata"
                          />
                        ) : item.kind === "image" ? (
                          <img
                            src={item.url}
                            alt=""
                            className="max-h-full max-w-full object-contain object-center"
                          />
                        ) : item.kind === "doc" ? (
                          <FileText className="h-8 w-8 text-white/30" />
                        ) : (
                          <ImageIcon className="h-8 w-8 text-white/30" />
                        )}
                        {item.broken ? (
                          <span className="absolute right-2 top-2 rounded bg-[#7f1d1d]/90 px-1.5 py-0.5 text-[10px] text-[#fecaca]">
                            质检未通过
                          </span>
                        ) : null}
                      </div>
                      <div className="p-3">
                        <div className="truncate text-sm font-semibold">{item.name || item.projectTitle}</div>
                        <div className="mt-1 truncate text-[11px] text-[var(--muted)]">
                          {catLabel} · {item.source === "upload" ? "上传" : "AI 生成"}
                          {item.broken && item.qaReason ? ` · ${item.qaReason}` : ""}
                        </div>
                        <div className="mt-2 flex items-center gap-2 text-[10px] text-white/40">
                          {item.kind === "video" ? <Video className="h-3 w-3" /> : <ImageIcon className="h-3 w-3" />}
                          {(item.size / 1024).toFixed(0)} KB
                        </div>
                      </div>
                    </button>
                  );
                })}
              </div>
            </>
          )}

          {hasMore ? (
            <div ref={moreSentinelRef} className="mt-6 flex h-8 items-center justify-center" aria-hidden>
              {loadingMore ? <Loader2 className="h-4 w-4 animate-spin text-white/35" /> : null}
            </div>
          ) : null}
        </>
      ) : (
        <>
          <FilterRow scroll>
            {PROMPT_CATS.map((cat) => (
              <Chip key={cat.id} active={promptCategory === cat.id} onClick={() => setPromptCategory(cat.id)}>
                {cat.label}
              </Chip>
            ))}
          </FilterRow>

          <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-center">
            <div className="flex shrink-0 items-center gap-3">
              <Filter className="h-3.5 w-3.5 text-white/35" aria-hidden />
              {PROMPT_SORTS.map(([value, label]) => (
                <SortLink key={value} active={promptSort === value} onClick={() => setPromptSort(value)}>
                  {label}
                </SortLink>
              ))}
            </div>
            <label className="relative min-w-0 flex-1">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--muted)]" />
              <input
                className="field !pl-10"
                value={promptQuery}
                onChange={(e) => setPromptQuery(e.target.value)}
                placeholder="搜索提示词..."
              />
            </label>
          </div>

          {promptLoading && !prompts.length ? (
            <div className="panel flex items-center justify-center gap-2 py-20 text-sm text-[var(--muted)]">
              <Loader2 className="h-4 w-4 animate-spin" /> 加载提示词…
            </div>
          ) : !prompts.length ? (
            <div className="panel py-20 text-center text-sm text-[var(--muted)]">还没有提示词，点击新建添加</div>
          ) : (
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {prompts.map((item) => (
                <article key={item.id} className="panel flex flex-col p-5">
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <span className="label">
                        {PROMPT_CATS.find((c) => c.id === item.category)?.label || item.category || "通用"}
                      </span>
                      <h3 className="mt-2 text-sm font-semibold text-white">{item.title || "未命名"}</h3>
                    </div>
                    <button type="button" className="btn-secondary !min-h-8 !px-2" onClick={() => void removePrompt(item.id)}>
                      <Trash2 className="h-3 w-3" />
                    </button>
                  </div>
                  <p className="mt-2 line-clamp-6 flex-1 text-sm leading-7 text-white/80">{item.text}</p>
                  <div className="mt-4 flex flex-wrap gap-2">
                    <button
                      type="button"
                      className="btn-secondary flex-1"
                      onClick={async () => {
                        await navigator.clipboard.writeText(item.text);
                        toast.success("已复制");
                      }}
                    >
                      <Copy className="h-3.5 w-3.5" /> 复制
                    </button>
                    <button type="button" className="btn-secondary flex-1" onClick={() => setEditor({ ...item })}>
                      编辑
                    </button>
                    <button type="button" className="btn-primary flex-1" onClick={() => onUsePrompt?.(item.text)}>
                      <Lightbulb className="h-3.5 w-3.5" /> 去创作
                    </button>
                  </div>
                </article>
              ))}
            </div>
          )}
        </>
      )}

      <Lightbox src={preview?.kind === "image" ? preview.url : null} alt={preview?.path} onClose={() => setPreview(null)} />
      {preview?.kind === "video" ? (
        <ModalOverlay onClose={() => setPreview(null)} className="bg-black/80" zClass="z-[200]" role="dialog">
          <div
            className="relative my-auto w-fit max-w-[min(92vw,720px)]"
            onMouseDown={(e) => e.stopPropagation()}
            onClick={(e) => e.stopPropagation()}
          >
            <button
              type="button"
              className="absolute right-2 top-2 z-10 rounded-full bg-black/65 px-3 py-1 text-sm text-white hover:bg-black/80"
              onClick={() => setPreview(null)}
            >
              关闭
            </button>
            <video
              src={preview.url}
              controls
              autoPlay
              playsInline
              className="block max-h-[min(78dvh,78vh)] w-auto max-w-full rounded-xl bg-black shadow-2xl"
            />
          </div>
        </ModalOverlay>
      ) : null}

      {editor ? (
        <ModalOverlay onClose={() => setEditor(null)} className="bg-[#09101d]/80 backdrop-blur-sm">
          <div className="panel my-auto w-full max-w-lg p-5" onMouseDown={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-base font-semibold">{editor.id ? "编辑提示词" : "新建提示词"}</h3>
              <button type="button" className="rounded-full bg-white/10 p-1.5" onClick={() => setEditor(null)}>
                <X className="h-4 w-4" />
              </button>
            </div>
            <label className="block">
              <span className="label">标题</span>
              <input
                className="field mt-1"
                value={editor.title || ""}
                onChange={(e) => setEditor((prev) => ({ ...prev, title: e.target.value }))}
                placeholder="可选"
              />
            </label>
            <label className="mt-3 block">
              <span className="label">分类</span>
              <select
                className="field mt-1"
                value={editor.category || "general"}
                onChange={(e) => setEditor((prev) => ({ ...prev, category: e.target.value }))}
              >
                {PROMPT_CATS.filter((c) => c.id !== "all").map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="mt-3 block">
              <span className="label">内容</span>
              <textarea
                className="field mt-1 min-h-40 resize-y leading-7"
                value={editor.text || ""}
                onChange={(e) => setEditor((prev) => ({ ...prev, text: e.target.value }))}
                placeholder="写下可复用的创作提示词…"
              />
            </label>
            <div className="mt-4 flex gap-2">
              <button type="button" className="btn-secondary flex-1" onClick={() => setEditor(null)}>
                取消
              </button>
              <button type="button" className="btn-primary flex-1" onClick={() => void savePrompt()}>
                保存
              </button>
            </div>
          </div>
        </ModalOverlay>
      ) : null}
    </PageShell>
  );
}
