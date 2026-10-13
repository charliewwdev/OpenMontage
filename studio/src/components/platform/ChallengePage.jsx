import { Trophy } from "lucide-react";
import { PageShell } from "./PageShell";

export function ChallengePage({ config, onStart }) {
  const challenges = config?.challenges || [];
  const page = config?.pages?.challenge || {};

  return (
    <PageShell
      eyebrow={page.eyebrow || "Challenge"}
      title={page.title || "创作挑战"}
      description={page.description || "限时主题任务。"}
    >
      <div className="grid gap-3 lg:grid-cols-3">
        {challenges.map((item) => (
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
