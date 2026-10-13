/** @deprecated Use config.six_steps / platform.yaml via /api/config */
export const STEPS = [];
/** @deprecated Desk labels belong in platform config when re-enabled */
export const DESKS = [];

export function titleFromName(name) {
  return String(name || "")
    .replace(/[-_]/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export function deriveProjectView(bundle) {
  if (!bundle) return null;
  const arts = bundle.artifacts || {};
  const script = arts.script || {};
  const bible = arts.character_bible || {};
  const breakdown = arts.episode_breakdown || {};
  const storyboard = arts.storyboard || {};
  const ledger = arts.ledger || {};

  const characters = (bible.characters || bible.cast || []).map((c) => ({
    ...c,
    name: c.name || c.display_name || c.id,
  }));
  const locations = (bible.locations || bible.scenes || bible.sets || []).map((c) => ({
    ...c,
    name: c.name || c.title || c.id,
  }));
  const props = (bible.props || bible.prop_assets || []).map((c) => ({
    ...c,
    name: c.name || c.title || c.id,
  }));
  const episodes =
    script.episodes ||
    (breakdown.episodes || []).map((ep) => ({
      ...ep,
      episodeNumber: ep.episodeNumber || ep.index || 1,
      content:
        ep.content ||
        (ep.scenes || [])
          .map((s) => `【${s.title || s.id}】\n${s.purpose || ""}`)
          .join("\n\n"),
      status: ep.status || "draft",
    })) ||
    (script.scenes
      ? [
          {
            id: "ep01",
            episodeNumber: 1,
            title: script.title || "第 1 集",
            content: (script.scenes || []).map((s) => s.text || s.summary || "").join("\n\n"),
            status: "draft",
          },
        ]
      : []);

  const shots = storyboard.shots || [];
  const jobs = ledger.jobs || [];
  const jobByShot = Object.fromEntries(jobs.map((j) => [j.shot_id, j]));
  const ready = jobs.filter((j) => ["needs_review", "succeeded", "approved"].includes(j.status)).length;
  const hasExport = Boolean((arts.metrics || {}).last_export?.path);

  return {
    name: bundle.name,
    title: script.title || titleFromName(bundle.name),
    ratio: script.aspect_ratio || breakdown.aspect_ratio || script.ratio || "9:16",
    genre: script.genre || arts.research?.genre || script.tone || "短剧",
    style: script.visual_style || bible.visual_style || script.style || "",
    synopsis: script.synopsis || script.logline || script.summary || bundle.source_excerpt || "",
    brief: script.brief || script.creative_brief || "",
    sourceExcerpt: bundle.source_excerpt || "",
    episodes,
    characters,
    locations,
    props,
    shots,
    jobs,
    jobByShot,
    ledger,
    storyboard,
    script,
    bible,
    breakdown,
    steps: bundle.steps || [],
    status: bundle.status || {},
    counts: {
      script: `${episodes.length} 集`,
      characters: String(characters.length),
      locations: String(locations.length),
      props: String(props.length),
      storyboard: `${ready}/${shots.length} 镜`,
      edit: hasExport ? "已成片" : shots.length ? (ready ? "可导出" : "待生成") : "未开始",
    },
    progress: STEPS.map((step) => {
      const meta = (bundle.steps || []).find((s) => s.id === step.id);
      return meta?.state === "done" || meta?.state === "partial";
    }),
  };
}

export function libraryCardFromListItem(name, bundleHint) {
  const view = bundleHint ? deriveProjectView(bundleHint) : null;
  return {
    id: name,
    title: view?.title || titleFromName(name),
    genre: view?.genre || "短剧",
    ratio: view?.ratio || "9:16",
    synopsis: view?.synopsis || "打开后加载剧本与素材档案",
    progress: view?.progress || STEPS.map(() => false),
    shotsReady: view
      ? `${view.jobs.filter((j) => ["needs_review", "succeeded", "approved"].includes(j.status)).length}/${view.shots.length}`
      : "—",
  };
}
