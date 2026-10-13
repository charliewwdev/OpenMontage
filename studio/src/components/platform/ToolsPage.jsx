import {
  Clapperboard,
  Image as ImageIcon,
  KeyRound,
  Scissors,
  ScrollText,
  Sparkles,
  Users,
  Wand2,
} from "lucide-react";
import { PageShell } from "./PageShell";

const TOOLS = [
  { id: "script", title: "剧本工作台", desc: "生成 / 续写 / 重写 / 定稿", icon: ScrollText, nav: "workshop", step: "script" },
  { id: "character", title: "角色造型", desc: "Seedream 出图与版本管理", icon: Users, nav: "workshop", step: "character" },
  { id: "scene", title: "空镜场景", desc: "空间与光线设定稿", icon: ImageIcon, nav: "workshop", step: "scene" },
  { id: "storyboard", title: "分镜导演台", desc: "拆镜与 Seedance 视频", icon: Clapperboard, nav: "workshop", step: "storyboard" },
  { id: "edit", title: "剪辑成片", desc: "时间线与 FFmpeg 导出", icon: Scissors, nav: "workshop", step: "edit" },
  { id: "agent", title: "创作 Agent", desc: "一句话建立项目并开写", icon: Sparkles, nav: "agent" },
  { id: "keys", title: "密钥配置", desc: "DeepSeek / 火山一键写入", icon: KeyRound, nav: "keys" },
  { id: "canvas", title: "无限画布", desc: "项目流程节点可视化", icon: Wand2, nav: "canvas" },
];

export function ToolsPage({ onOpenTool }) {
  return (
    <PageShell
      eyebrow="Creation center"
      title="创作中心"
      description="多模态影视工具入口。点击即可跳转到对应工作台或配置页。"
    >
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {TOOLS.map((tool) => {
          const Icon = tool.icon;
          return (
            <button
              key={tool.id}
              type="button"
              className="panel group p-5 text-left transition hover:-translate-y-0.5 hover:border-[#7c6cff]/45"
              onClick={() => onOpenTool?.(tool)}
            >
              <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-[var(--gradient)] text-white">
                <Icon className="h-5 w-5" />
              </span>
              <strong className="mt-4 block text-base">{tool.title}</strong>
              <p className="mt-1 text-sm text-[var(--muted)]">{tool.desc}</p>
            </button>
          );
        })}
      </div>
    </PageShell>
  );
}
