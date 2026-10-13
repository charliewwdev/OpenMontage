import { PageShell } from "./PageShell";

const SECTIONS = [
  {
    title: "快速开始",
    body: "1. 在「密钥配置」写入 DeepSeek 与火山 ARK Key。2. 新建项目或用创作 Agent。3. 按六步完成剧本到成片。",
  },
  {
    title: "六步工坊",
    body: "剧本（DeepSeek）→ 角色/场景/道具（Seedream）→ 分镜（Seedance）→ 剪辑（FFmpeg）。每一步都可以单独重跑或换版本。",
  },
  {
    title: "密钥与能力",
    body: "未配置 Key 时，相关按钮会引导你一键进入密钥页。密钥保存在服务器 PROJECTS_ROOT/.studio_secrets.json，热加载无需重启。",
  },
  {
    title: "资产与画布",
    body: "资产库汇总角色/场景/道具图片；无限画布展示当前项目节点进度；TV 页回看成片导出。",
  },
];

export function HelpPage({ onNeedKeys }) {
  return (
    <PageShell
      eyebrow="Help"
      title="帮助中心"
      description="影视工坊使用说明与常见问题。"
      actions={
        <button type="button" className="btn-secondary" onClick={() => onNeedKeys?.()}>
          配置密钥
        </button>
      }
    >
      <div className="space-y-3">
        {SECTIONS.map((section) => (
          <article key={section.title} className="panel p-5">
            <h3 className="text-base font-semibold">{section.title}</h3>
            <p className="mt-2 text-sm leading-7 text-[var(--muted)]">{section.body}</p>
          </article>
        ))}
      </div>
    </PageShell>
  );
}
