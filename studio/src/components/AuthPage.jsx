import { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Clapperboard, Loader2 } from "lucide-react";
import { api } from "../api";
import { setSession } from "../lib/auth";
import { renderGoogleButton } from "../lib/googleAuth";
import { useLocale } from "../lib/i18n";
import { toast } from "../lib/toast";

const SKIP_AUTO_DEMO_KEY = "om.studio.skipAutoDemo";

function Field({ label, children }) {
  return (
    <label className="block space-y-1.5">
      <span className="text-xs text-white/55">{label}</span>
      {children}
    </label>
  );
}

const inputClass =
  "w-full rounded-xl border border-[var(--line)] bg-white/[.04] px-3 py-2.5 text-sm text-white outline-none focus:border-[#7c6cff]/60";

function demoPrefill(authConfig) {
  const demo = authConfig?.demo || {};
  if (demo.prefill === false) {
    return { username: "", password: "" };
  }
  return {
    username: demo.username || "demo",
    password: demo.password || "demo",
  };
}

function isDemoCredentials(form, authConfig) {
  const demo = authConfig?.demo || {};
  const user = (demo.username || "demo").trim().toLowerCase();
  const pass = demo.password || "demo";
  return form.username.trim().toLowerCase() === user && form.password === pass;
}

export function AuthPage({ brand, tagline, authConfig, onAuthed, onClose, mode = "page" }) {
  const { t, locale, setLocale } = useLocale();
  const demoEnabled = authConfig?.demo?.enabled !== false;
  const googleCfg = authConfig?.google || {};
  const googleEnabled = Boolean(googleCfg.enabled && googleCfg.clientId);
  const isModal = mode === "modal";
  const [busy, setBusy] = useState(false);
  const [googleBusy, setGoogleBusy] = useState(false);
  const [form, setForm] = useState(() => demoPrefill(authConfig));
  const googleBtnRef = useRef(null);
  const autoStarted = useRef(false);

  useEffect(() => {
    setForm(demoPrefill(authConfig));
  }, [authConfig]);

  const setField = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }));

  const finish = (payload) => {
    const data = payload?.data || payload || {};
    const token = data.token || data.accessToken || "";
    if (!token) throw new Error(payload?.error || "missing token");
    try {
      sessionStorage.removeItem(SKIP_AUTO_DEMO_KEY);
    } catch {
      /* ignore */
    }
    setSession({
      token,
      user: {
        userId: data.userId,
        username: data.username || form.username || "user",
        avatar: data.avatar || "",
        expiresIn: data.expiresIn,
        demo: Boolean(data.demo),
      },
    });
    onAuthed?.(data);
  };

  const enterDemo = useCallback(async () => {
    const res = await api("/api/auth/demo", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    });
    finish(res);
    toast.success(t("auth_page_demo_ok"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [t]);

  useEffect(() => {
    if (!demoEnabled || !authConfig?.demo?.autoEnter || autoStarted.current) return;
    let skip = false;
    try {
      skip = sessionStorage.getItem(SKIP_AUTO_DEMO_KEY) === "1";
    } catch {
      skip = false;
    }
    if (skip) return;
    autoStarted.current = true;
    setBusy(true);
    void enterDemo()
      .catch((err) => toast.error(String(err.message || err)))
      .finally(() => setBusy(false));
  }, [demoEnabled, authConfig?.demo?.autoEnter, enterDemo]);

  const onGoogleCredential = useCallback(
    async (idToken) => {
      setGoogleBusy(true);
      try {
        const res = await api("/api/auth/social/google", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ idToken, client: "WEB" }),
        });
        finish(res);
        toast.success(t("auth_page_google_ok"));
      } catch (err) {
        toast.error(String(err.message || err));
      } finally {
        setGoogleBusy(false);
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [t],
  );

  useEffect(() => {
    if (!googleEnabled || !googleBtnRef.current) return undefined;
    return renderGoogleButton(googleBtnRef.current, {
      clientId: googleCfg.clientId,
      locale,
      onCredential: (token) => void onGoogleCredential(token),
      onError: (err) => toast.error(String(err.message || err || t("auth_page_google_fail"))),
    });
  }, [googleEnabled, googleCfg.clientId, locale, onGoogleCredential, t]);

  const onSubmit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      if (demoEnabled && isDemoCredentials(form, authConfig)) {
        await enterDemo();
      } else {
        const res = await api("/api/auth/login", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            username: form.username.trim(),
            password: form.password,
            client: "WEB",
          }),
        });
        finish(res);
        toast.success(t("auth_page_submit_login"));
      }
    } catch (err) {
      toast.error(String(err.message || err));
    } finally {
      setBusy(false);
    }
  };

  const content = (
    <div
      className={
        isModal
          ? "fixed inset-0 z-[80] flex items-center justify-center overflow-y-auto bg-black/70 px-4 py-8 backdrop-blur-sm"
          : "relative flex min-h-screen items-center justify-center overflow-hidden bg-[var(--stage)] px-4 text-[var(--ink)]"
      }
      style={isModal ? { left: 0, top: 0, right: 0, bottom: 0 } : undefined}
      role={isModal ? "dialog" : undefined}
      aria-modal={isModal ? true : undefined}
      onClick={isModal && onClose ? (e) => { if (e.target === e.currentTarget) onClose(); } : undefined}
    >
      {!isModal ? (
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_top,_rgba(124,108,255,.22),_transparent_55%),radial-gradient(ellipse_at_bottom,_rgba(56,189,248,.12),_transparent_50%)]" />
      ) : null}
      <div className="relative w-full max-w-md rounded-2xl border border-[var(--line)] bg-[#0c0d14]/95 p-4 text-[var(--ink)] shadow-[0_24px_60px_rgba(0,0,0,.45)] backdrop-blur md:p-5">
        <div className="mb-4 flex items-start justify-between gap-2">
          <div className="flex items-center gap-2.5">
            <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-[var(--gradient)] text-white shadow-[0_0_20px_rgba(124,108,255,.35)]">
              <Clapperboard className="h-4 w-4" />
            </span>
            <div>
              <div className="text-[13px] font-semibold tracking-wide">{brand || "OpenMontage"}</div>
              <div className="text-[11px] text-[var(--muted)]">{tagline || t("shell_brand_tagline")}</div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex rounded-lg border border-[var(--line)] p-0.5 text-[11px]">
              <button
                type="button"
                className={`rounded-md px-2 py-1 ${locale === "zh" ? "bg-white/10 text-white" : "text-white/50"}`}
                onClick={() => setLocale("zh")}
              >
                {t("shell_locale_zh")}
              </button>
              <button
                type="button"
                className={`rounded-md px-2 py-1 ${locale === "en" ? "bg-white/10 text-white" : "text-white/50"}`}
                onClick={() => setLocale("en")}
              >
                {t("shell_locale_en")}
              </button>
            </div>
            {isModal && onClose ? (
              <button
                type="button"
                className="rounded-lg px-2 py-1 text-xs text-white/45 hover:bg-white/[.06] hover:text-white"
                onClick={onClose}
              >
                {t("auth_page_close")}
              </button>
            ) : null}
          </div>
        </div>

        <h1 className="text-[1.1rem] font-semibold">{t("auth_page_welcome")}</h1>
        <p className="mt-1 text-[12px] text-white/55">{isModal ? t("auth_page_subtitle_modal") : t("auth_page_subtitle")}</p>

        <form className="mt-4 space-y-2.5" onSubmit={onSubmit}>
          <Field label={t("auth_page_username")}>
            <input
              className={inputClass}
              value={form.username}
              onChange={setField("username")}
              autoComplete="username"
              required
            />
          </Field>
          <Field label={t("auth_page_password")}>
            <input
              className={inputClass}
              type="password"
              value={form.password}
              onChange={setField("password")}
              autoComplete="current-password"
              required
            />
          </Field>
          {demoEnabled ? (
            <p className="text-[11px] text-white/40">{t("auth_page_demo_hint")}</p>
          ) : null}
          <button type="submit" className="btn-primary mt-2 w-full" disabled={busy || googleBusy}>
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
            {t("auth_page_submit_login")}
          </button>
        </form>

        {googleEnabled ? (
          <div className="mt-5 space-y-2">
            <div className="flex items-center gap-3 text-[11px] text-white/30">
              <span className="h-px flex-1 bg-white/10" />
              <span>{t("auth_page_google_hint")}</span>
              <span className="h-px flex-1 bg-white/10" />
            </div>
            <div className="flex min-h-[44px] items-center justify-center" ref={googleBtnRef} />
            {googleBusy ? (
              <p className="flex items-center justify-center gap-2 text-[11px] text-white/45">
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                {t("auth_page_google_busy")}
              </p>
            ) : null}
          </div>
        ) : null}

        <p className="mt-4 text-center text-[11px] text-white/35">
          {isModal ? t("auth_page_modal_hint") : t("auth_page_required_hint")}
        </p>
      </div>
    </div>
  );

  if (isModal && typeof document !== "undefined") {
    return createPortal(content, document.body);
  }
  return content;
}

export { SKIP_AUTO_DEMO_KEY };
