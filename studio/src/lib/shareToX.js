/**
 * One-click share to X: promo copy + video URL (Web Intent).
 * Does not attach the video file — paste the media link in the tweet.
 */

const GITHUB_URL = "https://github.com/charliewwdev/OpenMontage";

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

export function mediaPublicUrl(projectId, outputUrlOrPath) {
  const raw = String(outputUrlOrPath || "").trim();
  if (!raw) return "";
  if (/^https?:\/\//i.test(raw) || raw.startsWith("/api/")) return absoluteUrl(raw);
  if (!projectId) return absoluteUrl(raw);
  return absoluteUrl(`/api/media/${encodeURIComponent(projectId)}/${raw.replace(/^\//, "")}`);
}

function formatSeconds(sec) {
  if (typeof sec !== "number" || !(sec > 0)) return null;
  const n = Math.round(sec);
  return n >= 10 ? `~${n}s` : `~${n} sec`;
}

/**
 * Promo copy with video URL front-loaded so it always fits.
 * X Intent ~280 chars — keep short; video URL is required when present.
 */
export function buildXShareText(opts = {}) {
  const project = opts.project || {};
  const projectId = String(opts.projectId || project.id || "").trim();
  const title = String(project.title || "OpenMontage").trim();
  const tid = String(project.portraitTemplate || "").trim();
  const hook = TEMPLATE_HOOKS[tid] || "";
  const isPortrait = project.workflow === "portrait-match";
  const videoUrl = mediaPublicUrl(projectId, opts.outputUrl || opts.outputPath || opts.videoUrl);
  const dur = formatSeconds(opts.durationSec);

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
    ? `OpenMontage · ${title}`
    : `OpenMontage short-drama AI · ${title}`;

  // Video URL first after hook lines so the link is never dropped for length.
  const parts = [line1, line2];
  if (videoUrl) parts.push(videoUrl);
  parts.push(GITHUB_URL);

  let text = parts.join("\n\n");
  if (hook) {
    const withHook = `${text}\n\n${hook.charAt(0).toUpperCase()}${hook.slice(1)}.`;
    if (withHook.length <= 280) text = withHook;
  }
  if (text.length > 280) {
    // Keep video URL + github at the end; trim middle.
    const must = [line1, videoUrl || "", GITHUB_URL].filter(Boolean).join("\n\n");
    text = must.length <= 280 ? must : [videoUrl || line1, GITHUB_URL].filter(Boolean).join("\n\n").slice(0, 280);
  }
  return text;
}

function openIntent(text) {
  const intent = `https://twitter.com/intent/tweet?text=${encodeURIComponent(text)}`;
  const win = window.open(intent, "_blank", "noopener,noreferrer");
  if (!win) window.location.assign(intent);
  return true;
}

/**
 * One-click: open X compose with copy + video URL.
 * @returns {{ ok: boolean, mode: string, message: string, text: string, videoUrl: string }}
 */
export function shareVideoToX(opts = {}) {
  const project = opts.project || {};
  const projectId = String(opts.projectId || project.id || "").trim();
  const videoUrl = mediaPublicUrl(projectId, opts.outputUrl || opts.outputPath || opts.videoUrl);
  const text = buildXShareText(opts);
  openIntent(text);
  return {
    ok: true,
    mode: "intent",
    text,
    videoUrl: videoUrl || "",
    message: videoUrl
      ? "已打开 X，文案与成片链接已填好，确认后即可发布"
      : "已打开 X（未找到成片链接，仅文案）",
  };
}

/** @deprecated alias */
export function openShareToX(opts = {}) {
  return shareVideoToX(opts);
}
