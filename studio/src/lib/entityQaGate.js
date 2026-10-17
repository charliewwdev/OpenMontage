/** Client-side mirror of server entity-ref QA gate (preflight banners / force dialog). */

const KIND_LABEL = { character: "角色", scene: "场景", prop: "道具" };

function selectedImage(ent) {
  if (!ent) return null;
  if (ent.selectedImage) return ent.selectedImage;
  const sid = ent.selectedImageId;
  if (!sid) return null;
  return (ent.images || []).find((i) => i.id === sid) || null;
}

/**
 * @param {object[]} entities
 * @returns {{ entityId: string, name: string, kind: string, kindLabel: string, issue: string, reason: string, score?: number }[]}
 */
export function listEntityQaBlockers(entities = []) {
  const blockers = [];
  const seen = new Set();
  for (const ent of entities) {
    const eid = ent?.id;
    if (!eid || seen.has(eid)) continue;
    seen.add(eid);
    const variant = String(ent.variant || "").trim();
    const baseName = (ent.name || eid).trim() || eid;
    const name =
      variant && variant !== "默认形象" && variant !== "默认造型" && variant !== "default"
        ? `${baseName}·${variant}`
        : baseName;
    const kind = ent.kind || "unknown";
    const kindLabel = KIND_LABEL[kind] || "素材";
    const img = selectedImage(ent);
    if (!img?.path && !img?.url) {
      blockers.push({
        entityId: eid,
        name,
        kind,
        kindLabel,
        issue: "no_image",
        reason: "尚无可用参考图",
      });
      continue;
    }
    const qa = img.qa || {};
    const reason = String(qa.reason || ent.qaFailReason || "");
    const soft =
      (qa.skipped && reason !== "qa_disabled") ||
      /qa_error|qa_exception|软通过|vision_/i.test(reason);
    if (img.qaPass === true && !soft && !ent.qaFailed) continue;
    let issue = "qa_pending";
    let detail = reason || "尚未通过质检";
    if (soft) {
      issue = "soft_pass";
      detail = reason || "质检无效（软通过/跳过）";
    } else if (img.qaPass === false || ent.qaFailed) {
      issue = "qa_fail";
      detail = reason || "质检未达标";
    }
    blockers.push({
      entityId: eid,
      name,
      kind,
      kindLabel,
      issue,
      reason: detail.slice(0, 220),
      score: qa.score,
    });
  }
  return blockers;
}

export function formatEntityQaBlockers(blockers = [], { max = 8 } = {}) {
  if (!blockers.length) return "";
  return blockers
    .slice(0, max)
    .map((b) => `${b.kindLabel}「${b.name}」：${b.reason || b.issue}`)
    .join("\n");
}

export function isEntityQaBlockedError(error) {
  return Boolean(error && (error.code === "entity_qa_blocked" || error.data?.code === "entity_qa_blocked"));
}

export function blockersFromError(error) {
  return error?.blockers || error?.data?.blockers || [];
}
