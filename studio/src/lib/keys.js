import { toast } from "./toast";

import { tr } from "./i18n";

export function isKeyError(message) {
  return /API.?[Kk]ey|未配置|DEEPSEEK|VOLCENGINE|ARK_API|api[_ ]?key|缺少.*[Kk]ey/i.test(String(message || ""));
}

export function requireCapability(caps, key, onNeedKeys, label) {
  if (caps?.[key]) return true;
  toast.error(tr("ui_lib_keys_configure_first", {
    0: label || key
  }));
  onNeedKeys?.();
  return false;
}

export function toastMaybeKeys(error, onNeedKeys) {
  const message = String(error?.message || error || tr("ui_lib_keys_request_failed"));
  toast.error(message);
  if (isKeyError(message)) onNeedKeys?.();
}
