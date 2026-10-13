import { Coins } from "lucide-react";
import { PageShell } from "./PageShell";

export function CreditsPage({ config }) {
  const caps = config?.capabilities || {};
  const ready = [caps.deepseek, caps.seedream, caps.seedance].filter(Boolean).length;

  return (
    <PageShell eyebrow="Credits" title="积分与额度" description="本地部署版按你自己的 API 额度计费；此处展示能力就绪状态。">
      <div className="grid gap-3 md:grid-cols-3">
        <article className="panel p-5">
          <Coins className="h-5 w-5 text-[#fbbf24]" />
          <strong className="mt-3 block text-2xl">{ready}/3</strong>
          <p className="mt-1 text-sm text-[var(--muted)]">模型能力已就绪</p>
        </article>
        <article className="panel p-5">
          <strong className="block text-2xl">自有 Key</strong>
          <p className="mt-1 text-sm text-[var(--muted)]">费用发生在 DeepSeek / 火山账户</p>
        </article>
        <article className="panel p-5">
          <strong className="block text-2xl">无限项目</strong>
          <p className="mt-1 text-sm text-[var(--muted)]">本地 PROJECTS_ROOT 存储，无平台抽成</p>
        </article>
      </div>
      <div className="panel mt-4 p-5 text-sm leading-7 text-[var(--muted)]">
        <p>DeepSeek：剧本生成 / 续写 / 定稿</p>
        <p>Seedream：角色、场景、道具出图</p>
        <p>Seedance：分镜视频生成</p>
      </div>
    </PageShell>
  );
}
