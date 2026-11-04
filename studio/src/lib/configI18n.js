/**
 * English overlay for UI copy that lives in config/platform.yaml (/api/config).
 *
 * The YAML stays the zh source of truth. Only display fields listed in
 * DISPLAY_PATHS are swapped, and only when the exact zh string has an entry in
 * config/locales/platform.en.json. Data values (genre ids sent to the backend,
 * prompts, briefs, skill tags, viral scenario material) are never rewritten.
 */
import platformEn from "../../config/locales/platform.en.json";
import { getLocale } from "./i18n";

const DICTIONARIES = { en: platformEn };

const DISPLAY_PATHS = new Set([
  "tagline",
  "nav.[].label",
  "six_steps.[].label",
  "six_steps.[].note",
  "canvasSteps.[].label",
  "creationSteps.[]",
  "splitStages.[].title",
  "splitStages.[].detail",
  "entryCards.[].title",
  "entryCards.[].desc",
  "coverFormats.[].label",
  "coverFormats.[].description",
  "ratios.[].label",
  "ratios.[].description",
  "styleCategories.[].label",
  "tools.[].title",
  "tools.[].desc",
  "toolHub.categories.[].title",
  "toolHub.categories.[].desc",
  "toolHub.workflow.title",
  "toolHub.workflow.description",
  "toolHub.workflow.steps.[].title",
  "toolHub.workflow.steps.[].desc",
  "resources.[].title",
  "resources.[].desc",
  "helpSections.[].title",
  "helpSections.[].body",
  "inspirePlatforms.[].label",
  "inspirePlatforms.[].blurb",
  "inspirePrompts.[].tag",
  "pinterest.categories.[].label",
  "challenges.[].title",
  "challenges.[].prize",
  "pages.*.title",
  "pages.*.description",
]);

function pathMatches(path) {
  if (DISPLAY_PATHS.has(path)) return true;
  const parts = path.split(".");
  if (parts[0] === "pages" && parts.length === 3) return DISPLAY_PATHS.has(`pages.*.${parts[2]}`);
  return false;
}

/** Translate one config display string (e.g. a genre chip label) for the current locale. */
export function configText(value, locale = getLocale()) {
  if (typeof value !== "string") return value;
  const dict = DICTIONARIES[locale];
  return (dict && dict[value]) || value;
}

function walk(node, path, dict) {
  if (Array.isArray(node)) return node.map((item) => walk(item, `${path}.[]`, dict));
  if (node && typeof node === "object") {
    const out = {};
    for (const [key, value] of Object.entries(node)) {
      out[key] = walk(value, path ? `${path}.${key}` : key, dict);
    }
    return out;
  }
  if (typeof node === "string" && pathMatches(path)) return dict[node] || node;
  return node;
}

/** Return a copy of /api/config with display copy localized (zh returns the input as-is). */
export function localizeConfig(config, locale = getLocale()) {
  const dict = DICTIONARIES[locale];
  if (!config || !dict) return config;
  const out = { ...config };
  for (const key of Object.keys(config)) {
    if (key === "i18n") continue;
    out[key] = walk(config[key], key, dict);
  }
  return out;
}
