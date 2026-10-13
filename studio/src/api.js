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
    throw new Error((data && (data.error || data.msg || data.message)) || res.statusText || "request failed");
  }
  return data;
}
