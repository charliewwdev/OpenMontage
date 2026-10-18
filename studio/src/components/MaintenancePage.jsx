import { useEffect, useState } from "react";

/**
 * In-app standby when the API is unreachable (deploy / restart).
 * Complements public/maintenance.html used by nginx when upstream is down.
 */
export function MaintenancePage({ onRetry, brand = "OpenMontage" }) {
  const [tick, setTick] = useState(0);

  useEffect(() => {
    const id = window.setInterval(() => setTick((n) => n + 1), 6000);
    return () => window.clearInterval(id);
  }, []);

  useEffect(() => {
    if (tick === 0) return;
    onRetry?.();
  }, [tick, onRetry]);

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-[#05070d] text-[#e8f0ff]">
      <div
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            "radial-gradient(ellipse 90% 70% at 50% -10%, rgba(92,225,255,.12), transparent 55%), radial-gradient(ellipse 60% 50% at 100% 100%, rgba(139,124,255,.14), transparent 50%), linear-gradient(180deg,#0a0e18,#05070d)",
        }}
      />
      <div
        className="pointer-events-none absolute inset-0 opacity-70"
        style={{
          backgroundImage:
            "linear-gradient(rgba(92,225,255,.04) 1px, transparent 1px), linear-gradient(90deg, rgba(92,225,255,.04) 1px, transparent 1px)",
          backgroundSize: "48px 48px",
          maskImage: "radial-gradient(ellipse 70% 60% at 50% 45%, #000 20%, transparent 75%)",
        }}
        aria-hidden
      />

      <main className="relative z-[1] w-[min(460px,calc(100vw-2rem))] rounded-[20px] border border-[rgba(120,180,255,.18)] bg-[rgba(8,12,22,.72)] px-7 py-10 text-center shadow-[0_24px_80px_rgba(0,0,0,.45)] backdrop-blur-md">
        <div className="mb-5 inline-flex items-center gap-1.5 rounded-full border border-[rgba(92,225,255,.28)] bg-[rgba(92,225,255,.08)] px-3 py-1 text-[10px] uppercase tracking-[0.14em] text-[#5ce1ff]">
          <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-[#5ce1ff] shadow-[0_0_10px_#5ce1ff]" />
          System maintenance
        </div>
        <h1 className="text-[clamp(1.65rem,4vw,2.1rem)] font-semibold tracking-wide">
          {/\bMontage\b/i.test(brand) ? (
            <>
              {String(brand).replace(/Montage/i, "")}
              <span className="text-[#5ce1ff]">Montage</span>
            </>
          ) : (
            brand
          )}
        </h1>
        <p className="mt-3 text-sm leading-relaxed text-[rgba(200,220,255,.55)]">
          渲染集群热切换中，创作台暂时离线。
          <br />
          项目、密钥与成片均已保留，节点就绪后自动恢复。
        </p>
        <div className="mt-6 flex h-7 items-end justify-center gap-1" aria-hidden>
          {[40, 70, 100, 55, 85, 45, 65].map((h, i) => (
            <span
              key={i}
              className="w-1 animate-pulse rounded-sm bg-gradient-to-t from-[#8b7cff] to-[#5ce1ff]"
              style={{ height: `${h}%`, animationDelay: `${i * 0.1}s` }}
            />
          ))}
        </div>
        <div className="mt-6 flex flex-wrap justify-center gap-2.5">
          <button
            type="button"
            className="rounded-full border border-[rgba(120,180,255,.18)] bg-[rgba(92,225,255,.08)] px-4 py-2.5 text-sm text-[#e8f0ff] transition hover:border-[rgba(92,225,255,.5)] hover:bg-[rgba(92,225,255,.16)]"
            onClick={() => onRetry?.()}
          >
            重新探测节点
          </button>
        </div>
        <p className="mt-6 text-[10px] uppercase tracking-[0.12em] text-[rgba(200,220,255,.32)]">link · standby</p>
      </main>
    </div>
  );
}
