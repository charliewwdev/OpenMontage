import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { ExternalLink, Loader2, ShieldCheck, Star, X } from "lucide-react";
import { api } from "../api";
import { toast } from "../lib/toast";
import { clearGithubStarCache, fetchGithubStarStatus } from "../lib/githubStar";
import { tr, useLocale } from "../lib/i18n";

export function GithubStarModal({ open, onClose, onVerified }) {
  useLocale();
  const [login, setLogin] = useState("");
  const [busy, setBusy] = useState(false);
  const [gate, setGate] = useState(null);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    fetchGithubStarStatus({ force: true })
      .then((g) => {
        if (!cancelled) {
          setGate(g);
          if (g?.login) setLogin(g.login);
        }
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [open]);

  if (!open) return null;

  const starUrl = gate?.starUrl || "https://github.com/charliewwdev/OpenMontage";

  const verify = async () => {
    const name = String(login || "").trim().replace(/^@/, "");
    if (!name) {
      toast.error(tr("ui_keys_star_enter_username"));
      return;
    }
    setBusy(true);
    try {
      const data = await api("/api/settings/github-star/verify", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ login: name }),
      });
      clearGithubStarCache();
      toast.success(tr("ui_keys_star_verified"));
      onVerified?.(data);
      onClose?.();
    } catch (error) {
      toast.error(String(error.message || error));
    } finally {
      setBusy(false);
    }
  };

  return createPortal(
    <div className="fixed inset-0 z-[120] flex items-center justify-center bg-black/70 p-4" role="dialog" aria-modal="true">
      <div className="w-full max-w-md rounded-2xl border border-white/10 bg-[#12141c] p-5 shadow-[0_24px_80px_rgba(0,0,0,.55)]">
        <div className="mb-4 flex items-start justify-between gap-3">
          <div className="flex items-start gap-3">
            <div className="rounded-full bg-amber-500/15 p-2 text-amber-300">
              <Star className="h-5 w-5" />
            </div>
            <div>
              <h2 className="text-base font-semibold text-white">{tr("ui_keys_star_gen_title")}</h2>
              <p className="mt-1.5 text-sm leading-relaxed text-white/55">{tr("ui_keys_star_gen_body")}</p>
            </div>
          </div>
          <button type="button" className="provider-icon-btn" onClick={onClose} aria-label="Close">
            <X className="h-4 w-4" />
          </button>
        </div>
        <ol className="mb-4 list-decimal space-y-1.5 pl-5 text-sm text-white/75">
          <li>{tr("ui_keys_star_step_star")}</li>
          <li>{tr("ui_keys_star_step_username")}</li>
          <li>{tr("ui_keys_star_step_verify")}</li>
        </ol>
        <a
          className="btn-secondary mb-3 inline-flex w-full items-center justify-center gap-2 !min-h-10"
          href={starUrl}
          target="_blank"
          rel="noreferrer"
        >
          <ExternalLink className="h-4 w-4" />
          {tr("ui_keys_star_open_repo")}
        </a>
        <div className="flex flex-col gap-2 sm:flex-row">
          <input
            className="field flex-1"
            placeholder={tr("ui_keys_star_username_placeholder")}
            value={login}
            onChange={(e) => setLogin(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") void verify();
            }}
          />
          <button type="button" className="btn-primary !min-h-10 !px-4" disabled={busy} onClick={() => void verify()}>
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <ShieldCheck className="h-4 w-4" />}
            <span>{tr("ui_keys_star_verify_btn")}</span>
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
