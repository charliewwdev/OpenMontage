import { authHeaders, clearSession, getToken } from "./lib/auth";

import { getLocale, tr } from "./lib/i18n";

export async function api(path, options = {}) {
  const headers = authHeaders(options.headers || {});
  // Lets the server localize user-visible status/error text (server/ui_messages.py).
  if (!headers["X-Studio-Locale"]) headers["X-Studio-Locale"] = getLocale();
  const res = await fetch(path, { ...options, headers });
  const text = await res.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = { error: text };
  }
  const hadSession = Boolean(getToken());
  if (res.status === 401 && hadSession && !String(path).includes("/api/auth/")) {
    clearSession();
  }
  if (!res.ok) {
    const msg = (data && (data.error || data.msg || data.message)) || res.statusText || "request failed";
    if (res.status === 401 && /login required/i.test(String(msg))) {
      // Only reopen login when a session just expired. Anonymous browse must not
      // get a forced modal from background POSTs (bind-refs / ensure edit / …).
      // Explicit create/generate actions already call requireAuth() first.
      if (hadSession) {
        try {
          window.dispatchEvent(
            new CustomEvent("om:need-auth", { detail: { path, method: options.method || "GET" } }),
          );
        } catch {
          /* ignore */
        }
      }
      const err = new Error(tr("ui_api_please_sign_in_before_calling_models"));
      err.status = 401;
      err.code = "login_required";
      err.data = data;
      throw err;
    }
    const err = new Error(msg);
    err.status = res.status;
    err.data = data;
    if (data && typeof data === "object") {
      err.code = data.code;
      err.blockers = data.blockers;
      err.forceHint = data.forceHint;
      err.quota = data.quota;
    }
    // Hosted GitHub login gate / daily quota (server/github_gate.py).
    const gateEvents = {
      github_login_required: ["om:github-required", "ui_github_login_required_toast"],
      quota_exceeded: ["om:quota-exceeded", "ui_github_quota_toast"],
      github_oauth_not_configured: ["", "ui_github_oauth_not_configured"],
    };
    const gate = gateEvents[err.code];
    if (gate) {
      err.message = tr(gate[1], { used: err.quota?.used ?? "", limit: err.quota?.limit ?? "" });
      if (gate[0]) {
        try {
          window.dispatchEvent(new CustomEvent(gate[0], { detail: { path, message: err.message } }));
        } catch {
          /* ignore */
        }
      }
    }
    throw err;
  }
  return data;
}
