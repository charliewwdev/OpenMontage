/**
 * X (Twitter) Web Intent share — promo copy tuned to current open-source AI
 * launch patterns on X (short hook + number + what it is + OSS proof + link).
 *
 * Research-backed habits (2025–26 launch posts):
 * - Lead with a concrete result / number (not "excited to announce")
 * - Say what it does in one breath
 * - Name open-source / self-host / BYOK as proof
 * - Keep under ~260 chars (URL expansion headroom)
 * - Prefer one link in-body; video URL first, product page second if room
 */

const GITHUB_URL = "https://github.com/charliewwdev/OpenMontage";

/** One concrete hook per portrait template (English — X AI feed default). */
const TEMPLATE_HOOKS = {
  ref1: "night portrait look-back, warm bokeh, beat-locked to the original track",
  ref2: "sakura lolita dance, sheer sleeves, beat-locked to the original track",
  ref3: "indoor sweet dance, trio hands, beat-locked to the original track",
};

function absoluteUrl(pathOrUrl) {
  const raw = String(pathOrUrl || "").trim();
  if (!raw) return "";
  if (/^https?:\/\//i.test(raw)) return raw;
  if (typeof window === "undefined") return raw;
  const origin = window.location.origin.replace(/\/$/, "");
  return raw.startsWith("/") ? `${origin}${raw}` : `${origin}/${raw}`;
}

function mediaPublicUrl(projectId, outputUrlOrPath) {
  const raw = String(outputUrlOrPath || "").trim();
  if (!raw) return "";
  if (/^https?:\/\//i.test(raw) || raw.startsWith("/api/")) return absoluteUrl(raw);
  if (!projectId) return absoluteUrl(raw);
  return absoluteUrl(`/api/media/${encodeURIComponent(projectId)}/${raw.replace(/^\//, "")}`);
}

function projectPageUrl(projectId, opts = {}) {
  if (!projectId || typeof window === "undefined") return absoluteUrl("/");
  const u = new URL(window.location.origin);
  u.searchParams.set("project", projectId);
  if (opts.workflow === "portrait-match" || opts.screen === "portrait") {
    u.searchParams.set("screen", "portrait");
  } else if (opts.episodeId) {
    u.searchParams.set("step", "workspace");
    u.searchParams.set("ep", opts.episodeId);
  }
  return u.toString();
}

function formatSeconds(sec) {
  if (typeof sec !== "number" || !(sec > 0)) return null;
  const n = Math.round(sec);
  return n >= 10 ? `~${n}s` : `~${n} sec`;
}

/**
 * @param {{
 *   project?: { id?: string, title?: string, workflow?: string, portraitTemplate?: string },
 *   projectId?: string,
 *   outputUrl?: string,
 *   outputPath?: string,
 *   episodeId?: string,
 *   durationSec?: number | null,
 * }} opts
 */
export function buildXShareText(opts = {}) {
  const project = opts.project || {};
  const projectId = String(opts.projectId || project.id || "").trim();
  const title = String(project.title || "OpenMontage").trim();
  const tid = String(project.portraitTemplate || "").trim();
  const hook = TEMPLATE_HOOKS[tid] || "";
  const isPortrait = project.workflow === "portrait-match";
  const videoUrl = mediaPublicUrl(projectId, opts.outputUrl || opts.outputPath);
  const pageUrl = projectPageUrl(projectId, {
    workflow: project.workflow,
    screen: isPortrait ? "portrait" : "",
    episodeId: opts.episodeId,
  });
  const dur = formatSeconds(opts.durationSec);

  // Pattern: [number] + one-sentence result → what OSS product → proof → link
  // Avoid: "Excited to announce", emoji spam, "thread ↓", vague "AI magic".
  // Compact formula (Karos / OSS launch posts): number-first hook → name product → proof → link.
  let line1;
  if (isPortrait && dur) {
    line1 = `Douyin-style portrait edit in ${dur} — open-source AI.`;
  } else if (isPortrait) {
    line1 = "Douyin-style portrait edit — open-source AI.";
  } else if (dur) {
    line1 = `Vertical short in ${dur} — open-source AI.`;
  } else {
    line1 = "Vertical short — open-source AI.";
  }

  const line2 = isPortrait
    ? `OpenMontage: match looks + original audio beats (${title}).`
    : `OpenMontage: short-drama AI video studio (${title}).`;

  const line3 = "Open source · self-hostable · BYOK.";
  const lineHook = hook ? `${hook.charAt(0).toUpperCase()}${hook.slice(1)}.` : "";

  // Must-fit: hook + product + GitHub. Optional: scene line, page, video.
  const required = [line1, line2, GITHUB_URL];
  const optional = [lineHook, line3, pageUrl || "", videoUrl || ""];

  let text = required.join("\n\n");
  for (const part of optional) {
    if (!part) continue;
    const next = `${text}\n\n${part}`;
    if (next.length > 260) continue;
    text = next;
  }
  return text;
}

export function openShareToX(opts = {}) {
  const text = buildXShareText(opts);
  if (!text) return false;
  const intent = `https://twitter.com/intent/tweet?text=${encodeURIComponent(text)}`;
  const win = window.open(intent, "_blank", "noopener,noreferrer");
  if (!win) {
    window.location.assign(intent);
  }
  return true;
}
