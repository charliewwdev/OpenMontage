export const STEPS = [
  { id: "script", label: "剧本", note: "故事与分集" },
  { id: "characters", label: "角色", note: "人物与造型" },
  { id: "locations", label: "场景", note: "空间与光线" },
  { id: "props", label: "道具", note: "关键物件" },
  { id: "storyboard", label: "分镜", note: "镜头与视频" },
  { id: "edit", label: "剪辑", note: "排序与成片" },
];

export const DESKS = [
  { id: "director", label: "编导台", note: "六步制片" },
  { id: "canvas", label: "画布", note: "节点编排" },
  { id: "edit", label: "剪辑室", note: "时间线" },
];

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

  const characters = bible.characters || bible.cast || [];
  const locations = bible.locations || bible.scenes || bible.sets || [];
  const props = bible.props || bible.prop_assets || [];
  const episodes =
    script.episodes ||
    breakdown.episodes ||
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
  const succeeded = jobs.filter((j) => j.status === "succeeded").length;

  return {
    name: bundle.name,
    title: script.title || titleFromName(bundle.name),
    ratio: script.aspect_ratio || script.ratio || "9:16",
    genre: script.genre || script.tone || "短剧",
    style: script.visual_style || script.style || "",
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
    steps: bundle.steps || [],
    status: bundle.status || {},
    counts: {
      script: `${episodes.length} 集`,
      characters: String(characters.length),
      locations: String(locations.length),
      props: String(props.length),
      storyboard: `${succeeded}/${shots.length} 镜`,
      edit: shots.length ? (succeeded ? "可剪辑" : "待生成") : "未开始",
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
    shotsReady: view ? `${view.jobs.filter((j) => j.status === "succeeded").length}/${view.shots.length}` : "—",
  };
}
