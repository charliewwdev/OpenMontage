import { useEffect, useState } from "react";

/**
 * In-app standby when the API is unreachable (deploy / restart).
 * Complements public/maintenance.html used by nginx on hard 502.
 */
export function MaintenancePage({ onRetry, brand = "OpenMontage" }) {
  const [tick, setTick] = useState(0);

  useEffect(() => {
    const id = window.setInterval(() => setTick((n) => n + 1), 8000);
    return () => window.clearInterval(id);
  }, []);

  useEffect(() => {
    if (tick === 0) return;
    onRetry?.();
  }, [tick, onRetry]);

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-[#0c0e14] text-[#f4f1ea]">
      <div
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            "radial-gradient(ellipse 80% 60% at 20% 20%, rgba(232,196,124,.14), transparent 55%), radial-gradient(ellipse 70% 50% at 85% 75%, rgba(90,140,180,.12), transparent 50%), linear-gradient(165deg,#12151e,#0c0e14 45%,#151018)",
        }}
      />
      <div className="om-maint-orb om-maint-orb-a" aria-hidden />
      <div className="om-maint-orb om-maint-orb-b" aria-hidden />
      <div className="om-maint-grain" aria-hidden />

      <main className="relative z-[1] w-[min(440px,calc(100vw-2.5rem))] px-2 text-center">
        <div className="om-maint-mark mx-auto mb-5 flex h-16 w-16 items-center justify-center rounded-[18px] border border-white/10 bg-[linear-gradient(145deg,rgba(232,196,124,.25),rgba(232,196,124,.05))]">
          <img src="/favicon.svg" alt="" className="h-9 w-9" width={36} height={36} />
        </div>
        <h1 className="font-serif text-[clamp(1.75rem,4vw,2.25rem)] font-semibold tracking-wide">
          {/\bMontage\b/i.test(brand) ? (
            <>
              {String(brand).replace(/Montage/i, "")}
              <span className="text-[#e8c47c]">Montage</span>
            </>
          ) : (
            brand
          )}
        </h1>
        <p className="mt-3 text-sm leading-relaxed text-white/55">
          工坊正在换幕检修，片刻后继续创作。
          <br />
          影片还在，密钥还在，稍等镜头归位。
        </p>
        <div className="om-maint-reel mt-7 flex justify-center gap-1.5" aria-hidden>
          <span />
          <span />
          <span />
          <span />
          <span />
        </div>
        <div className="mt-7 flex flex-wrap justify-center gap-2.5">
          <button
            type="button"
            className="rounded-full border border-white/15 bg-white/[.06] px-4 py-2.5 text-sm text-white transition hover:border-[#e8c47c]/45 hover:bg-[#e8c47c]/15"
            onClick={() => onRetry?.()}
          >
            重新连接
          </button>
        </div>
        <p className="mt-6 text-[10px] uppercase tracking-[0.12em] text-white/30">standby · openmontage</p>
      </main>
    </div>
  );
}
