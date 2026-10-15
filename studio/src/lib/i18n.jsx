import { createContext, use, useCallback, useEffect, useMemo, useState } from "react";

const LocaleContext = createContext(null);
const LOCALE_KEY = "om.studio.locale";

const FALLBACK = {
  zh: {},
  en: {},
};

/**
 * Key convention: module_feature_element
 * Examples: shell_nav_workshop_label, auth_page_submit_login, inspire_action_copy
 * Locale packs are per-language JSON; never put language codes inside the key.
 */

function interpolate(template, vars = {}) {
  return String(template ?? "").replace(/\{(\w+)\}/g, (_, key) => {
    if (vars[key] == null) return `{${key}}`;
    return String(vars[key]);
  });
}

/** Flatten nested locale objects into module_feature_element keys. */
export function flattenMessages(input, prefix = "", out = {}) {
  if (!input || typeof input !== "object" || Array.isArray(input)) return out;
  for (const [rawKey, value] of Object.entries(input)) {
    const part = String(rawKey).replace(/\./g, "_");
    const key = prefix ? `${prefix}_${part}` : part;
    if (value && typeof value === "object" && !Array.isArray(value)) {
      flattenMessages(value, key, out);
    } else if (value != null) {
      out[key] = String(value);
    }
  }
  return out;
}

function normalizePacks(messages = FALLBACK) {
  const next = {};
  for (const [locale, pack] of Object.entries(messages || {})) {
    if (!pack || typeof pack !== "object") {
      next[locale] = {};
      continue;
    }
    // Already flat underscore keys, or nested module trees.
    const looksNested = Object.values(pack).some((v) => v && typeof v === "object");
    next[locale] = looksNested ? flattenMessages(pack) : { ...pack };
  }
  return next;
}

export function LocaleProvider({ children, messages = FALLBACK, defaultLocale = "zh" }) {
  const packs = useMemo(() => normalizePacks(messages), [messages]);
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
    (key, vars, fallbackText) => {
      const id = String(key || "").replace(/\./g, "_");
      const pack = packs[locale] || packs.zh || {};
      const zh = packs.zh || {};
      const text = pack[id] ?? zh[id] ?? fallbackText ?? id;
      return interpolate(text, vars && typeof vars === "object" ? vars : {});
    },
    [locale, packs],
  );

  const value = useMemo(
    () => ({
      locale,
      setLocale,
      t,
      available: Object.keys(packs).length ? Object.keys(packs) : ["zh", "en"],
    }),
    [locale, setLocale, t, packs],
  );

  return <LocaleContext value={value}>{children}</LocaleContext>;
}

export function useLocale() {
  const ctx = use(LocaleContext);
  if (!ctx) {
    return {
      locale: "zh",
      setLocale: () => {},
      t: (key, _vars, fallbackText) => fallbackText ?? String(key || "").replace(/\./g, "_"),
      available: ["zh", "en"],
    };
  }
  return ctx;
}
