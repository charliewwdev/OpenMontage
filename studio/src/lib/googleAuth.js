const GIS_SRC = "https://accounts.google.com/gsi/client";

let loadPromise = null;

export function loadGoogleIdentity() {
  if (typeof window === "undefined") return Promise.reject(new Error("no window"));
  if (window.google?.accounts?.id) return Promise.resolve(window.google);
  if (loadPromise) return loadPromise;
  loadPromise = new Promise((resolve, reject) => {
    const existing = document.querySelector(`script[src="${GIS_SRC}"]`);
    if (existing) {
      existing.addEventListener("load", () => resolve(window.google));
      existing.addEventListener("error", () => reject(new Error("Google Identity load failed")));
      if (window.google?.accounts?.id) resolve(window.google);
      return;
    }
    const script = document.createElement("script");
    script.src = GIS_SRC;
    script.async = true;
    script.defer = true;
    script.onload = () => resolve(window.google);
    script.onerror = () => reject(new Error("Google Identity load failed"));
    document.head.appendChild(script);
  });
  return loadPromise;
}

export function renderGoogleButton(container, { clientId, locale = "zh_CN", onCredential, onError }) {
  if (!container || !clientId) return () => {};
  let cancelled = false;
  void loadGoogleIdentity()
    .then((google) => {
      if (cancelled || !google?.accounts?.id) return;
      google.accounts.id.initialize({
        client_id: clientId,
        callback: (response) => {
          const idToken = response?.credential;
          if (!idToken) {
            onError?.(new Error("missing Google credential"));
            return;
          }
          onCredential?.(idToken);
        },
        auto_select: false,
        cancel_on_tap_outside: true,
        context: "signin",
        ux_mode: "popup",
      });
      container.innerHTML = "";
      google.accounts.id.renderButton(container, {
        type: "standard",
        theme: "outline",
        size: "large",
        text: "signin_with",
        shape: "pill",
        logo_alignment: "left",
        width: Math.min(container.clientWidth || 360, 360),
        locale: locale === "en" ? "en" : "zh_CN",
      });
    })
    .catch((err) => onError?.(err));
  return () => {
    cancelled = true;
  };
}
