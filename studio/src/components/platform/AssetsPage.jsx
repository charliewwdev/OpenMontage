import { useEffect, useMemo, useState } from "react";
import { Image as ImageIcon, Loader2, RefreshCw, Search, Video } from "lucide-react";
import { api } from "../../api";
import { toast } from "../../lib/toast";
import { PageShell } from "./PageShell";
import { Lightbox } from "../Lightbox";

export function AssetsPage() {
  const [assets, setAssets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [kind, setKind] = useState("all");
  const [preview, setPreview] = useState(null);

  const refresh = async () => {
    setLoading(true);
    try {
      const data = await api("/api/platform/assets");
      setAssets(data.assets || []);
    } catch (error) {
      toast.error(String(error.message || error));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void refresh();
  }, []);

  const visible = useMemo(() => {
    const q = query.trim().toLocaleLowerCase("zh-CN");
    return assets.filter((item) => {
      if (kind !== "all" && item.kind !== kind) return false;
      if (!q) return true;
      return `${item.projectTitle} ${item.path}`.toLocaleLowerCase("zh-CN").includes(q);
    });
  }, [assets, query, kind]);

  return (
    <PageShell
      eyebrow="Library"
      title="个人资产"
      description="汇总全部项目下的本地图片与成片文件，可预览与复用。"
      actions={
        <button type="button" className="btn-secondary" onClick={() => void refresh()}>
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} /> 刷新
        </button>
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

      {loading ? (
        <div className="panel flex items-center justify-center gap-2 py-20 text-sm text-[var(--muted)]">
          <Loader2 className="h-4 w-4 animate-spin" /> 加载资产…
        </div>
      ) : !visible.length ? (
        <div className="panel py-20 text-center text-sm text-[var(--muted)]">还没有资产。先去影视工坊生成角色图或导出成片。</div>
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
                </div>
              </div>
            </button>
          ))}
        </div>
      )}
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
