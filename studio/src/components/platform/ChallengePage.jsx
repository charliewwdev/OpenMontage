import { Trophy } from "lucide-react";
import { PageShell } from "./PageShell";

const CHALLENGES = [
  {
    id: "hook-15",
    title: "15 秒钩子挑战",
    prize: "创作积分 +50",
    brief: "用一集剧本写出前 15 秒必须抓住观众的冲突钩子，并生成至少 3 个分镜镜头。",
  },
  {
    id: "character-loop",
    title: "角色一致性挑战",
    prize: "创作积分 +80",
    brief: "同一角色出 4 张不同情绪造型，保持脸型与服装主色一致。",
  },
  {
    id: "vertical-ep",
    title: "竖屏单集挑战",
    prize: "创作积分 +120",
    brief: "完成 9:16 单集：剧本 → 角色 → 场景 → 分镜 → 剪辑导出。",
  },
];

export function ChallengePage({ onStart }) {
  return (
    <PageShell
      eyebrow="Challenge"
      title="创作挑战"
      description="限时主题任务，帮你练熟六步工坊节奏。完成进度会计入项目备注。"
    >
      <div className="grid gap-3 lg:grid-cols-3">
        {CHALLENGES.map((item) => (
          <article key={item.id} className="panel flex flex-col p-5">
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#f59e0b]/15 text-[#fbbf24]">
              <Trophy className="h-5 w-5" />
            </span>
            <h3 className="mt-4 text-lg font-semibold">{item.title}</h3>
            <p className="mt-1 text-xs text-[#fbbf24]">{item.prize}</p>
            <p className="mt-3 flex-1 text-sm leading-7 text-[var(--muted)]">{item.brief}</p>
            <button type="button" className="btn-primary mt-4" onClick={() => onStart?.(item)}>
              接受挑战
            </button>
          </article>
        ))}
      </div>
    </PageShell>
  );
}
