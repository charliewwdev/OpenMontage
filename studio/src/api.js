import { authHeaders, clearSession, getToken } from "./lib/auth";

export async function api(path, options = {}) {
  const headers = authHeaders(options.headers || {});
  const res = await fetch(path, { ...options, headers });
  const text = await res.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = { error: text };
  }
  if (res.status === 401 && getToken() && !String(path).includes("/api/auth/")) {
    clearSession();
  }
  if (!res.ok) {
    const msg = (data && (data.error || data.msg || data.message)) || res.statusText || "request failed";
    if (res.status === 401 && /login required/i.test(String(msg))) {
      try {
        window.dispatchEvent(new CustomEvent("om:need-auth", { detail: { path, method: options.method || "GET" } }));
      } catch {
        /* ignore */
      }
      const err = new Error("请先登录后再调用模型或保存内容");
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
    }
    throw err;
  }
  return data;
}
