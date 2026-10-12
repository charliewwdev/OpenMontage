import { useEffect, useMemo } from "react";
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

function StageNode({ data }) {
  return (
    <div className="node-card stage">
      <Handle type="target" position={Position.Left} className="handle" />
      <div className="eyebrow">
        <span className="kind">stage</span>
        {data.human ? <span className="status-pill needs_review">gate</span> : null}
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
        <span className={`status-pill ${data.status || "pending"}`}>{data.status || "pending"}</span>
      </div>
      <strong>{data.label}</strong>
      <div className="sub">{data.blurb || "—"}</div>
      <Handle type="source" position={Position.Right} className="handle" />
    </div>
  );
}

function SubgraphNode({ data }) {
  return (
    <div className="node-card">
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

export function CanvasDesk({
  canvasSource,
  setCanvasSource,
  pipeline,
  subgraphs,
  selectedSubgraph,
  setSelectedSubgraph,
  subgraphDoc,
  view,
  onSelectShot,
}) {
  const storyboard = view?.storyboard;
  const ledger = view?.ledger;

  const graph = useMemo(() => {
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
        style: { stroke: "#56c7c1", strokeWidth: 1.6 },
        markerEnd: { type: MarkerType.ArrowClosed, color: "#56c7c1" },
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
    if (!storyboard?.shots?.length) return { nodes: [], edges: [] };
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

  return (
    <div className="grid h-full min-h-[560px] gap-4 lg:grid-cols-[220px_minmax(0,1fr)]">
      <aside className="panel h-full space-y-1 p-3">
        <div className="label px-1">Canvas source</div>
        {[
          ["shots", "镜头 DAG"],
          ["pipeline", "short-drama 主链"],
        ].map(([id, label]) => (
          <button
            key={id}
            type="button"
            className={`w-full rounded-xl px-3 py-2.5 text-left text-sm font-semibold ${
              canvasSource === id ? "bg-[var(--projector)]/15 text-[var(--navy)]" : "hover:bg-[var(--panel-muted)]"
            }`}
            onClick={() => setCanvasSource(id)}
          >
            {label}
          </button>
        ))}
        <div className="label mt-4 px-1">Subgraph IR</div>
        {(subgraphs || []).map((s) => (
          <button
            key={s.id}
            type="button"
            className={`w-full rounded-xl px-3 py-2.5 text-left text-xs font-semibold ${
              selectedSubgraph === s.id && canvasSource === "subgraph"
                ? "bg-[var(--projector)]/15 text-[var(--navy)]"
                : "hover:bg-[var(--panel-muted)]"
            }`}
            onClick={() => {
              setSelectedSubgraph(s.id);
              setCanvasSource("subgraph");
            }}
          >
            {s.id}
          </button>
        ))}
      </aside>

      <div className="panel canvas-host relative min-h-[560px] overflow-hidden">
        <ReactFlowProvider>
          <ReactFlow
            nodes={graph.nodes}
            edges={graph.edges}
            nodeTypes={nodeTypes}
            fitView
            onNodeClick={(_, node) => {
              if (node.data?.shot) onSelectShot?.(node.data.shot);
            }}
            proOptions={{ hideAttribution: true }}
          >
            <Background gap={18} size={1} color="#d5dbe3" />
            <Controls />
            <MiniMap pannable zoomable />
            <FitOnChange deps={[canvasSource, graph.nodes.length, selectedSubgraph]} />
          </ReactFlow>
        </ReactFlowProvider>
      </div>
    </div>
  );
}
