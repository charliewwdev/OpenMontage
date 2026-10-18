import { useEffect, useMemo, useRef, useState } from "react";
import { ArrowLeft, Clapperboard, KeyRound, Loader2, Plus, RotateCcw, Sparkles, Upload, Wand2 } from "lucide-react";
import { api } from "../api";
import { requireCapability, toastMaybeKeys } from "../lib/keys";
import { toast } from "../lib/toast";
import { AspectRatioPicker } from "./project-settings/AspectRatioPicker";
import { GenrePicker } from "./project-settings/GenrePicker";
import { VideoStylePicker } from "./project-settings/VideoStylePicker";

const BRIEF_PLACEHOLDER = `描述你想要的短剧内容，简单想法也可以，点击右上角「AI 优化需求」自动扩写。

【主角设定】
• 姓名、性别、表面身份与隐藏身份
• 核心性格、当前困境、目标与失败代价

【故事框架】
• 开场处境：故事从什么危机、背叛或机会开始
• 核心对立：谁在阻碍主角，冲突为什么不断升级
• 身份反转：主角隐藏的优势、证据或秘密如何兑现
• 复仇 / 逆袭路径：主角如何一步步反击
• 高潮与结局：最终对决和人物关系如何收束

【关键场景】（可选）
• 首集吸引点、中期反转、最终对决

【特殊要求】（可选）
• 感情线、反派、金手指、时代、职业或世界观
• 无虐主 / 快节奏 / 反转多 / 指定结局 / 必须保留的情节`;

export function CreateProjectPage({ config, entryMode = null, onBack, onCreated, onNeedKeys }) {
  const genres = config?.genres || [];
  const styles = config?.styles || [];
  const ratios = config?.ratios;
  const creationSteps = config?.creationSteps || [];
  const defaults = config?.defaults || {};
  const defaultStyle = useMemo(() => styles[0], [styles]);
  const isUpload = entryMode?.mode === "upload" || entryMode?.id === "upload";
  const preset = entryMode?.preset || {};
  const fileRef = useRef(null);

  const [creating, setCreating] = useState(false);
  const [autoRunning, setAutoRunning] = useState(false);
  const [optimizingBrief, setOptimizingBrief] = useState(false);
  const [parsing, setParsing] = useState(false);
  const [uploadName, setUploadName] = useState("");
  const [briefHistory, setBriefHistory] = useState([]);
  const [form, setForm] = useState({
    title: "",
    brief: "",
    genre: preset.genre || defaults.genre || genres[0] || "",
    visualStyle: defaultStyle?.promptValue || defaultStyle?.generationPrompt || defaults.visualStyle || "",
    ratio: preset.ratio || defaults.ratio || ratios?.[0]?.value || "",
  });
  const formLocked = optimizingBrief || creating || parsing || autoRunning;
  const caps = config?.capabilities || {};

  useEffect(() => {
    if (!entryMode) return;
    setForm((current) => ({
      ...current,
      genre: entryMode.preset?.genre || current.genre,
      ratio: entryMode.preset?.ratio || current.ratio,
    }));
  }, [entryMode?.id]);

  const onPickScript = async (file) => {
    if (!file) return;
    setParsing(true);
    try {
      const body = new FormData();
      body.append("file", file);
      const res = await api("/api/projects/parse-script", { method: "POST", body });
      const text = (res.text || "").trim();
      if (!text) throw new Error("未能从文件中提取文本");
      setUploadName(file.name);
      setForm((current) => ({
        ...current,
        title: current.title || String(res.title || file.name.replace(/\.[^.]+$/, "")).slice(0, 40),
        brief: text.slice(0, 100000),
      }));
      toast.success(`已导入 ${file.name}`);
    } catch (error) {
      toast.error(String(error.message || error));
    } finally {
      setParsing(false);
    }
  };

  const optimizeBrief = async () => {
    if (!requireCapability(config?.capabilities, "deepseek", onNeedKeys, "文本大模型 Key")) return;
    if (!form.brief.trim()) return toast.error("先写下一句话故事想法，再让 AI 帮你扩写");
    if (!form.genre.trim()) return toast.error("请选择题材或填写自定义题材");
    if (!form.visualStyle.trim()) return toast.error("请选择视觉风格");
    const requestInput = { ...form };
    setOptimizingBrief(true);
    try {
      const result = await api("/api/script-brief", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(requestInput),
      });
      const optimizedBrief = (result.brief || "").trim();
      if (!optimizedBrief) throw new Error("AI 未返回有效的创作需求");
      if (optimizedBrief !== requestInput.brief.trim()) {
        setBriefHistory((current) => [...current, requestInput.brief].slice(-10));
        setForm((current) => ({ ...current, brief: optimizedBrief }));
        toast.success("创作需求已优化，可继续修改或恢复上个版本");
      } else {
        toast.info("当前创作需求已经足够完整");
      }
    } catch (error) {
      toastMaybeKeys(error, onNeedKeys);
    } finally {
      setOptimizingBrief(false);
    }
  };

  const restoreBrief = () => {
    if (formLocked) return;
    const previousBrief = briefHistory.at(-1);
    if (previousBrief === undefined) return;
    setForm((current) => ({ ...current, brief: previousBrief }));
    setBriefHistory((current) => current.slice(0, -1));
    toast.success("已恢复上个创作需求版本");
  };

  const create = async () => {
    if (optimizingBrief || autoRunning) return;
    if (!form.title.trim()) return toast.error("先给项目起个名字");
    if (!form.genre.trim()) return toast.error("请选择题材或填写自定义题材");
    if (!form.visualStyle.trim()) return toast.error("请选择视觉风格");
    setCreating(true);
    try {
      const bundle = await api("/api/projects", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      onCreated?.(bundle.project?.id);
    } catch (error) {
      toast.error(String(error.message || error));
    } finally {
      setCreating(false);
    }
  };

  const createAndAutoProduce = async () => {
    if (optimizingBrief || creating) return;
    if (!form.title.trim()) return toast.error("先给项目起个名字");
    if (!form.brief.trim()) return toast.error("先写一句话想法或粘贴剧本");
    if (!form.genre.trim()) return toast.error("请选择题材或填写自定义题材");
    if (!form.visualStyle.trim()) return toast.error("请选择视觉风格");
    if (!requireCapability(caps, "deepseek", onNeedKeys, "文本大模型 Key")) return;
    if (!caps.seedream || !caps.seedance) {
      toast.error("全流程需要 Seedream + Seedance Key");
      onNeedKeys?.();
      return;
    }
    setAutoRunning(true);
    try {
      const res = await api("/api/auto-produce", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...form,
          episodeCount: 1,
          maxShots: 24,
          maxCharacters: 6,
          maxScenes: 4,
          forceIllustration: false,
          resolution: "720p",
        }),
      });
      toast.success("已开始一键全流程，后台制作中");
      onCreated?.(res.projectId);
    } catch (error) {
      toastMaybeKeys(error, onNeedKeys);
    } finally {
      setAutoRunning(false);
    }
  };

  return (
    <main className="min-h-screen p-2 md:p-3">
      <div className="yc-frame mx-0 w-full max-w-none p-3 md:p-4">
      <header className="overflow-hidden rounded-[22px] border border-white/10 bg-[linear-gradient(135deg,#15182a_0%,#1a1240_45%,#0d1b3a_100%)] text-white shadow-float">
        <div className="grid lg:grid-cols-[1fr_360px]">
          <div className="p-6 md:p-9">
            <button
              type="button"
              onClick={onBack}
              className="inline-flex items-center gap-2 text-xs font-semibold text-white/55 transition hover:text-white"
            >
              <ArrowLeft className="h-4 w-4" /> 返回影视工坊
            </button>
            <div className="mt-10 flex items-center gap-3 text-xs font-bold uppercase tracking-[.2em] text-white/45">
              <Clapperboard className="h-4 w-4 text-[#b7acff]" /> New production
            </div>
            <h1 className="mt-3 text-4xl font-semibold md:text-5xl">
              {isUpload ? "上传剧本建项" : entryMode?.id === "formal" ? "正剧项目" : "建立新项目"}
            </h1>
            <p className="mt-4 max-w-3xl text-sm leading-7 text-white/60 md:text-base">
              {isUpload
                ? "支持 TXT / MD / DOCX。导入后可再改片名、题材与风格，再进入六步生产线。"
                : "先确定故事方向与统一画面语言。建立后从专业剧本开始，继续整理角色、场景和道具，再进入分镜与成片。"}
            </p>
          </div>
          <div className="relative border-t border-white/10 bg-black/20 p-6 lg:border-l lg:border-t-0 md:p-8">
            <div className="timecode text-[10px] text-[#b7acff]">PROJECT SETUP / 01</div>
            <p className="mt-4 text-sm leading-7 text-white/65">
              这里保存的是创作底稿，不必一开始就写得完美。一句话也能交给 AI 补全，所有结果仍可继续编辑。
            </p>
            <ol className="mt-6 space-y-2 text-sm text-white/70">
              {creationSteps.map((step, i) => (
                <li key={step} className="flex gap-3 border-b border-white/10 py-2">
                  <span className="timecode text-[10px] text-[#b7acff]">{String(i + 1).padStart(2, "0")}</span>
                  {step}
                </li>
              ))}
            </ol>
          </div>
        </div>
      </header>

      {!config?.capabilities?.deepseek ? (
        <section className="mt-4 flex flex-col gap-3 rounded-2xl border border-[#f59e0b]/40 bg-[linear-gradient(90deg,rgba(245,158,11,.16),rgba(239,68,68,.1))] px-4 py-4 md:flex-row md:items-center md:justify-between md:px-5">
          <div className="text-sm text-white/85">
            <strong className="block">AI 优化需求需要文本大模型 Key</strong>
            <span className="mt-1 block text-white/60">可先建项目，生成剧本前请一键配置密钥。</span>
          </div>
          <button type="button" className="btn-primary shrink-0" onClick={() => onNeedKeys?.()}>
            <KeyRound className="h-4 w-4" /> 一键配置密钥
          </button>
        </section>
      ) : null}

      <div className="mt-6 grid gap-6 xl:grid-cols-[minmax(0,1fr)_340px]">
        <div className="space-y-6">
          {isUpload ? (
            <section className="panel p-5 md:p-7">
              <div className="label">Script upload</div>
              <h2 className="display-type text-2xl font-semibold">上传剧本文件</h2>
              <p className="mt-1 text-sm leading-6 text-[var(--muted)]">TXT / Markdown / Word（.docx）。内容会填入创作想法，可继续编辑。</p>
              <input
                ref={fileRef}
                type="file"
                accept=".txt,.md,.markdown,.docx,text/plain,text/markdown,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                className="hidden"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  e.target.value = "";
                  void onPickScript(file);
                }}
              />
              <button
                type="button"
                className="btn-primary mt-5"
                disabled={formLocked}
                onClick={() => fileRef.current?.click()}
              >
                {parsing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
                {parsing ? "解析中…" : "选择文件"}
              </button>
              {uploadName ? <p className="mt-3 text-xs text-[var(--muted)]">已导入：{uploadName}</p> : null}
            </section>
          ) : null}
          <section className="panel p-5 md:p-7">
            <div className="label">Basic setup</div>
            <h2 className="display-type text-2xl font-semibold">故事身份</h2>
            <p className="mt-1 text-sm leading-6 text-[var(--muted)]">先给项目一个可识别的名字，再选择最接近的题材方向。</p>
            <div className="mt-5 space-y-5">
              <label>
                <span className="label">片名</span>
                <input
                  className="field"
                  value={form.title}
                  onChange={(event) => setForm({ ...form, title: event.target.value })}
                  placeholder="例如：雨夜最后一班车"
                  autoFocus
                  disabled={formLocked}
                />
              </label>
              <div>
                <span className="label">题材</span>
                <GenrePicker
                  value={form.genre}
                  onChange={(genre) => setForm({ ...form, genre })}
                  disabled={formLocked}
                  genres={genres}
                />
              </div>
            </div>
          </section>

          <section className="panel p-5 md:p-7">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <div className="label">Story brief</div>
                <label htmlFor="project-brief" className="display-type block text-2xl font-semibold">
                  创作想法 / 原始故事
                </label>
                <p className="mt-1 text-sm leading-6 text-[var(--muted)]">
                  写一句话、详细大纲或粘贴已有素材。AI 优化会保存当前版本，随时可以恢复。
                </p>
              </div>
              <div className="flex flex-wrap justify-end gap-2">
                {briefHistory.length > 0 ? (
                  <button type="button" className="btn-secondary shrink-0" disabled={formLocked} onClick={restoreBrief}>
                    <RotateCcw className="h-4 w-4" />
                    恢复上个版本
                  </button>
                ) : null}
                <button
                  type="button"
                  className="btn-secondary shrink-0"
                  disabled={!form.brief.trim() || !form.genre.trim() || !form.visualStyle.trim() || formLocked}
                  onClick={() => void optimizeBrief()}
                >
                  {optimizingBrief ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
                  {optimizingBrief ? "AI 优化中…" : "AI 优化需求"}
                </button>
              </div>
            </div>
            <textarea
              id="project-brief"
              className="field mt-5 min-h-[420px] resize-y leading-7 md:min-h-[520px]"
              value={form.brief}
              onChange={(event) => setForm({ ...form, brief: event.target.value })}
              placeholder={BRIEF_PLACEHOLDER}
              maxLength={100000}
              disabled={formLocked}
            />
            <div className="mt-3 flex flex-wrap items-center justify-between gap-3 text-xs text-[var(--muted)]">
              <span>AI 会保留已明确的人物、情节、结局和禁忌，只补全缺失的创作要素。</span>
              <span className="timecode shrink-0">
                {form.brief.length} / 100000
              </span>
            </div>
          </section>

          <section className="panel p-5 md:p-7">
            <div className="label">Visual language</div>
            <h2 className="display-type text-2xl font-semibold">视觉风格</h2>
            <p className="mb-5 mt-1 text-sm leading-6 text-[var(--muted)]">
              统一角色、场景、道具和所有分镜的材质、色彩、光线与构图语言。
            </p>
            <VideoStylePicker
              value={form.visualStyle}
              onChange={(visualStyle) => setForm({ ...form, visualStyle })}
              disabled={formLocked}
              styles={styles}
              categories={config?.styleCategories}
            />
          </section>
        </div>

        <aside className="space-y-5 xl:sticky xl:top-6 xl:self-start">
          <section className="panel p-5">
            <div className="label">Frame</div>
            <h2 className="display-type text-xl font-semibold">画面比例</h2>
            <div className="mt-4">
              <AspectRatioPicker
                value={form.ratio}
                onChange={(ratio) => setForm({ ...form, ratio })}
                disabled={formLocked}
                ratios={ratios}
              />
            </div>
            <div className="panel-muted mt-4 p-4">
              <div className="timecode text-[10px] text-[var(--muted)]">PRODUCTION LOCK</div>
              <p className="mt-2 text-xs leading-6 text-[var(--muted)]">
                画幅会贯穿角色、场景、道具、分镜与最终成片，建立后仍可在剧本页调整。
              </p>
            </div>
          </section>

          <section className="panel p-5">
            <div className="label">Ready</div>
            <h2 className="display-type text-xl font-semibold">进入剧本台</h2>
            <p className="mt-2 text-sm leading-6 text-[var(--muted)]">
              可只建项进六步工坊，或一句话/剧本直接后台跑通到成片。
            </p>
            <button type="button" className="btn-primary mt-5 w-full" disabled={formLocked} onClick={() => void createAndAutoProduce()}>
              {autoRunning ? <Loader2 className="h-4 w-4 animate-spin" /> : <Wand2 className="h-4 w-4" />}
              {autoRunning ? "全流程启动中…" : "一键全流程成片"}
            </button>
            <button type="button" className="btn-secondary mt-2 w-full" disabled={formLocked} onClick={() => void create()}>
              {creating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
              {creating ? "创建中…" : "仅建立片场"}
            </button>
            <button type="button" className="btn-ghost mt-2 w-full" disabled={formLocked} onClick={onBack}>
              取消
            </button>
          </section>
        </aside>
      </div>
      </div>
    </main>
  );
}
