import { useEffect, useState } from "react";
import { BookOpen, Loader2, RefreshCw } from "lucide-react";
import { api } from "../../api";
import { toast } from "../../lib/toast";
import { PageShell } from "./PageShell";

export function SkillsPage() {
  const [skills, setSkills] = useState([]);
  const [activeId, setActiveId] = useState("");
  const [loading, setLoading] = useState(true);

  const refresh = async () => {
    setLoading(true);
    try {
      const data = await api("/api/platform/skills");
      setSkills(data.skills || []);
      setActiveId((current) => current || data.skills?.[0]?.id || "");
    } catch (error) {
      toast.error(String(error.message || error));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void refresh();
  }, []);

  const active = skills.find((s) => s.id === activeId) || skills[0];

  return (
    <PageShell
      eyebrow="Skills"
      title="Skill 专家"
      description="影视工坊内置的剧本、分镜与需求优化 Skill，可直接查看契约与提示规则。"
      actions={
        <button type="button" className="btn-secondary" onClick={() => void refresh()}>
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} /> 刷新
        </button>
      }
    >
      {loading ? (
        <div className="panel flex items-center justify-center gap-2 py-20 text-sm text-[var(--muted)]">
          <Loader2 className="h-4 w-4 animate-spin" /> 加载 Skill…
        </div>
      ) : (
        <div className="grid gap-4 lg:grid-cols-[280px_1fr]">
          <aside className="panel space-y-1 p-2">
            {skills.map((skill) => (
              <button
                key={skill.id}
                type="button"
                onClick={() => setActiveId(skill.id)}
                className={`flex w-full items-start gap-3 rounded-xl px-3 py-3 text-left ${
                  active?.id === skill.id ? "bg-[var(--projector)]/15" : "hover:bg-white/[.04]"
                }`}
              >
                <BookOpen className="mt-0.5 h-4 w-4 text-[#a78bfa]" />
                <span>
                  <span className="block text-sm font-semibold">{skill.title}</span>
                  <span className="mt-1 block text-[11px] text-[var(--muted)]">{skill.summary}</span>
                </span>
              </button>
            ))}
          </aside>
          <section className="panel p-5 md:p-6">
            <div className="label">{active?.id}</div>
            <h2 className="text-xl font-semibold">{active?.title}</h2>
            <pre className="scrollbar-thin mt-5 max-h-[70vh] overflow-auto whitespace-pre-wrap rounded-xl bg-black/30 p-4 text-xs leading-6 text-white/75">
              {active?.content || "暂无内容"}
            </pre>
          </section>
        </div>
      )}
    </PageShell>
  );
}
