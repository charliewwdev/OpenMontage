import { api } from "../api";

let _cache = null;
let _cacheAt = 0;

export function clearGithubStarCache() {
  _cache = null;
  _cacheAt = 0;
}

export async function fetchGithubStarStatus({ force = false } = {}) {
  const now = Date.now();
  if (!force && _cache && now - _cacheAt < 15_000) return _cache;
  const data = await api("/api/settings/github-star");
  _cache = data?.githubStar || { required: false, verified: true };
  _cacheAt = now;
  return _cache;
}

/** Returns true when generation may proceed. Opens the star modal when blocked. */
export async function requireGithubStar() {
  try {
    const gate = await fetchGithubStarStatus({ force: true });
    if (!gate?.required || gate?.verified) return true;
  } catch {
    // If status check fails, let the server enforce on the generate call.
    return true;
  }
  try {
    window.dispatchEvent(new CustomEvent("om:star-required"));
  } catch {
    /* ignore */
  }
  return false;
}
