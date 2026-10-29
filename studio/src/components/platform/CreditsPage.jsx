import { useEffect, useState } from "react";
import { Coins, KeyRound, Loader2, Sparkles, Zap } from "lucide-react";
import { api } from "../../api";
import { PageShell } from "./PageShell";

function fmtUsd(n) {
  const v = Number(n) || 0;
  if (v < 0.01 && v > 0) return `$${v.toFixed(4)}`;
  return `$${v.toFixed(2)}`;
}

export function CreditsPage({ config, onNeedKeys }) {
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
      title="积分与用量"
      description="本地部署版按你自己的 API 额度计费，平台不抽成、无在线充值。创作积分来自挑战完成与邀请落地。"
      actions={
        <button type="button" className="btn-secondary" onClick={() => onNeedKeys?.()}>
          <KeyRound className="h-3.5 w-3.5" /> 模型配置
        </button>
      }
    >
      {loading ? (
        <div className="panel flex items-center gap-2 px-3 py-6 text-[12px] text-[var(--muted)]">
          <Loader2 className="h-4 w-4 animate-spin" /> 加载积分…
        </div>
      ) : (
        <>
          <div className="mb-3 grid gap-2 md:grid-cols-3">
            <article className="panel p-3">
              <Coins className="h-4 w-4 text-[#fbbf24]" />
              <strong className="mt-1.5 block text-[1.25rem]">{credits?.balance ?? 0}</strong>
              <p className="mt-0.5 text-[12px] text-[var(--muted)]">创作积分余额</p>
            </article>
            <article className="panel p-3">
              <Zap className="h-4 w-4 text-[#a78bfa]" />
              <strong className="mt-1.5 block text-[1.25rem]">{fmtUsd(usage?.hero?.cost_usd)}</strong>
              <p className="mt-0.5 text-[12px] text-[var(--muted)]">近 30 天估算 API 费用</p>
            </article>
            <article className="panel p-3">
              <Sparkles className="h-4 w-4 text-[#34d399]" />
              <strong className="mt-1.5 block text-[1.25rem]">{ready}/3</strong>
              <p className="mt-0.5 text-[12px] text-[var(--muted)]">模型能力已就绪</p>
            </article>
          </div>

          <div className="grid gap-2 lg:grid-cols-2">
            <article className="panel p-3">
              <h3 className="text-[13px] font-semibold">自有 Key（推荐）</h3>
              <p className="mt-1.5 text-[12px] text-[var(--muted)]">
                DeepSeek / 火山等费用发生在你的供应商账户。配置后立即热加载，无需充值平台积分。
              </p>
              <button type="button" className="btn-primary mt-3" onClick={() => onNeedKeys?.()}>
                去模型配置
              </button>
            </article>
            <article className="panel p-3">
              <h3 className="text-[13px] font-semibold">如何获得创作积分</h3>
              <ul className="mt-2 space-y-1 text-[12px] text-white/75">
                <li>· 完成创作挑战（按奖项加分）</li>
                <li>· 分享推荐链接，对方首次打开可获邀请积分</li>
                <li>· 积分仅本地展示，不影响 API 调用</li>
              </ul>
            </article>
          </div>

          <section className="panel mt-3 overflow-x-auto p-0">
            <div className="border-b border-[var(--line)] px-3 py-2 text-[13px] font-semibold">积分流水</div>
            <table className="min-w-full text-left text-sm">
              <thead className="text-xs text-[var(--muted)]">
                <tr>
                  {["时间", "变动", "原因", "余额"].map((h) => (
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
                    <td colSpan={4} className="px-4 py-8 text-center text-[var(--muted)]">
                      暂无流水。去创作挑战完成一项即可获得积分。
                    </td>
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
