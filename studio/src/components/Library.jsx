import { useMemo, useState } from "react";
import { Clapperboard, Film, FolderOpen, Plus, Search, Trash2 } from "lucide-react";
import { api } from "../api";
import { toast } from "../lib/toast";
import { ConfirmDialog } from "./ConfirmDialog";

const STEP_LABELS = ["剧本", "角色", "场景", "道具", "分镜", "剪辑"];

function progressSteps(project) {
  const p = project.progress || {};
  return [
    (p.episodes?.total || 0) > 0,
    (p.characters?.total || 0) > 0,
    (p.scenes?.total || 0) > 0,
    (p.props?.total || 0) > 0,
    (p.shots?.total || 0) > 0,
    (p.shots?.completed || 0) > 0,
  ];
}

export function Library({ projects, config, onOpen, onCreate, onDeleted, onRefresh }) {
  const [confirmId, setConfirmId] = useState(null);
  const [query, setQuery] = useState("");
  const caps = config?.capabilities || {};

  const visible = useMemo(() => {
    const keyword = query.trim().toLocaleLowerCase("zh-CN");
    if (!keyword) return projects || [];
    return (projects || []).filter((project) =>
      `${project.title} ${project.genre}`.toLocaleLowerCase("zh-CN").includes(keyword),
    );
  }, [projects, query]);

  const remove = async (id) => {
    try {
      await api(`/api/projects/${encodeURIComponent(id)}`, { method: "DELETE" });
      onDeleted?.(id);
      toast.success("项目已删除");
    } catch (e) {
      toast.error(String(e.message || e));
    } finally {
      setConfirmId(null);
    }
  };

  const target = (projects || []).find((p) => p.id === confirmId);

  return (
    <main className="mx-auto min-h-screen max-w-[1500px] px-4 py-5 md:px-8 md:py-8">
      <header className="overflow-hidden rounded-[26px] bg-[var(--navy)] text-white shadow-float">
        <div className="grid min-h-[280px] lg:grid-cols-[1.25fr_.75fr]">
          <div className="flex flex-col justify-between p-7 md:p-10">
            <div className="flex items-center gap-3 text-xs font-bold uppercase tracking-[.2em] text-white/55">
              <Clapperboard className="h-4 w-4 text-[var(--timecode)]" />
              OpenMontage · 影视工坊
            </div>
            <div className="mt-12 max-w-3xl">
              <h1 className="display-type text-4xl font-semibold leading-tight md:text-6xl">
                把一个想法或故事，变成一部完整影片。
              </h1>
              <p className="mt-5 max-w-2xl text-sm leading-7 text-white/65 md:text-base">
                从构思和剧本，到角色、场景、道具与分镜视频，再剪辑完成成片——对齐有彩视界影视工坊完整制作流程。
              </p>
            </div>
          </div>
          <div className="relative border-t border-white/10 bg-[var(--navy-soft)] p-7 lg:border-l lg:border-t-0 md:p-10">
            <div className="absolute bottom-0 left-5 top-0 w-5 film-perforation opacity-70" />
            <div className="ml-8 flex h-full flex-col justify-between">
              <div className="timecode text-xs text-[var(--timecode)]">PIPELINE / 06 STAGES</div>
              <ol className="mt-6 space-y-2">
                {STEP_LABELS.map((label, index) => (
                  <li key={label} className="flex items-center gap-4 border-b border-white/10 py-2.5">
                    <span className="timecode w-7 text-xs text-white/35">{String(index + 1).padStart(2, "0")}</span>
                    <span className="text-sm font-semibold tracking-wide">{label}</span>
                  </li>
                ))}
              </ol>
              <button
                type="button"
                className="btn-primary mt-7 !border-[var(--projector)] !bg-[var(--projector)] !text-[var(--navy)]"
                onClick={onCreate}
              >
                <Plus className="h-4 w-4" /> 建立新片场
              </button>
            </div>
          </div>
        </div>
      </header>

      <section className="mt-8">
        <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <div className="label">Production archive</div>
            <h2 className="display-type text-2xl font-semibold">本地项目</h2>
            <p className="mt-1 text-xs text-[var(--muted)]">
              供应商 {caps.configured ?? 0}/{caps.total ?? 3}
              {caps.deepseek ? " · DeepSeek" : ""}
              {caps.seedream ? " · Seedream" : ""}
              {caps.seedance ? " · Seedance" : ""}
            </p>
          </div>
          <div className="flex w-full flex-wrap items-center gap-2 sm:w-auto">
            <label className="relative w-full sm:w-72">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--muted)]" />
              <input
                className="field !pl-10"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="搜索片名或题材"
              />
            </label>
            <button type="button" className="btn-ghost" onClick={onRefresh}>
              刷新
            </button>
          </div>
        </div>

        {!projects?.length ? (
          <button
            type="button"
            onClick={onCreate}
            className="panel group flex w-full flex-col items-center border-dashed py-20 text-center hover:border-[var(--projector)]"
          >
            <FolderOpen className="mb-4 h-10 w-10 text-[var(--projector)]" />
            <strong className="display-type text-xl">片场还是空的</strong>
            <span className="mt-2 text-sm text-[var(--muted)]">建立第一个项目，从创作需求开始。</span>
          </button>
        ) : visible.length === 0 ? (
          <div className="panel py-16 text-center text-sm text-[var(--muted)]">没有匹配的项目。</div>
        ) : (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {visible.map((project) => {
              const steps = progressSteps(project);
              return (
                <article
                  key={project.id}
                  className="panel group overflow-hidden transition hover:-translate-y-0.5 hover:border-[#b9c2ce]"
                >
                  <button type="button" className="w-full p-5 text-left" onClick={() => onOpen(project.id)}>
                    <div className="flex items-start justify-between gap-4">
                      <div className="min-w-0">
                        <div className="timecode text-[10px] text-[var(--muted)]">
                          UPDATED {project.updatedAt ? new Date(project.updatedAt).toLocaleDateString("zh-CN") : "—"}
                        </div>
                        <h3 className="display-type mt-2 truncate text-xl font-semibold">{project.title}</h3>
                        <p className="mt-1 line-clamp-2 min-h-10 text-sm leading-5 text-[var(--muted)]">
                          {project.synopsis || project.brief || "尚未生成剧本"}
                        </p>
                      </div>
                      <Film className="mt-1 h-5 w-5 shrink-0 text-[var(--projector)]" />
                    </div>
                    <div className="mt-5 grid grid-cols-6 gap-1.5" aria-label="制作进度">
                      {steps.map((done, index) => (
                        <div key={STEP_LABELS[index]}>
                          <div className={`h-1.5 rounded-full ${done ? "bg-[var(--projector)]" : "bg-[#e2e6ec]"}`} />
                          <div className="mt-1.5 text-center text-[10px] text-[var(--muted)]">{STEP_LABELS[index]}</div>
                        </div>
                      ))}
                    </div>
                  </button>
                  <div className="flex items-center justify-between border-t border-[var(--line)] bg-[var(--panel-muted)] px-5 py-3">
                    <span className="timecode text-[10px] text-[var(--muted)]">
                      {project.progress?.shots?.completed || 0}/{project.progress?.shots?.total || 0} SHOTS READY
                    </span>
                    <button
                      type="button"
                      className="btn-quiet !min-h-8 !px-2 text-xs hover:!text-[var(--danger)]"
                      onClick={() => setConfirmId(project.id)}
                    >
                      <Trash2 className="h-3.5 w-3.5" /> 删除
                    </button>
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </section>

      <ConfirmDialog
        open={Boolean(confirmId)}
        title="删除整个项目？"
        message={`《${target?.title || confirmId}》及其剧本、素材档案、分镜和剪辑记录将被删除。`}
        confirmLabel="删除项目"
        danger
        onCancel={() => setConfirmId(null)}
        onConfirm={() => void remove(confirmId)}
      />
    </main>
  );
}
