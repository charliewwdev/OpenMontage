import { useCallback, useEffect, useMemo, useState } from "react";
import { Clapperboard, Clock3, Loader2, Plus, Save, Sparkles, Trash2, Video } from "lucide-react";
import { api } from "../../api";
import { SEEDANCE_MODELS_FALLBACK } from "../../config/options";
import { requireCapability, toastMaybeKeys } from "../../lib/keys";
import { toast } from "../../lib/toast";
import { useTimer } from "../../lib/useTimer";
import { ConfirmDialog } from "../ConfirmDialog";

const SPLIT_STAGES = [
  { startsAt: 0, title: "正在核对剧本与创作素材", detail: "识别本集角色、空镜场景、道具与视觉风格。" },
  { startsAt: 25, title: "正在拆分剧情节拍与时长", detail: "按场景、对白、动作和情绪转折规划连续视频片段。" },
  { startsAt: 70, title: "正在规划镜头衔接与素材引用", detail: "匹配每个镜头出场的角色形象、场景和道具参考图。" },
  { startsAt: 130, title: "正在编写 Seedance 视频提示词", detail: "组织景别、运镜、动作、对白、声音和画面风格。" },
  { startsAt: 220, title: "正在检查完整性并组装结果", detail: "核对剧情覆盖、片段时长、素材引用和输出结构。" },
];

export function StoryboardStep({ projectId, bundle, config, setBusyMsg, onBundle, onRefresh, onNeedKeys }) {
  const caps = config?.capabilities || {};
  const confirmedEpisodes = useMemo(
    () =>
      [...(bundle?.episodes || [])]
        .filter((e) => e.status === "confirmed")
        .sort((a, b) => a.episodeNumber - b.episodeNumber),
    [bundle?.episodes],
  );
  const models = config?.seedanceModels?.length ? config.seedanceModels : SEEDANCE_MODELS_FALLBACK;
  const [episodeId, setEpisodeId] = useState(confirmedEpisodes[0]?.id || "");
  const [model, setModel] = useState(models[0]?.id || "");
  const selectedModel = models.find((m) => m.id === model) || models[0];
  const [resolution, setResolution] = useState(selectedModel?.resolutions?.[1] || selectedModel?.resolutions?.[0] || "720p");
  const [splitting, setSplitting] = useState(false);
  const [batching, setBatching] = useState(false);
  const [selectedShotIds, setSelectedShotIds] = useState(() => new Set());
  const [dirtyShotIds, setDirtyShotIds] = useState(() => new Set());
  const [confirmSplit, setConfirmSplit] = useState(false);
  const [confirmBatch, setConfirmBatch] = useState(false);
  const { elapsed: splitElapsed, formatted: splitElapsedTime } = useTimer(splitting);

  useEffect(() => {
    if (!confirmedEpisodes.some((e) => e.id === episodeId)) {
      setEpisodeId(confirmedEpisodes[0]?.id || "");
    }
  }, [confirmedEpisodes, episodeId]);

  useEffect(() => {
    const resolutions = selectedModel?.resolutions || ["720p"];
    if (!resolutions.includes(resolution)) setResolution(resolutions[0]);
  }, [selectedModel, resolution]);

  const episode = (bundle?.episodes || []).find((e) => e.id === episodeId);
  const shots = useMemo(
    () =>
      (bundle?.shots || [])
        .filter((s) => s.episodeId === episodeId && !s.deletedAt)
        .sort((a, b) => a.shotOrder - b.shotOrder),
    [bundle?.shots, episodeId],
  );
  const availableEntities = useMemo(
    () =>
      (bundle?.entities || []).filter(
        (entity) =>
          !entity.deletedAt &&
          entity.selectedImage &&
          (!episode || !entity.episodes?.length || entity.episodes.includes(episode.episodeNumber)),
      ),
    [bundle?.entities, episode],
  );
  const episodeHasGenerating = shots.some((s) => s.status === "generating");
  const workflowBusy = splitting || batching;
  const generatingIds = (bundle?.shots || [])
    .filter((s) => s.status === "generating" && !s.deletedAt)
    .map((s) => s.id)
    .join(",");
  const splitStageIndex = SPLIT_STAGES.reduce(
    (current, stage, index) => (splitElapsed >= stage.startsAt ? index : current),
    0,
  );
  const splitStage = SPLIT_STAGES[splitStageIndex];

  useEffect(() => {
    const currentIds = new Set(shots.map((s) => s.id));
    setSelectedShotIds((prev) => new Set([...prev].filter((id) => currentIds.has(id))));
    setDirtyShotIds((prev) => new Set([...prev].filter((id) => currentIds.has(id))));
  }, [shots]);

  const handleDirtyChange = useCallback((shotId, dirty) => {
    setDirtyShotIds((prev) => {
      const next = new Set(prev);
      if (dirty) next.add(shotId);
      else next.delete(shotId);
      return next;
    });
  }, []);

  const apply = (res) => {
    if (res?.bundle) onBundle?.(res.bundle);
    else onRefresh?.();
  };

  useEffect(() => {
    if (!generatingIds) return undefined;
    let cancelled = false;
    const poll = async () => {
      const ids = generatingIds.split(",").filter(Boolean);
      let changed = false;
      await Promise.all(
        ids.map(async (id) => {
          try {
            const shot = await api(
              `/api/projects/${encodeURIComponent(projectId)}/shots/${encodeURIComponent(id)}`,
            );
            if (shot.status !== "generating") changed = true;
          } catch {
            /* next poll */
          }
        }),
      );
      if (changed && !cancelled) await onRefresh?.();
    };
    void poll();
    const timer = setInterval(() => void poll(), 5000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [generatingIds, projectId, onRefresh]);

  const split = async () => {
    if (!episode) return;
    if (batching || episodeHasGenerating) {
      toast.info("请等待本集视频任务完成后再重新拆分");
      return;
    }
    if (shots.length && !confirmSplit) {
      setConfirmSplit(true);
      return;
    }
    if (!requireCapability(caps, "deepseek", onNeedKeys, "DeepSeek Key")) return;
    setConfirmSplit(false);
    setSplitting(true);
    setBusyMsg?.("AI 拆镜中…");
    try {
      const res = await api(`/api/projects/${encodeURIComponent(projectId)}/storyboard`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "generate", episodeId: episode.id }),
      });
      apply(res);
      toast.success(`DeepSeek 已拆分 ${res.shots?.length || 0} 个镜头`);
    } catch (error) {
      toastMaybeKeys(error, onNeedKeys);
    } finally {
      setSplitting(false);
      setBusyMsg?.("");
    }
  };

  const add = async () => {
    if (!episode) return;
    try {
      const res = await api(`/api/projects/${encodeURIComponent(projectId)}/storyboard`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "add", episodeId: episode.id }),
      });
      apply(res);
    } catch (error) {
      toast.error(String(error.message || error));
    }
  };

  const generateVideo = async (shotId, silent = false) => {
    if (!requireCapability(caps, "seedance", onNeedKeys, "火山 Seedance Key")) return;
    try {
      const res = await api(`/api/projects/${encodeURIComponent(projectId)}/storyboard`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "video", shotId, model, resolution }),
      });
      if (!silent) {
        apply(res);
        toast.success("Seedance 任务已提交");
      }
    } catch (error) {
      if (!silent) toastMaybeKeys(error, onNeedKeys);
      throw error;
    }
  };

  const batchGenerate = async () => {
    if (splitting) return toast.info("请等待分镜拆分完成后再提交视频任务");
    const selected = shots.filter((s) => selectedShotIds.has(s.id));
    if (!selected.length) return toast.info("请先勾选要批量生成的镜头");
    if (selected.some((s) => dirtyShotIds.has(s.id))) {
      return toast.error("选中的镜头有未保存修改，请先保存后再批量生成");
    }
    const pending = selected.filter((s) => s.status !== "generating" && (s.prompt || "").trim());
    if (!pending.length) return toast.info("选中的镜头没有可提交任务");
    if (!confirmBatch) {
      setConfirmBatch(true);
      return;
    }
    setConfirmBatch(false);
    setBatching(true);
    setBusyMsg?.(`批量提交 ${pending.length} 镜…`);
    try {
      let succeeded = 0;
      for (let index = 0; index < pending.length; index += 2) {
        const group = pending.slice(index, index + 2);
        const results = await Promise.allSettled(group.map((shot) => generateVideo(shot.id, true)));
        succeeded += results.filter((r) => r.status === "fulfilled").length;
      }
      await onRefresh?.();
      if (succeeded === pending.length) toast.success(`已提交 ${succeeded}/${pending.length} 个视频任务`);
      else toast.error(`批量提交完成：${succeeded} 成功，${pending.length - succeeded} 失败`);
    } catch (error) {
      toast.error(String(error.message || error));
    } finally {
      setBatching(false);
      setBusyMsg?.("");
    }
  };

  const ratio = bundle?.project?.ratio || "9:16";
  const resolutions = selectedModel?.resolutions || ["720p"];

  return (
    <div className="mx-auto max-w-[1500px] space-y-5">
      <section className="panel p-5 md:p-6">
        <div className="grid gap-5 min-[1500px]:grid-cols-[480px_minmax(0,1fr)] min-[1500px]:items-end">
          <div className="min-w-0">
            <div className="label">Shot planning & generation</div>
            <h3 className="display-type text-2xl font-semibold">分镜导演台</h3>
            <p className="mt-1 text-sm text-[var(--muted)]">
              DeepSeek 拆镜，Seedance 使用选定角色、场景和道具本地图片作为参考。
            </p>
          </div>
          <div className="grid min-w-0 gap-2 sm:grid-cols-2 md:grid-cols-3 min-[1500px]:grid-cols-[minmax(0,1.1fr)_minmax(0,1.3fr)_minmax(88px,.55fr)_auto_auto]">
            <label>
              <span className="label">已定稿分集</span>
              <select
                className="field"
                value={episodeId}
                disabled={workflowBusy}
                onChange={(e) => {
                  setEpisodeId(e.target.value);
                  setSelectedShotIds(new Set());
                }}
              >
                {!confirmedEpisodes.length && <option value="">无定稿分集</option>}
                {confirmedEpisodes.map((item) => (
                  <option key={item.id} value={item.id}>
                    第{item.episodeNumber}集 · {item.title || "未命名"}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span className="label">视频模型</span>
              <select className="field" value={model} disabled={workflowBusy} onChange={(e) => setModel(e.target.value)}>
                {models.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name || item.id}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span className="label">分辨率</span>
              <select
                className="field"
                value={resolution}
                disabled={workflowBusy}
                onChange={(e) => setResolution(e.target.value)}
              >
                {resolutions.map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
              </select>
            </label>
            <button
              type="button"
              className="btn-secondary self-end whitespace-nowrap"
              disabled={!episode || workflowBusy || episodeHasGenerating}
              onClick={() => void split()}
            >
              {splitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
              {splitting ? `拆分中 ${splitElapsedTime}` : shots.length ? "重新拆分" : "AI 拆分"}
            </button>
            <button
              type="button"
              className="btn-primary self-end whitespace-nowrap md:col-span-2 min-[1500px]:col-span-1"
              disabled={!selectedShotIds.size || workflowBusy}
              onClick={() => void batchGenerate()}
            >
              {batching ? <Loader2 className="h-4 w-4 animate-spin" /> : <Video className="h-4 w-4" />}
              批量生成{selectedShotIds.size ? ` (${selectedShotIds.size})` : ""}
            </button>
          </div>
        </div>
        {splitting ? (
          <div className="mt-5 rounded-xl border border-[var(--projector)]/30 bg-[var(--projector)]/[.08] p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="flex min-w-0 items-start gap-3" role="status">
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-[var(--projector)]/15">
                  <Loader2 className="h-4 w-4 animate-spin text-[var(--projector)]" />
                </span>
                <div className="min-w-0">
                  <div className="timecode text-[10px] text-[var(--muted)]">
                    AI 分镜导演 · 阶段 {splitStageIndex + 1}/{SPLIT_STAGES.length}
                  </div>
                  <strong className="mt-1 block text-sm">{splitStage.title}</strong>
                  <p className="mt-1 text-xs leading-5 text-[var(--muted)]">
                    {splitStage.detail} 剧本越长，等待时间越久，完成后会自动载入结果。
                  </p>
                </div>
              </div>
              <span className="timecode flex shrink-0 items-center gap-1.5 rounded-lg border border-[var(--line)] bg-black/40 px-3 py-2 text-xs text-[var(--ink)]">
                <Clock3 className="h-3.5 w-3.5 text-[var(--projector)]" />
                已用时 {splitElapsedTime}
              </span>
            </div>
            <div className="mt-4 grid grid-cols-5 gap-1.5" aria-hidden="true">
              {SPLIT_STAGES.map((stage, index) => (
                <span
                  key={stage.title}
                  className={`h-1.5 rounded-full ${index <= splitStageIndex ? "bg-[var(--projector)]" : "bg-[var(--line)]"}`}
                />
              ))}
            </div>
          </div>
        ) : null}
      </section>

      {!episode ? (
        <div className="panel py-24 text-center text-sm text-[var(--muted)]">请先在剧本步骤创建并定稿分集。</div>
      ) : shots.length === 0 ? (
        <div className="panel flex flex-col items-center border-dashed py-24 text-center">
          <Clapperboard className="mb-4 h-10 w-10 text-[var(--projector)]" />
          <strong className="text-lg">本集还没有分镜</strong>
          <p className="mt-2 text-sm text-[var(--muted)]">确认剧本和素材后，让 DeepSeek 拆成可生成的视频镜头。</p>
          <button type="button" className="btn-primary mt-5" disabled={workflowBusy} onClick={() => void split()}>
            {splitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
            {splitting ? `拆分中 · ${splitElapsedTime}` : "AI 拆分本集"}
          </button>
        </div>
      ) : (
        <div className="space-y-4">
          <div className="panel-muted flex flex-wrap items-center justify-between gap-3 px-4 py-3 text-xs text-[var(--muted)]">
            <span>勾选需要一起提交的镜头；有未保存修改时会阻止批量生成。</span>
            <button
              type="button"
              className="btn-secondary !min-h-8 !py-1.5"
              disabled={workflowBusy}
              onClick={() =>
                setSelectedShotIds((current) =>
                  current.size === shots.length ? new Set() : new Set(shots.map((s) => s.id)),
                )
              }
            >
              {selectedShotIds.size === shots.length ? "清空选择" : "全选本集"}
            </button>
          </div>
          {shots.map((shot) => (
            <ShotCard
              key={`${shot.id}-${shot.updatedAt}`}
              projectId={projectId}
              shot={shot}
              entities={availableEntities}
              models={models}
              ratio={ratio}
              selected={selectedShotIds.has(shot.id)}
              locked={workflowBusy}
              onToggleSelected={() =>
                setSelectedShotIds((current) => {
                  const next = new Set(current);
                  if (next.has(shot.id)) next.delete(shot.id);
                  else next.add(shot.id);
                  return next;
                })
              }
              onDirtyChange={handleDirtyChange}
              onBundle={onBundle}
              onRefresh={onRefresh}
              onGenerate={generateVideo}
            />
          ))}
          <button
            type="button"
            className="panel flex w-full items-center justify-center border-dashed py-5 text-sm font-semibold text-[var(--muted)] hover:border-[var(--projector)] hover:text-[var(--ink)]"
            disabled={workflowBusy}
            onClick={() => void add()}
          >
            <Plus className="mr-2 h-4 w-4" /> 手动追加镜头
          </button>
        </div>
      )}

      <ConfirmDialog
        open={confirmSplit}
        title="重新拆分本集分镜？"
        message="本集现有镜头、视频版本记录和剪辑草稿将被替换；本地视频与已导出文件仍会保留。"
        confirmLabel="重新拆分"
        onCancel={() => setConfirmSplit(false)}
        onConfirm={() => void split()}
      />
      <ConfirmDialog
        open={confirmBatch}
        title={`提交 ${selectedShotIds.size} 个视频任务？`}
        message="Seedance 任务将按每组 2 个控制并发，提交后可在分镜列表查看进度。"
        confirmLabel="确认提交"
        onCancel={() => setConfirmBatch(false)}
        onConfirm={() => void batchGenerate()}
      />
    </div>
  );
}

function ShotCard({
  projectId,
  shot,
  entities,
  models,
  ratio,
  selected,
  locked,
  onToggleSelected,
  onDirtyChange,
  onBundle,
  onRefresh,
  onGenerate,
}) {
  const [prompt, setPrompt] = useState(shot.prompt || "");
  const [duration, setDuration] = useState(shot.duration || 5);
  const [referenceIds, setReferenceIds] = useState(shot.referenceEntityIds || []);
  const [saving, setSaving] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const dirty =
    prompt !== (shot.prompt || "") ||
    duration !== (shot.duration || 5) ||
    JSON.stringify(referenceIds) !== JSON.stringify(shot.referenceEntityIds || []);
  const editLocked = locked || shot.status === "generating";

  useEffect(() => {
    onDirtyChange(shot.id, dirty);
    return () => onDirtyChange(shot.id, false);
  }, [dirty, onDirtyChange, shot.id]);

  const apply = (res) => {
    if (res?.bundle) onBundle?.(res.bundle);
    else onRefresh?.();
  };

  const save = async (quiet = false) => {
    setSaving(true);
    try {
      const res = await api(`/api/projects/${encodeURIComponent(projectId)}/storyboard`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "patch",
          shotId: shot.id,
          patch: { prompt, duration, referenceEntityIds: referenceIds },
        }),
      });
      apply(res);
      if (!quiet) toast.success(`镜头 ${shot.shotOrder} 已保存`);
    } catch (error) {
      toast.error(String(error.message || error));
      throw error;
    } finally {
      setSaving(false);
    }
  };

  const generate = async () => {
    setGenerating(true);
    try {
      if (dirty) await save(true);
      await onGenerate(shot.id);
      await onRefresh?.();
    } finally {
      setGenerating(false);
    }
  };

  const remove = async () => {
    if (!confirmDelete) {
      setConfirmDelete(true);
      return;
    }
    setConfirmDelete(false);
    try {
      const res = await api(`/api/projects/${encodeURIComponent(projectId)}/storyboard`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "delete", shotId: shot.id }),
      });
      apply(res);
    } catch (error) {
      toast.error(String(error.message || error));
    }
  };

  const selectVideo = async (videoId) => {
    try {
      const res = await api(`/api/projects/${encodeURIComponent(projectId)}/storyboard`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "select-take", shotId: shot.id, videoId }),
      });
      apply(res);
    } catch (error) {
      toast.error(String(error.message || error));
    }
  };

  const updateVideo = async (videoId, fields) => {
    try {
      const res = await api(`/api/projects/${encodeURIComponent(projectId)}/storyboard`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "patch-take", shotId: shot.id, videoId, ...fields }),
      });
      apply(res);
    } catch (error) {
      toast.error(String(error.message || error));
    }
  };

  const statusStyle =
    shot.status === "success"
      ? "bg-emerald-100 text-emerald-700"
      : shot.status === "generating"
        ? "bg-blue-100 text-blue-700"
        : shot.status === "failed"
          ? "bg-red-100 text-red-700"
          : "bg-slate-100 text-slate-600";
  const completeVideos = (shot.videos || []).filter((v) => v.path || v.url);
  const activeVideo = shot.selectedVideo?.url ? shot.selectedVideo : completeVideos[0] || null;

  return (
    <>
      <article className="panel overflow-hidden">
        <div className="grid xl:grid-cols-[minmax(0,1fr)_360px]">
          <div className="p-5">
            <div className="flex flex-wrap items-center gap-3">
              <label className="flex cursor-pointer items-center gap-2 text-xs font-semibold">
                <input type="checkbox" checked={selected} disabled={locked} onChange={onToggleSelected} /> 批量选择
              </label>
              <span className="timecode rounded-md bg-[var(--navy)] px-2.5 py-1 text-xs text-white">
                SHOT {String(shot.shotOrder).padStart(2, "0")}
              </span>
              <span className={`rounded-full px-2.5 py-1 text-[10px] font-bold ${statusStyle}`}>
                {shot.status === "success"
                  ? "已完成"
                  : shot.status === "generating"
                    ? "生成中"
                    : shot.status === "failed"
                      ? "失败"
                      : "待生成"}
              </span>
              <label className="ml-auto flex items-center gap-2 text-xs text-[var(--muted)]">
                时长
                <input
                  type="number"
                  min={4}
                  max={15}
                  className="field !w-20 !py-1.5"
                  value={duration}
                  disabled={editLocked}
                  onChange={(e) => setDuration(Math.max(4, Math.min(15, Number(e.target.value) || 4)))}
                />
                秒
              </label>
            </div>
            <label className="mt-4 block">
              <span className="label">Seedance 提示词</span>
              <textarea
                className="field min-h-56 resize-y leading-6 md:min-h-72"
                value={prompt}
                disabled={editLocked}
                onChange={(e) => setPrompt(e.target.value)}
                placeholder="主体、动作、台词、景别、运镜、光线与声音…"
              />
            </label>
            <div className="mt-4">
              <div className="label">参考素材 · 最多 9 张</div>
              <div className="flex flex-wrap gap-2">
                {entities.map((entity) => {
                  const on = referenceIds.includes(entity.id);
                  return (
                    <button
                      key={entity.id}
                      type="button"
                      disabled={editLocked}
                      onClick={() =>
                        setReferenceIds((current) =>
                          on
                            ? current.filter((id) => id !== entity.id)
                            : current.length < 9
                              ? [...current, entity.id]
                              : current,
                        )
                      }
                      className={`flex items-center gap-2 rounded-lg border px-2 py-1.5 text-xs ${
                        on ? "border-[var(--projector)] bg-[var(--projector)]/10" : "border-[var(--line)] bg-white/[.03]"
                      }`}
                    >
                      <img src={entity.selectedImage.url} alt="" className="h-7 w-7 rounded object-cover" />
                      <span>
                        {entity.name}
                        {entity.variant ? ` / ${entity.variant}` : ""}
                      </span>
                    </button>
                  );
                })}
                {!entities.length ? (
                  <span className="text-xs text-[var(--muted)]">本集暂无已定稿图片，仍可纯文本生成。</span>
                ) : null}
              </div>
            </div>
            {shot.error ? (
              <p className="mt-3 rounded-lg bg-[var(--danger)]/10 px-3 py-2 text-xs text-[var(--danger)]">{shot.error}</p>
            ) : null}
            <div className="mt-5 flex flex-wrap gap-2">
              <button
                type="button"
                className="btn-secondary"
                disabled={locked || !dirty || saving || shot.status === "generating"}
                onClick={() => void save()}
              >
                {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />} 保存镜头
              </button>
              <button
                type="button"
                className="btn-primary"
                disabled={locked || generating || shot.status === "generating" || !prompt.trim()}
                onClick={() => void generate()}
              >
                {generating || shot.status === "generating" ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Video className="h-4 w-4" />
                )}
                {shot.selectedVideo ? "再生成一个版本" : "生成分镜视频"}
              </button>
              <button
                type="button"
                className="btn-danger ml-auto"
                disabled={locked || shot.status === "generating"}
                onClick={() => void remove()}
              >
                <Trash2 className="h-4 w-4" /> 删除
              </button>
            </div>
          </div>
          <div className="border-t border-[var(--line)] bg-[var(--navy)] p-4 text-white xl:border-l xl:border-t-0">
            <div className="timecode mb-3 flex items-center justify-between text-[10px] text-white/45">
              <span>VIDEO TAKE · {ratio}</span>
              <span>{completeVideos.length} VERSIONS</span>
            </div>
            <div
              className={`flex items-center justify-center overflow-hidden rounded-xl bg-black/45 ${
                ratio === "9:16" ? "mx-auto aspect-[9/16] w-full max-w-[20rem]" : "aspect-video w-full"
              }`}
            >
              {activeVideo?.url ? (
                <video
                  key={activeVideo.url}
                  src={activeVideo.url}
                  controls
                  preload="metadata"
                  className="h-full w-full object-contain"
                />
              ) : shot.status === "generating" ? (
                <div className="text-center text-xs text-white/60">
                  <Loader2 className="mx-auto mb-2 h-6 w-6 animate-spin text-[var(--projector)]" />
                  Seedance 正在制作
                </div>
              ) : (
                <Video className="h-10 w-10 text-white/15" />
              )}
            </div>
            {completeVideos.length > 0 ? (
              <div className="mt-3 flex gap-2 overflow-x-auto">
                {completeVideos.map((video, index) => (
                  <button
                    key={video.id}
                    type="button"
                    disabled={editLocked}
                    onClick={() => void selectVideo(video.id)}
                    className={`timecode rounded-lg border px-3 py-2 text-[10px] ${
                      video.id === activeVideo?.id
                        ? "border-[var(--projector)] bg-[var(--projector)]/10 text-[var(--projector)]"
                        : "border-white/10 text-white/50"
                    }`}
                  >
                    TAKE {String(index + 1).padStart(2, "0")}
                  </button>
                ))}
              </div>
            ) : null}
            {activeVideo ? (
              <div className="mt-3 space-y-3 rounded-xl border border-white/10 bg-white/[.04] p-3 text-xs text-white/65">
                <div>
                  <strong className="block text-white">
                    {models.find((m) => m.id === activeVideo.model)?.name || activeVideo.model || "Seedance"}
                  </strong>
                  <span>
                    {activeVideo.resolution || "—"} ·{" "}
                    {Number(activeVideo.duration || shot.duration || 0).toFixed(1)} 秒
                  </span>
                </div>
                <div className="flex items-center gap-1" aria-label="视频版本评分">
                  {[1, 2, 3, 4, 5].map((star) => (
                    <button
                      key={star}
                      type="button"
                      disabled={editLocked}
                      className={`text-base ${(activeVideo.rating ?? 0) >= star ? "text-amber-300" : "text-white/20"} hover:text-amber-200`}
                      onClick={() =>
                        void updateVideo(activeVideo.id, {
                          rating: activeVideo.rating === star ? null : star,
                        })
                      }
                      aria-label={`${star} 星`}
                    >
                      ★
                    </button>
                  ))}
                </div>
                <input
                  className="w-full rounded-md border border-white/10 bg-black/20 px-2 py-1.5 text-xs text-white placeholder:text-white/30 focus:border-[var(--projector)] focus:outline-none"
                  defaultValue={activeVideo.note || ""}
                  disabled={editLocked}
                  maxLength={200}
                  placeholder="给这个版本添加备注…"
                  onBlur={(event) => {
                    const note = event.target.value.trim();
                    if (note !== (activeVideo.note || "")) void updateVideo(activeVideo.id, { note });
                  }}
                />
              </div>
            ) : null}
          </div>
        </div>
      </article>
      <ConfirmDialog
        open={confirmDelete}
        title={`删除镜头 ${shot.shotOrder}？`}
        message="该镜头及其视频版本记录将被删除；本地视频文件仍会保留。"
        confirmLabel="删除镜头"
        danger
        onCancel={() => setConfirmDelete(false)}
        onConfirm={() => void remove()}
      />
    </>
  );
}
