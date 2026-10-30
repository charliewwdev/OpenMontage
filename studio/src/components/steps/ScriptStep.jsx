import { useEffect, useMemo, useState } from "react";
import {
  Check,
  ChevronDown,
  ChevronUp,
  Clock3,
  Copy,
  FilePenLine,
  Forward,
  Loader2,
  Save,
  Sparkles,
  Trash2,
  X,
} from "lucide-react";
import { api } from "../../api";
import { requireCapability, toastMaybeKeys } from "../../lib/keys";
import { toast } from "../../lib/toast";
import { useTimer } from "../../lib/useTimer";
import { ConfirmDialog } from "../ConfirmDialog";
import { ModalOverlay } from "../ModalPortal";
import { AspectRatioPicker } from "../project-settings/AspectRatioPicker";
import { GenrePicker } from "../project-settings/GenrePicker";
import { VideoStylePicker } from "../project-settings/VideoStylePicker";

const MAX_PER_REQUEST = 10;

function parseCount(value, max = MAX_PER_REQUEST) {
  const count = Number(value);
  return Number.isInteger(count) && count >= 1 && count <= max ? count : null;
}

export function ScriptStep({
  projectId,
  bundle,
  config,
  setBusyMsg,
  onBundle,
  onRefresh,
  onNeedKeys,
  onRequireAuth,
  readOnly = false,
  focusEpisodeId,
  onFocusEpisode,
}) {
  const project = bundle?.project || {};
  const caps = config?.capabilities || {};
  const episodes = useMemo(
    () => [...(bundle?.episodes || [])].sort((a, b) => a.episodeNumber - b.episodeNumber),
    [bundle?.episodes],
  );

  const [form, setForm] = useState({
    title: project.title || "",
    brief: project.brief || "",
    synopsis: project.synopsis || "",
    genre: project.genre || "",
    visualStyle: project.visualStyle || "",
    ratio: project.ratio || "9:16",
  });
  const [generationEpisodeCount, setGenerationEpisodeCount] = useState(() => {
    const planned = Number(project.plannedEpisodes);
    if (Number.isInteger(planned) && planned >= 1) return Math.min(planned, MAX_PER_REQUEST);
    return 1;
  });
  const [plannedEpisodes, setPlannedEpisodes] = useState(project.plannedEpisodes ?? "");
  const [saving, setSaving] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [continuing, setContinuing] = useState(false);
  const [rewriting, setRewriting] = useState(false);
  const [batchConfirming, setBatchConfirming] = useState(false);
  const [briefCollapsed, setBriefCollapsed] = useState(() => {
    try {
      const raw = sessionStorage.getItem(`om-script-brief-collapsed:${projectId}`);
      if (raw === "1") return true;
      if (raw === "0") return false;
    } catch {
      /* ignore */
    }
    // Already have episodes → collapse public brief so the editor gets space.
    return (bundle?.episodes || []).length > 0;
  });
  const [selectedId, setSelectedId] = useState(focusEpisodeId || episodes[0]?.id || null);
  const [confirmRegen, setConfirmRegen] = useState(false);
  const [confirmBatch, setConfirmBatch] = useState(false);
  const [showContinue, setShowContinue] = useState(false);
  const [showRewrite, setShowRewrite] = useState(false);
  const [continueEpisodeCount, setContinueEpisodeCount] = useState(1);
  const [continueInstruction, setContinueInstruction] = useState("");
  const [continueBrief, setContinueBrief] = useState("");
  const [continueAsFinale, setContinueAsFinale] = useState(false);
  const [rewriteStartEpisode, setRewriteStartEpisode] = useState(1);
  const [rewriteEpisodeCount, setRewriteEpisodeCount] = useState(1);
  const [rewriteInstruction, setRewriteInstruction] = useState("");

  const operationBusy = saving || generating || continuing || rewriting || batchConfirming;
  const creativeBusy = generating || continuing || rewriting;
  const { formatted: elapsedTime } = useTimer(creativeBusy);
  const creativeStatus = generating
    ? "正在创作剧本与整理素材档案"
    : continuing
      ? "正在续写后续分集"
      : rewriting
        ? "正在重写指定分集"
        : "";

  useEffect(() => {
    setForm({
      title: project.title || "",
      brief: project.brief || "",
      synopsis: project.synopsis || "",
      genre: project.genre || "",
      visualStyle: project.visualStyle || "",
      ratio: project.ratio || "9:16",
    });
    setPlannedEpisodes(project.plannedEpisodes ?? "");
    const planned = Number(project.plannedEpisodes);
    if (Number.isInteger(planned) && planned >= 1) {
      setGenerationEpisodeCount((current) => {
        const n = Number(current);
        if (!Number.isInteger(n) || n < 1) return Math.min(planned, MAX_PER_REQUEST);
        return Math.min(n, planned, MAX_PER_REQUEST);
      });
    }
  }, [project.title, project.brief, project.synopsis, project.genre, project.visualStyle, project.ratio, project.plannedEpisodes]);

  useEffect(() => {
    if (focusEpisodeId && focusEpisodeId !== selectedId) {
      setSelectedId(focusEpisodeId);
    }
  }, [focusEpisodeId]); // eslint-disable-line react-hooks/exhaustive-deps -- sync from shell focus only

  useEffect(() => {
    if (selectedId && !episodes.some((e) => e.id === selectedId)) {
      const next = episodes[0]?.id || null;
      setSelectedId(next);
      if (next) onFocusEpisode?.(next);
    } else if (!selectedId && episodes[0]) {
      setSelectedId(episodes[0].id);
      onFocusEpisode?.(episodes[0].id);
    }
  }, [episodes, selectedId, onFocusEpisode]);

  useEffect(() => {
    try {
      sessionStorage.setItem(`om-script-brief-collapsed:${projectId}`, briefCollapsed ? "1" : "0");
    } catch {
      /* ignore */
    }
  }, [briefCollapsed, projectId]);

  const selected = useMemo(() => episodes.find((e) => e.id === selectedId) || null, [episodes, selectedId]);
  const maxEpisodeNumber = useMemo(() => Math.max(0, ...episodes.map((e) => e.episodeNumber)), [episodes]);
  const draftEpisodes = useMemo(() => episodes.filter((e) => e.status !== "confirmed"), [episodes]);
  const maxRewriteCount = Math.max(1, Math.min(MAX_PER_REQUEST, maxEpisodeNumber - rewriteStartEpisode + 1));

  const apply = (b) => {
    if (b?.project) onBundle?.(b);
    else onRefresh?.();
  };

  const saveProject = async (quiet = false) => {
    if (!form.genre.trim()) {
      toast.error("请选择题材或填写自定义题材");
      return false;
    }
    setSaving(true);
    setBusyMsg?.(quiet ? "" : "保存设定…");
    try {
      const planned =
        plannedEpisodes === "" || plannedEpisodes === null
          ? null
          : Number(plannedEpisodes);
      const b = await api(`/api/projects/${encodeURIComponent(projectId)}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: form.title,
          brief: form.brief,
          synopsis: form.synopsis,
          genre: form.genre,
          visualStyle: form.visualStyle,
          ratio: form.ratio,
          plannedEpisodes: Number.isFinite(planned) ? planned : null,
        }),
      });
      apply(b);
      if (!quiet) toast.success("项目设定已保存");
      return true;
    } catch (e) {
      toast.error(String(e.message || e));
      return false;
    } finally {
      setSaving(false);
      setBusyMsg?.("");
    }
  };

  const plannedCount = useMemo(() => {
    if (plannedEpisodes === "" || plannedEpisodes === null) return null;
    const n = Number(plannedEpisodes);
    return Number.isInteger(n) && n >= 1 ? n : null;
  }, [plannedEpisodes]);

  const runGenerate = async () => {
    if (onRequireAuth && !onRequireAuth()) return;
    if (!requireCapability(caps, "deepseek", onNeedKeys, "文本大模型 Key")) return;
    if (!form.brief.trim()) return toast.error("先填写创作需求或粘贴原始故事");
    if (!form.genre.trim()) return toast.error("请选择题材或填写自定义题材");
    const episodeCount = parseCount(generationEpisodeCount);
    if (episodeCount === null) return toast.error(`本次生成集数必须是 1–${MAX_PER_REQUEST} 的整数`);
    if (plannedCount !== null && episodeCount > plannedCount) {
      return toast.error(`本次生成集数不能超过计划总集数（${plannedCount}）`);
    }
    if (episodes.length > 0 && !confirmRegen) {
      setConfirmRegen(true);
      return;
    }
    setConfirmRegen(false);
    setGenerating(true);
    setBusyMsg("正在创作剧本…");
    try {
      if (!(await saveProject(true))) return;
      const b = await api(`/api/projects/${encodeURIComponent(projectId)}/script`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "generate",
          episodeCount,
          plannedEpisodes: plannedCount,
        }),
      });
      apply(b);
      const nextEps = b.episodes || [];
      const firstId = nextEps[0]?.id || null;
      setSelectedId(firstId);
      if (firstId) onFocusEpisode?.(firstId);
      const backend = caps.llmBackend || "LLM";
      toast.success(`${backend} 已完成第 1–${nextEps.length} 集剧本与素材档案`);
    } catch (e) {
      toastMaybeKeys(e, onNeedKeys);
    } finally {
      setGenerating(false);
      setBusyMsg("");
    }
  };

  const runContinue = async () => {
    if (!requireCapability(caps, "deepseek", onNeedKeys, "文本大模型 Key")) return;
    const episodeCount = parseCount(continueEpisodeCount);
    if (episodeCount === null) return toast.error(`本次续写集数必须是 1–${MAX_PER_REQUEST} 的整数`);
    setContinuing(true);
    setShowContinue(false);
    setBusyMsg("续写中…");
    try {
      if (!(await saveProject(true))) return;
      const b = await api(`/api/projects/${encodeURIComponent(projectId)}/script`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "continue",
          episodeCount,
          instruction: continueInstruction.trim(),
          brief: continueBrief.trim(),
          asFinale: continueAsFinale,
        }),
      });
      apply(b);
      toast.success("续写完成");
    } catch (e) {
      toastMaybeKeys(e, onNeedKeys);
    } finally {
      setContinuing(false);
      setBusyMsg("");
    }
  };

  const runRewrite = async () => {
    if (!requireCapability(caps, "deepseek", onNeedKeys, "文本大模型 Key")) return;
    const episodeCount = parseCount(rewriteEpisodeCount, maxRewriteCount);
    if (episodeCount === null) return toast.error("重写集数无效");
    if (!rewriteInstruction.trim()) return toast.error("请填写重写要求");
    setRewriting(true);
    setShowRewrite(false);
    setBusyMsg("重写中…");
    try {
      const b = await api(`/api/projects/${encodeURIComponent(projectId)}/script`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "rewrite",
          startEpisode: rewriteStartEpisode,
          episodeCount,
          instruction: rewriteInstruction.trim(),
        }),
      });
      apply(b);
      toast.success(`已重写第 ${rewriteStartEpisode}–${rewriteStartEpisode + episodeCount - 1} 集`);
    } catch (e) {
      toastMaybeKeys(e, onNeedKeys);
    } finally {
      setRewriting(false);
      setBusyMsg("");
    }
  };

  const confirmAllDrafts = async () => {
    if (!draftEpisodes.length) return toast.info("没有待定稿分集");
    setConfirmBatch(false);
    setBatchConfirming(true);
    setBusyMsg("批量定稿…");
    try {
      const b = await api(`/api/projects/${encodeURIComponent(projectId)}/episodes`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ episodeIds: draftEpisodes.map((e) => e.id), status: "confirmed" }),
      });
      apply(b);
      toast.success(`已定稿 ${draftEpisodes.length} 集`);
    } catch (e) {
      toast.error(String(e.message || e));
    } finally {
      setBatchConfirming(false);
      setBusyMsg("");
    }
  };

  const copyAll = async () => {
    const text = episodes
      .map((ep) => `${ep.title || `第${ep.episodeNumber}集`}\n\n${ep.content || ""}`)
      .join("\n\n");
    try {
      await navigator.clipboard.writeText(text);
      toast.success("已复制全部分集剧本");
    } catch {
      toast.error("复制失败");
    }
  };

  return (
    <div className="mx-auto max-w-[1500px] space-y-5">
      <section className="panel overflow-hidden">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--line)] px-4 py-3 md:px-5">
          <div className="min-w-0">
            <div className="label !mb-0">Story brief</div>
            <div className="flex flex-wrap items-baseline gap-2">
              <h3 className="display-type text-lg font-semibold md:text-xl">创作底稿</h3>
              {briefCollapsed ? (
                <span className="truncate text-xs text-[var(--muted)]">
                  {form.title || "未命名"} · {form.ratio || "9:16"} · {form.genre || "未选题材"} · 已生成 {episodes.length} 集
                </span>
              ) : null}
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {!briefCollapsed ? (
              <button type="button" className="btn-secondary !min-h-9" disabled={operationBusy} onClick={() => void saveProject()}>
                <Save className="h-4 w-4" />
                {saving ? "保存中…" : "保存设定"}
              </button>
            ) : null}
            <button
              type="button"
              className="btn-secondary !min-h-9"
              onClick={() => setBriefCollapsed((v) => !v)}
              aria-expanded={!briefCollapsed}
            >
              {briefCollapsed ? <ChevronDown className="h-4 w-4" /> : <ChevronUp className="h-4 w-4" />}
              {briefCollapsed ? "展开公共设定" : "折叠公共设定"}
            </button>
          </div>
        </div>
        {!briefCollapsed ? (
          <div className="grid lg:grid-cols-[minmax(0,1fr)_360px]">
            <div className="p-5 md:p-6">
              <p className="text-sm text-[var(--muted)]">
                DeepSeek 按本次集数分批创作，剧本可继续续写或按指定范围重写。
              </p>
              <div className="mt-5 grid gap-4 md:grid-cols-2">
                <label className="md:col-span-2">
                  <span className="label">片名</span>
                  <input
                    className="field"
                    value={form.title}
                    disabled={operationBusy}
                    onChange={(e) => setForm({ ...form, title: e.target.value })}
                  />
                </label>
                <div className="min-w-0 md:col-span-2">
                  <span className="label">画面比例</span>
                  <AspectRatioPicker
                    value={form.ratio}
                    disabled={operationBusy}
                    ratios={config?.ratios}
                    onChange={(ratio) => setForm({ ...form, ratio })}
                  />
                </div>
                <div className="md:col-span-2">
                  <span className="label">题材</span>
                  <GenrePicker
                    value={form.genre}
                    disabled={operationBusy}
                    genres={config?.genres}
                    onChange={(genre) => setForm({ ...form, genre })}
                  />
                </div>
                <div className="md:col-span-2">
                  <span className="label">视觉风格</span>
                  <VideoStylePicker
                    value={form.visualStyle}
                    disabled={operationBusy}
                    styles={config?.styles}
                    categories={config?.styleCategories}
                    onChange={(visualStyle) => setForm({ ...form, visualStyle })}
                  />
                </div>
                <label className="md:col-span-2">
                  <span className="label">故事梗概</span>
                  <textarea
                    className="field min-h-20 resize-y"
                    value={form.synopsis}
                    disabled={operationBusy}
                    onChange={(e) => setForm({ ...form, synopsis: e.target.value })}
                    placeholder="生成后会自动写入，也可以先给出已有梗概。"
                  />
                </label>
                <label className="md:col-span-2">
                  <span className="label">创作需求 / 原始素材</span>
                  <textarea
                    className="field min-h-52 resize-y leading-7"
                    value={form.brief}
                    disabled={operationBusy}
                    onChange={(e) => setForm({ ...form, brief: e.target.value })}
                    placeholder="粘贴故事、小说片段或写下人物、核心冲突与结局要求…"
                  />
                </label>
              </div>
            </div>

            <div className="flex flex-col justify-between border-t border-[var(--line)] bg-[var(--navy)] p-6 text-white lg:border-l lg:border-t-0">
              <div>
                <div className="timecode text-[10px] text-[var(--timecode)]">TEXT MODEL</div>
                <div className="mt-2 text-lg font-semibold">{caps.llmBackend || "LLM"} · drama-script</div>
                <p className="mt-2 text-xs leading-6 text-white/55">
                  本次生成集数决定当前调用输出多少集；计划总集数用于安排全剧情绪曲线，可以留空。建议先生成 1 集核对大纲，再扩写。
                </p>
                {episodes.length > 0 ? (
                  <div className="mt-5 rounded-xl border border-white/10 bg-white/5 p-4">
                    <div className="timecode text-[10px] text-white/40">CURRENT PROGRESS</div>
                    <div className="mt-2 text-xl font-semibold">已生成 {episodes.length} 集</div>
                    <div className="mt-1 text-xs text-white/50">
                      计划 {plannedEpisodes === "" ? "未设定" : `${plannedEpisodes} 集`}
                    </div>
                  </div>
                ) : null}
                {creativeBusy ? (
                  <div className="mt-5 rounded-xl border border-[var(--projector)]/35 bg-[var(--projector)]/10 p-4" role="status">
                    <div className="flex items-center gap-2 text-sm font-semibold">
                      <Loader2 className="h-4 w-4 shrink-0 animate-spin text-[var(--projector)]" />
                      <span>{creativeStatus}</span>
                    </div>
                    <div className="timecode mt-2 flex items-center gap-1.5 pl-6 text-[var(--timecode)]">
                      <Clock3 className="h-3.5 w-3.5" />
                      {elapsedTime}
                    </div>
                  </div>
                ) : null}
              </div>
              <div className="mt-8 space-y-4">
                <div className="grid grid-cols-2 gap-3">
                  <label className="min-w-0">
                    <span className="mb-2 flex items-center gap-2 text-xs text-white/60">
                      本次生成 <b className="text-[var(--timecode)]">必填</b>
                    </span>
                    <input
                      type="number"
                      min={1}
                      max={plannedCount ?? MAX_PER_REQUEST}
                      className="field !border-white/20 !bg-[#17243a] !text-white [color-scheme:dark] focus:!border-[var(--projector)]"
                      value={generationEpisodeCount}
                      disabled={operationBusy}
                      onChange={(e) => {
                        const raw = e.target.value === "" ? "" : Number(e.target.value);
                        if (raw === "") {
                          setGenerationEpisodeCount("");
                          return;
                        }
                        const capped =
                          plannedCount !== null ? Math.min(Number(raw), plannedCount, MAX_PER_REQUEST) : Math.min(Number(raw), MAX_PER_REQUEST);
                        setGenerationEpisodeCount(capped);
                      }}
                    />
                  </label>
                  <label className="min-w-0">
                    <span className="mb-2 flex items-center gap-2 text-xs text-white/60">
                      计划总集数 <b className="font-normal text-white/35">可选</b>
                    </span>
                    <input
                      type="number"
                      min={1}
                      max={200}
                      className="field !border-white/20 !bg-[#17243a] !text-white [color-scheme:dark] focus:!border-[var(--projector)]"
                      value={plannedEpisodes}
                      disabled={operationBusy}
                      onChange={(e) => {
                        const next = e.target.value === "" ? "" : Number(e.target.value);
                        setPlannedEpisodes(next);
                        if (next !== "" && Number.isInteger(Number(next)) && Number(next) >= 1) {
                          setGenerationEpisodeCount((current) => {
                            const n = Number(current);
                            if (!Number.isInteger(n) || n < 1) return Math.min(Number(next), MAX_PER_REQUEST);
                            return Math.min(n, Number(next), MAX_PER_REQUEST);
                          });
                        }
                      }}
                      placeholder="开放式可留空"
                    />
                  </label>
                </div>
                {plannedCount !== null && Number(generationEpisodeCount) > plannedCount ? (
                  <p className="text-xs text-amber-300/90">本次生成不能超过计划总集数 {plannedCount}。</p>
                ) : null}
                <button
                  type="button"
                  className="btn-primary flex min-h-12 w-full !rounded-xl font-bold disabled:opacity-45"
                  disabled={operationBusy}
                  onClick={() => void runGenerate()}
                >
                  {generating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
                  {generating ? `正在创作… ${elapsedTime}` : episodes.length ? "按本次集数重新生成" : "生成剧本与素材档案"}
                </button>
              </div>
            </div>
          </div>
        ) : null}
      </section>

      <section className="space-y-4">
        {episodes.length > 0 ? (
          <div className="panel flex flex-wrap items-center justify-between gap-3 px-4 py-3">
            <div>
              <div className="label !mb-0">Episodes</div>
              <strong className="text-sm">{episodes.length} 集 · 左侧切换当前集</strong>
            </div>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                className="btn-secondary !min-h-9 !justify-center !gap-1 !px-2.5 text-[11px]"
                disabled={operationBusy || !draftEpisodes.length}
                onClick={() => setConfirmBatch(true)}
              >
                {batchConfirming ? <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin" /> : <Check className="h-3.5 w-3.5 shrink-0" />}
                定稿{draftEpisodes.length ? ` ${draftEpisodes.length}` : ""}
              </button>
              <button
                type="button"
                className="btn-secondary !min-h-9 !justify-center !gap-1 !px-2.5 text-[11px]"
                disabled={operationBusy}
                onClick={() => void copyAll()}
              >
                <Copy className="h-3.5 w-3.5 shrink-0" />
                复制
              </button>
              <button
                type="button"
                className="btn-secondary !min-h-9 !justify-center !gap-1 !px-2.5 text-[11px]"
                disabled={operationBusy}
                onClick={() => setShowContinue(true)}
              >
                {continuing ? <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin" /> : <Forward className="h-3.5 w-3.5 shrink-0" />}
                {continuing ? elapsedTime : "续写"}
              </button>
              <button
                type="button"
                className="btn-secondary !min-h-9 !justify-center !gap-1 !px-2.5 text-[11px]"
                disabled={operationBusy}
                onClick={() => {
                  setRewriteStartEpisode(episodes[0]?.episodeNumber || 1);
                  setShowRewrite(true);
                }}
              >
                {rewriting ? <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin" /> : <FilePenLine className="h-3.5 w-3.5 shrink-0" />}
                {rewriting ? elapsedTime : "重写"}
              </button>
            </div>
          </div>
        ) : null}

        {selected ? (
          <EpisodeEditor
            key={selected.id + (selected.updatedAt || "")}
            projectId={projectId}
            episode={selected}
            onRefresh={onRefresh}
            onBundle={onBundle}
          />
        ) : (
          <div className="panel flex min-h-[320px] items-center justify-center px-6 text-center text-sm text-[var(--muted)]">
            {episodes.length
              ? "在左侧选择一个分集开始编辑。"
              : "生成剧本后，分集会出现在左侧导航。"}
          </div>
        )}
      </section>

      {showContinue ? (
        <Modal title="续写剧本" label="Continue script" onClose={() => setShowContinue(false)}>
          <p className="text-sm text-[var(--muted)]">从第 {maxEpisodeNumber + 1} 集继续，已有分集不会被覆盖。</p>
          <label className="mt-5 block">
            <span className="label">新的创作需求（可选）</span>
            <textarea className="field min-h-28 resize-y" value={continueBrief} onChange={(e) => setContinueBrief(e.target.value)} />
          </label>
          <label className="mt-4 block">
            <span className="label">续写指导（可选）</span>
            <textarea
              className="field min-h-24 resize-y"
              value={continueInstruction}
              onChange={(e) => setContinueInstruction(e.target.value)}
              placeholder="例如：反派升级、加强感情线…"
            />
          </label>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <label>
              <span className="label">本次续写集数</span>
              <input
                className="field"
                type="number"
                min={1}
                max={MAX_PER_REQUEST}
                value={continueEpisodeCount}
                onChange={(e) => setContinueEpisodeCount(e.target.value === "" ? "" : Number(e.target.value))}
              />
            </label>
            <label className="panel-muted flex min-h-20 items-center gap-3 p-4">
              <input
                type="checkbox"
                className="h-4 w-4 accent-[var(--projector)]"
                checked={continueAsFinale}
                onChange={(e) => setContinueAsFinale(e.target.checked)}
              />
              <span>
                <strong className="block text-sm">本次续写后剧终</strong>
                <span className="mt-1 block text-xs text-[var(--muted)]">最后一集完整收尾。</span>
              </span>
            </label>
          </div>
          <div className="mt-6 flex justify-end gap-3 border-t border-[var(--line)] pt-4">
            <button type="button" className="btn-secondary" onClick={() => setShowContinue(false)}>
              取消
            </button>
            <button type="button" className="btn-primary" onClick={() => void runContinue()}>
              <Forward className="h-4 w-4" />
              确认续写
            </button>
          </div>
        </Modal>
      ) : null}

      {showRewrite ? (
        <Modal title="重写指定分集" label="Rewrite episodes" onClose={() => setShowRewrite(false)}>
          <label className="block">
            <span className="label">重写要求</span>
            <textarea
              className="field min-h-32 resize-y"
              value={rewriteInstruction}
              onChange={(e) => setRewriteInstruction(e.target.value)}
              placeholder="例如：保留人物关系，重写冲突过程…"
              autoFocus
            />
          </label>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <label>
              <span className="label">从第几集开始</span>
              <select
                className="field"
                value={rewriteStartEpisode}
                onChange={(e) => {
                  setRewriteStartEpisode(Number(e.target.value));
                  setRewriteEpisodeCount(1);
                }}
              >
                {episodes.map((ep) => (
                  <option key={ep.id} value={ep.episodeNumber}>
                    第 {ep.episodeNumber} 集 · {ep.title}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span className="label">连续重写集数</span>
              <input
                className="field"
                type="number"
                min={1}
                max={maxRewriteCount}
                value={rewriteEpisodeCount}
                onChange={(e) => setRewriteEpisodeCount(e.target.value === "" ? "" : Number(e.target.value))}
              />
            </label>
          </div>
          <div className="mt-6 flex justify-end gap-3 border-t border-[var(--line)] pt-4">
            <button type="button" className="btn-secondary" onClick={() => setShowRewrite(false)}>
              取消
            </button>
            <button
              type="button"
              className="btn-primary"
              disabled={!rewriteInstruction.trim()}
              onClick={() => void runRewrite()}
            >
              <FilePenLine className="h-4 w-4" />
              确认重写
            </button>
          </div>
        </Modal>
      ) : null}

      <ConfirmDialog
        open={confirmRegen}
        title="重新生成整套剧本？"
        message="现有分集与素材档案将被新结果替换。"
        confirmLabel="重新生成"
        danger
        onCancel={() => setConfirmRegen(false)}
        onConfirm={() => void runGenerate()}
      />
      <ConfirmDialog
        open={confirmBatch}
        title={`批量定稿 ${draftEpisodes.length} 集？`}
        message="定稿后这些分集才能进入分镜制作。"
        confirmLabel="全部定稿"
        onCancel={() => setConfirmBatch(false)}
        onConfirm={() => void confirmAllDrafts()}
      />
    </div>
  );
}

function Modal({ title, label, onClose, children }) {
  return (
    <ModalOverlay onClose={onClose} className="bg-[#09101d]/80 backdrop-blur-sm">
      <section
        role="dialog"
        aria-modal="true"
        className="scrollbar-thin my-auto max-h-[min(760px,calc(100vh-2rem))] w-full max-w-3xl overflow-y-auto rounded-3xl bg-[var(--panel)] p-6 shadow-float"
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="label">{label}</div>
            <h3 className="display-type text-2xl font-semibold">{title}</h3>
          </div>
          <button type="button" className="btn-quiet !min-h-9 !px-2.5" onClick={onClose}>
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="mt-4">{children}</div>
      </section>
    </ModalOverlay>
  );
}

function EpisodeEditor({ projectId, episode, onRefresh, onBundle }) {
  const [title, setTitle] = useState(episode.title || "");
  const [content, setContent] = useState(episode.content || "");
  const [saving, setSaving] = useState(false);
  const locked = episode.status === "confirmed";

  const save = async (status = episode.status) => {
    setSaving(true);
    try {
      await api(`/api/projects/${encodeURIComponent(projectId)}/episodes`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ episodeId: episode.id, title, content, status }),
      });
      await onRefresh?.();
      toast.success(status === "confirmed" ? "本集已定稿" : "本集已保存");
    } catch (e) {
      toast.error(String(e.message || e));
    } finally {
      setSaving(false);
    }
  };

  const remove = async () => {
    if (!window.confirm(`删除第 ${episode.episodeNumber} 集？`)) return;
    try {
      // soft: mark draft empty via rewrite range not available — keep confirm only for status for now
      toast.info("请使用重写覆盖；单集删除将在下一版补齐");
    } catch (e) {
      toast.error(String(e.message || e));
    }
  };

  return (
    <div className="panel flex min-h-0 flex-col overflow-hidden">
      <div className="space-y-3 border-b border-[var(--line)] bg-[var(--panel-muted)] px-4 py-3 sm:px-5">
        <div className="flex min-w-0 items-center gap-3">
          <span className="timecode shrink-0 text-xs text-[var(--muted)]">
            EP {String(episode.episodeNumber).padStart(2, "0")}
          </span>
          <input
            className="field min-w-0 flex-1 !bg-transparent !py-2 font-semibold read-only:cursor-not-allowed read-only:opacity-70"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            readOnly={locked}
          />
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button type="button" className="btn-secondary !min-h-9" disabled={saving || locked} onClick={() => void save()}>
            <Save className="h-3.5 w-3.5" /> 保存
          </button>
          <button
            type="button"
            className={episode.status === "confirmed" ? "btn-secondary !min-h-9" : "btn-primary !min-h-9"}
            disabled={saving}
            onClick={() => void save(episode.status === "confirmed" ? "draft" : "confirmed")}
          >
            <Check className="h-3.5 w-3.5" />
            {episode.status === "confirmed" ? "取消定稿" : "定稿"}
          </button>
          <button type="button" className="btn-danger !min-h-9 !px-2.5" onClick={() => void remove()}>
            <Trash2 className="h-4 w-4" />
          </button>
        </div>
      </div>
      {locked ? (
        <div className="border-b border-[var(--line)] bg-[var(--ok)]/10 px-5 py-2 text-xs text-[var(--ok)]">
          本集已定稿。需要修改时请先取消定稿。
        </div>
      ) : null}
      <textarea
        className="min-h-[500px] flex-1 resize-y border-0 bg-transparent p-5 font-mono text-sm leading-7 text-[var(--ink)] outline-none read-only:cursor-not-allowed read-only:bg-black/20 lg:resize-none"
        value={content}
        onChange={(e) => setContent(e.target.value)}
        placeholder="写下本集场景、动作与对白…"
        readOnly={locked}
      />
    </div>
  );
}
