import { createContext, use, useCallback, useEffect, useMemo, useState } from "react";

const LocaleContext = createContext(null);
const LOCALE_KEY = "om.studio.locale";

const FALLBACK = {
  zh: {},
  en: {},
};

function interpolate(template, vars = {}) {
  return String(template ?? "").replace(/\{(\w+)\}/g, (_, key) => {
    if (vars[key] == null) return `{${key}}`;
    return String(vars[key]);
  });
}

export function LocaleProvider({ children, messages = FALLBACK, defaultLocale = "zh" }) {
  const [locale, setLocaleState] = useState(() => {
    try {
      return localStorage.getItem(LOCALE_KEY) || defaultLocale || "zh";
    } catch {
      return defaultLocale || "zh";
    }
  });

  useEffect(() => {
    try {
      localStorage.setItem(LOCALE_KEY, locale);
    } catch {
      /* ignore */
    }
    if (typeof document !== "undefined") {
      document.documentElement.lang = locale === "en" ? "en" : "zh-CN";
    }
  }, [locale]);

  const setLocale = useCallback((next) => {
    setLocaleState(next === "en" ? "en" : "zh");
  }, []);

  const t = useCallback(
    (key, vars) => {
      const pack = messages[locale] || messages.zh || {};
      const fallback = messages.zh || {};
      const text = pack[key] ?? fallback[key] ?? key;
      return interpolate(text, vars);
    },
    [locale, messages],
  );

  const value = useMemo(
    () => ({
      locale,
      setLocale,
      t,
      available: Object.keys(messages).length ? Object.keys(messages) : ["zh", "en"],
    }),
    [locale, setLocale, t, messages],
  );

  return <LocaleContext value={value}>{children}</LocaleContext>;
}

export function useLocale() {
  const ctx = use(LocaleContext);
  if (!ctx) {
    return {
      locale: "zh",
      setLocale: () => {},
      t: (key) => key,
      available: ["zh", "en"],
    };
  }
  return ctx;
}
