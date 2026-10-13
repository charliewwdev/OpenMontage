import { toast } from "./toast";

export function isKeyError(message) {
  return /API.?[Kk]ey|未配置|DEEPSEEK|VOLCENGINE|ARK_API|api[_ ]?key|缺少.*[Kk]ey/i.test(String(message || ""));
}

export function requireCapability(caps, key, onNeedKeys, label) {
  if (caps?.[key]) return true;
  toast.error(`请先配置 ${label || key}`);
  onNeedKeys?.();
  return false;
}

export function toastMaybeKeys(error, onNeedKeys) {
  const message = String(error?.message || error || "请求失败");
  toast.error(message);
  if (isKeyError(message)) onNeedKeys?.();
}
