import { useEffect, useMemo, useState } from "react";
import { Copy, Gift, Share2, Users } from "lucide-react";
import { api } from "../../api";
import { toast } from "../../lib/toast";
import { PageShell } from "./PageShell";

import { tr, useLocale } from "../../lib/i18n";

const TIERS = [
  {
    get title() {
      return tr("ui_refer_share_the_link");
    },

    get desc() {
      return tr("ui_refer_send_the_link_with_your_invite");
    }
  },
  {
    get title() {
      return tr("ui_refer_collaborative_production");
    },

    get desc() {
      return tr("ui_refer_one_deployment_can_serve_several_people");
    }
  },
  {
    get title() {
      return tr("ui_refer_invite_reward");
    },

    get desc() {
      return tr("ui_refer_20_creator_credits_when_someone_opens");
    }
  },
];

const REF_CAPTURE_KEY = "om.refer.captured";

export function ReferPage({ config }) {
  useLocale();
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
        toast.success(tr("ui_refer_invite_recorded_creator_credits_20"));
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
    <PageShell eyebrow="Refer" title={tr("ui_refer_referral_program")} description={tr("ui_refer_share_the_film_workshop_and_invite")}>
      <div className="grid gap-4 lg:grid-cols-[1.2fr_0.8fr]">
        <div className="panel p-6">
          <Gift className="h-8 w-8 text-[#a78bfa]" />
          <h3 className="mt-4 text-lg font-semibold">{tr("ui_refer_share_the_studio_link")}</h3>
          <p className="mt-2 text-sm text-[var(--muted)]">{tr("ui_refer_the_link_includes_your_invite_code")}</p>
          <code className="mt-4 block break-all rounded-xl bg-black/30 px-4 py-3 text-sm">{link || tr("ui_refer_loading")}</code>
          <div className="mt-3 text-xs text-[var(--muted)]">{tr("ui_refer_invited_times_credit_balance", {
              0: credits?.referrals ?? 0,
              1: credits?.balance ?? 0
            })}</div>
          <div className="mt-4 flex flex-wrap gap-2">
            <button
              type="button"
              className="btn-primary"
              disabled={!link}
              onClick={async () => {
                await navigator.clipboard.writeText(link);
                toast.success(tr("ui_refer_invite_link_copied"));
              }}
            >
              <Copy className="h-4 w-4" />{" "}{tr("ui_refer_copy_link")}</button>
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
              <Share2 className="h-4 w-4" />{" "}{tr("ui_refer_system_share")}</button>
          </div>
        </div>

        <aside className="panel space-y-4 p-5">
          <div className="flex items-center gap-2 text-sm font-semibold">
            <Users className="h-4 w-4 text-[#a78bfa]" />{" "}{tr("ui_refer_ideas")}</div>
          {TIERS.map((tier) => (
            <div key={tier.title}>
              <strong className="block text-sm">{tier.title}</strong>
              <p className="mt-1 text-sm text-[var(--muted)]">{tier.desc}</p>
            </div>
          ))}
        </aside>
      </div>
    </PageShell>
  );
}
