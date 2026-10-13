import { ExternalLink, FileText, Film, Mic2 } from "lucide-react";
import { PageShell } from "./PageShell";

const LINKS = [
  { title: "OpenMontage AGENT_GUIDE", desc: "仓库总路由与制作规范", href: "/docs/agent-guide", icon: FileText, external: false },
  { title: "六步工坊说明", desc: "剧本 → 角色 → 场景 → 道具 → 分镜 → 剪辑", href: "#help", icon: Film, external: false },
  { title: "DeepSeek API", desc: "剧本模型文档", href: "https://platform.deepseek.com/api-docs/", icon: ExternalLink, external: true },
  { title: "火山方舟", desc: "Seedream / Seedance 控制台", href: "https://console.volcengine.com/ark", icon: ExternalLink, external: true },
  { title: "FFmpeg 指南", desc: "剪辑与导出依赖", href: "https://ffmpeg.org/documentation.html", icon: Mic2, external: true },
];

export function ResourcesPage({ onNavigate }) {
  return (
    <PageShell eyebrow="Resources" title="资源中心" description="文档、模型控制台与制作参考入口。">
      <div className="grid gap-3 md:grid-cols-2">
        {LINKS.map((link) => {
          const Icon = link.icon;
          return (
            <a
              key={link.title}
              href={link.external ? link.href : undefined}
              target={link.external ? "_blank" : undefined}
              rel={link.external ? "noreferrer" : undefined}
              className="panel flex items-start gap-4 p-5 transition hover:-translate-y-0.5 hover:border-[#7c6cff]/45"
              onClick={(e) => {
                if (!link.external) {
                  e.preventDefault();
                  if (link.href === "#help") onNavigate?.("help");
                  else onNavigate?.("help");
                }
              }}
            >
              <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-white/[.06]">
                <Icon className="h-5 w-5 text-[#a78bfa]" />
              </span>
              <span>
                <strong className="block">{link.title}</strong>
                <span className="mt-1 block text-sm text-[var(--muted)]">{link.desc}</span>
              </span>
            </a>
          );
        })}
      </div>
    </PageShell>
  );
}
