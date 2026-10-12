import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  MarkerType,
  Handle,
  Position,
  ReactFlowProvider,
  useReactFlow,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { api } from "./api";

const STEPS = [
  { id: "script", label: "剧本" },
  { id: "characters", label: "角色" },
  { id: "locations", label: "场景" },
  { id: "props", label: "道具" },
  { id: "storyboard", label: "分镜" },
  { id: "edit", label: "剪辑" },
];

const DESKS = [
  { id: "director", label: "编导台" },
  { id: "canvas", label: "画布" },
  { id: "edit", label: "剪辑室" },
];

const LEDGER_KEYS = [
  "pending",
  "running",
  "succeeded",
  "rewriting",
  "failed",
  "needs_review",
];

function StageNode({ data }) {
  return (
    <div className="node-card stage">
      <Handle type="target" position={Position.Left} className="handle" />
      <div className="eyebrow">
        <span className="kind">stage</span>
        {data.human ? <span className="status-pill human">gate</span> : null}
      </div>
      <strong>{data.label}</strong>
      <div className="sub">{data.subtitle || "main chain"}</div>
      <Handle type="source" position={Position.Right} className="handle" />
    </div>
  );
}

function ShotNode({ data }) {
  return (
    <div className={`node-card shot status-${data.status || "pending"}`}>
      <Handle type="target" position={Position.Left} className="handle" />
      <div className="eyebrow">
        <span className="kind">{data.intent || "shot"}</span>
        <span className={`status-pill ${data.status || "pending"}`}>
          {data.status || "pending"}
        </span>
      </div>
      <strong>{data.label}</strong>
      <div className="sub">{data.blurb || "—"}</div>
      <Handle type="source" position={Position.Right} className="handle" />
    </div>
  );
}

function SubgraphNode({ data }) {
  return (
    <div className="node-card subgraph">
      <Handle type="target" position={Position.Left} className="handle" />
      <div className="eyebrow">
        <span className="kind">{data.type || "node"}</span>
      </div>
      <strong>{data.label}</strong>
      <Handle type="source" position={Position.Right} className="handle" />
    </div>
  );
}

const nodeTypes = { stage: StageNode, shot: ShotNode, subgraph: SubgraphNode };

function FitOnChange({ deps }) {
  const { fitView } = useReactFlow();
  useEffect(() => {
    const id = requestAnimationFrame(() => fitView({ padding: 0.16, duration: 220 }));
    return () => cancelAnimationFrame(id);
  }, [fitView, ...deps]);
  return null;
}

function StepRail({ steps, active, onSelect }) {
  return (
    <nav className="step-rail" aria-label="六步工作流">
      {STEPS.map((step, i) => {
        const meta = (steps || []).find((s) => s.id === step.id);
        const state = meta?.state || "empty";
        return (
          <button
            key={step.id}
            type="button"
            className={`step-chip ${active === step.id ? "active" : ""} ${state}`}
            onClick={() => onSelect(step.id)}
          >
            <span className="step-num">{i + 1}</span>
            <span className="step-label">{step.label}</span>
            <span className={`step-dot ${state}`} />
          </button>
        );
      })}
    </nav>
  );
}

function AssetCard({ title, subtitle, meta, onClick, active }) {
  return (
    <button type="button" className={`asset-card ${active ? "active" : ""}`} onClick={onClick}>
      <div className="asset-thumb" aria-hidden />
      <div className="asset-body">
        <strong>{title}</strong>
        <p>{subtitle}</p>
        {meta ? <span className="asset-meta">{meta}</span> : null}
      </div>
    </button>
  );
}

function DirectorDesk({
  step,
  bundle,
  selectedId,
  onSelect,
}) {
  const arts = bundle?.artifacts || {};
  const bible = arts.character_bible || {};
  const breakdown = arts.episode_breakdown || {};
  const script = arts.script || {};
  const episode = (breakdown.episodes || [])[0];

  if (step === "script") {
    const scenes = episode?.scenes || [];
    const lines = script.scenes || script.beats || script.dialogue || [];
    return (
      <div className="desk-panel">
        <header className="desk-head">
          <h2>{breakdown.series_title || script.title || "剧本"}</h2>
          <p>{episode?.logline || script.logline || "分集剧本与场次结构"}</p>
        </header>
        <div className="script-layout">
          <aside className="scene-list">
            <h3>场次</h3>
            {scenes.length === 0 ? (
              <p className="hint">暂无 episode_breakdown</p>
            ) : (
              scenes.map((sc) => (
                <button
                  key={sc.id}
                  type="button"
                  className={`item ${selectedId === sc.id ? "active" : ""}`}
                  onClick={() => onSelect(sc)}
                >
                  <span className="mono">{sc.id}</span>
                  <strong>{sc.title}</strong>
                  <span className="muted">{sc.purpose}</span>
                </button>
              ))
            )}
          </aside>
          <article className="script-body">
            <h3>正文 / 结构</h3>
            {episode ? (
              <div className="prose">
                <p>
                  <b>钩子：</b>
                  {episode.hook}
                </p>
                <p>
                  <b>悬念：</b>
                  {episode.cliffhanger}
                </p>
                <p>
                  <b>时长：</b>
                  {episode.target_duration_seconds}s · {breakdown.aspect_ratio}
                </p>
              </div>
            ) : null}
            {Array.isArray(lines) && lines.length > 0 ? (
              <pre className="script-dump">{JSON.stringify(lines, null, 2)}</pre>
            ) : script.full_text || script.text ? (
              <pre className="script-dump">{script.full_text || script.text}</pre>
            ) : (
              <p className="hint">script.json 已加载时可在此展示对白正文</p>
            )}
          </article>
        </div>
      </div>
    );
  }

  if (step === "characters") {
    const chars = bible.characters || [];
    return (
      <div className="desk-panel">
        <header className="desk-head">
          <h2>角色圣经</h2>
          <p>{bible.visual_style || "外貌 · 服装变体 · 一致性锚点"}</p>
        </header>
        <div className="asset-grid">
          {chars.map((c) => (
            <AssetCard
              key={c.id}
              title={c.display_name || c.id}
              subtitle={c.appearance || c.role}
              meta={(c.wardrobe_variants || []).map((w) => w.label).join(" · ")}
              active={selectedId === c.id}
              onClick={() => onSelect(c)}
            />
          ))}
          {chars.length === 0 ? <p className="hint">暂无 character_bible</p> : null}
        </div>
      </div>
    );
  }

  if (step === "locations") {
    const locs = bible.locations || [];
    return (
      <div className="desk-panel">
        <header className="desk-head">
          <h2>场景资产</h2>
          <p>地点描述与分集场次绑定</p>
        </header>
        <div className="asset-grid">
          {locs.map((loc) => (
            <AssetCard
              key={loc.id}
              title={loc.name || loc.id}
              subtitle={loc.description}
              meta={loc.id}
              active={selectedId === loc.id}
              onClick={() => onSelect(loc)}
            />
          ))}
          {locs.length === 0 ? <p className="hint">圣经中尚无 locations</p> : null}
        </div>
      </div>
    );
  }

  if (step === "props") {
    const props = bible.props || bible.prop_assets || [];
    return (
      <div className="desk-panel">
        <header className="desk-head">
          <h2>道具档案</h2>
          <p>关键道具三视图与稳定描述（有则展示）</p>
        </header>
        <div className="asset-grid">
          {props.length === 0 ? (
            <div className="empty-block">
              <h3>本集暂无独立道具表</h3>
              <p className="hint">可在 character_bible.props 补充；分镜里的 insert 镜头可暂代关键道具。</p>
            </div>
          ) : (
            props.map((p) => (
              <AssetCard
                key={p.id}
                title={p.name || p.id}
                subtitle={p.description}
                active={selectedId === p.id}
                onClick={() => onSelect(p)}
              />
            ))
          )}
        </div>
      </div>
    );
  }

  if (step === "storyboard") {
    const shots = arts.storyboard?.shots || [];
    const jobs = Object.fromEntries((arts.ledger?.jobs || []).map((j) => [j.shot_id, j]));
    return (
      <div className="desk-panel">
        <header className="desk-head">
          <h2>分镜导演台</h2>
          <p>
            {arts.storyboard?.episode_id || "episode"} · {arts.storyboard?.aspect_ratio || "9:16"} ·{" "}
            {shots.length} 镜
          </p>
        </header>
        <div className="shot-grid">
          {shots.map((shot) => {
            const st = jobs[shot.id]?.status || "pending";
            return (
              <button
                key={shot.id}
                type="button"
                className={`shot-tile ${selectedId === shot.id ? "active" : ""}`}
                onClick={() => onSelect(shot)}
              >
                <div className="shot-frame">
                  <span className="shot-index">#{shot.index ?? "·"}</span>
                  <span className={`status-pill ${st}`}>{st}</span>
                </div>
                <strong>{shot.description || shot.id}</strong>
                <div className="shot-meta">
                  <span>{shot.shot_intent}</span>
                  <span>{shot.duration_sec}s</span>
                </div>
                {shot.dialogue ? <p className="dialogue">「{shot.dialogue}」</p> : null}
              </button>
            );
          })}
          {shots.length === 0 ? <p className="hint">暂无 storyboard</p> : null}
        </div>
      </div>
    );
  }

  // edit step summary in director desk
  const shots = arts.storyboard?.shots || [];
  const stats = arts.ledger?.stats || {};
  return (
    <div className="desk-panel">
      <header className="desk-head">
        <h2>成片准备</h2>
        <p>镜头账本与剪辑室共用同一时间线数据</p>
      </header>
      <div className="ledger-grid big">
        {LEDGER_KEYS.filter((k) => stats[k] != null).map((k) => (
          <div className="ledger-chip" key={k}>
            <span className="k">{k}</span>
            <span className="v">{stats[k]}</span>
          </div>
        ))}
        <div className="ledger-chip">
          <span className="k">shots</span>
          <span className="v">{shots.length}</span>
        </div>
      </div>
      <p className="hint">切换到「剪辑室」编排时间线；切换到「画布」查看镜头 DAG / 子图。</p>
    </div>
  );
}

function EditDesk({ storyboard, ledger, selectedShot, onSelect }) {
  const shots = storyboard?.shots || [];
  const jobs = Object.fromEntries((ledger?.jobs || []).map((j) => [j.shot_id, j]));
  const total = shots.reduce((n, s) => n + (Number(s.duration_sec) || 0), 0);

  return (
    <div className="desk-panel edit-desk">
      <header className="desk-head">
        <h2>剪辑室</h2>
        <p>
          预览轨 · 总时长约 {total.toFixed(1)}s · {storyboard?.aspect_ratio || "9:16"}
        </p>
      </header>
      <div className="preview-stage">
        <div className={`phone-frame ratio-${(storyboard?.aspect_ratio || "9:16").replace(":", "x")}`}>
          {selectedShot ? (
            <div className="preview-copy">
              <span className="eyebrow-text">{selectedShot.id}</span>
              <h3>{selectedShot.description}</h3>
              {selectedShot.dialogue ? <p className="dialogue">「{selectedShot.dialogue}」</p> : null}
              <p className="muted">
                {selectedShot.shot_intent} · {selectedShot.duration_sec}s ·{" "}
                {jobs[selectedShot.id]?.status || "pending"}
              </p>
            </div>
          ) : (
            <div className="preview-copy">
              <h3>选择时间线上的镜头</h3>
              <p className="muted">竖屏预览位 · 绑定 storyboard 与 ledger</p>
            </div>
          )}
        </div>
      </div>
      <div className="timeline">
        <div className="timeline-track">
          {shots.map((shot) => {
            const st = jobs[shot.id]?.status || "pending";
            const flex = Math.max(Number(shot.duration_sec) || 1, 1);
            return (
              <button
                key={shot.id}
                type="button"
                className={`tl-clip ${st} ${selectedShot?.id === shot.id ? "active" : ""}`}
                style={{ flex }}
                onClick={() => onSelect(shot)}
                title={shot.description}
              >
                <span>{shot.id.replace(/^ep\d+_/, "")}</span>
              </button>
            );
          })}
        </div>
        {shots.length === 0 ? <p className="hint">无镜头可编排</p> : null}
      </div>
    </div>
  );
}

function StudioApp() {
  const [desk, setDesk] = useState("director");
  const [step, setStep] = useState("script");
  const [pipeline, setPipeline] = useState(null);
  const [subgraphs, setSubgraphs] = useState([]);
  const [selectedSubgraph, setSelectedSubgraph] = useState(null);
  const [subgraphDoc, setSubgraphDoc] = useState(null);
  const [projects, setProjects] = useState([]);
  const [project, setProject] = useState("");
  const [bundle, setBundle] = useState(null);
  const [selected, setSelected] = useState(null);
  const [chat, setChat] = useState("");
  const [statusMsg, setStatusMsg] = useState("");
  const [canvasSource, setCanvasSource] = useState("shots"); // shots | pipeline | subgraph

  const storyboard = bundle?.artifacts?.storyboard || null;
  const ledger = bundle?.artifacts?.ledger || null;

  const loadProject = useCallback(async (name) => {
    setProject(name);
    setSelected(null);
    setStatusMsg("");
    try {
      const b = await api(`/api/project/bundle?name=${encodeURIComponent(name)}`);
      setBundle(b);
      const firstDone = (b.steps || []).find((s) => s.state !== "empty");
      if (firstDone) setStep(firstDone.id);
    } catch (e) {
      setBundle(null);
      setStatusMsg(String(e));
    }
  }, []);

  useEffect(() => {
    api("/api/pipeline/short-drama").then(setPipeline).catch((e) => setStatusMsg(String(e)));
    api("/api/subgraphs")
      .then((d) => setSubgraphs(d.subgraphs || []))
      .catch(() => {});
    api("/api/projects")
      .then((d) => {
        const list = d.projects || [];
        setProjects(list);
        if (list.length) loadProject(list[0]);
      })
      .catch(() => {});
  }, [loadProject]);

  useEffect(() => {
    if (!selectedSubgraph) {
      setSubgraphDoc(null);
      return;
    }
    api(`/api/subgraphs/${selectedSubgraph}/graph`)
      .then((d) => setSubgraphDoc(d.document))
      .catch((e) => setStatusMsg(String(e)));
  }, [selectedSubgraph]);

  const refreshLedger = useCallback(async () => {
    if (!project) return;
    const b = await api(`/api/project/bundle?name=${encodeURIComponent(project)}`);
    setBundle(b);
  }, [project]);

  const labNodesEdges = useMemo(() => {
    if (canvasSource === "subgraph" && subgraphDoc) {
      const nodes = (subgraphDoc.nodes || []).map((n, i) => ({
        id: n.id,
        type: "subgraph",
        position: { x: 80 + (i % 4) * 210, y: 70 + Math.floor(i / 4) * 130 },
        data: { label: n.label || n.id, type: n.type },
      }));
      const edges = (subgraphDoc.edges || []).map((e, i) => ({
        id: `e-${i}`,
        source: e.from,
        target: e.to,
        label: e.port || "default",
        style: { stroke: "#0d8a7c", strokeWidth: 1.6 },
        labelStyle: { fill: "#3d4f5f", fontSize: 10, fontWeight: 600 },
        markerEnd: { type: MarkerType.ArrowClosed, color: "#0d8a7c" },
      }));
      return { nodes, edges };
    }
    if (canvasSource === "pipeline" && pipeline) {
      const nodes = pipeline.stage_details.map((s, i) => ({
        id: s.name,
        type: "stage",
        position: { x: 40 + i * 200, y: 140 },
        data: {
          label: s.name,
          subtitle: s.subgraph_refs ? "has subgraph_refs" : "stage",
          human: !!s.human_approval_default,
        },
      }));
      const edges = pipeline.stages.slice(0, -1).map((name, i) => ({
        id: `stage-${i}`,
        source: name,
        target: pipeline.stages[i + 1],
        style: { stroke: "#15202b", strokeWidth: 1.5 },
        markerEnd: { type: MarkerType.ArrowClosed, color: "#15202b" },
      }));
      return { nodes, edges };
    }
    // shots DAG
    if (!storyboard) return { nodes: [], edges: [] };
    const jobByShot = {};
    for (const job of ledger?.jobs || []) jobByShot[job.shot_id] = job;
    const nodes = storyboard.shots.map((shot, i) => ({
      id: shot.id,
      type: "shot",
      position: { x: 48 + (i % 4) * 220, y: 56 + Math.floor(i / 4) * 150 },
      data: {
        label: shot.id,
        intent: shot.shot_intent,
        status: jobByShot[shot.id]?.status || "pending",
        blurb: shot.description || "No description",
        shot,
      },
    }));
    const edges = storyboard.shots.slice(0, -1).map((shot, i) => ({
      id: `shot-e-${i}`,
      source: shot.id,
      target: storyboard.shots[i + 1].id,
      style: { stroke: "#9aa8b0", strokeWidth: 1.4 },
      markerEnd: { type: MarkerType.ArrowClosed, color: "#9aa8b0" },
    }));
    return { nodes, edges };
  }, [canvasSource, subgraphDoc, pipeline, storyboard, ledger]);

  const onNodeClick = useCallback((_e, node) => {
    if (node.type === "shot" && node.data.shot) {
      setSelected(node.data.shot);
      setStep("storyboard");
    }
  }, []);

  const sendChat = async () => {
    const text = chat.trim();
    if (!text) return;
    if (project && selected?.id && storyboard) {
      const patch = {};
      const dur = text.match(/(\d+(?:\.\d+)?)\s*秒|duration\s*[:=]?\s*(\d+(?:\.\d+)?)/i);
      if (dur) patch.duration_sec = Number(dur[1] || dur[2]);
      if (/仰拍|low\s*angle/i.test(text)) {
        patch.shot_language = {
          ...(selected.shot_language || {}),
          camera_movement: "tilt_up",
        };
        patch.description = `${selected.description || ""} (仰拍)`.trim();
      }
      if (Object.keys(patch).length) {
        try {
          await api("/api/project/storyboard/patch", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ project, shot_id: selected.id, patch }),
          });
          await api("/api/project/ledger/invalidate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ project, shot_id: selected.id }),
          });
          await refreshLedger();
          setStatusMsg(`已更新 ${selected.id} 并作废账本任务`);
        } catch (e) {
          setStatusMsg(String(e));
        }
      } else {
        setStatusMsg("选中镜头后可用：「改成仰拍」「时长 4 秒」");
      }
    } else {
      setStatusMsg("先选项目与镜头，再下达手术式指令");
    }
    setChat("");
  };

  const selectedShot =
    selected && storyboard?.shots?.some((s) => s.id === selected.id) ? selected : null;

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark">
            OpenMontage <span>Drama</span>
          </div>
          <div className="brand-sub">六步 · 三台 · 可部署制片台</div>
        </div>

        <label className="project-select">
          <span>项目</span>
          <select
            value={project}
            onChange={(e) => (e.target.value ? loadProject(e.target.value) : null)}
          >
            <option value="">选择项目…</option>
            {projects.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
        </label>

        <div className="desk-toggle">
          {DESKS.map((d) => (
            <button
              key={d.id}
              type="button"
              className={desk === d.id ? "active" : ""}
              onClick={() => {
                setDesk(d.id);
                if (d.id === "edit") setStep("edit");
                if (d.id === "director" && step === "edit") setStep("storyboard");
              }}
            >
              {d.label}
            </button>
          ))}
        </div>

        <div className="spacer" />
        {statusMsg ? <div className="status-toast">{statusMsg}</div> : null}
      </header>

      <StepRail
        steps={bundle?.steps}
        active={step}
        onSelect={(id) => {
          setStep(id);
          if (id === "edit") setDesk("edit");
          else if (desk === "edit") setDesk("director");
          else setDesk(desk === "canvas" ? "canvas" : "director");
        }}
      />

      <div className="main">
        <aside className="rail">
          {desk === "canvas" ? (
            <>
              <h3>画布源</h3>
              <button
                type="button"
                className={`item ${canvasSource === "shots" ? "active" : ""}`}
                onClick={() => setCanvasSource("shots")}
              >
                镜头 DAG
              </button>
              <button
                type="button"
                className={`item ${canvasSource === "pipeline" ? "active" : ""}`}
                onClick={() => setCanvasSource("pipeline")}
              >
                short-drama 主链
              </button>
              <h3>子图 IR</h3>
              {subgraphs.map((s) => (
                <button
                  key={s.id}
                  type="button"
                  className={`item ${selectedSubgraph === s.id && canvasSource === "subgraph" ? "active" : ""}`}
                  onClick={() => {
                    setSelectedSubgraph(s.id);
                    setCanvasSource("subgraph");
                  }}
                >
                  {s.id}
                </button>
              ))}
            </>
          ) : (
            <>
              <h3>项目</h3>
              {projects.length === 0 ? (
                <p className="hint">projects/ 为空。挂载数据卷或放入短剧项目。</p>
              ) : (
                projects.map((p) => (
                  <button
                    key={p}
                    type="button"
                    className={`item ${project === p ? "active" : ""}`}
                    onClick={() => loadProject(p)}
                  >
                    {p}
                  </button>
                ))
              )}
              {ledger?.stats ? (
                <>
                  <h3>任务队列</h3>
                  <div className="ledger-grid">
                    {LEDGER_KEYS.filter((k) => ledger.stats[k] != null).map((k) => (
                      <div className="ledger-chip" key={k}>
                        <span className="k">{k}</span>
                        <span className="v">{ledger.stats[k]}</span>
                      </div>
                    ))}
                  </div>
                </>
              ) : null}
            </>
          )}
        </aside>

        <div className="workspace">
          {desk === "director" ? (
            project ? (
              <DirectorDesk
                step={step}
                bundle={bundle}
                selectedId={selected?.id}
                onSelect={setSelected}
              />
            ) : (
              <div className="empty-canvas">
                <div>
                  <h2>打开一个短剧项目</h2>
                  <p className="hint">编导台：剧本 · 角色 · 场景 · 道具 · 分镜</p>
                </div>
              </div>
            )
          ) : null}

          {desk === "edit" ? (
            project ? (
              <EditDesk
                storyboard={storyboard}
                ledger={ledger}
                selectedShot={selectedShot}
                onSelect={setSelected}
              />
            ) : (
              <div className="empty-canvas">
                <div>
                  <h2>剪辑室待项目</h2>
                  <p className="hint">时间线来自 storyboard + shot_jobs</p>
                </div>
              </div>
            )
          ) : null}

          {desk === "canvas" ? (
            <div className="canvas-wrap">
              {!project && canvasSource === "shots" ? (
                <div className="empty-canvas">
                  <div>
                    <h2>画布待命</h2>
                    <p className="hint">选项目看镜头 DAG，或切换主链 / 子图</p>
                  </div>
                </div>
              ) : null}
              <ReactFlow
                key={`${canvasSource}-${selectedSubgraph || "x"}-${project || "none"}`}
                nodes={labNodesEdges.nodes}
                edges={labNodesEdges.edges}
                nodeTypes={nodeTypes}
                fitView
                fitViewOptions={{ padding: 0.16 }}
                minZoom={0.2}
                maxZoom={1.6}
                onNodeClick={onNodeClick}
                proOptions={{ hideAttribution: true }}
                defaultEdgeOptions={{ type: "smoothstep" }}
              >
                <FitOnChange
                  deps={[
                    canvasSource,
                    selectedSubgraph,
                    project,
                    labNodesEdges.nodes.length,
                    ledger?.jobs?.length,
                  ]}
                />
                <Background gap={18} size={1} color="rgba(21,32,43,0.08)" />
                <Controls />
                <MiniMap
                  pannable
                  zoomable
                  nodeColor={() => "#0d8a7c"}
                  maskColor="rgba(238,241,244,0.72)"
                />
              </ReactFlow>
            </div>
          ) : null}
        </div>

        <aside className="inspector">
          <h3>检视</h3>
          {selectedShot ? (
            <>
              <p className="title">{selectedShot.id}</p>
              <p className="hint">{selectedShot.description}</p>
              <div className="meta-row">
                <span className="meta-pill">{selectedShot.shot_intent}</span>
                <span className="meta-pill">{selectedShot.duration_sec}s</span>
                {(selectedShot.character_ids || []).map((id) => (
                  <span className="meta-pill" key={id}>
                    {id}
                  </span>
                ))}
              </div>
              {selectedShot.keyframe_prompt ? (
                <p className="prompt-block">{selectedShot.keyframe_prompt}</p>
              ) : null}
              <button
                type="button"
                className="btn"
                onClick={async () => {
                  if (!project) return;
                  try {
                    await api("/api/project/ledger/invalidate", {
                      method: "POST",
                      headers: { "Content-Type": "application/json" },
                      body: JSON.stringify({ project, shot_id: selectedShot.id }),
                    });
                    await refreshLedger();
                    setStatusMsg(`已作废 ${selectedShot.id}`);
                  } catch (e) {
                    setStatusMsg(String(e));
                  }
                }}
              >
                重跑镜头
              </button>
            </>
          ) : selected ? (
            <>
              <p className="title">{selected.display_name || selected.name || selected.title || selected.id}</p>
              <p className="hint">
                {selected.appearance || selected.description || selected.purpose || selected.logline || "—"}
              </p>
              <pre className="inspect-json">{JSON.stringify(selected, null, 2)}</pre>
            </>
          ) : (
            <p className="hint">在编导台选资产，或在分镜 / 画布点选镜头。</p>
          )}

          {desk === "canvas" && canvasSource === "subgraph" && subgraphDoc ? (
            <>
              <h3>子图</h3>
              <p className="title">{subgraphDoc.title || subgraphDoc.id}</p>
              <p className="hint">{subgraphDoc.description}</p>
            </>
          ) : null}
        </aside>
      </div>

      <div className="chat">
        <div className="chat-label">Agent</div>
        <input
          value={chat}
          onChange={(e) => setChat(e.target.value)}
          placeholder="手术式修改：例如「改成仰拍，时长 4 秒」"
          onKeyDown={(e) => e.key === "Enter" && sendChat()}
        />
        <button type="button" onClick={sendChat}>
          发送
        </button>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <ReactFlowProvider>
      <StudioApp />
    </ReactFlowProvider>
  );
}
