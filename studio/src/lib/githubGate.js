import { api } from "../api";

let _cache = null;
let _cacheAt = 0;

export function clearGithubGateCache() {
  _cache = null;
  _cacheAt = 0;
}

/** Hosted gate status: { required, verified, login, quota: { limit, used, remaining, … } }. */
export async function fetchGithubGateStatus({ force = false } = {}) {
  const now = Date.now();
  if (!force && _cache && now - _cacheAt < 15_000) return _cache;
  const data = await api("/api/settings/github-gate");
  _cache = data?.githubGate || { required: false, verified: true };
  _cacheAt = now;
  return _cache;
}

/**
 * Returns true when generation may proceed. When the hosted instance requires a
 * GitHub sign-in it opens the GitHub modal instead. The daily quota (images and
 * videos only) is enforced by the server, which answers 429 `quota_exceeded`;
 * api.js turns that into the `om:quota-exceeded` modal.
 */
export async function requireGithubLogin() {
  let gate;
  try {
    gate = await fetchGithubGateStatus({ force: true });
  } catch {
    // If the status check fails, let the server enforce on the generate call.
    return true;
  }
  if (!gate?.required || gate?.verified) return true;
  try {
    window.dispatchEvent(new CustomEvent("om:github-required", { detail: { gate } }));
  } catch {
    /* ignore */
  }
  return false;
}

/** Start GitHub OAuth (sign in, or link GitHub to the current account) and leave the page. */
export async function startGithubLogin(returnTo) {
  const target = returnTo || `${window.location.pathname}${window.location.search}`;
  const data = await api("/api/auth/github/start", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ returnTo: target }),
  });
  if (!data?.url) throw new Error("missing GitHub authorize URL");
  window.location.assign(data.url);
}

/**
 * Consume the OAuth callback result from the URL:
 *   #gh_token=…        → GitHub sign-in session (returned to the caller to store)
 *   ?github=linked     → GitHub linked to the current account
 *   ?github_error=code → failure
 */
let _callback;

export function consumeGithubCallback() {
  if (_callback !== undefined) return _callback; // idempotent (StrictMode double init)
  _callback = readGithubCallback();
  return _callback;
}

function readGithubCallback() {
  if (typeof window === "undefined") return null;
  const out = { token: "", linked: false, error: "" };
  const hash = window.location.hash || "";
  if (hash.startsWith("#gh_token=") || hash.includes("&gh_token=")) {
    const hp = new URLSearchParams(hash.slice(1));
    out.token = hp.get("gh_token") || "";
  }
  const params = new URLSearchParams(window.location.search);
  if (params.get("github") === "linked") out.linked = true;
  out.error = params.get("github_error") || "";
  if (!out.token && !out.linked && !out.error) return null;
  params.delete("github");
  params.delete("github_error");
  const qs = params.toString();
  const clean = `${window.location.pathname}${qs ? `?${qs}` : ""}`;
  try {
    window.history.replaceState(window.history.state, "", clean);
  } catch {
    /* ignore */
  }
  return out;
}
