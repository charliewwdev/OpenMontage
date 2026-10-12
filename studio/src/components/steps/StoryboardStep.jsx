import { useEffect, useMemo, useState } from "react";
import { api } from "../../api";
import { SEEDANCE_MODELS_FALLBACK } from "../../config/options";
import { Lightbox } from "../Lightbox";

export function StoryboardStep({ projectId, bundle, config, setBusyMsg, onBundle, onRefresh }) {
  const episodes = useMemo(
    () =>
      [...(bundle?.episodes || [])]
        .filter((e) => e.status === "confirmed")
        .sort((a, b) => a.episodeNumber - b.episodeNumber),
    [bundle?.episodes],
  );
  const entities = (bundle?.entities || []).filter((e) => !e.deletedAt && e.selectedImageId);
  const models = config?.seedanceModels?.length ? config.seedanceModels : SEEDANCE_MODELS_FALLBACK;

  const [episodeId, setEpisodeId] = useState(episodes[0]?.id || "");
  const [model, setModel] = useState(models[0]?.id || "");
  const [resolution, setResolution] = useState(models[0]?.resolutions?.[1] || models[0]?.resolutions?.[0] || "720p");
  const [activeShotId, setActiveShotId] = useState("");
  const [lightbox, setLightbox] = useState(null);
  const [pollIds, setPollIds] = useState([]);

  useEffect(() => {
    if (!episodeId && episodes[0]) setEpisodeId(episodes[0].id);
  }, [episodes, episodeId]);

  const shots = useMemo(
    () =>
      (bundle?.shots || [])
        .filter((s) => s.episodeId === episodeId && !s.deletedAt)
        .sort((a, b) => a.shotOrder - b.shotOrder),
    [bundle?.shots, episodeId],
  );

  const active = shots.find((s) => s.id === activeShotId) || shots[0];

  useEffect(() => {
    if (active) setActiveShotId(active.id);
  }, [active?.id]);

  const modelMeta = models.find((m) => m.id === model) || models[0];
  const resolutions = modelMeta?.resolutions || ["720p"];

  useEffect(() => {
    if (!resolutions.includes(resolution)) setResolution(resolutions[0]);
  }, [model, resolutions, resolution]);

  // poll generating shots
  useEffect(() => {
    if (!pollIds.length) return undefined;
    const timer = setInterval(async () => {
      let changed = false;
      const still = [];
      for (const sid of pollIds) {
        try {
          const shot = await api(
            `/api/projects/${encodeURIComponent(projectId)}/shots/${encodeURIComponent(sid)}`,
          );
          if (shot.status === "generating" || shot.status === "pending") still.push(sid);
          else changed = true;
        } catch {
          /* ignore */
        }
      }
      setPollIds(still);
      if (changed || still.length !== pollIds.length) onRefresh?.();
    }, 2500);
    return () => clearInterval(timer);
  }, [pollIds, projectId, onRefresh]);

  const apply = (res) => {
    if (res?.bundle) onBundle?.(res.bundle);
    else onRefresh?.();
  };

  const generateBoard = async () => {
    if (!episodeId) {
      window.alert("请先定稿至少一集剧本");
      return;
    }
    setBusyMsg("拆镜中（DeepSeek）…");
    const t0 = performance.now();
    try {
      const res = await api(`/api/projects/${encodeURIComponent(projectId)}/storyboard`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "generate", episodeId }),
      });
      apply(res);
      setBusyMsg(`拆镜完成（${((performance.now() - t0) / 1000).toFixed(1)}s）`);
      setTimeout(() => setBusyMsg(""), 1500);
    } catch (e) {
      setBusyMsg("");
      window.alert(String(e.message || e));
    }
  };

  const patchShot = async (patch) => {
    if (!active) return;
    setBusyMsg("保存镜头…");
    try {
      const res = await api(`/api/projects/${encodeURIComponent(projectId)}/storyboard`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "patch", shotId: active.id, patch }),
      });
      apply(res);
    } catch (e) {
      window.alert(String(e.message || e));
    } finally {
      setBusyMsg("");
    }
  };

  const genVideo = async (shotId) => {
    setBusyMsg("提交 Seedance…");
    try {
      const res = await api(`/api/projects/${encodeURIComponent(projectId)}/storyboard`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "video", shotId, model, resolution }),
      });
      apply(res);
      setPollIds((ids) => (ids.includes(shotId) ? ids : [...ids, shotId]));
    } catch (e) {
      window.alert(String(e.message || e));
    } finally {
      setBusyMsg("");
    }
  };

  const batchVideo = async () => {
    const ids = shots.filter((s) => s.status !== "success" && s.status !== "generating").map((s) => s.id);
    if (!ids.length) {
      window.alert("没有待生成镜头");
      return;
    }
    setBusyMsg(`批量提交 ${ids.length} 镜…`);
    try {
      const res = await api(`/api/projects/${encodeURIComponent(projectId)}/storyboard`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "batch-video", shotIds: ids, model, resolution }),
      });
      apply(res);
      setPollIds((prev) => [...new Set([...prev, ...ids])]);
    } catch (e) {
      window.alert(String(e.message || e));
    } finally {
      setBusyMsg("");
    }
  };

  const selectTake = async (videoId) => {
    setBusyMsg("选用 TAKE…");
    try {
      const res = await api(`/api/projects/${encodeURIComponent(projectId)}/storyboard`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "select-take", shotId: active.id, videoId }),
      });
      apply(res);
    } catch (e) {
      window.alert(String(e.message || e));
    } finally {
      setBusyMsg("");
    }
  };

  const patchTake = async (videoId, patch) => {
    try {
      const res = await api(`/api/projects/${encodeURIComponent(projectId)}/storyboard`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "patch-take", shotId: active.id, videoId, ...patch }),
      });
      apply(res);
    } catch (e) {
      window.alert(String(e.message || e));
    }
  };

  const toggleRef = (entityId) => {
    if (!active) return;
    const cur = active.referenceEntityIds || [];
    let next;
    if (cur.includes(entityId)) next = cur.filter((id) => id !== entityId);
    else if (cur.length >= 9) {
      window.alert("最多绑定 9 张参考图");
      return;
    } else next = [...cur, entityId];
    void patchShot({ referenceEntityIds: next });
  };

  const refEntities = entities.filter((e) => (active?.referenceEntityIds || []).includes(e.id));

  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="display-type text-3xl">分镜导演台</h2>
          <p className="mt-1 text-sm text-[var(--muted)]">定稿拆镜 · 最多 9 张参考 · Seedance · 多 TAKE</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <select className="field !w-auto !py-1.5" value={episodeId} onChange={(e) => setEpisodeId(e.target.value)}>
            {!episodes.length && <option value="">无定稿分集</option>}
            {episodes.map((ep) => (
              <option key={ep.id} value={ep.id}>
                EP{ep.episodeNumber} {ep.title || ""}
              </option>
            ))}
          </select>
          <button type="button" className="btn-primary" disabled={!episodeId} onClick={() => void generateBoard()}>
            拆镜
          </button>
          <button type="button" className="btn-ghost" disabled={!shots.length} onClick={() => void batchVideo()}>
            批量生成视频
          </button>
        </div>
      </header>

      <section className="panel flex flex-wrap items-end gap-3 p-3">
        <label className="text-xs text-[var(--muted)]">
          Seedance 模型
          <select className="field mt-1" value={model} onChange={(e) => setModel(e.target.value)}>
            {models.map((m) => (
              <option key={m.id} value={m.id}>
                {m.name || m.id}
              </option>
            ))}
          </select>
        </label>
        <label className="text-xs text-[var(--muted)]">
          分辨率
          <select className="field mt-1" value={resolution} onChange={(e) => setResolution(e.target.value)}>
            {resolutions.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>
        </label>
        <span className="text-xs text-[var(--muted)]">镜头数 {shots.length}</span>
      </section>

      <div className="grid gap-4 lg:grid-cols-[220px_1fr]">
        <aside className="panel max-h-[70vh] overflow-auto p-2">
          {shots.map((s) => (
            <button
              key={s.id}
              type="button"
              className={`mb-1 w-full rounded-lg px-2 py-2 text-left text-sm ${
                active?.id === s.id ? "bg-[var(--panel-muted)]" : "hover:bg-[var(--panel-muted)]"
              }`}
              onClick={() => setActiveShotId(s.id)}
            >
              <div className="flex justify-between">
                <span className="timecode text-[11px]">SHOT {String(s.shotOrder).padStart(2, "0")}</span>
                <span className="text-[10px] text-[var(--muted)]">{s.status || "pending"}</span>
              </div>
              <p className="mt-0.5 line-clamp-2 text-xs text-[var(--muted)]">{s.prompt || "无提示词"}</p>
            </button>
          ))}
          {!shots.length && (
            <p className="px-2 py-8 text-center text-xs text-[var(--muted)]">选择定稿分集后拆镜</p>
          )}
        </aside>

        <section className="panel space-y-4 p-4">
          {active ? (
            <>
              <label className="block text-xs text-[var(--muted)]">
                专业镜头提示词
                <textarea
                  className="field mt-1 min-h-[120px]"
                  defaultValue={active.prompt || ""}
                  key={active.id + "-prompt"}
                  onBlur={(e) => {
                    if (e.target.value !== active.prompt) void patchShot({ prompt: e.target.value });
                  }}
                />
              </label>
              <label className="inline-flex items-center gap-2 text-xs text-[var(--muted)]">
                时长(秒)
                <input
                  type="number"
                  min={2}
                  max={15}
                  className="field !w-20"
                  defaultValue={active.duration || 5}
                  key={active.id + "-dur"}
                  onBlur={(e) => {
                    const d = Number(e.target.value) || 5;
                    if (d !== active.duration) void patchShot({ duration: d });
                  }}
                />
              </label>

              <div>
                <p className="mb-2 text-xs text-[var(--muted)]">
                  参考图绑定 ({(active.referenceEntityIds || []).length}/9)
                </p>
                <div className="flex flex-wrap gap-2">
                  {entities.map((ent) => {
                    const on = (active.referenceEntityIds || []).includes(ent.id);
                    return (
                      <button
                        key={ent.id}
                        type="button"
                        className={`h-14 w-14 overflow-hidden rounded-lg border-2 ${
                          on ? "border-[var(--projector)]" : "border-[var(--line)] opacity-70"
                        }`}
                        title={ent.name}
                        onClick={() => toggleRef(ent.id)}
                      >
                        <img src={ent.selectedImage?.url} alt={ent.name} className="h-full w-full object-cover" />
                      </button>
                    );
                  })}
                  {!entities.length && <span className="text-xs text-[var(--muted)]">请先在资产台出图</span>}
                </div>
                {refEntities.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-2">
                    {refEntities.map((e) => (
                      <button
                        key={e.id}
                        type="button"
                        className="text-[11px] text-[var(--run)] underline"
                        onClick={() => setLightbox(e.selectedImage?.url)}
                      >
                        预览 {e.name}
                      </button>
                    ))}
                  </div>
                )}
              </div>

              <div className="flex flex-wrap gap-2">
                <button type="button" className="btn-primary" onClick={() => void genVideo(active.id)}>
                  生成本镜视频
                </button>
              </div>

              {active.selectedVideo?.url || active.videos?.some((v) => v.url) ? (
                <video
                  key={active.selectedVideo?.id || active.id}
                  className="max-h-[360px] w-full rounded-xl bg-black"
                  controls
                  src={active.selectedVideo?.url || active.videos?.find((v) => v.url)?.url}
                />
              ) : (
                <div className="flex h-48 items-center justify-center rounded-xl bg-[var(--panel-muted)] text-sm text-[var(--muted)]">
                  {active.status === "generating" ? "生成中…" : "尚无视频 TAKE"}
                </div>
              )}

              <div>
                <p className="mb-2 text-xs text-[var(--muted)]">TAKE 列表</p>
                <div className="space-y-2">
                  {(active.videos || []).map((v, i) => (
                    <div
                      key={v.id}
                      className={`flex flex-wrap items-center gap-3 rounded-xl border p-3 ${
                        v.id === active.selectedVideoId ? "border-[var(--projector)]" : "border-[var(--line)]"
                      }`}
                    >
                      <span className="timecode text-xs">TAKE {i + 1}</span>
                      <span className="text-[11px] text-[var(--muted)]">{v.status || "—"}</span>
                      <label className="text-[11px] text-[var(--muted)]">
                        评分
                        <input
                          type="number"
                          min={0}
                          max={5}
                          className="field ml-1 !w-14 !py-0.5"
                          defaultValue={v.rating ?? ""}
                          onBlur={(e) => void patchTake(v.id, { rating: Number(e.target.value) || 0 })}
                        />
                      </label>
                      <input
                        className="field !max-w-xs flex-1 !py-1 text-xs"
                        placeholder="备注"
                        defaultValue={v.note || ""}
                        onBlur={(e) => {
                          if (e.target.value !== (v.note || "")) void patchTake(v.id, { note: e.target.value });
                        }}
                      />
                      <button type="button" className="btn-ghost !py-1 !text-xs" onClick={() => void selectTake(v.id)}>
                        选用进剪辑
                      </button>
                    </div>
                  ))}
                  {!active.videos?.length && <p className="text-xs text-[var(--muted)]">暂无 TAKE</p>}
                </div>
              </div>
            </>
          ) : (
            <p className="py-16 text-center text-sm text-[var(--muted)]">定稿分集后点击「拆镜」</p>
          )}
        </section>
      </div>

      <Lightbox src={lightbox} onClose={() => setLightbox(null)} />
    </div>
  );
}
