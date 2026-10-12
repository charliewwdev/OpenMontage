import { useMemo, useState } from "react";
import { Clapperboard, Film, FolderOpen, Plus, Search, Trash2 } from "lucide-react";
import { STEPS, libraryCardFromListItem } from "../lib/projectModel";
import { api } from "../api";

export function Library({ projects, bundles, onOpen, onCreate, onDeleted, caps }) {
  const [query, setQuery] = useState("");
  const [busyId, setBusyId] = useState("");

  const cards = useMemo(
    () => projects.map((name) => libraryCardFromListItem(name, bundles[name])),
    [projects, bundles],
  );

  const visible = useMemo(() => {
    const keyword = query.trim().toLocaleLowerCase("zh-CN");
    if (!keyword) return cards;
    return cards.filter((p) => `${p.title} ${p.genre} ${p.id}`.toLocaleLowerCase("zh-CN").includes(keyword));
  }, [cards, query]);

  const remove = async (card) => {
    if (!window.confirm(`删除项目「${card.title}」？本地产物目录将被移除。`)) return;
    setBusyId(card.id);
    try {
      await api("/api/project/delete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ project: card.id }),
      });
      onDeleted?.(card.id);
    } catch (e) {
      window.alert(String(e.message || e));
    } finally {
      setBusyId("");
    }
  };

  return (
    <main className="mx-auto min-h-screen max-w-[1500px] px-4 py-5 md:px-8 md:py-8">
      <header className="overflow-hidden rounded-[26px] bg-[var(--navy)] text-white shadow-float">
        <div className="grid min-h-[280px] lg:grid-cols-[1.25fr_.75fr]">
          <div className="flex flex-col justify-between p-7 md:p-10">
            <div className="flex items-center gap-3 text-xs font-bold uppercase tracking-[.2em] text-white/55">
              <Clapperboard className="h-4 w-4 text-[var(--timecode)]" />
              OpenMontage Drama Studio · Production desk
            </div>
            <div className="mt-12 max-w-3xl">
              <h1 className="display-type text-4xl font-semibold leading-tight md:text-6xl">
                把一个想法或故事，变成一部完整短剧。
              </h1>
              <p className="mt-5 max-w-2xl text-sm leading-7 text-white/65 md:text-base">
                上传小说 → 拆解剧本与资产 → 分镜生成 → 剪辑导出 MP4。六步制片台覆盖从故事到成片的完整流程。
              </p>
            </div>
            {caps ? (
              <div className="timecode mt-8 text-[11px] text-white/40">
                CAPABILITY {caps.configured}/{caps.total} · {caps.mode === "online" ? "ONLINE KEYS" : "OFFLINE BOOTSTRAP"}
              </div>
            ) : null}
          </div>
          <div className="relative border-t border-white/10 bg-[var(--navy-soft)] p-7 lg:border-l lg:border-t-0 md:p-10">
            <div className="absolute bottom-0 left-5 top-0 w-5 film-perforation opacity-70" />
            <div className="ml-8 flex h-full flex-col justify-between">
              <div className="timecode text-xs text-[var(--timecode)]">PIPELINE / 06 STAGES · 3 DESKS</div>
              <ol className="mt-6 space-y-2">
                {STEPS.map((step, index) => (
                  <li key={step.id} className="flex items-center gap-4 border-b border-white/10 py-2.5">
                    <span className="timecode w-7 text-xs text-white/35">{String(index + 1).padStart(2, "0")}</span>
                    <span className="text-sm font-semibold tracking-wide">{step.label}</span>
                    <span className="ml-auto text-[10px] text-white/35">{step.note}</span>
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
          </div>
          <label className="relative w-full sm:w-72">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--muted)]" />
            <input
              className="field !pl-10"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="搜索片名或题材"
            />
          </label>
        </div>

        {projects.length === 0 ? (
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
            {visible.map((project) => (
              <article
                key={project.id}
                className="panel group overflow-hidden transition hover:-translate-y-0.5 hover:border-[#b9c2ce]"
              >
                <button type="button" className="w-full p-5 text-left" onClick={() => onOpen(project.id)}>
                  <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0">
                      <div className="timecode text-[10px] text-[var(--muted)]">
                        {project.ratio} · {project.genre}
                      </div>
                      <h3 className="display-type mt-2 truncate text-xl font-semibold">{project.title}</h3>
                      <p className="mt-1 line-clamp-2 min-h-10 text-sm leading-5 text-[var(--muted)]">
                        {project.synopsis || "尚未生成剧本"}
                      </p>
                    </div>
                    <Film className="mt-1 h-5 w-5 shrink-0 text-[var(--projector)]" />
                  </div>
                  <div className="mt-5 grid grid-cols-6 gap-1.5" aria-label="制作进度">
                    {project.progress.map((done, index) => (
                      <div key={STEPS[index].id}>
                        <div className={`h-1.5 rounded-full ${done ? "bg-[var(--projector)]" : "bg-[#e2e6ec]"}`} />
                        <div className="mt-1.5 text-center text-[10px] text-[var(--muted)]">{STEPS[index].label}</div>
                      </div>
                    ))}
                  </div>
                </button>
                <div className="flex items-center justify-between border-t border-[var(--line)] bg-[var(--panel-muted)] px-5 py-3">
                  <span className="timecode text-[10px] text-[var(--muted)]">{project.shotsReady} SHOTS</span>
                  <button
                    type="button"
                    className="btn-quiet !min-h-8 !px-2 text-xs hover:!text-[var(--danger)]"
                    disabled={busyId === project.id}
                    onClick={() => void remove(project)}
                  >
                    <Trash2 className="h-3.5 w-3.5" /> 删除
                  </button>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
