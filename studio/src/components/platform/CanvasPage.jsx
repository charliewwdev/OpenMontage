import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  addEdge,
  useEdgesState,
  useNodesState,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Loader2, RefreshCw } from "lucide-react";
import { api } from "../../api";
import { toast } from "../../lib/toast";
import { PageShell } from "./PageShell";

function buildGraph(project, stepMeta = []) {
  const p = project?.progress || {};
  const counts = {
    script: p.episodes?.total || 0,
    character: p.characters?.total || 0,
    scene: p.scenes?.total || 0,
    prop: p.props?.total || 0,
    storyboard: p.shots?.total || 0,
    edit: p.shots?.completed || 0,
  };
  const meta = stepMeta;
  const nodes = meta.map((step) => ({
    id: step.id,
    position: { x: step.x, y: step.y },
    data: { label: `${step.label}\n${counts[step.id] ?? 0}` },
    style: {
      background: "#151822",
      color: "#f4f6fb",
      border: "1px solid rgba(124,108,255,.45)",
      borderRadius: 14,
      padding: 12,
      width: 140,
      whiteSpace: "pre-line",
      textAlign: "center",
      fontSize: 13,
      fontWeight: 600,
    },
  }));
  const edges = [
    { id: "e1", source: "script", target: "character" },
    { id: "e2", source: "script", target: "scene" },
    { id: "e3", source: "script", target: "prop" },
    { id: "e4", source: "character", target: "storyboard" },
    { id: "e5", source: "scene", target: "storyboard" },
    { id: "e6", source: "prop", target: "storyboard" },
    { id: "e7", source: "storyboard", target: "edit" },
  ].map((edge) => ({
    ...edge,
    animated: true,
    style: { stroke: "#7c6cff" },
  }));
  return { nodes, edges };
}

export function CanvasPage({ projects, config, onOpenProject }) {
  const stepMeta = config?.canvasSteps || [];
  const [projectId, setProjectId] = useState(projects?.[0]?.id || "");
  const [loading, setLoading] = useState(false);
  const [bundle, setBundle] = useState(null);
  const initial = useMemo(() => buildGraph(projects?.[0], stepMeta), [projects, stepMeta]);
  const [nodes, setNodes, onNodesChange] = useNodesState(initial.nodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initial.edges);
  const onConnect = useCallback((connection) => setEdges((eds) => addEdge({ ...connection, animated: true }, eds)), [setEdges]);

  const load = async (id) => {
    if (!id) return;
    setLoading(true);
    try {
      const data = await api(`/api/projects/${encodeURIComponent(id)}`);
      setBundle(data);
      const ents = (data.entities || []).filter((e) => !e.deletedAt);
      const shots = (data.shots || []).filter((s) => !s.deletedAt);
      const project = {
        ...data.project,
        progress: {
          episodes: { total: (data.episodes || []).length },
          characters: { total: ents.filter((e) => e.kind === "character").length },
          scenes: { total: ents.filter((e) => e.kind === "scene").length },
          props: { total: ents.filter((e) => e.kind === "prop").length },
          shots: { total: shots.length, completed: shots.filter((s) => s.status === "success").length },
        },
      };
      const next = buildGraph(project, stepMeta);
      setNodes(next.nodes);
      setEdges(next.edges);
    } catch (error) {
      toast.error(String(error.message || error));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!projectId && projects?.[0]?.id) setProjectId(projects[0].id);
  }, [projects, projectId]);

  useEffect(() => {
    if (projectId) void load(projectId);
  }, [projectId]);

  return (
    <PageShell
      eyebrow="Canvas"
      title="无限画布"
      description="把当前项目的六步生产线可视化为可拖拽节点图，便于查看素材与镜头推进。"
      actions={
        <>
          <select className="field !w-56" value={projectId} onChange={(e) => setProjectId(e.target.value)}>
            {!projects?.length ? <option value="">暂无项目</option> : null}
            {(projects || []).map((project) => (
              <option key={project.id} value={project.id}>
                {project.title}
              </option>
            ))}
          </select>
          <button type="button" className="btn-secondary" disabled={!projectId || loading} onClick={() => void load(projectId)}>
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />} 刷新图谱
          </button>
          <button type="button" className="btn-primary" disabled={!projectId} onClick={() => onOpenProject?.(projectId)}>
            打开工坊
          </button>
        </>
      }
    >
      <div className="panel h-[70vh] overflow-hidden">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          fitView
          colorMode="dark"
        >
          <Background gap={18} color="rgba(255,255,255,0.06)" />
          <MiniMap pannable zoomable />
          <Controls />
        </ReactFlow>
      </div>
      {bundle?.project ? (
        <p className="mt-3 text-xs text-[var(--muted)]">
          当前项目：{bundle.project.title} · {bundle.project.ratio} · {bundle.project.genre}
        </p>
      ) : null}
    </PageShell>
  );
}
