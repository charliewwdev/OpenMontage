/** Extract spoken lines from episode / shot script text for dubbing preview. */

const SPEAKER_LINE = /^([^：:\n「」""]{1,24})\s*[：:]\s*(.+)$/;
const QUOTED = /[「""]([^」""]{2,120})[」""]/g;

/**
 * @param {string} content
 * @param {{ limit?: number }} [opts]
 * @returns {{ speaker: string, text: string }[]}
 */
export function extractDialogueLines(content, opts = {}) {
  const limit = opts.limit ?? 40;
  const text = String(content || "").trim();
  if (!text) return [];

  const lines = [];
  const seen = new Set();

  const push = (speaker, spoken) => {
    const sp = String(speaker || "旁白")
      .trim()
      .replace(/(问|说|道|喊|叫|答)$/, "")
      .slice(0, 24) || "旁白";
    const tx = String(spoken || "")
      .replace(/^["「”]|["」”]$/g, "")
      .trim();
    if (tx.length < 2) return;
    const key = `${sp}::${tx}`;
    if (seen.has(key)) return;
    seen.add(key);
    lines.push({ speaker: sp, text: tx });
  };

  for (const raw of text.split(/\r?\n/)) {
    const line = raw.trim();
    if (!line || /^#{1,6}\s/.test(line) || /^[-*]{3,}$/.test(line)) continue;
    if (/^(内景|外景|场景|镜头|SHOT|\[)/i.test(line) && line.length < 40) continue;

    const m = line.match(SPEAKER_LINE);
    if (m) {
      push(m[1], m[2]);
      continue;
    }

    let hit = false;
    QUOTED.lastIndex = 0;
    let qm;
    while ((qm = QUOTED.exec(line)) !== null) {
      hit = true;
      // Prefer nearby name before the quote: 玛蒂尔德含泪说「…」
      const before = line.slice(0, qm.index);
      const nameHit = before.match(/([\u4e00-\u9fff·]{2,12})[^「""]{0,12}$/);
      push(nameHit?.[1] || "对白", qm[1]);
    }
    if (!hit && lines.length === 0 && /[\u4e00-\u9fff]{8,}/.test(line) && !/昏黄|公寓|斑驳|木质/.test(line)) {
      // keep pure narration only as last resort later
    }
  }

  if (!lines.length) {
    // Fallback: short narration chunks (not stage dressing paragraphs)
    for (const raw of text.split(/\r?\n/)) {
      const line = raw.replace(/^[-*]\s+/, "").trim();
      if (line.length >= 8 && line.length <= 80 && !/^(内景|外景|\[)/.test(line)) {
        push("旁白", line);
      }
      if (lines.length >= 6) break;
    }
  }

  return lines.slice(0, limit);
}

/** Flatten spoken text only (no「X说：」— multi-voice TTS uses speaker separately). */
export function dialogueToTtsText(content, limit = 1200) {
  const lines = extractDialogueLines(content, { limit: 60 });
  if (!lines.length) return String(content || "").slice(0, limit);
  return lines.map((l) => l.text).join("。").slice(0, limit);
}
