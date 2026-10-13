import { useCallback, useEffect, useState } from "react";
import { Clapperboard, Loader2, RefreshCw, Sparkles } from "lucide-react";
import { api } from "../api";
import { setSession } from "../lib/auth";
import { useLocale } from "../lib/i18n";
import { toast } from "../lib/toast";

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

export function AuthPage({ brand, tagline, authConfig, onAuthed }) {
  const { t, locale, setLocale } = useLocale();
  const demoEnabled = authConfig?.demo?.enabled !== false;
  const [mode, setMode] = useState("login");
  const [busy, setBusy] = useState(false);
  const [demoBusy, setDemoBusy] = useState(false);
  const [captcha, setCaptcha] = useState({ uuid: "", imageUrl: "" });
  const [providers, setProviders] = useState([]);
  const [form, setForm] = useState({
    username: "",
    email: "",
    password: "",
    phone: "",
    code: "",
    captcha: "",
  });

  const loadCaptcha = useCallback(async () => {
    try {
      const res = await api("/api/auth/captcha");
      const data = res?.data || res;
      setCaptcha({
        uuid: data?.uuid || "",
        imageUrl: data?.imageUrl || data?.img || "",
      });
    } catch {
      setCaptcha({ uuid: "", imageUrl: "" });
    }
  }, []);

  useEffect(() => {
    void loadCaptcha();
    api("/api/auth/social-providers")
      .then((res) => setProviders(res?.data || res?.providers || []))
      .catch(() => setProviders([]));
  }, [loadCaptcha]);

  const setField = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }));

  const finish = (payload) => {
    const data = payload?.data || payload || {};
    const token = data.token || data.accessToken || "";
    if (!token) throw new Error(payload?.error || "missing token");
    setSession({
      token,
      user: {
        userId: data.userId,
        username: data.username || form.username || form.email || form.phone,
        avatar: data.avatar || "",
        expiresIn: data.expiresIn,
        demo: Boolean(data.demo),
      },
    });
    onAuthed?.(data);
  };

  const enterDemo = async () => {
    setDemoBusy(true);
    try {
      const res = await api("/api/auth/demo", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: "{}",
      });
      finish(res);
      toast.success(t("auth.demoOk"));
    } catch (err) {
      toast.error(String(err.message || err));
    } finally {
      setDemoBusy(false);
    }
  };

  useEffect(() => {
    if (!demoEnabled || !authConfig?.demo?.autoEnter) return;
    void enterDemo();
    // intentionally only on mount when autoEnter is configured
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [demoEnabled, authConfig?.demo?.autoEnter]);

  const onSubmit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      let res;
      if (mode === "login") {
        res = await api("/api/auth/login", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            username: form.username.trim(),
            password: form.password,
            captcha: form.captcha.trim() || undefined,
            uuid: captcha.uuid || undefined,
            client: "WEB",
          }),
        });
      } else if (mode === "register") {
        res = await api("/api/auth/register", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            username: form.username.trim() || form.email.trim(),
            email: form.email.trim() || undefined,
            password: form.password,
            phone: form.phone.trim() || undefined,
            captcha: form.captcha.trim() || undefined,
          }),
        });
      } else {
        res = await api("/api/auth/phone-login", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            phone: form.phone.trim(),
            code: form.code.trim(),
          }),
        });
      }
      finish(res);
      toast.success(t("auth.submitLogin"));
    } catch (err) {
      toast.error(String(err.message || err));
      void loadCaptcha();
    } finally {
      setBusy(false);
    }
  };

  const sendCode = async () => {
    if (!form.phone.trim()) {
      toast.error(t("auth.phoneNumber"));
      return;
    }
    try {
      await api("/api/auth/send-code", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          phone: form.phone.trim(),
          type: mode === "register" ? "register" : "login",
        }),
      });
      toast.success(t("auth.sendCode"));
    } catch (err) {
      toast.error(String(err.message || err));
    }
  };

  const tabs = [
    { id: "login", label: t("auth.login") },
    { id: "register", label: t("auth.register") },
    { id: "phone", label: t("auth.phone") },
  ];

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-[var(--stage)] px-4 text-[var(--ink)]">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_top,_rgba(124,108,255,.22),_transparent_55%),radial-gradient(ellipse_at_bottom,_rgba(56,189,248,.12),_transparent_50%)]" />
      <div className="relative w-full max-w-md rounded-3xl border border-[var(--line)] bg-[#0c0d14]/90 p-6 shadow-[0_30px_80px_rgba(0,0,0,.45)] backdrop-blur">
        <div className="mb-6 flex items-start justify-between gap-3">
          <div className="flex items-center gap-3">
            <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-[var(--gradient)] text-white shadow-[0_0_28px_rgba(124,108,255,.4)]">
              <Clapperboard className="h-5 w-5" />
            </span>
            <div>
              <div className="text-base font-semibold tracking-wide">{brand || "OpenMontage"}</div>
              <div className="text-xs text-[var(--muted)]">{tagline || t("app.tagline")}</div>
            </div>
          </div>
          <div className="flex rounded-lg border border-[var(--line)] p-0.5 text-[11px]">
            <button
              type="button"
              className={`rounded-md px-2 py-1 ${locale === "zh" ? "bg-white/10 text-white" : "text-white/50"}`}
              onClick={() => setLocale("zh")}
            >
              {t("lang.zh")}
            </button>
            <button
              type="button"
              className={`rounded-md px-2 py-1 ${locale === "en" ? "bg-white/10 text-white" : "text-white/50"}`}
              onClick={() => setLocale("en")}
            >
              {t("lang.en")}
            </button>
          </div>
        </div>

        <h1 className="text-xl font-semibold">{t("auth.welcome")}</h1>
        <p className="mt-1 text-sm text-white/55">{t("auth.subtitle")}</p>

        {demoEnabled ? (
          <div className="mt-5 space-y-2">
            <button
              type="button"
              className="btn-primary flex w-full items-center justify-center gap-2"
              disabled={demoBusy || busy}
              onClick={() => void enterDemo()}
            >
              {demoBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
              {demoBusy ? t("auth.demoBusy") : t("auth.demoEnter")}
            </button>
            <p className="text-center text-[11px] text-white/40">{t("auth.demoHint")}</p>
            <div className="flex items-center gap-3 py-1 text-[11px] text-white/30">
              <span className="h-px flex-1 bg-white/10" />
              <span>{t("auth.orAccount")}</span>
              <span className="h-px flex-1 bg-white/10" />
            </div>
          </div>
        ) : null}

        <div className="mt-2 flex gap-1 rounded-xl border border-[var(--line)] bg-white/[.03] p-1">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              type="button"
              className={`flex-1 rounded-lg px-2 py-2 text-xs transition ${
                mode === tab.id ? "bg-[var(--gradient)] text-white" : "text-white/55 hover:text-white"
              }`}
              onClick={() => setMode(tab.id)}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <form className="mt-5 space-y-3" onSubmit={onSubmit}>
          {mode !== "phone" ? (
            <>
              <Field label={t("auth.username")}>
                <input className={inputClass} value={form.username} onChange={setField("username")} autoComplete="username" required={mode === "login"} />
              </Field>
              {mode === "register" ? (
                <Field label={t("auth.email")}>
                  <input className={inputClass} type="email" value={form.email} onChange={setField("email")} autoComplete="email" />
                </Field>
              ) : null}
              <Field label={t("auth.password")}>
                <input className={inputClass} type="password" value={form.password} onChange={setField("password")} autoComplete={mode === "register" ? "new-password" : "current-password"} required />
              </Field>
              {mode === "register" ? (
                <Field label={t("auth.phoneNumber")}>
                  <input className={inputClass} value={form.phone} onChange={setField("phone")} autoComplete="tel" />
                </Field>
              ) : null}
            </>
          ) : (
            <>
              <Field label={t("auth.phoneNumber")}>
                <input className={inputClass} value={form.phone} onChange={setField("phone")} autoComplete="tel" required />
              </Field>
              <Field label={t("auth.code")}>
                <div className="flex gap-2">
                  <input className={inputClass} value={form.code} onChange={setField("code")} required />
                  <button type="button" className="btn-secondary shrink-0 !min-h-10" onClick={() => void sendCode()}>
                    {t("auth.sendCode")}
                  </button>
                </div>
              </Field>
            </>
          )}

          {mode !== "phone" ? (
            <Field label={t("auth.captcha")}>
              <div className="flex gap-2">
                <input className={inputClass} value={form.captcha} onChange={setField("captcha")} autoComplete="off" />
                <button type="button" className="btn-secondary shrink-0 !min-h-10 !px-3" onClick={() => void loadCaptcha()} title={t("auth.refreshCaptcha")}>
                  {captcha.imageUrl ? (
                    <img src={captcha.imageUrl} alt="captcha" className="h-8 w-20 rounded object-cover" />
                  ) : (
                    <RefreshCw className="h-4 w-4" />
                  )}
                </button>
              </div>
            </Field>
          ) : null}

          <button type="submit" className="btn-primary mt-2 w-full" disabled={busy || demoBusy}>
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
            {mode === "login" ? t("auth.submitLogin") : mode === "register" ? t("auth.submitRegister") : t("auth.submitPhone")}
          </button>
        </form>

        {providers?.length ? (
          <p className="mt-4 text-center text-[11px] text-white/35">
            {t("auth.socialHint")} {providers.map((p) => p.displayName || p.provider).join(" · ")}
          </p>
        ) : (
          <p className="mt-4 text-center text-[11px] text-white/35">{t("auth.requiredHint")}</p>
        )}
      </div>
    </div>
  );
}
