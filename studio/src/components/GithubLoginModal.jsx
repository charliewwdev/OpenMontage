import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { Github, Loader2, LogIn, X } from "lucide-react";
import { toast } from "../lib/toast";
import { fetchGithubGateStatus, startGithubLogin } from "../lib/githubGate";
import { tr, useLocale } from "../lib/i18n";

function resetTimeLabel(resetsAt) {
  if (!resetsAt) return "";
  try {
    return new Date(resetsAt * 1000).toLocaleString(undefined, {
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return "";
  }
}

/** Hosted instance: sign in with GitHub before generating; shows today's quota. */
export function GithubLoginModal({ open, reason = "login", onClose }) {
  useLocale();
  const [busy, setBusy] = useState(false);
  const [gate, setGate] = useState(null);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    fetchGithubGateStatus({ force: true })
      .then((g) => {
        if (!cancelled) setGate(g);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [open]);

  if (!open) return null;

  const quota = gate?.quota || null;
  const exhausted = reason === "quota" || Boolean(gate?.verified && quota?.limit && quota?.remaining === 0);
  const resetAt = resetTimeLabel(quota?.resetsAt);

  const signIn = async () => {
    setBusy(true);
    try {
      await startGithubLogin();
    } catch (error) {
      toast.error(String(error?.message || error));
      setBusy(false);
    }
  };

  return createPortal(
    <div className="fixed inset-0 z-[120] flex items-center justify-center bg-black/70 p-4" role="dialog" aria-modal="true">
      <div className="w-full max-w-md rounded-2xl border border-white/10 bg-[#12141c] p-5 shadow-[0_24px_80px_rgba(0,0,0,.55)]">
        <div className="mb-4 flex items-start justify-between gap-3">
          <div className="flex items-start gap-3">
            <div className="rounded-full bg-white/10 p-2 text-white">
              <Github className="h-5 w-5" />
            </div>
            <div>
              <h2 className="text-base font-semibold text-white">
                {exhausted ? tr("ui_github_quota_title") : tr("ui_github_login_title")}
              </h2>
              <p className="mt-1.5 text-sm leading-relaxed text-white/55">
                {exhausted
                  ? tr("ui_github_quota_body", { used: quota?.used ?? 0, limit: quota?.limit ?? 0, reset: resetAt })
                  : tr("ui_github_login_body")}
              </p>
            </div>
          </div>
          <button type="button" className="provider-icon-btn" onClick={onClose} aria-label="Close">
            <X className="h-4 w-4" />
          </button>
        </div>
        {quota && quota.limit ? (
          <p className="mb-4 text-xs text-white/45">
            {tr("ui_github_quota_line", {
              used: quota.used ?? 0,
              limit: quota.limit,
              videoUsed: quota.videoUsed ?? 0,
              videoLimit: quota.videoLimit || "∞",
            })}
          </p>
        ) : null}
        {exhausted ? (
          <p className="mb-1 text-xs leading-relaxed text-white/45">{tr("ui_github_quota_selfhost")}</p>
        ) : (
          <>
            <button type="button" className="btn-primary inline-flex w-full items-center justify-center gap-2 !min-h-10" disabled={busy} onClick={() => void signIn()}>
              {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <LogIn className="h-4 w-4" />}
              <span>{tr("ui_github_login_btn")}</span>
            </button>
            <p className="mt-3 text-[11px] leading-relaxed text-white/40">{tr("ui_github_login_privacy")}</p>
          </>
        )}
      </div>
    </div>,
    document.body,
  );
}
