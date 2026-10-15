import { PageShell } from "./PageShell";

export function HelpPage({ config, onNeedKeys, onNavigate }) {
  const sections = config?.helpSections || [];
  const page = config?.pages?.help || {};
  const extras = [
    {
      title: "个人资产",
      body: "「素材」页可上传图片/视频/音频/文档，按来源（上传 / AI 生成）与分类筛选，支持批量删除。「提示词」页可新建、编辑个人提示词库并一键带入创作 Agent。",
    },
    {
      title: "灵感广场",
      body: "浏览 Pinterest 影视灵感墙。卡片带「含提示词」角标，点开可复制完整创作提示词或带入 Agent。",
    },
    {
      title: "创作中心与 Agent",
      body: "创作中心按文本 / 视觉 / 音频 / 视频分组进入工具。创作 Agent 支持「仅生成剧本」或「一键全流程成片」：一句话/粘贴剧本 → 定稿 → 素材 → 分镜视频 → 配音 → 导出。",
    },
    {
      title: "作品频道与画布",
      body: "作品频道汇总导出成片；无限画布可视化六步节点进度，可拖拽查看后回到工坊继续制作。",
    },
  ];
  const all = [...sections, ...extras];

  return (
    <PageShell
      eyebrow={page.eyebrow || "Help"}
      title={page.title || "帮助中心"}
      description={page.description || "影视工坊使用说明与常见问题。"}
      actions={
        <div className="flex flex-wrap gap-2">
          <button type="button" className="btn-secondary" onClick={() => onNeedKeys?.()}>
            配置密钥
          </button>
          <button type="button" className="btn-secondary" onClick={() => onNavigate?.("assets")}>
            个人资产
          </button>
        </div>
      }
    >
      <div className="space-y-3">
        {all.map((section) => (
          <article key={section.title} className="panel p-5">
            <h3 className="text-base font-semibold">{section.title}</h3>
            <p className="mt-2 text-sm leading-7 text-[var(--muted)]">{section.body}</p>
          </article>
        ))}
      </div>
    </PageShell>
  );
}
