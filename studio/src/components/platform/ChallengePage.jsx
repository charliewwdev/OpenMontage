import { useEffect, useState } from "react";
import { CheckCircle2, Trophy } from "lucide-react";
import { api } from "../../api";
import { toast } from "../../lib/toast";
import { PageShell } from "./PageShell";

import { tr, useLocale } from "../../lib/i18n";

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
  useLocale();
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
      if (res.already) toast.info(tr("ui_challenge_credits_for_this_challenge_were_already"));
      else toast.success(tr("ui_challenge_done_creator_credits", {
        0: prizePoints(item.prize)
      }));
    } catch (error) {
      toast.error(String(error.message || error));
    }
  };

  return (
    <PageShell
      eyebrow={page.eyebrow || "Challenge"}
      title={page.title || tr("ui_challenge_creative_challenges")}
      description={page.description || tr("ui_challenge_time_limited_themed_tasks_to_get")}
    >
      <div className="mb-5 grid gap-3 sm:grid-cols-4">
        <article className="panel p-4">
          <div className="text-xs text-[var(--muted)]">{tr("ui_challenge_all_challenges")}</div>
          <strong className="mt-1 block text-2xl">{challenges.length}</strong>
        </article>
        <article className="panel p-4">
          <div className="text-xs text-[var(--muted)]">{tr("ui_challenge_in_progress")}</div>
          <strong className="mt-1 block text-2xl">
            {Object.values(progress).filter((p) => p.status === "accepted").length}
          </strong>
        </article>
        <article className="panel p-4">
          <div className="text-xs text-[var(--muted)]">{tr("ui_challenge_completed")}</div>
          <strong className="mt-1 block text-2xl">
            {Object.values(progress).filter((p) => p.status === "done").length}
          </strong>
        </article>
        <article className="panel p-4">
          <div className="text-xs text-[var(--muted)]">{tr("ui_challenge_creator_credits")}</div>
          <strong className="mt-1 block text-2xl">{balance ?? "—"}</strong>
        </article>
      </div>

      {!challenges.length ? (
        <div className="panel py-20 text-center text-sm text-[var(--muted)]">{tr("ui_challenge_no_challenges_yet_check_back_later")}</div>
      ) : (
        <div className="grid gap-3 lg:grid-cols-3">
          {challenges.map((item, index) => {
            const state = progress[item.id]?.status || "open";
            return (
              <article key={item.id} className="panel flex flex-col p-5">
                <div className="flex items-start justify-between gap-2">
                  <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#f59e0b]/15 text-[#fbbf24]">
                    <Trophy className="h-5 w-5" />
                  </span>
                  <span className="rounded-full bg-white/[.06] px-2 py-0.5 text-[10px] text-white/45">
                    {state === "done" ? tr("ui_challenge_completed") : state === "accepted" ? tr("ui_challenge_in_progress") : `#${index + 1}`}
                  </span>
                </div>
                <h3 className="mt-4 text-lg font-semibold">{item.title}</h3>
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
                    {state === "accepted" ? tr("ui_challenge_continue_challenge") : tr("ui_challenge_accept_challenge")}
                  </button>
                  <button
                    type="button"
                    className="btn-secondary flex-1"
                    onClick={async () => {
                      await navigator.clipboard.writeText(item.brief || "");
                      toast.success(tr("ui_challenge_brief_copied"));
                    }}
                  >{tr("ui_challenge_copy_brief")}</button>
                </div>
                {state !== "done" ? (
                  <button
                    type="button"
                    className="mt-2 inline-flex items-center justify-center gap-1 text-xs text-white/45 hover:text-white/80"
                    onClick={() => void complete(item)}
                  >
                    <CheckCircle2 className="h-3.5 w-3.5" />{" "}{tr("ui_challenge_mark_done_and_claim_credits")}</button>
                ) : (
                  <div className="mt-2 text-center text-xs text-[var(--ok)]">{tr("ui_challenge_completed")}</div>
                )}
              </article>
            );
          })}
        </div>
      )}
    </PageShell>
  );
}
