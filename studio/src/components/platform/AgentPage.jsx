import { useEffect, useState } from "react";
import { Loader2, Sparkles } from "lucide-react";
import { api } from "../../api";
import { toast } from "../../lib/toast";
import { PageShell } from "./PageShell";

export function AgentPage({ config, seedPrompt = "", onCreated, onNeedKeys }) {
  const [prompt, setPrompt] = useState(seedPrompt || "");
  const [title, setTitle] = useState("");
  const [genre, setGenre] = useState(config?.genres?.[0] || "都市情感");
  const [ratio, setRatio] = useState("9:16");
  const [episodeCount, setEpisodeCount] = useState(3);
  const [busy, setBusy] = useState(false);
  const caps = config?.capabilities || {};

  useEffect(() => {
    if (seedPrompt) setPrompt(seedPrompt);
  }, [seedPrompt]);

  const run = async () => {
    if (!prompt.trim()) return toast.error("先描述你想拍的故事");
    if (!caps.deepseek) {
      toast.error("请先配置 DeepSeek Key");
      onNeedKeys?.();
      return;
    }
    setBusy(true);
    try {
      const projectTitle = title.trim() || prompt.trim().slice(0, 24) || "Agent 项目";
      const created = await api("/api/projects", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: projectTitle,
          brief: prompt.trim(),
          genre,
          ratio,
          visualStyle: config?.styles?.[0]?.promptValue || "",
        }),
      });
      const projectId = created.project?.id;
      await api(`/api/projects/${encodeURIComponent(projectId)}/script`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "generate", episodeCount }),
      });
      toast.success("Agent 已创建项目并生成剧本");
      onCreated?.(projectId);
    } catch (error) {
      toast.error(String(error.message || error));
    } finally {
      setBusy(false);
    }
  };

  return (
    <PageShell
      eyebrow="Creation agent"
      title="创作 Agent"
      description="用一句话描述故事。Agent 会建立项目、写入创作需求，并调用 DeepSeek 生成首批剧本。"
    >
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_320px]">
        <section className="panel p-5 md:p-6">
          <label>
            <span className="label">故事想法</span>
            <textarea
              className="field min-h-56 resize-y leading-7"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="例如：现代都市爽剧，落魄女婿三年后以隐秘身份归来，打脸丈母娘与假千金……"
              disabled={busy}
            />
          </label>
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            <label>
              <span className="label">片名（可选）</span>
              <input className="field" value={title} disabled={busy} onChange={(e) => setTitle(e.target.value)} />
            </label>
            <label>
              <span className="label">本次生成集数</span>
              <input
                className="field"
                type="number"
                min={1}
                max={10}
                value={episodeCount}
                disabled={busy}
                onChange={(e) => setEpisodeCount(Number(e.target.value) || 1)}
              />
            </label>
            <label>
              <span className="label">题材</span>
              <select className="field" value={genre} disabled={busy} onChange={(e) => setGenre(e.target.value)}>
                {(config?.genres || ["都市情感"]).map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span className="label">画幅</span>
              <select className="field" value={ratio} disabled={busy} onChange={(e) => setRatio(e.target.value)}>
                <option value="9:16">9:16 竖屏</option>
                <option value="16:9">16:9 横屏</option>
                <option value="1:1">1:1 方屏</option>
              </select>
            </label>
          </div>
          <button type="button" className="btn-primary mt-5 min-h-12 w-full" disabled={busy} onClick={() => void run()}>
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
            {busy ? "Agent 创作中…" : "一句话开始创作"}
          </button>
        </section>
        <aside className="panel-muted space-y-3 p-5 text-sm leading-6 text-[var(--muted)]">
          <strong className="block text-[var(--ink)]">运行检查</strong>
          <p>DeepSeek：{caps.deepseek ? "就绪" : "未配置"}</p>
          <p>Seedream：{caps.seedream ? "就绪" : "未配置（角色出图时需要）"}</p>
          <p>Seedance：{caps.seedance ? "就绪" : "未配置（分镜视频时需要）"}</p>
          {!caps.deepseek ? (
            <button type="button" className="btn-secondary mt-2 w-full" onClick={() => onNeedKeys?.()}>
              去配置密钥
            </button>
          ) : null}
        </aside>
      </div>
    </PageShell>
  );
}
