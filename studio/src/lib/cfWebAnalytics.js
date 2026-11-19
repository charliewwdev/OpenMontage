/**
 * Inject Cloudflare Web Analytics beacon when a site token is provided.
 * Token comes from GET /api/config → cfWebAnalyticsToken (env STUDIO_CF_WEB_ANALYTICS_TOKEN).
 * Empty / missing → no-op. Safe to call multiple times (idempotent).
 *
 * This is Cloudflare's public site token for Web Analytics (beacon), not an API secret.
 * Docs: https://developers.cloudflare.com/web-analytics/get-started/
 */
const SCRIPT_ID = "om-cf-web-analytics";
const BEACON_SRC = "https://static.cloudflareinsights.com/beacon.min.js";

export function installCfWebAnalytics(token) {
  const value = typeof token === "string" ? token.trim() : "";
  if (!value) return false;
  if (typeof document === "undefined") return false;
  if (document.getElementById(SCRIPT_ID)) return true;

  const script = document.createElement("script");
  script.id = SCRIPT_ID;
  script.defer = true;
  script.src = BEACON_SRC;
  script.setAttribute("data-cf-beacon", JSON.stringify({ token: value }));
  document.head.appendChild(script);
  return true;
}
