import { useEffect, useState } from "react";
import { CheckCircle2, Trophy } from "lucide-react";
import { api } from "../../api";
import { toast } from "../../lib/toast";
import { PageShell } from "./PageShell";

const STORAGE_KEY = "om.challenges.v1";

function loadProgress() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}") || {};
  } catch {
    return {};
  }
}

function prizePoints(prize) {
  const digits = String(prize || "").replace(/\D/g, "");
  return Number(digits || 0);
}

export function ChallengePage({ config, onStart }) {
  const challenges = config?.challenges || [];
  const page = config?.pages?.challenge || {};
  const [progress, setProgress] = useState(() => loadProgress());
  const [balance, setBalance] = useState(null);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(progress));
  }, [progress]);

  useEffect(() => {
    api("/api/settings/credits")
      .then((res) => setBalance(res.credits?.balance ?? 0))
      .catch(() => {});
  }, []);

  const mark = (id, status) => {
    setProgress((prev) => ({ ...prev, [id]: { status, at: Date.now() } }));
  };

  const complete = async (item) => {
    mark(item.id, "done");
    try {
      const res = await api("/api/settings/credits/challenge", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          id: item.id,
          title: item.title,
          prize: item.prize,
          prizePoints: prizePoints(item.prize),
        }),
      });
      const next = res.credits?.balance;
      if (typeof next === "number") setBalance(next);
      if (res.already) toast.info("该挑战积分已发放过");
      else toast.success(`已完成，创作积分 +${prizePoints(item.prize)}`);
    } catch (error) {
      toast.error(String(error.message || error));
    }
  };

  return (
    <PageShell
      eyebrow={page.eyebrow || "Challenge"}
      title={page.title || "创作挑战"}
      description={page.description || "限时主题任务，练熟六步工坊节奏；接受后会把 brief 带入创作 Agent。完成可获得本地创作积分。"}
    >
      <div className="mb-3 grid gap-2 sm:grid-cols-4">
        <article className="panel p-2.5">
          <div className="text-[11px] text-[var(--muted)]">全部挑战</div>
          <strong className="mt-0.5 block text-[1.2rem]">{challenges.length}</strong>
        </article>
        <article className="panel p-2.5">
          <div className="text-[11px] text-[var(--muted)]">进行中</div>
          <strong className="mt-0.5 block text-[1.2rem]">
            {Object.values(progress).filter((p) => p.status === "accepted").length}
          </strong>
        </article>
        <article className="panel p-2.5">
          <div className="text-[11px] text-[var(--muted)]">已完成</div>
          <strong className="mt-0.5 block text-[1.2rem]">
            {Object.values(progress).filter((p) => p.status === "done").length}
          </strong>
        </article>
        <article className="panel p-2.5">
          <div className="text-[11px] text-[var(--muted)]">创作积分</div>
          <strong className="mt-0.5 block text-[1.2rem]">{balance ?? "—"}</strong>
        </article>
      </div>

      {!challenges.length ? (
        <div className="panel py-10 text-center text-[12px] text-[var(--muted)]">暂无挑战，稍后再来</div>
      ) : (
        <div className="grid gap-2 lg:grid-cols-3">
          {challenges.map((item, index) => {
            const state = progress[item.id]?.status || "open";
            return (
              <article key={item.id} className="panel flex flex-col p-3">
                <div className="flex items-start justify-between gap-2">
                  <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#f59e0b]/15 text-[#fbbf24]">
                    <Trophy className="h-4 w-4" />
                  </span>
                  <span className="rounded-full bg-white/[.06] px-2 py-0.5 text-[10px] text-white/45">
                    {state === "done" ? "已完成" : state === "accepted" ? "进行中" : `#${index + 1}`}
                  </span>
                </div>
                <h3 className="mt-2.5 text-[14px] font-semibold">{item.title}</h3>
                <p className="mt-1 text-xs text-[#fbbf24]">{item.prize}</p>
                <p className="mt-3 flex-1 text-sm leading-7 text-[var(--muted)]">{item.brief}</p>
                <div className="mt-4 flex flex-wrap gap-2">
                  <button
                    type="button"
                    className="btn-primary flex-1"
                    onClick={() => {
                      mark(item.id, "accepted");
                      onStart?.(item);
                    }}
                  >
                    {state === "accepted" ? "继续挑战" : "接受挑战"}
                  </button>
                  <button
                    type="button"
                    className="btn-secondary flex-1"
                    onClick={async () => {
                      await navigator.clipboard.writeText(item.brief || "");
                      toast.success("brief 已复制");
                    }}
                  >
                    复制 brief
                  </button>
                </div>
                {state !== "done" ? (
                  <button
                    type="button"
                    className="mt-2 inline-flex items-center justify-center gap-1 text-xs text-white/45 hover:text-white/80"
                    onClick={() => void complete(item)}
                  >
                    <CheckCircle2 className="h-3.5 w-3.5" /> 标记完成并领取积分
                  </button>
                ) : (
                  <div className="mt-2 text-center text-xs text-[var(--ok)]">已完成</div>
                )}
              </article>
            );
          })}
        </div>
      )}
    </PageShell>
  );
}
