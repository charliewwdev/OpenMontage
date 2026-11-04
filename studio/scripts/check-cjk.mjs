#!/usr/bin/env node
/**
 * Flags hardcoded CJK (Han) text in frontend UI source so new user-visible
 * strings go through the i18n packs (config/locales/*.json) instead.
 *
 * Checked: string literals, template literal text and JSX text under src/.
 * Not checked: comments, object keys, equality comparisons, regexes,
 * console.* calls, string-method arguments (includes/startsWith/replace/...)
 * and the i18n runtime itself.
 *
 * Known data values (genre/tag values matched against stored data, LLM prompt
 * templates, parser speaker names) live in scripts/cjk-allowlist.json as
 * { "file": "src/...", "text": "..." }.
 *
 * Usage: npm run check:i18n        (exit code 1 when something is flagged)
 */
import { readFileSync, readdirSync, statSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";
import { parse } from "@babel/parser";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const SRC = join(ROOT, "src");
const HAN = /[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]/;
const SKIP_FILES = new Set(["src/lib/i18n.jsx"]);
const STRING_METHODS = new Set([
  "includes", "startsWith", "endsWith", "indexOf", "lastIndexOf", "replace", "replaceAll",
  "split", "match", "matchAll", "test", "search",
]);
const COMPARE_OPS = new Set(["===", "!==", "==", "!="]);

const allowlist = JSON.parse(readFileSync(join(ROOT, "scripts/cjk-allowlist.json"), "utf8"));
const allowed = new Set(allowlist.map((entry) => `${entry.file}\u0000${entry.text}`));
const usedAllow = new Set();

function listFiles(dir) {
  const out = [];
  for (const name of readdirSync(dir)) {
    const full = join(dir, name);
    if (statSync(full).isDirectory()) out.push(...listFiles(full));
    else if (/\.(jsx?|tsx?|mjs)$/.test(name)) out.push(full);
  }
  return out;
}

function isIgnoredContext(node, parent, grand) {
  if (!parent) return false;
  if ((parent.type === "ObjectProperty" || parent.type === "ObjectMethod") && parent.key === node && !parent.computed) return true;
  if (parent.type === "ImportDeclaration" || parent.type === "ExportAllDeclaration" || parent.type === "ExportNamedDeclaration") return true;
  if (parent.type === "BinaryExpression" && COMPARE_OPS.has(parent.operator)) return true;
  if (parent.type === "SwitchCase" && parent.test === node) return true;
  const call = parent.type === "TemplateLiteral" ? grand : parent;
  if (call && (call.type === "CallExpression" || call.type === "OptionalCallExpression") && call.callee !== node) {
    const callee = call.callee;
    if (callee.type === "MemberExpression" || callee.type === "OptionalMemberExpression") {
      if (callee.object.type === "Identifier" && callee.object.name === "console") return true;
      if (callee.property.type === "Identifier" && STRING_METHODS.has(callee.property.name)) return true;
    }
    if (callee.type === "Identifier" && callee.name === "RegExp") return true;
  }
  if (parent.type === "NewExpression" && parent.callee.type === "Identifier" && parent.callee.name === "RegExp") return true;
  return false;
}

const findings = [];

function visit(node, parent, grand, file) {
  if (!node || typeof node.type !== "string") return;
  let text = null;
  if (node.type === "StringLiteral" || node.type === "JSXText") text = node.value;
  else if (node.type === "TemplateElement") text = node.value.cooked ?? node.value.raw;
  if (text && HAN.test(text) && !isIgnoredContext(node, parent, grand)) {
    const trimmed = text.trim();
    const key = `${file}\u0000${trimmed}`;
    if (allowed.has(key)) usedAllow.add(key);
    else findings.push({ file, line: node.loc.start.line, text: trimmed });
  }
  for (const key of Object.keys(node)) {
    if (key === "loc" || key === "leadingComments" || key === "trailingComments" || key === "innerComments") continue;
    const value = node[key];
    if (Array.isArray(value)) value.forEach((child) => visit(child, node, parent, file));
    else if (value && typeof value.type === "string") visit(value, node, parent, file);
  }
}

for (const full of listFiles(SRC)) {
  const file = relative(ROOT, full).split("\\").join("/");
  if (SKIP_FILES.has(file)) continue;
  const ast = parse(readFileSync(full, "utf8"), {
    sourceType: "module",
    plugins: ["jsx", "typescript"],
    errorRecovery: true,
  });
  visit(ast.program, null, null, file);
}

const stale = allowlist.filter((entry) => !usedAllow.has(`${entry.file}\u0000${entry.text}`));
for (const entry of stale) console.warn(`warning: unused allowlist entry ${entry.file}: ${JSON.stringify(entry.text)}`);

if (findings.length) {
  for (const f of findings) console.error(`${f.file}:${f.line}  ${JSON.stringify(f.text.slice(0, 80))}`);
  console.error(`\n${findings.length} hardcoded CJK string(s) found. Move them into config/locales/{zh,en}.json and use tr()/t(),`);
  console.error("or, if the value is data rather than UI copy, add it to scripts/cjk-allowlist.json.");
  process.exit(1);
}
console.log("check:i18n passed — no hardcoded CJK UI strings in src/.");
