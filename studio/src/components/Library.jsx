import { useState } from "react";
import { api } from "../api";
import { ConfirmDialog } from "./ConfirmDialog";

function ProgressBar({ label, done, total }) {
  const pct = total > 0 ? Math.round((done / total) * 100) : 0;
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-[11px] text-[var(--muted)]">
        <span>{label}</span>
        <span className="timecode">
          {done}/{total}
        </span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-[var(--line)]">
        <div className="h-full rounded-full bg-[var(--projector)] transition-all" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

export function Library({ projects, config, onOpen, onCreate, onDeleted, onRefresh }) {
  const [confirmId, setConfirmId] = useState(null);
  const caps = config?.capabilities || {};

  const remove = async (id) => {
    try {
      await api(`/api/projects/${encodeURIComponent(id)}`, { method: "DELETE" });
      onDeleted?.(id);
    } catch (e) {
      window.alert(String(e.message || e));
    } finally {
      setConfirmId(null);
    }
  };

  return (
    <div className="mx-auto min-h-full max-w-6xl px-4 py-8 md:px-8">
      <header className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-[0.2em] text-[var(--muted)]">OpenMontage</p>
          <h1 className="display-type mt-1 text-4xl md:text-5xl">短剧片库</h1>
          <p className="mt-2 max-w-xl text-sm text-[var(--muted)]">
            六步创作：剧本 → 角色 → 场景 → 道具 → 分镜 → 剪辑。需配置 DeepSeek / 方舟密钥后方可生成。
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className="rounded-full border border-[var(--line)] bg-white px-3 py-1 text-xs text-[var(--muted)]">
            供应商 {caps.configured ?? 0}/{caps.total ?? 3}
            {caps.deepseek ? " · DeepSeek" : ""}
            {caps.seedream ? " · Seedream" : ""}
            {caps.seedance ? " · Seedance" : ""}
          </span>
          <button type="button" className="btn-ghost" onClick={onRefresh}>
            刷新
          </button>
          <button type="button" className="btn-primary" onClick={onCreate}>
            新建片场
          </button>
        </div>
      </header>

      {!projects?.length ? (
        <div className="panel flex flex-col items-center gap-4 px-6 py-16 text-center">
          <p className="display-type text-2xl">还没有片场</p>
          <p className="text-sm text-[var(--muted)]">创建片名与创作需求，开始第一部短剧。</p>
          <button type="button" className="btn-primary" onClick={onCreate}>
            创建片场
          </button>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {projects.map((p) => {
            const prog = p.progress || {};
            return (
              <article key={p.id} className="panel flex flex-col gap-3 p-4 transition hover:border-[var(--projector)]">
                <button type="button" className="text-left" onClick={() => onOpen(p.id)}>
                  <h2 className="display-type text-xl leading-tight">{p.title || p.id}</h2>
                  <p className="mt-1 line-clamp-2 text-xs text-[var(--muted)]">{p.brief || "暂无创作需求"}</p>
                  <div className="mt-2 flex flex-wrap gap-2 text-[11px] text-[var(--muted)]">
                    <span>{p.genre}</span>
                    <span>·</span>
                    <span>{p.ratio}</span>
                    <span>·</span>
                    <span className="timecode">{(p.updatedAt || "").slice(0, 10)}</span>
                  </div>
                </button>
                <div className="space-y-2 border-t border-[var(--line)] pt-3">
                  <ProgressBar
                    label="剧本定稿"
                    done={prog.episodes?.confirmed || 0}
                    total={prog.episodes?.total || 0}
                  />
                  <ProgressBar
                    label="角色出图"
                    done={prog.characters?.withImage || 0}
                    total={prog.characters?.total || 0}
                  />
                  <ProgressBar
                    label="分镜成片"
                    done={prog.shots?.completed || 0}
                    total={prog.shots?.total || 0}
                  />
                </div>
                <div className="mt-auto flex justify-between pt-1">
                  <button type="button" className="btn-primary !py-1.5 !text-xs" onClick={() => onOpen(p.id)}>
                    进入片场
                  </button>
                  <button type="button" className="btn-ghost !text-xs text-[var(--danger)]" onClick={() => setConfirmId(p.id)}>
                    删除
                  </button>
                </div>
              </article>
            );
          })}
        </div>
      )}

      <ConfirmDialog
        open={Boolean(confirmId)}
        title="删除片场？"
        message="将永久删除项目目录与媒体文件，不可恢复。"
        confirmLabel="删除"
        danger
        onCancel={() => setConfirmId(null)}
        onConfirm={() => void remove(confirmId)}
      />
    </div>
  );
}
