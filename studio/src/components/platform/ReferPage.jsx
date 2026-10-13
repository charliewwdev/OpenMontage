import { Gift, Share2 } from "lucide-react";
import { toast } from "../../lib/toast";
import { PageShell } from "./PageShell";

export function ReferPage() {
  const link = typeof window !== "undefined" ? window.location.origin : "https://openmontage.dtok.io";

  return (
    <PageShell eyebrow="Refer" title="邀请好友" description="分享影视工坊链接，一起用六步流程做短剧。">
      <div className="panel max-w-xl p-6">
        <Gift className="h-8 w-8 text-[#a78bfa]" />
        <h3 className="mt-4 text-lg font-semibold">分享工作台地址</h3>
        <p className="mt-2 text-sm text-[var(--muted)]">对方打开后可自行配置 API Key，开始创作。</p>
        <code className="mt-4 block break-all rounded-xl bg-black/30 px-4 py-3 text-sm">{link}</code>
        <button
          type="button"
          className="btn-primary mt-4"
          onClick={async () => {
            await navigator.clipboard.writeText(link);
            toast.success("邀请链接已复制");
          }}
        >
          <Share2 className="h-4 w-4" /> 复制链接
        </button>
      </div>
    </PageShell>
  );
}
