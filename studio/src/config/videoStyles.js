/**
 * @deprecated Visual styles are loaded from `studio/server/video_styles.json`
 * via GET /api/config (`styles`). Do not maintain a frontend duplicate list.
 */

export const VIDEO_STYLES = [];

export function getDefaultVideoStyle() {
  return null;
}

export function getStyleByPromptValue() {
  return null;
}

export function stylePromptFromValue(value) {
  return value || "";
}
