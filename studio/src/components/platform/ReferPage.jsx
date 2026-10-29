import { useEffect, useMemo, useState } from "react";
import { Copy, Gift, Share2, Users } from "lucide-react";
import { api } from "../../api";
import { toast } from "../../lib/toast";
import { PageShell } from "./PageShell";

const TIERS = [
  { title: "分享链接", desc: "把带邀请码的地址发给搭档或客户，对方打开后可自行配置 Key。" },
  { title: "协作生产", desc: "同一台部署可多人使用；项目存在本地 PROJECTS_ROOT。" },
  { title: "邀请奖励", desc: "对方首次通过你的链接打开时，记 +20 创作积分。" },
];

const REF_CAPTURE_KEY = "om.refer.captured";

export function ReferPage({ config }) {
  const [credits, setCredits] = useState(null);
  const origin =
    config?.public_url ||
    (typeof window !== "undefined" ? window.location.origin : "");

  useEffect(() => {
    api("/api/settings/credits")
      .then((res) => setCredits(res.credits))
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    const ref = params.get("ref");
    if (!ref) return;
    try {
      if (sessionStorage.getItem(REF_CAPTURE_KEY) === ref) return;
      sessionStorage.setItem(REF_CAPTURE_KEY, ref);
    } catch {
      /* ignore */
    }
    api("/api/settings/credits/referral", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ref }),
    })
      .then((res) => {
        setCredits(res.credits);
        toast.success("已记录邀请，创作积分 +20");
      })
      .catch(() => {});
  }, []);

  const link = useMemo(() => {
    if (!origin) return "";
    const code = credits?.refCode || "om";
    const base = origin.replace(/\/$/, "");
    return `${base}/?ref=${encodeURIComponent(code)}`;
  }, [origin, credits?.refCode]);

  return (
    <PageShell eyebrow="Refer" title="推荐计划" description="分享影视工坊，邀请伙伴一起用七步流程做短剧。">
      <div className="grid gap-3 lg:grid-cols-[1.2fr_0.8fr]">
        <div className="panel p-3.5">
          <Gift className="h-6 w-6 text-[#a78bfa]" />
          <h3 className="mt-2.5 text-[14px] font-semibold">分享工作台地址</h3>
          <p className="mt-1.5 text-[12px] text-[var(--muted)]">链接含你的邀请码。对方首次打开时本地记邀请奖励。</p>
          <code className="mt-2.5 block break-all rounded-lg bg-black/30 px-3 py-2 text-[12px]">{link || "（加载中）"}</code>
          <div className="mt-2 text-[11px] text-[var(--muted)]">
            已邀请 {credits?.referrals ?? 0} 次 · 积分余额 {credits?.balance ?? 0}
          </div>
          <div className="mt-3 flex flex-wrap gap-1.5">
            <button
              type="button"
              className="btn-primary"
              disabled={!link}
              onClick={async () => {
                await navigator.clipboard.writeText(link);
                toast.success("邀请链接已复制");
              }}
            >
              <Copy className="h-4 w-4" /> 复制链接
            </button>
            <button
              type="button"
              className="btn-secondary"
              disabled={!link || typeof navigator.share !== "function"}
              onClick={async () => {
                try {
                  await navigator.share({ title: "OpenMontage Drama Studio", url: link });
                } catch {
                  /* cancelled */
                }
              }}
            >
              <Share2 className="h-4 w-4" /> 系统分享
            </button>
          </div>
        </div>

        <aside className="panel space-y-2.5 p-3">
          <div className="flex items-center gap-2 text-[13px] font-semibold">
            <Users className="h-3.5 w-3.5 text-[#a78bfa]" /> 推荐玩法
          </div>
          {TIERS.map((tier) => (
            <div key={tier.title}>
              <strong className="block text-[12px]">{tier.title}</strong>
              <p className="mt-0.5 text-[12px] text-[var(--muted)]">{tier.desc}</p>
            </div>
          ))}
        </aside>
      </div>
    </PageShell>
  );
}
