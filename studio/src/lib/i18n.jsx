import { createContext, use, useCallback, useEffect, useMemo, useSyncExternalStore } from "react";
import bundledZh from "../../config/locales/zh.json";
import bundledEn from "../../config/locales/en.json";

const LocaleContext = createContext(null);
const LOCALE_KEY = "om.studio.locale";
const SUPPORTED = ["zh", "en"];

// Bundled packs make tr() usable before /api/config arrives (module-level
// labels, first paint). Server packs from /api/config are merged on top.
const FALLBACK = {
  zh: bundledZh,
  en: bundledEn,
};

/**
 * Key convention: module_feature_element
 * Examples: shell_nav_workshop_label, auth_page_submit_login, inspire_action_copy
 * Locale packs are per-language JSON (studio/config/locales/*.json); never put
 * language codes inside the key.
 *
 * Two ways to translate:
 *   - inside React components: `const { t } = useLocale(); t("key")`
 *   - anywhere else (helpers, toasts, module-level getters): `tr("key")`
 * Both read the same packs and the same persisted locale. Components that
 * render `tr(...)` output should call `useLocale()` so they re-render when the
 * language changes.
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

function mergePacks(base, extra) {
  const out = { ...base };
  for (const [locale, pack] of Object.entries(extra || {})) {
    out[locale] = { ...(base[locale] || {}), ...(pack || {}) };
  }
  return out;
}

const BUNDLED = normalizePacks(FALLBACK);

function normalizeLocale(value) {
  return value === "en" ? "en" : "zh";
}

function readStoredLocale() {
  try {
    const raw = localStorage.getItem(LOCALE_KEY);
    return SUPPORTED.includes(raw) ? raw : null;
  } catch {
    return null;
  }
}

/* ------------------------------------------------------------------ */
/* Module-level store: one locale + one set of packs for the whole app. */
/* ------------------------------------------------------------------ */

const store = {
  locale: readStoredLocale() || "zh",
  explicit: Boolean(readStoredLocale()),
  packs: BUNDLED,
  version: 0,
  listeners: new Set(),
};

/** Module-level arrays/objects built with tr(); rebuilt in place on change. */
const localizedTargets = [];

function refreshLocalized() {
  for (const entry of localizedTargets) {
    const fresh = entry.factory();
    const target = entry.target;
    if (Array.isArray(target)) {
      target.splice(0, target.length, ...fresh);
    } else {
      for (const key of Object.keys(target)) delete target[key];
      Object.defineProperties(target, Object.getOwnPropertyDescriptors(fresh));
    }
  }
}

/**
 * Build a module-level array or object whose labels come from tr(). The
 * returned value keeps its identity and is refilled whenever the language or
 * the packs change, so imports stay valid.
 */
export function localized(factory) {
  const target = factory();
  if (target && typeof target === "object") localizedTargets.push({ factory, target });
  return target;
}

function emit() {
  refreshLocalized();
  store.version += 1;
  for (const fn of store.listeners) fn();
}

function subscribe(fn) {
  store.listeners.add(fn);
  return () => store.listeners.delete(fn);
}

function getSnapshot() {
  return store.version;
}

function applyDocumentLang(locale) {
  if (typeof document !== "undefined") {
    document.documentElement.lang = locale === "en" ? "en" : "zh-CN";
  }
}

export function getLocale() {
  return store.locale;
}

export function setLocale(next) {
  const locale = normalizeLocale(next);
  store.explicit = true;
  try {
    localStorage.setItem(LOCALE_KEY, locale);
  } catch {
    /* ignore */
  }
  applyDocumentLang(locale);
  if (store.locale !== locale) {
    store.locale = locale;
    emit();
  }
}

/** Translate outside React render (toasts, helpers, module-level getters). */
export function tr(key, vars, fallbackText) {
  const id = String(key || "").replace(/\./g, "_");
  const pack = store.packs[store.locale] || store.packs.zh || {};
  const zh = store.packs.zh || {};
  const text = pack[id] ?? zh[id] ?? fallbackText ?? id;
  return interpolate(text, vars && typeof vars === "object" ? vars : {});
}

/** Pick the localized variant of a `{ zh, en }` pair (falls back to zh). */
export function pickLocale(pair) {
  if (pair == null || typeof pair !== "object") return pair;
  return pair[store.locale] ?? pair.zh ?? "";
}

export function LocaleProvider({ children, messages, defaultLocale = "zh" }) {
  const packs = useMemo(() => mergePacks(BUNDLED, normalizePacks(messages || {})), [messages]);
  // Packs must be visible to tr() before children render.
  let changed = false;
  if (store.packs !== packs) {
    store.packs = packs;
    changed = true;
  }
  if (!store.explicit && defaultLocale && store.locale !== normalizeLocale(defaultLocale)) {
    store.locale = normalizeLocale(defaultLocale);
    changed = true;
  }
  if (changed) refreshLocalized();

  useSyncExternalStore(subscribe, getSnapshot, getSnapshot);
  const locale = store.locale;

  useEffect(() => {
    applyDocumentLang(locale);
  }, [locale]);

  useEffect(() => {
    // Packs arrive with /api/config; let subscribed components refresh.
    emit();
  }, [packs]);

  const t = useCallback(
    (key, vars, fallbackText) => tr(key, vars, fallbackText),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [locale, packs],
  );

  const value = useMemo(
    () => ({
      locale,
      setLocale,
      t,
      available: Object.keys(packs).length ? Object.keys(packs) : SUPPORTED,
    }),
    [locale, t, packs],
  );

  return <LocaleContext value={value}>{children}</LocaleContext>;
}

/**
 * Subscribe the calling component to locale changes.
 * Works with or without a surrounding <LocaleProvider>.
 */
export function useLocale() {
  const ctx = use(LocaleContext);
  useSyncExternalStore(subscribe, getSnapshot, getSnapshot);
  const locale = store.locale;
  if (ctx && ctx.locale === locale) return ctx;
  return {
    locale,
    setLocale,
    t: tr,
    available: SUPPORTED,
  };
}
