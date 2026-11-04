import { useEffect, useState } from "react";
import { Coins, KeyRound, Loader2, Sparkles, Zap } from "lucide-react";
import { api } from "../../api";
import { PageShell } from "./PageShell";

import { tr, useLocale } from "../../lib/i18n";

function fmtUsd(n) {
  const v = Number(n) || 0;
  if (v < 0.01 && v > 0) return `$${v.toFixed(4)}`;
  return `$${v.toFixed(2)}`;
}

export function CreditsPage({ config, onNeedKeys }) {
  useLocale();
  const caps = config?.capabilities || {};
  const ready = [caps.deepseek || caps.llmReady, caps.seedream, caps.seedance].filter(Boolean).length;
  const [loading, setLoading] = useState(true);
  const [credits, setCredits] = useState(null);
  const [usage, setUsage] = useState(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const [c, u] = await Promise.all([
          api("/api/settings/credits"),
          api("/api/settings/usage?range=30d&log_limit=1"),
        ]);
        if (!cancelled) {
          setCredits(c.credits);
          setUsage(u);
        }
      } catch {
        /* optional */
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <PageShell
      eyebrow="Credits"
      title={tr("ui_credits_credits_usage")}
      description={tr("ui_credits_the_self_hosted_version_bills_against")}
      actions={
        <button type="button" className="btn-secondary" onClick={() => onNeedKeys?.()}>
          <KeyRound className="h-3.5 w-3.5" />{" "}{tr("ui_credits_model_settings")}</button>
      }
    >
      {loading ? (
        <div className="panel flex items-center gap-2 px-5 py-10 text-sm text-[var(--muted)]">
          <Loader2 className="h-4 w-4 animate-spin" />{" "}{tr("ui_credits_loading_credits")}</div>
      ) : (
        <>
          <div className="mb-4 grid gap-3 md:grid-cols-3">
            <article className="panel p-5">
              <Coins className="h-5 w-5 text-[#fbbf24]" />
              <strong className="mt-3 block text-2xl">{credits?.balance ?? 0}</strong>
              <p className="mt-1 text-sm text-[var(--muted)]">{tr("ui_credits_creator_credit_balance")}</p>
            </article>
            <article className="panel p-5">
              <Zap className="h-5 w-5 text-[#a78bfa]" />
              <strong className="mt-3 block text-2xl">{fmtUsd(usage?.hero?.cost_usd)}</strong>
              <p className="mt-1 text-sm text-[var(--muted)]">{tr("ui_credits_estimated_api_cost_last_30_days")}</p>
            </article>
            <article className="panel p-5">
              <Sparkles className="h-5 w-5 text-[#34d399]" />
              <strong className="mt-3 block text-2xl">{ready}/3</strong>
              <p className="mt-1 text-sm text-[var(--muted)]">{tr("ui_credits_models_ready")}</p>
            </article>
          </div>

          <div className="grid gap-3 lg:grid-cols-2">
            <article className="panel p-5">
              <h3 className="text-lg font-semibold">{tr("ui_credits_your_own_keys_recommended")}</h3>
              <p className="mt-2 text-sm text-[var(--muted)]">{tr("ui_credits_deepseek_volcengine_and_other_charges_go")}</p>
              <button type="button" className="btn-primary mt-4" onClick={() => onNeedKeys?.()}>{tr("ui_credits_go_to_model_settings")}</button>
            </article>
            <article className="panel p-5">
              <h3 className="text-lg font-semibold">{tr("ui_credits_how_to_earn_creator_credits")}</h3>
              <ul className="mt-3 space-y-2 text-sm text-white/75">
                <li>{tr("ui_credits_complete_creative_challenges_points_per_prize")}</li>
                <li>{tr("ui_credits_share_your_referral_link_you_get")}</li>
                <li>{tr("ui_credits_credits_are_shown_locally_only_and")}</li>
              </ul>
            </article>
          </div>

          <section className="panel mt-4 overflow-x-auto p-0">
            <div className="border-b border-[var(--line)] px-4 py-3 text-sm font-semibold">{tr("ui_credits_credit_history")}</div>
            <table className="min-w-full text-left text-sm">
              <thead className="text-xs text-[var(--muted)]">
                <tr>
                  {[tr("ui_credits_time"), tr("ui_credits_change"), tr("ui_credits_reason"), tr("ui_credits_balance")].map((h) => (
                    <th key={h} className="px-4 py-2 font-medium">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {(credits?.ledger || []).slice(0, 30).map((row) => (
                  <tr key={row.id} className="border-t border-[var(--line)]">
                    <td className="px-4 py-2 text-xs text-[var(--muted)]">
                      {row.ts ? new Date(row.ts * 1000).toLocaleString() : "—"}
                    </td>
                    <td className="px-4 py-2 text-[var(--ok)]">+{row.amount}</td>
                    <td className="px-4 py-2">{row.reason}</td>
                    <td className="px-4 py-2">{row.balance}</td>
                  </tr>
                ))}
                {!credits?.ledger?.length ? (
                  <tr>
                    <td colSpan={4} className="px-4 py-8 text-center text-[var(--muted)]">{tr("ui_credits_no_history_yet_complete_a_creative")}</td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </section>
        </>
      )}
    </PageShell>
  );
}
