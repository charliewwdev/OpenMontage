import { useEffect, useMemo, useRef, useState } from "react";
import { Image as ImageIcon, Loader2, RefreshCw, Search, Upload, Video } from "lucide-react";
import { api } from "../../api";
import { toast } from "../../lib/toast";
import { PageShell } from "./PageShell";
import { Lightbox } from "../Lightbox";

const PAGE_SIZE = 60;

function readAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(new Error("read failed"));
    reader.readAsDataURL(file);
  });
}

export function AssetsPage() {
  const [assets, setAssets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [query, setQuery] = useState("");
  const [kind, setKind] = useState("all");
  const [preview, setPreview] = useState(null);
  const [total, setTotal] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [nextOffset, setNextOffset] = useState(null);
  const fileRef = useRef(null);

  const refresh = async ({ append = false, offset = 0 } = {}) => {
    if (append) setLoadingMore(true);
    else setLoading(true);
    try {
      const q = new URLSearchParams({ limit: String(PAGE_SIZE), offset: String(offset) });
      const data = await api(`/api/platform/assets?${q.toString()}`);
      const batch = data.assets || [];
      setAssets((prev) => (append ? [...prev, ...batch] : batch));
      setTotal(data.total || batch.length);
      setHasMore(Boolean(data.hasMore));
      setNextOffset(data.nextOffset ?? null);
    } catch (error) {
      toast.error(String(error.message || error));
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  };

  useEffect(() => {
    void refresh({ offset: 0 });
  }, []);

  const visible = useMemo(() => {
    const q = query.trim().toLocaleLowerCase("zh-CN");
    return assets.filter((item) => {
      if (kind !== "all" && item.kind !== kind) return false;
      if (!q) return true;
      return `${item.projectTitle} ${item.path}`.toLocaleLowerCase("zh-CN").includes(q);
    });
  }, [assets, query, kind]);

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
          body: JSON.stringify({ dataUrl, filename: file.name }),
        });
        ok += 1;
      }
      toast.success(`已上传 ${ok} 个素材`);
      await refresh({ offset: 0 });
    } catch (error) {
      toast.error(String(error.message || error));
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  return (
    <PageShell
      eyebrow="Library"
      title="个人资产"
      description="上传个人参考图/视频，并汇总各项目生成的本地素材，可预览与复用。"
      actions={
        <div className="flex flex-wrap gap-2">
          <button type="button" className="btn-primary" disabled={uploading} onClick={() => fileRef.current?.click()}>
            {uploading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Upload className="h-3.5 w-3.5" />}
            上传素材
          </button>
          <button type="button" className="btn-secondary" onClick={() => void refresh({ offset: 0 })}>
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} /> 刷新
          </button>
          <input
            ref={fileRef}
            type="file"
            accept="image/*,video/mp4,video/webm,audio/wav,audio/mpeg,.svg"
            multiple
            className="hidden"
            onChange={(e) => void onUploadFiles(e.target.files)}
          />
        </div>
      }
    >
      <div className="mb-4 flex flex-wrap gap-2">
        <label className="relative min-w-[220px] flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--muted)]" />
          <input className="field !pl-10" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="搜索项目或文件名" />
        </label>
        {[
          ["all", "全部"],
          ["image", "图片"],
          ["video", "视频"],
          ["audio", "音频"],
        ].map(([value, label]) => (
          <button key={value} type="button" className={kind === value ? "chip-active" : "chip"} onClick={() => setKind(value)}>
            {label}
          </button>
        ))}
      </div>

      <div className="mb-3 text-xs text-white/40">
        {total ? `共 ${total} 个 · 当前列表 ${visible.length}` : null}
      </div>

      {loading ? (
        <div className="panel flex items-center justify-center gap-2 py-20 text-sm text-[var(--muted)]">
          <Loader2 className="h-4 w-4 animate-spin" /> 加载资产…
        </div>
      ) : !visible.length ? (
        <div className="panel py-20 text-center text-sm text-[var(--muted)]">
          还没有资产。点击上方「上传素材」，或先去影视工坊生成角色图 / 导出成片。
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {visible.map((item) => (
            <button
              key={`${item.projectId}-${item.path}`}
              type="button"
              className="panel overflow-hidden text-left transition hover:-translate-y-0.5 hover:border-white/20"
              onClick={() => setPreview(item)}
            >
              <div className="flex aspect-video items-center justify-center bg-black/40">
                {item.kind === "video" ? (
                  <video src={item.url} className="h-full w-full object-cover" muted />
                ) : item.kind === "image" ? (
                  <img src={item.url} alt="" className="h-full w-full object-cover" />
                ) : (
                  <ImageIcon className="h-8 w-8 text-white/30" />
                )}
              </div>
              <div className="p-3">
                <div className="truncate text-sm font-semibold">{item.projectTitle}</div>
                <div className="mt-1 truncate text-[11px] text-[var(--muted)]">{item.path}</div>
                <div className="mt-2 flex items-center gap-2 text-[10px] text-white/40">
                  {item.kind === "video" ? <Video className="h-3 w-3" /> : <ImageIcon className="h-3 w-3" />}
                  {(item.size / 1024).toFixed(0)} KB
                  {item.uploaded ? " · 上传" : ""}
                </div>
              </div>
            </button>
          ))}
        </div>
      )}

      {hasMore && !query ? (
        <div className="mt-6 flex justify-center">
          <button
            type="button"
            className="btn-secondary"
            disabled={loadingMore}
            onClick={() => void refresh({ append: true, offset: nextOffset ?? assets.length })}
          >
            {loadingMore ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}
            加载更多
          </button>
        </div>
      ) : null}

      <Lightbox
        src={preview?.kind === "image" ? preview.url : null}
        alt={preview?.path}
        onClose={() => setPreview(null)}
      />
      {preview?.kind === "video" ? (
        <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/80 p-4" onMouseDown={() => setPreview(null)}>
          <video
            src={preview.url}
            controls
            autoPlay
            className="max-h-[80vh] max-w-4xl rounded-xl"
            onMouseDown={(e) => e.stopPropagation()}
          />
        </div>
      ) : null}
    </PageShell>
  );
}
