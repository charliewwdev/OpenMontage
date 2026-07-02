// Backlot project board — renders BoardState and stays live via SSE.

import {
  STAGE_ICONS, el, fmtAgo, fmtClock, fmtDuration, fmtMoney,
  getJSON, mediaURL, subscribe, thumbURL, waveBars,
} from "/ui/lib.js";

const projectId = decodeURIComponent(location.pathname.split("/p/")[1] || "");
const app = document.getElementById("app");
const modal = document.getElementById("modal");
const player = document.getElementById("player");

let state = null;
let selectedStage = null;   // stage drawer open for this stage name
let activeRender = 0;

// ---------------------------------------------------------------------------
// header slate
// ---------------------------------------------------------------------------

function renderSlate(s) {
  const board = s.storyboard;
  const chips = [
    el("span", { class: "chip" }, `${s.pipeline.pipeline_type} pipeline`),
    board && board.total_duration_seconds
      ? el("span", { class: "chip" }, `${board.scenes.length} scenes · ${fmtDuration(board.total_duration_seconds)}`)
      : null,
    s.style_playbook ? el("span", { class: "chip" }, s.style_playbook) : null,
  ];

  const awaiting = s.stages.find((x) => x.status === "awaiting_human");
  const inProgress = s.stages.find((x) => x.status === "in_progress");
  let liveEl;
  if (awaiting) {
    liveEl = el("span", { class: "live" }, el("span", { class: "dot" }), "◈ AWAITING YOU");
  } else if (s.live || inProgress) {
    liveEl = el("span", { class: "live" }, el("span", { class: "dot" }), "LIVE");
  } else {
    liveEl = el("span", { class: "live idle" }, el("span", { class: "dot" }),
      `IDLE${s.last_activity ? " · " + fmtAgo(s.last_activity).toUpperCase() : ""}`);
  }

  const cost = el("div", { class: "cost" });
  if (s.cost) {
    const spent = s.cost.total_spent_usd ?? 0;
    const budget = spent + (s.cost.budget_remaining_usd ?? 0);
    const hasBudget = s.cost.budget_remaining_usd != null;
    const pct = hasBudget && budget > 0 ? Math.min(100, (spent / budget) * 100) : 0;
    cost.append(
      el("div", { class: "nums" }, el("b", {}, fmtMoney(spent)),
        hasBudget ? el("span", {}, ` / ${fmtMoney(budget)}`) : null),
      hasBudget
        ? el("div", { class: "bar" }, el("i", {
            class: pct > 75 ? "warn" : "", style: `width:${pct}%`,
          }))
        : null,
      el("div", { class: "label" }, "generation spend"),
    );
  }

  return el("header", { class: "slate" },
    el("div", { class: "clapper" }),
    el("div", {},
      el("a", { class: "wordmark", href: "/", style: "text-decoration:none" }, "Backlot"),
      el("h1", {}, s.title),
    ),
    ...chips,
    el("div", { class: "spacer" }),
    liveEl,
    cost,
  );
}

// ---------------------------------------------------------------------------
// stage rail
// ---------------------------------------------------------------------------

function stageSub(st) {
  if (st.status === "awaiting_human") return "awaiting your approval\nreply in chat to continue";
  if (st.status === "in_progress" && st.partial_progress) {
    const done = st.partial_progress.completed_scene_ids;
    if (Array.isArray(done)) return `${done.length} scene${done.length === 1 ? "" : "s"} done`;
    return "in progress";
  }
  if (st.status === "in_progress") return "in progress";
  if (st.status === "failed") return st.error ? String(st.error).slice(0, 60) : "failed";
  if (st.timestamp) {
    const approved = st.gated && st.human_approved ? " · approved" : "";
    return fmtClock(st.timestamp) + approved;
  }
  return "";
}

function renderRail(s) {
  const rail = el("nav", { class: "rail" });
  let pendingIndex = 1;
  for (const st of s.stages) {
    const cls = st.status === "completed" ? "done"
      : st.status === "in_progress" ? "active"
      : st.status === "awaiting_human" ? "await"
      : st.status === "failed" ? "failed" : "";
    const icon = STAGE_ICONS[st.status] || String(pendingIndex);
    if (!STAGE_ICONS[st.status]) pendingIndex += 1;
    const node = el("div", {
      class: `stage ${cls}${selectedStage === st.name ? " selected" : ""}`,
      onclick: () => toggleDrawer(st.name),
    },
      el("span", { class: "line" }),
      el("span", { class: "node" }, icon),
      el("span", { class: "name" }, st.name),
      el("span", { class: "sub", style: "white-space:pre-line" }, stageSub(st)),
    );
    rail.append(node);
  }
  return rail;
}

function toggleDrawer(stageName) {
  selectedStage = selectedStage === stageName ? null : stageName;
  render();
}

const STAGE_ARTIFACTS = {
  research: ["research_brief"],
  proposal: ["proposal_packet"],
  idea: ["brief"],
  script: ["script"],
  scene_plan: ["scene_plan"],
  assets: ["asset_manifest"],
  edit: ["edit_decisions"],
  compose: ["render_report", "final_review"],
  publish: ["publish_log"],
};

function renderDrawer(s) {
  if (!selectedStage) return null;
  const st = s.stages.find((x) => x.name === selectedStage);
  if (!st) return null;

  const body = el("div", { class: "drawer-body" });

  if (st.review) {
    body.append(el("div", { class: "findings", style: "margin-bottom:12px" },
      el("span", { class: `f ${st.review.critical ? "crit" : ""}` }, `${st.review.critical ?? 0} critical`),
      el("span", { class: `f ${st.review.suggestions ? "sugg" : ""}` }, `${st.review.suggestions ?? 0} suggestions`),
      el("span", { class: "f" }, `${st.review.nitpicks ?? 0} nitpicks`),
      typeof st.review.summary === "string" ? el("span", { style: "font-size:11.5px;color:var(--text-2);margin-left:8px" }, st.review.summary) : null,
    ));
  }

  const names = STAGE_ARTIFACTS[st.name] || [];
  let shown = false;
  for (const name of names) {
    const artifact = s.artifacts[name];
    if (!artifact) continue;
    shown = true;
    body.append(
      el("div", { class: "d-cat", style: "font-family:var(--mono);font-size:9.5px;color:var(--text-3);letter-spacing:.1em;text-transform:uppercase;margin:6px 0 4px" }, name),
      el("pre", {}, JSON.stringify(artifact, null, 2)),
    );
  }
  if (!shown) {
    body.append(el("div", { class: "hint" },
      st.status === "pending" ? "This stage hasn't run yet." : "No canonical artifact found on disk for this stage."));
  }

  return el("div", { class: "drawer" },
    el("div", { class: "drawer-head" },
      el("h3", {}, `${st.name} — ${st.status}`),
      st.gate_skipped ? el("span", { class: "gate-chip" }, "⚑ GATE SKIPPED") : null,
      st.versions > 1 ? el("span", { class: "ver-chip" }, `v${st.versions}`) : null,
      st.timestamp ? el("span", { class: "meta", style: "font-family:var(--mono);font-size:10.5px;color:var(--text-3)" }, st.timestamp) : null,
      el("span", { class: "close", onclick: () => toggleDrawer(st.name) }, "CLOSE ✕"),
    ),
    body,
  );
}

// ---------------------------------------------------------------------------
// script card
// ---------------------------------------------------------------------------

function scriptSections(script, limit) {
  const sections = script.sections || [];
  const shown = limit ? sections.slice(0, limit) : sections;
  const nodes = [];
  for (const sec of shown) {
    nodes.push(el("div", { class: "sp-slug" },
      `${(sec.id || "").toUpperCase()} — ${sec.label || "Section"} `,
      el("span", { class: "tc" }, `${fmtDuration(sec.start_seconds)} – ${fmtDuration(sec.end_seconds)}`)));
    if (sec.text) nodes.push(el("div", { class: "sp-action" }, sec.text));
    if (sec.speaker_directions) nodes.push(el("div", { class: "sp-paren" }, `(${sec.speaker_directions})`));
    const cues = sec.enhancement_cues || [];
    if (cues.length) {
      nodes.push(el("div", { style: "margin-left:42px" },
        cues.map((c) => el("span", { class: "sp-cue" }, `▸ ${c.type} · ${String(c.description || "").slice(0, 60)}`))));
    }
  }
  if (limit && sections.length > limit) {
    nodes.push(el("div", { class: "sp-fade" }, `… ${sections.length - limit} more sections`));
  }
  return nodes;
}

function renderScriptCard(s) {
  const script = s.artifacts.script;
  if (!script) return null;
  const scriptStage = s.stages.find((x) => x.name === "script");
  const approved = scriptStage && scriptStage.status === "completed";

  const card = el("div", { class: "script-card", title: "Click to expand full script", onclick: openScriptModal },
    approved ? el("span", { class: "script-approved" }, "APPROVED") : null,
    el("div", { class: "sp-title" }, script.title || s.title),
    el("div", { class: "sp-meta" },
      `script · ${fmtDuration(script.total_duration_seconds)} · ${(script.sections || []).length} sections`),
    ...scriptSections(script, 4),
    el("span", { class: "sp-expand" }, "⤢ EXPAND SCRIPT"),
  );
  return card;
}

function openScriptModal() {
  const script = state && state.artifacts.script;
  if (!script) return;
  modal.innerHTML = "";
  modal.append(
    el("span", { class: "modal-close", onclick: closeModal }, "ESC · CLOSE"),
    el("div", { class: "modal-page" },
      el("div", { class: "script-card", style: "cursor:default" },
        el("div", { class: "sp-title" }, script.title || state.title),
        el("div", { class: "sp-meta" },
          `script · ${fmtDuration(script.total_duration_seconds)} · ${(script.sections || []).length} sections`),
        ...scriptSections(script, 0),
        el("div", { class: "sp-fade" }, "END"),
      )),
  );
  modal.classList.add("open");
}

function closeModal() { modal.classList.remove("open"); }
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeModal(); });
modal.addEventListener("click", (e) => { if (e.target === modal) closeModal(); });

// ---------------------------------------------------------------------------
// right rail: decisions, activity
// ---------------------------------------------------------------------------

function renderDecisions(s) {
  const log = s.artifacts.decision_log;
  const decisions = (log && log.decisions) || [];
  if (!decisions.length) return null;
  const body = el("div", { class: "panel-body" });
  for (const d of decisions.slice(-8).reverse()) {
    const alts = (d.options_considered || [])
      .filter((o) => (o.option_id || o.label) !== d.selected && o.rejected_because !== undefined || (o.option_id !== d.selected && (o.option_id || o.label)))
      .filter((o) => o.option_id !== d.selected);
    body.append(el("div", { class: "decision" },
      el("div", { class: "d-cat" }, `${d.category || "decision"}${d.confidence ? ` · ${d.confidence}` : ""}`),
      el("div", { class: "d-pick" }, `${d.subject || ""} `, el("span", { class: "arrow" }, "→"), ` ${d.selected || ""}`),
      d.reason ? el("div", { class: "d-why" }, d.reason) : null,
      alts.length ? el("div", { class: "d-alt" }, "also considered: ",
        alts.slice(0, 3).map((o, i) => [i ? " · " : "", el("s", {}, o.label || o.option_id)]).flat()) : null,
    ));
  }
  return el("div", { class: "panel" },
    el("div", { class: "panel-head" }, el("h2", {}, "Decisions"), el("span", { class: "meta" }, "decision_log.json")),
    body);
}

function renderActivity(s) {
  const events = s.events || [];
  if (!events.length) return null;
  const body = el("div", { class: "panel-body" });
  const started = new Map();
  for (const ev of events) {
    if (ev.event === "start") started.set(`${ev.tool}:${ev.scene_id || ""}`, ev);
  }
  for (const ev of events.slice(-10).reverse()) {
    let statusEl;
    if (ev.event === "finish") {
      statusEl = el("span", { class: "status ok" },
        `✓${ev.duration_s != null ? ` ${ev.duration_s}s` : ""}`);
    } else if (ev.event === "error") {
      statusEl = el("span", { class: "status err" }, "✕");
    } else {
      statusEl = el("span", { class: "status run" }, "● running");
    }
    body.append(el("div", { class: "act-row" },
      el("span", { class: "t" }, fmtClock(ev.ts)),
      el("span", { class: "tool" }, ev.tool || ""),
      el("span", { class: "target" }, ev.scene_id || ""),
      statusEl,
    ));
  }
  return el("div", { class: "panel" },
    el("div", { class: "panel-head" }, el("h2", {}, "Activity"), el("span", { class: "meta" }, "events.jsonl")),
    body);
}

// ---------------------------------------------------------------------------
// storyboard filmstrip
// ---------------------------------------------------------------------------

function sceneCard(s, card) {
  const dur = card.duration_seconds;
  const width = Math.max(132, Math.min(300, 70 + (dur || 3) * 26));
  const wrap = el("div", { class: "scene-card", style: `width:${width}px` });

  const slate = el("div", { class: "sc-slate" },
    el("span", { class: "num" }, `SC ${String(card.id).replace(/^sc/i, "").padStart(2, "0")}`),
    card.takes.length > 1 ? el("span", { class: "take" }, `T${card.takes.length}`) : null,
    card.hero_moment ? el("span", { class: "hero" }, "★ HERO") : null,
    el("span", { class: "dur" }, fmtDuration(dur)),
  );
  wrap.append(slate);

  // visual slot
  let thumb;
  if (card.generating) {
    thumb = el("div", { class: "thumb generating" },
      el("div", { class: "shimmer" }),
      el("div", { class: "gen-label" },
        el("span", {}, "◉ GENERATING"),
        el("span", { class: "sub" }, card.generating_tool || "")));
  } else if (card.visual && card.visual.exists) {
    const v = card.visual;
    const badge = [v.model || v.source_tool, v.cost_usd != null ? fmtMoney(v.cost_usd) : null,
      v.quality_score != null ? `q ${v.quality_score}` : null].filter(Boolean).join(" · ");
    if (v.type === "video") {
      thumb = el("div", { class: "thumb approved" },
        el("video", { src: mediaURL(s.project_id, v.path), muted: "", preload: "metadata", playsinline: "" }),
        el("span", { class: "play" }, "▶"),
        badge ? el("span", { class: "badge" }, badge) : null);
      thumb.onclick = () => {
        const vid = thumb.querySelector("video");
        if (vid.paused) vid.play(); else vid.pause();
      };
    } else {
      thumb = el("div", { class: "thumb approved" },
        el("img", { src: thumbURL(s.project_id, v.path, 640), loading: "lazy", alt: "" }),
        badge ? el("span", { class: "badge" }, badge) : null);
    }
  } else if (card.visual && !card.visual.exists) {
    thumb = el("div", { class: "thumb missing" },
      el("div", { class: "spec-in" },
        el("span", { class: "warn-ic" }, "⚑"),
        el("div", { class: "spec-desc" }, "asset in manifest, file missing"),
        el("div", { class: "spec-shot" }, card.visual.path || "")));
  } else if (card.type === "text_card") {
    thumb = el("div", { class: "thumb textcard" },
      el("div", { class: "tc-copy" }, (card.narration || card.description || "").slice(0, 48)));
  } else if (card.required_assets.length) {
    thumb = el("div", { class: "thumb missing" },
      el("div", { class: "spec-in" },
        el("span", { class: "warn-ic" }, "⚑"),
        el("div", { class: "spec-desc" }, "no asset yet"),
        el("div", { class: "spec-shot" }, (card.required_assets[0].description || "").slice(0, 60))));
  } else {
    thumb = el("div", { class: "thumb spec" },
      el("div", { class: "spec-in" },
        el("div", { class: "spec-desc" }, card.description || ""),
        el("div", { class: "spec-shot" }, [card.framing, card.movement].filter(Boolean).join(" · ").slice(0, 70))));
  }
  wrap.append(thumb);

  // shot language chips
  const sl = card.shot_language;
  if (sl) {
    wrap.append(el("div", { class: "shotchips", style: "display:flex;flex-wrap:wrap;gap:4px;padding:7px 2px 0" },
      [sl.shot_size, sl.camera_movement, sl.lens_mm ? `${sl.lens_mm}mm` : null, sl.lighting_key]
        .filter(Boolean)
        .map((t) => el("span", { style: "font-family:var(--mono);font-size:8.5px;letter-spacing:.04em;color:#62626c;border:1px solid #212129;border-radius:3px;padding:1px 5px" }, String(t).replaceAll("_", " ")))));
  }

  // takes drawer
  if (card.takes.length > 1) {
    const takes = el("div", { class: "takes" });
    card.takes.forEach((t, i) => {
      const isActive = t === card.visual;
      const tk = el("span", { class: `tk${isActive ? " active" : ""}`, title: `take ${i + 1}` });
      if (t.exists && t.type === "image") tk.append(el("img", { src: thumbURL(s.project_id, t.path, 320), loading: "lazy", alt: "" }));
      takes.append(tk);
    });
    takes.append(el("span", { class: "tk-label" }, `${card.takes.length} TAKES`));
    wrap.append(takes);
  }

  // narration + audio
  if (card.narration) {
    wrap.append(el("div", { class: "narr" }, card.narration));
  } else if (card.shot_intent || card.description) {
    wrap.append(el("div", { class: "narr tc-note" }, (card.shot_intent || card.description || "").slice(0, 110)));
  }
  const narrAudio = card.audio.find((a) => a.exists && (a.type === "narration" || a.type === "audio"));
  if (narrAudio) {
    const wave = el("div", { class: "wave", style: "cursor:pointer", title: "Play narration" });
    waveBars(wave, card.id + narrAudio.path);
    wave.append(el("span", { class: "wv-time" }, narrAudio.duration_seconds ? fmtDuration(narrAudio.duration_seconds) : "♪"));
    wave.onclick = () => {
      player.src = mediaURL(s.project_id, narrAudio.path);
      player.play();
    };
    wrap.append(wave);
  }
  return wrap;
}

function renderStoryboard(s) {
  const board = s.storyboard;
  if (!board) return null;
  const strip = el("div", { class: "filmstrip" });
  for (const card of board.scenes) strip.append(sceneCard(s, card));
  return el("div", {},
    el("div", { class: "section-title" }, "Storyboard",
      el("span", { class: "meta" },
        `${board.scenes.length} scenes${board.total_duration_seconds ? ` · ${fmtDuration(board.total_duration_seconds)}` : ""} · card width ∝ duration`)),
    el("div", { class: "strip-outer" }, strip));
}

// ---------------------------------------------------------------------------
// renders + degraded media
// ---------------------------------------------------------------------------

function renderRenders(s) {
  const renders = s.media.renders;
  if (!renders.length) return null;
  if (activeRender >= renders.length) activeRender = 0;
  const current = renders[activeRender];
  const video = el("video", { src: mediaURL(s.project_id, current.path), controls: "", preload: "none" });
  const versions = el("div", { class: "render-meta" },
    renders.map((r, i) => el("span", {
      class: `v${i === activeRender ? " active" : ""}`,
      onclick: () => { activeRender = i; render(); },
    }, `${r.path.split("/").pop()}${r.at_root ? " · root" : ""}`)),
    el("span", { style: "margin-left:auto" }, `${(current.size / 1048576).toFixed(1)} MB`),
  );
  return el("div", {},
    el("div", { class: "section-title" }, "Renders",
      el("span", { class: "meta" }, `${renders.length} version${renders.length === 1 ? "" : "s"}`)),
    el("div", { class: "render-hero" }, video),
    versions);
}

function renderFoundMedia(s) {
  // Degraded view: show discovered snapshots when there's no storyboard.
  if (s.storyboard || !s.media.snapshots.length) return null;
  const grid = el("div", { class: "found-grid" });
  for (const snap of s.media.snapshots.slice(0, 12)) {
    grid.append(el("div", { class: "thumb" },
      el("img", { src: thumbURL(s.project_id, snap.path, 640), loading: "lazy", alt: "" })));
  }
  return el("div", {},
    el("div", { class: "section-title" }, "What the watcher found",
      el("span", { class: "meta" }, "snapshots / verification frames")),
    grid);
}

function renderNoState(s) {
  if (s.has_pipeline_state) return null;
  return el("div", { class: "notice", style: "border-color:#2b2b33;background:var(--surface-2);color:var(--text-3)" },
    el("span", { style: "font-size:15px" }, "◌"),
    el("span", {},
      el("b", { style: "color:var(--text-2)" }, "No pipeline state. "),
      "This project has no checkpoints — Backlot is showing what it found on disk. ",
      "Runs that follow the checkpoint protocol get the full board."));
}

function renderAwaitingNotice(s) {
  const awaiting = s.stages.find((x) => x.status === "awaiting_human");
  if (!awaiting) return null;
  return el("div", { class: "notice" },
    el("span", { style: "font-size:16px" }, "◈"),
    el("span", {},
      el("b", {}, `The ${awaiting.name} stage is waiting for your review. `),
      "The agent is paused at this gate — reply ", el("b", {}, "in chat"), " to approve or request changes."));
}

// ---------------------------------------------------------------------------
// page assembly
// ---------------------------------------------------------------------------

function render() {
  if (!state) return;
  const s = state;
  document.title = `Backlot — ${s.title}`;
  app.innerHTML = "";
  app.append(renderSlate(s));
  app.append(renderRail(s));
  const drawer = renderDrawer(s);
  if (drawer) app.append(drawer);
  const awaitingNotice = renderAwaitingNotice(s);
  if (awaitingNotice) app.append(awaitingNotice);
  const noState = renderNoState(s);
  if (noState) app.append(noState);

  const main = el("div", { class: "main-col" });
  const script = renderScriptCard(s);
  if (script) main.append(script);
  const aside = el("aside", {});
  const decisions = renderDecisions(s);
  const activity = renderActivity(s);
  if (decisions) aside.append(decisions);
  if (activity) aside.append(activity);

  if (script || decisions || activity) {
    app.append(el("div", { class: "board" }, main, aside));
  }

  const storyboard = renderStoryboard(s);
  if (storyboard) app.append(storyboard);
  const found = renderFoundMedia(s);
  if (found) app.append(found);
  const renders = renderRenders(s);
  if (renders) app.append(renders);
}

async function refresh() {
  state = await getJSON(`/api/project/${encodeURIComponent(projectId)}/state`);
  render();
}

refresh().catch((err) => {
  app.innerHTML = "";
  app.append(el("div", { class: "empty", style: "margin-top:80px" },
    el("div", { class: "big" }, "PROJECT NOT FOUND"),
    el("div", {}, String(err))));
});
// ?static=1 disables the live feed (screenshots, static exports).
if (!new URLSearchParams(location.search).has("static")) {
  subscribe(`/api/project/${encodeURIComponent(projectId)}/events`, () => refresh().catch(console.error));
}
