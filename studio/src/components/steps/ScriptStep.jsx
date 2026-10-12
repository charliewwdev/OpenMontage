import { useEffect, useState } from "react";
import { api } from "../../api";
import { ConfirmDialog } from "../ConfirmDialog";

export function ScriptStep({ projectId, bundle, setBusyMsg, onBundle, onRefresh }) {
  const project = bundle?.project || {};
  const episodes = [...(bundle?.episodes || [])].sort((a, b) => a.episodeNumber - b.episodeNumber);
  const [activeId, setActiveId] = useState(episodes[0]?.id || "");
  const [brief, setBrief] = useState(project.brief || "");
  const [count, setCount] = useState(1);
  const [instruction, setInstruction] = useState("");
  const [rewriteStart, setRewriteStart] = useState(1);
  const [draft, setDraft] = useState("");
  const [confirmBatch, setConfirmBatch] = useState(false);

  const active = episodes.find((e) => e.id === activeId) || episodes[0];

  useEffect(() => {
    setBrief(project.brief || "");
  }, [project.brief]);

  useEffect(() => {
    if (active) {
      setActiveId(active.id);
      setDraft(active.content || "");
    }
  }, [active?.id]);

  useEffect(() => {
    if (active && activeId === active.id) setDraft(active.content || "");
  }, [active?.content, active?.id, activeId]);

  const applyBundle = (b) => {
    if (b?.bundle) onBundle?.(b.bundle);
    else if (b?.project) onBundle?.(b);
    else onRefresh?.();
  };

  const saveBrief = async () => {
    setBusyMsg("保存创作需求…");
    try {
      const b = await api(`/api/projects/${encodeURIComponent(projectId)}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ brief }),
      });
      onBundle?.(b);
    } catch (e) {
      window.alert(String(e.message || e));
    } finally {
      setBusyMsg("");
    }
  };

  const optimizeBrief = async () => {
    setBusyMsg("AI 优化需求…");
    try {
      const res = await api(`/api/projects/${encodeURIComponent(projectId)}/script-brief`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          brief,
          genre: project.genre,
          visualStyle: project.visualStyle,
          title: project.title,
        }),
      });
      if (res.brief) {
        setBrief(res.brief);
        await api(`/api/projects/${encodeURIComponent(projectId)}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ brief: res.brief }),
        });
        onRefresh?.();
      }
    } catch (e) {
      window.alert(String(e.message || e));
    } finally {
      setBusyMsg("");
    }
  };

  const runScript = async (action, extra = {}) => {
    setBusyMsg(action === "generate" ? "生成剧本…" : action === "continue" ? "续写中…" : "改写中…");
    const t0 = performance.now();
    try {
      const b = await api(`/api/projects/${encodeURIComponent(projectId)}/script`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action, episodeCount: count, instruction, ...extra }),
      });
      applyBundle(b);
      const sec = ((performance.now() - t0) / 1000).toFixed(1);
      setBusyMsg(`完成（${sec}s）`);
      setTimeout(() => setBusyMsg(""), 1500);
    } catch (e) {
      setBusyMsg("");
      window.alert(String(e.message || e));
    }
  };

  const saveEpisode = async () => {
    if (!active) return;
    setBusyMsg("保存分集…");
    try {
      await api(`/api/projects/${encodeURIComponent(projectId)}/episodes`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ episodeId: active.id, content: draft, title: active.title }),
      });
      onRefresh?.();
    } catch (e) {
      window.alert(String(e.message || e));
    } finally {
      setBusyMsg("");
    }
  };

  const setStatus = async (ids, status) => {
    setBusyMsg(status === "confirmed" ? "定稿中…" : "更新状态…");
    try {
      const b = await api(`/api/projects/${encodeURIComponent(projectId)}/episodes`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ episodeIds: ids, status }),
      });
      applyBundle(b);
    } catch (e) {
      window.alert(String(e.message || e));
    } finally {
      setBusyMsg("");
    }
  };

  const draftIds = episodes.filter((e) => e.status !== "confirmed").map((e) => e.id);

  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="display-type text-3xl">剧本台</h2>
          <p className="mt-1 text-sm text-[var(--muted)]">分批生成 1–10 集 · 续写 · 指定集改写 · 逐集定稿</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <label className="flex items-center gap-2 text-xs text-[var(--muted)]">
            集数
            <input
              type="number"
              min={1}
              max={10}
              className="field !w-16 !py-1.5"
              value={count}
              onChange={(e) => setCount(Math.min(10, Math.max(1, Number(e.target.value) || 1)))}
            />
          </label>
          <button
            type="button"
            className="btn-primary"
            onClick={() => void runScript(episodes.length ? "continue" : "generate", { brief, instruction })}
          >
            {episodes.length ? "追加生成" : "生成剧本"}
          </button>
          <button
            type="button"
            className="btn-ghost"
            disabled={!episodes.length}
            onClick={() => void runScript("continue", { brief, instruction })}
          >
            续写
          </button>
          <button
            type="button"
            className="btn-ghost"
            disabled={!episodes.length}
            onClick={() => void runScript("rewrite", { startEpisode: rewriteStart, instruction })}
          >
            改写自第 {rewriteStart} 集
          </button>
        </div>
      </header>

      <section className="panel space-y-3 p-4">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold">创作需求</h3>
          <div className="flex gap-2">
            <button type="button" className="btn-ghost !py-1 !text-xs" onClick={() => void optimizeBrief()}>
              AI 优化需求
            </button>
            <button type="button" className="btn-ghost !py-1 !text-xs" onClick={() => void saveBrief()}>
              保存
            </button>
          </div>
        </div>
        <textarea className="field min-h-[100px]" value={brief} onChange={(e) => setBrief(e.target.value)} />
        <div className="grid gap-2 sm:grid-cols-2">
          <label className="text-xs text-[var(--muted)]">
            续写/改写指令
            <input
              className="field mt-1"
              value={instruction}
              onChange={(e) => setInstruction(e.target.value)}
              placeholder="可选：加强冲突、收束结局…"
            />
          </label>
          <label className="text-xs text-[var(--muted)]">
            改写起始集
            <input
              type="number"
              min={1}
              className="field mt-1"
              value={rewriteStart}
              onChange={(e) => setRewriteStart(Math.max(1, Number(e.target.value) || 1))}
            />
          </label>
        </div>
      </section>

      <div className="grid gap-4 lg:grid-cols-[240px_1fr]">
        <aside className="panel p-2">
          <div className="mb-2 flex items-center justify-between px-2 pt-1">
            <span className="text-xs text-[var(--muted)]">分集 ({episodes.length})</span>
            <button
              type="button"
              className="btn-ghost !py-0.5 !text-[11px]"
              disabled={!draftIds.length}
              onClick={() => setConfirmBatch(true)}
            >
              批量定稿
            </button>
          </div>
          <ul className="max-h-[60vh] space-y-1 overflow-auto">
            {episodes.map((ep) => (
              <li key={ep.id}>
                <button
                  type="button"
                  className={`flex w-full items-center justify-between rounded-lg px-2 py-2 text-left text-sm ${
                    (active?.id || activeId) === ep.id ? "bg-[var(--panel-muted)]" : "hover:bg-[var(--panel-muted)]"
                  }`}
                  onClick={() => {
                    setActiveId(ep.id);
                    setDraft(ep.content || "");
                  }}
                >
                  <span>
                    <span className="timecode mr-1 text-[10px] text-[var(--muted)]">
                      EP{String(ep.episodeNumber).padStart(2, "0")}
                    </span>
                    {ep.title || `第${ep.episodeNumber}集`}
                  </span>
                  <span
                    className={`rounded px-1.5 py-0.5 text-[10px] ${
                      ep.status === "confirmed"
                        ? "bg-emerald-100 text-emerald-800"
                        : "bg-amber-50 text-amber-800"
                    }`}
                  >
                    {ep.status === "confirmed" ? "定稿" : "草稿"}
                  </span>
                </button>
              </li>
            ))}
            {!episodes.length && (
              <li className="px-2 py-6 text-center text-xs text-[var(--muted)]">尚未生成分集</li>
            )}
          </ul>
        </aside>

        <section className="panel flex min-h-[420px] flex-col p-4">
          {active ? (
            <>
              <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                <h3 className="display-type text-xl">
                  第 {active.episodeNumber} 集 · {active.title || "未命名"}
                </h3>
                <div className="flex gap-2">
                  <button type="button" className="btn-ghost !py-1.5 !text-xs" onClick={() => void saveEpisode()}>
                    保存编辑
                  </button>
                  {active.status === "confirmed" ? (
                    <button
                      type="button"
                      className="btn-ghost !py-1.5 !text-xs"
                      onClick={() => void setStatus([active.id], "draft")}
                    >
                      撤回定稿
                    </button>
                  ) : (
                    <button
                      type="button"
                      className="btn-primary !py-1.5 !text-xs"
                      onClick={() => void setStatus([active.id], "confirmed")}
                    >
                      定稿本集
                    </button>
                  )}
                </div>
              </div>
              <textarea
                className="field min-h-0 flex-1 font-[var(--font-body)] leading-relaxed"
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
              />
            </>
          ) : (
            <div className="flex flex-1 items-center justify-center text-sm text-[var(--muted)]">
              填写创作需求后生成剧本
            </div>
          )}
        </section>
      </div>

      <ConfirmDialog
        open={confirmBatch}
        title="批量定稿？"
        message={`将把 ${draftIds.length} 集草稿标记为定稿，之后可进入分镜拆镜。`}
        confirmLabel="全部定稿"
        onCancel={() => setConfirmBatch(false)}
        onConfirm={() => {
          setConfirmBatch(false);
          void setStatus(draftIds, "confirmed");
        }}
      />
    </div>
  );
}
