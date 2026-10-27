/**
 * X (Twitter) Web Intent share — prefill promo copy + public media/project links.
 * Does not upload video; user confirms in the X compose window.
 */

const TEMPLATE_HOOKS = {
  ref1: "雨夜回眸 · 暖光 bokeh · JK 甜妹",
  ref2: "樱花洛丽塔 · 薄纱袖摆 · 卡点对齐原曲",
  ref3: "室内甜舞 · 三人手势 · 高调窗光",
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
  const title = String(project.title || "OpenMontage 成片").trim();
  const tid = String(project.portraitTemplate || "").trim();
  const hook = TEMPLATE_HOOKS[tid] || "";
  const isPortrait = project.workflow === "portrait-match";
  const videoUrl = mediaPublicUrl(projectId, opts.outputUrl || opts.outputPath);
  const pageUrl = projectPageUrl(projectId, {
    workflow: project.workflow,
    screen: isPortrait ? "portrait" : "",
    episodeId: opts.episodeId,
  });
  const dur =
    typeof opts.durationSec === "number" && opts.durationSec > 0
      ? `约 ${Math.round(opts.durationSec)} 秒 · `
      : "";

  const lines = [
    title,
    hook ? `${dur}${hook}` : dur ? dur.replace(/\s·\s$/, "") : "",
    isPortrait
      ? "用 OpenMontage 写真对标生成，卡点对齐原曲。"
      : "用 OpenMontage 影视工坊一键成片。",
    videoUrl ? `▶️ ${videoUrl}` : "",
    pageUrl ? `🔗 ${pageUrl}` : "",
    "#OpenMontage #AIVideo",
  ].filter(Boolean);

  // X hard limit ~280; keep headroom for URL expansion.
  let text = lines.join("\n");
  if (text.length > 260) {
    text = lines
      .filter((l) => !l.startsWith("🔗"))
      .join("\n")
      .slice(0, 260);
  }
  return text;
}

export function openShareToX(opts = {}) {
  const text = buildXShareText(opts);
  if (!text) return false;
  const intent = `https://twitter.com/intent/tweet?text=${encodeURIComponent(text)}`;
  const win = window.open(intent, "_blank", "noopener,noreferrer");
  if (!win) {
    // Popup blocked — navigate same tab as fallback.
    window.location.assign(intent);
  }
  return true;
}
