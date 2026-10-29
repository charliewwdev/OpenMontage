import { useEffect, useMemo, useState } from "react";
import { CheckCircle2, Loader2, Search, Sparkles, Store, X } from "lucide-react";
import { api } from "../../api";
import { toast } from "../../lib/toast";
import { ModalOverlay } from "../ModalPortal";
import { PageShell } from "./PageShell";

const FALLBACK_SOURCES = [
  { id: "all", label: "全部来源" },
  { id: "official", label: "官方精选" },
  { id: "community", label: "用户分享" },
];

const FALLBACK_CATS = [
  { id: "all", label: "全部分类" },
  { id: "text", label: "文本写作" },
  { id: "image", label: "图片设计" },
  { id: "video", label: "视频创作" },
  { id: "audio", label: "音频音乐" },
  { id: "film", label: "影视制作" },
  { id: "business", label: "商业营销" },
  { id: "productivity", label: "效率工具" },
  { id: "other", label: "其他" },
];

const FALLBACK_TAGS = [
  "全部标签",
  "短剧漫剧",
  "剧本创作",
  "分镜设计",
  "角色设计",
  "场景设计",
  "提示词",
  "镜头语言",
  "图片生成",
  "视频生成",
  "配音旁白",
  "优化改写",
  "Seedance",
  "创作工作流",
];

function Chip({ active, children, onClick }) {
  return (
    <button type="button" className={`${active ? "chip-active" : "chip"} shrink-0`} onClick={onClick}>
      {children}
    </button>
  );
}

function skillPrompt(skill) {
  if (skill.prompt) return skill.prompt;
  return `请按 Skill「${skill.title}」${skill.slash || `/${skill.id}`} 的规则帮我创作：\n\n${(skill.summary || "").trim()}`;
}

function ctaLabel(skill) {
  const route = skill?.workshop?.route;
  if (route === "portrait") return "打开写真对标";
  if (route === "workshop") return "进入影视工坊";
  if (route === "agent") return "对话创作";
  return "去创作";
}

export function SkillsPage({ config, onUsePrompt, onUseSkill }) {
  const activate = (skill) => {
    if (onUseSkill) onUseSkill(skill);
    else onUsePrompt?.(skillPrompt(skill));
  };

  const page = config?.pages?.skills || {};
  const [skills, setSkills] = useState([]);
  const [sources, setSources] = useState(FALLBACK_SOURCES);
  const [categories, setCategories] = useState(FALLBACK_CATS);
  const [tagOptions, setTagOptions] = useState(FALLBACK_TAGS);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [source, setSource] = useState("all");
  const [category, setCategory] = useState("all");
  const [tag, setTag] = useState("全部标签");
  const [active, setActive] = useState(null);
  const [showSubmit, setShowSubmit] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [draft, setDraft] = useState({ title: "", summary: "", prompt: "", category: "other" });

  const refresh = async () => {
    setLoading(true);
    try {
      const data = await api("/api/platform/skills");
      setSkills(data.skills || []);
      if (data.sources?.length) setSources(data.sources);
      if (data.categories?.length) setCategories(data.categories);
      if (data.tags?.length) setTagOptions(data.tags);
    } catch (error) {
      toast.error(String(error.message || error));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void refresh();
  }, []);

  const filtered = useMemo(() => {
    const q = query.trim().toLocaleLowerCase("zh-CN");
    return skills.filter((s) => {
      if (source !== "all" && (s.source || "official") !== source) return false;
      if (category !== "all" && (s.category || "other") !== category) return false;
      if (tag !== "全部标签" && !(s.tags || []).includes(tag)) return false;
      if (!q) return true;
      const blob = `${s.title} ${s.summary} ${s.id} ${(s.tags || []).join(" ")} ${s.content || ""}`.toLocaleLowerCase(
        "zh-CN",
      );
      return blob.includes(q);
    });
  }, [skills, query, source, category, tag]);

  const officialCount = filtered.filter((s) => (s.source || "official") === "official").length;

  return (
    <PageShell
      eyebrow={page.eyebrow || "Skills"}
      title={page.title || "把专业方法装进你的创作 Agent"}
      description={
        page.description ||
        "官方 Skill 已绑定影视工坊步骤：一点即进入对应剧本 / 定妆 / 分镜 / 写真对标。对话类 Skill 仍走创作 Agent。"
      }
      actions={
        <>
          <button type="button" className="btn-secondary" onClick={() => setShowSubmit(true)}>
            投稿到用户分享
          </button>
          <button type="button" className="btn-secondary" onClick={() => void refresh()}>
            <Store className="h-3.5 w-3.5" /> Skill 商店
          </button>
        </>
      }
    >
      <label className="relative mb-2.5 block">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--muted)]" />
        <input
          className="field !pl-10"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="搜索能力或 Skill 名称"
        />
      </label>

      <div className="mb-3 flex flex-wrap gap-2">
        {sources.map((item) => (
          <Chip key={item.id} active={source === item.id} onClick={() => setSource(item.id)}>
            {item.label}
          </Chip>
        ))}
      </div>
      <div className="mb-3 flex flex-wrap gap-2">
        {categories.map((item) => (
          <Chip key={item.id} active={category === item.id} onClick={() => setCategory(item.id)}>
            {item.label}
          </Chip>
        ))}
      </div>
      <div className="mb-3 flex flex-wrap gap-1.5">
        {tagOptions.map((item) => (
          <Chip key={item} active={tag === item} onClick={() => setTag(item)}>
            {item}
          </Chip>
        ))}
      </div>

      <div className="mb-2.5 flex items-center gap-2 text-[12px] text-white/70">
        <CheckCircle2 className="h-4 w-4 text-[#60a5fa]" />
        <span className="font-medium">官方精选</span>
        <span className="rounded-full bg-[#60a5fa]/15 px-2 py-0.5 text-[11px] text-[#93c5fd]">{officialCount} 个可用</span>
      </div>

      {loading ? (
        <div className="panel flex items-center justify-center gap-2 py-10 text-[12px] text-[var(--muted)]">
          <Loader2 className="h-4 w-4 animate-spin" /> 加载 Skill…
        </div>
      ) : !filtered.length ? (
        <div className="panel py-10 text-center text-[12px] text-[var(--muted)]">没有匹配的 Skill</div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {filtered.map((skill) => (
            <article
              key={skill.id}
              className="panel flex flex-col p-3 transition hover:-translate-y-0.5 hover:border-white/20"
            >
              <button type="button" className="flex flex-1 flex-col text-left" onClick={() => setActive(skill)}>
                <span
                  className="flex h-10 w-10 items-center justify-center rounded-xl text-sm font-bold text-white"
                  style={{ background: skill.accent || "var(--gradient)" }}
                >
                  {(skill.title || skill.id).slice(0, 1)}
                </span>
                <strong className="mt-3 block text-base">{skill.title}</strong>
                <span className="mt-1 font-mono text-[11px] text-white/35">{skill.slash || `/${skill.id}`}</span>
                <p className="mt-2 line-clamp-3 flex-1 text-sm leading-6 text-[var(--muted)]">{skill.summary}</p>
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {(skill.tags || []).slice(0, 4).map((t) => (
                    <span key={t} className="rounded-full bg-white/[.06] px-2 py-0.5 text-[10px] text-white/50">
                      {t}
                    </span>
                  ))}
                </div>
                {skill.experience?.totalHits > 0 || skill.experience?.learnedCount > 0 ? (
                  <div className="mt-3 rounded-lg border border-emerald-500/20 bg-emerald-500/10 px-2.5 py-1.5 text-[10px] text-emerald-100/90">
                    经验 {skill.experience.patchCount || 0} 条 · 命中 {skill.experience.totalHits || 0} 次
                    {skill.experience.learnedCount
                      ? ` · 自动学习 ${skill.experience.learnedCount}`
                      : ""}
                  </div>
                ) : null}
              </button>
              <div className="mt-4 flex items-center justify-between gap-2 border-t border-white/5 pt-3">
                <span className="text-[11px] text-white/35">平台内置 · 无需安装</span>
                <button
                  type="button"
                  className="btn-primary !min-h-8 !px-3 !text-xs"
                  onClick={() => activate(skill)}
                >
                  <Sparkles className="h-3 w-3" /> {ctaLabel(skill)}
                </button>
              </div>
            </article>
          ))}
        </div>
      )}

      {showSubmit ? (
        <ModalOverlay onClose={() => setShowSubmit(false)} className="bg-black/70">
          <div
            className="panel my-auto w-full max-w-lg space-y-3 p-5"
            onClick={(e) => e.stopPropagation()}
            onMouseDown={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold">投稿 Skill（本地社区）</h3>
              <button type="button" className="btn-ghost p-1" onClick={() => setShowSubmit(false)}>
                <X className="h-4 w-4" />
              </button>
            </div>
            <label>
              <span className="label">标题</span>
              <input className="field" value={draft.title} onChange={(e) => setDraft({ ...draft, title: e.target.value })} />
            </label>
            <label>
              <span className="label">摘要</span>
              <input className="field" value={draft.summary} onChange={(e) => setDraft({ ...draft, summary: e.target.value })} />
            </label>
            <label>
              <span className="label">分类</span>
              <select className="field" value={draft.category} onChange={(e) => setDraft({ ...draft, category: e.target.value })}>
                {categories.filter((c) => c.id !== "all").map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span className="label">Prompt / 规则</span>
              <textarea
                className="field min-h-36"
                value={draft.prompt}
                onChange={(e) => setDraft({ ...draft, prompt: e.target.value })}
                placeholder="写下可复用的创作规则或提示词…"
              />
            </label>
            <div className="flex justify-end gap-2 pt-2">
              <button type="button" className="btn-secondary" onClick={() => setShowSubmit(false)}>
                取消
              </button>
              <button
                type="button"
                className="btn-primary"
                disabled={submitting}
                onClick={async () => {
                  if (!draft.title.trim() || !draft.prompt.trim()) return toast.error("请填写标题和 Prompt");
                  setSubmitting(true);
                  try {
                    await api("/api/platform/skills/community", {
                      method: "POST",
                      headers: { "Content-Type": "application/json" },
                      body: JSON.stringify(draft),
                    });
                    toast.success("已投稿到用户分享");
                    setShowSubmit(false);
                    setDraft({ title: "", summary: "", prompt: "", category: "other" });
                    setSource("community");
                    await refresh();
                  } catch (error) {
                    toast.error(String(error.message || error));
                  } finally {
                    setSubmitting(false);
                  }
                }}
              >
                {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                提交
              </button>
            </div>
          </div>
        </ModalOverlay>
      ) : null}

      {active ? (
        <ModalOverlay onClose={() => setActive(null)} className="bg-black/70">
          <div
            className="panel my-auto max-h-[85vh] w-full max-w-3xl overflow-hidden"
            onClick={(e) => e.stopPropagation()}
            onMouseDown={(e) => e.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-3 border-b border-white/10 p-5">
              <div>
                <div className="label">{active.slash || `/${active.id}`}</div>
                <h2 className="text-[1.1rem] font-semibold">{active.title}</h2>
                <p className="mt-2 text-sm text-[var(--muted)]">{active.summary}</p>
              </div>
              <button type="button" className="btn-secondary !min-h-8 !px-2" onClick={() => setActive(null)}>
                <X className="h-4 w-4" />
              </button>
            </div>
            {(active.experience?.topFailures || []).length ? (
              <div className="border-b border-white/10 bg-black/20 px-5 py-3">
                <div className="text-[11px] font-semibold uppercase tracking-wide text-white/45">
                  质检经验（自动累积）
                </div>
                <ul className="mt-2 space-y-1.5">
                  {active.experience.topFailures.slice(0, 5).map((f) => (
                    <li key={f.id} className="rounded-lg border border-white/8 bg-white/[.03] px-2.5 py-1.5 text-[11px] text-white/70">
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-mono text-white/50">{f.id}</span>
                        <span className="text-emerald-300/80">×{f.hits || 0}</span>
                      </div>
                      {f.lastReason ? (
                        <p className="mt-1 line-clamp-2 text-white/55">{f.lastReason}</p>
                      ) : null}
                      {f.promptBoost ? (
                        <p className="mt-1 line-clamp-2 text-[#c4b5fd]/90">{f.promptBoost}</p>
                      ) : null}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
            <pre className="max-h-[50vh] overflow-auto whitespace-pre-wrap bg-black/30 p-5 text-xs leading-6 text-white/75">
              {active.content || "暂无内容"}
            </pre>
            <div className="flex justify-end gap-2 border-t border-white/10 p-4">
              <button type="button" className="btn-secondary" onClick={() => setActive(null)}>
                关闭
              </button>
              <button
                type="button"
                className="btn-primary"
                onClick={() => {
                  activate(active);
                  setActive(null);
                }}
              >
                <Sparkles className="h-3.5 w-3.5" /> {ctaLabel(active)}
              </button>
            </div>
          </div>
        </ModalOverlay>
      ) : null}
    </PageShell>
  );
}
