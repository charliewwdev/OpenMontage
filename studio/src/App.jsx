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

const api = (path, opts) =>
  fetch(path, opts).then(async (r) => {
    const data = await r.json();
    if (!r.ok) throw new Error(data.error || r.statusText);
    return data;
  });

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
    <div className="node-card shot">
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

const nodeTypes = {
  stage: StageNode,
  shot: ShotNode,
  subgraph: SubgraphNode,
};

const LEDGER_KEYS = [
  "pending",
  "running",
  "succeeded",
  "rewriting",
  "failed",
  "needs_review",
];

function FitOnChange({ deps }) {
  const { fitView } = useReactFlow();
  useEffect(() => {
    const id = requestAnimationFrame(() => {
      fitView({ padding: 0.18, duration: 220 });
    });
    return () => cancelAnimationFrame(id);
  }, [fitView, ...deps]);
  return null;
}

function StudioApp() {
  const [mode, setMode] = useState("lab");
  const [pipeline, setPipeline] = useState(null);
  const [subgraphs, setSubgraphs] = useState([]);
  const [selectedSubgraph, setSelectedSubgraph] = useState(null);
  const [subgraphDoc, setSubgraphDoc] = useState(null);
  const [projects, setProjects] = useState([]);
  const [project, setProject] = useState("");
  const [storyboard, setStoryboard] = useState(null);
  const [ledger, setLedger] = useState(null);
  const [selectedShot, setSelectedShot] = useState(null);
  const [chat, setChat] = useState("");
  const [statusMsg, setStatusMsg] = useState("");

  useEffect(() => {
    api("/api/pipeline/short-drama").then(setPipeline).catch((e) => setStatusMsg(String(e)));
    api("/api/subgraphs").then((d) => setSubgraphs(d.subgraphs || [])).catch(() => {});
    api("/api/projects").then((d) => setProjects(d.projects || [])).catch(() => {});
  }, []);

  useEffect(() => {
    if (!selectedSubgraph) {
      setSubgraphDoc(null);
      return;
    }
    api(`/api/subgraphs/${selectedSubgraph}/graph`)
      .then((d) => setSubgraphDoc(d.document))
      .catch((e) => setStatusMsg(String(e)));
  }, [selectedSubgraph]);

  const loadProject = useCallback(async (name) => {
    setProject(name);
    setSelectedShot(null);
    setStatusMsg("");
    try {
      const sb = await api(`/api/project/storyboard?name=${encodeURIComponent(name)}`);
      setStoryboard(sb.storyboard);
    } catch {
      setStoryboard(null);
    }
    try {
      const ld = await api(`/api/project/ledger?name=${encodeURIComponent(name)}`);
      setLedger(ld.ledger);
    } catch {
      setLedger(null);
    }
  }, []);

  const labNodesEdges = useMemo(() => {
    if (subgraphDoc) {
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
    if (!pipeline) return { nodes: [], edges: [] };
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
  }, [pipeline, subgraphDoc]);

  const prodNodesEdges = useMemo(() => {
    if (!storyboard) return { nodes: [], edges: [] };
    const jobByShot = {};
    for (const job of ledger?.jobs || []) {
      jobByShot[job.shot_id] = job;
    }
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
  }, [storyboard, ledger]);

  const onNodeClick = useCallback(
    (_e, node) => {
      if (mode === "production" && node.type === "shot") {
        setSelectedShot(node.data.shot);
      }
    },
    [mode]
  );

  const sendChat = async () => {
    const text = chat.trim();
    if (!text) return;
    if (mode === "production" && project && selectedShot) {
      const patch = {};
      const dur = text.match(/(\d+(?:\.\d+)?)\s*秒|duration\s*[:=]?\s*(\d+(?:\.\d+)?)/i);
      if (dur) {
        patch.duration_sec = Number(dur[1] || dur[2]);
      }
      if (/仰拍|low\s*angle/i.test(text)) {
        patch.shot_language = {
          ...(selectedShot.shot_language || {}),
          camera_movement: "tilt_up",
        };
        patch.description = `${selectedShot.description || ""} (仰拍)`.trim();
      }
      if (Object.keys(patch).length) {
        try {
          const res = await api("/api/project/storyboard/patch", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              project,
              shot_id: selectedShot.id,
              patch,
            }),
          });
          setStoryboard(res.storyboard);
          const updated = (res.storyboard?.shots || []).find((s) => s.id === selectedShot.id);
          if (updated) setSelectedShot(updated);
          await api("/api/project/ledger/invalidate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ project, shot_id: selectedShot.id }),
          });
          const ld = await api(`/api/project/ledger?name=${encodeURIComponent(project)}`);
          setLedger(ld.ledger);
          setStatusMsg(`Patched ${selectedShot.id} and invalidated ledger job`);
        } catch (e) {
          setStatusMsg(String(e));
        }
      } else {
        setStatusMsg("Select a shot and include duration or 仰拍 / low angle.");
      }
    } else if (mode === "lab") {
      setStatusMsg(
        "Lab NL graph edits: use director chat in Cursor to patch subgraph IR (validate via API)."
      );
    }
    setChat("");
  };

  const flow = mode === "lab" ? labNodesEdges : prodNodesEdges;
  const showEmpty = mode === "production" && !project;

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark">
            OpenMontage <span>Drama</span>
          </div>
          <div className="brand-sub">Cutting room</div>
        </div>
        <div className="mode-toggle">
          <button
            className={mode === "lab" ? "active" : ""}
            onClick={() => setMode("lab")}
          >
            编辑流程
          </button>
          <button
            className={mode === "production" ? "active" : ""}
            onClick={() => setMode("production")}
          >
            制作中
          </button>
        </div>
        <div className="spacer" />
        {statusMsg ? <div className="status-toast">{statusMsg}</div> : null}
      </header>

      <div className="main">
        <aside className="rail">
          {mode === "lab" ? (
            <>
              <h3>Main chain</h3>
              <button
                className={`item ${!selectedSubgraph ? "active" : ""}`}
                onClick={() => setSelectedSubgraph(null)}
              >
                short-drama stages
              </button>
              <h3>Subgraphs</h3>
              {subgraphs.map((s) => (
                <button
                  key={s.id}
                  className={`item ${selectedSubgraph === s.id ? "active" : ""}`}
                  onClick={() => setSelectedSubgraph(s.id)}
                >
                  {s.id}
                </button>
              ))}
            </>
          ) : (
            <>
              <h3>Projects</h3>
              {projects.length === 0 ? (
                <p className="hint">No projects/ yet</p>
              ) : (
                projects.map((p) => (
                  <button
                    key={p}
                    className={`item ${project === p ? "active" : ""}`}
                    onClick={() => loadProject(p)}
                  >
                    {p}
                  </button>
                ))
              )}
              {ledger?.stats ? (
                <>
                  <h3>Ledger</h3>
                  <div className="ledger-grid">
                    {LEDGER_KEYS.filter((k) => ledger.stats[k] != null).map((k) => (
                      <div className="ledger-chip" key={k}>
                        <span className="k">{k}</span>
                        <span className="v">{ledger.stats[k]}</span>
                      </div>
                    ))}
                    {ledger.stats.total_cost_usd != null ? (
                      <div className="ledger-chip">
                        <span className="k">cost</span>
                        <span className="v">${ledger.stats.total_cost_usd}</span>
                      </div>
                    ) : null}
                  </div>
                </>
              ) : null}
            </>
          )}
        </aside>

        <div className="canvas-wrap">
          {showEmpty ? (
            <div className="empty-canvas">
              <div>
                <h2>选择一个项目</h2>
                <p className="hint">从左侧 Projects 打开 storyboard 与镜头账本</p>
              </div>
            </div>
          ) : null}
          <ReactFlow
            key={`${mode}-${selectedSubgraph || "main"}-${project || "none"}`}
            nodes={flow.nodes}
            edges={flow.edges}
            nodeTypes={nodeTypes}
            fitView
            fitViewOptions={{ padding: 0.18 }}
            minZoom={0.2}
            maxZoom={1.6}
            onNodeClick={onNodeClick}
            proOptions={{ hideAttribution: true }}
            defaultEdgeOptions={{ type: "smoothstep" }}
          >
            <FitOnChange
              deps={[mode, selectedSubgraph, project, flow.nodes.length, ledger?.jobs?.length]}
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

        <aside className="inspector">
          <h3>Inspector</h3>
          {mode === "lab" && selectedSubgraph && subgraphDoc ? (
            <>
              <p className="title">{subgraphDoc.title || subgraphDoc.id}</p>
              <p className="hint">{subgraphDoc.description}</p>
              <div className="meta-row">
                <span className="meta-pill">nodes {subgraphDoc.nodes?.length ?? 0}</span>
                <span className="meta-pill">edges {subgraphDoc.edges?.length ?? 0}</span>
              </div>
            </>
          ) : null}
          {mode === "lab" && !selectedSubgraph && pipeline ? (
            <>
              <p className="title">Scheme F</p>
              <p className="hint">
                主链 {pipeline.stages.length} 个阶段。点左侧子图可钻入路由 / I2V / QA。
              </p>
            </>
          ) : null}
          {mode === "production" && selectedShot ? (
            <>
              <p className="title">{selectedShot.id}</p>
              <p className="hint">{selectedShot.description}</p>
              <div className="meta-row">
                <span className="meta-pill">intent {selectedShot.shot_intent}</span>
                <span className="meta-pill">{selectedShot.duration_sec}s</span>
              </div>
              <button
                className="btn"
                onClick={async () => {
                  if (!project) return;
                  try {
                    await api("/api/project/ledger/invalidate", {
                      method: "POST",
                      headers: { "Content-Type": "application/json" },
                      body: JSON.stringify({
                        project,
                        shot_id: selectedShot.id,
                      }),
                    });
                    const ld = await api(
                      `/api/project/ledger?name=${encodeURIComponent(project)}`
                    );
                    setLedger(ld.ledger);
                    setStatusMsg(`Invalidated ${selectedShot.id}`);
                  } catch (e) {
                    setStatusMsg(String(e));
                  }
                }}
              >
                Rerun shot
              </button>
            </>
          ) : (
            mode === "production" && (
              <p className="hint">点选镜头卡片查看详情或重跑。</p>
            )
          )}
        </aside>
      </div>

      <div className="chat">
        <input
          value={chat}
          onChange={(e) => setChat(e.target.value)}
          placeholder={
            mode === "production"
              ? "改选中镜头：例如「改成仰拍，时长 4 秒」"
              : "Lab：在 Cursor 中对 EP 描述子图修改；此处提示向导"
          }
          onKeyDown={(e) => e.key === "Enter" && sendChat()}
        />
        <button onClick={sendChat}>Send</button>
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
