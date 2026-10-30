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

const LAYOUT_KEY = "om.canvas.layout.v1";

function progressFor(project) {
  const p = project?.progress || {};
  const allImaged = (block) => {
    const total = Number(block?.total || 0);
    const withImage = Number(block?.withImage || 0);
    return total > 0 && withImage >= total;
  };
  const shotTotal = Number(p.shots?.total || 0);
  const shotDone = Number(p.shots?.completed || 0);
  const epTotal = Number(p.episodes?.total || 0);
  const epConfirmed = Number(p.episodes?.confirmed || 0);
  return {
    script: epTotal > 0 && epConfirmed >= epTotal,
    character: allImaged(p.characters),
    scene: allImaged(p.scenes),
    prop: allImaged(p.props),
    storyboard: shotTotal > 0 && shotDone >= shotTotal,
    audio: Number(p.audios?.total || 0) > 0 && epConfirmed > 0 && Number(p.audios?.total || 0) >= epConfirmed,
    edit: shotTotal > 0 && shotDone >= shotTotal && Number(p.shots?.completed || 0) > 0,
  };
}

function nodeStyle(done, activeish) {
  if (done) {
    return {
      background: "rgba(52, 211, 153, 0.16)",
      color: "#f4f6fb",
      border: "1px solid rgba(52, 211, 153, 0.55)",
      borderRadius: 14,
      padding: 12,
      width: 140,
      whiteSpace: "pre-line",
      textAlign: "center",
      fontSize: 13,
      fontWeight: 600,
    };
  }
  return {
    background: activeish ? "#1a1d2e" : "#151822",
    color: "#f4f6fb",
    border: "1px solid rgba(124,108,255,.45)",
    borderRadius: 14,
    padding: 12,
    width: 140,
    whiteSpace: "pre-line",
    textAlign: "center",
    fontSize: 13,
    fontWeight: 600,
  };
}

function buildGraph(project, stepMeta = [], savedLayout = {}) {
  const p = project?.progress || {};
  const counts = {
    script: p.episodes?.total || 0,
    character: p.characters?.total || 0,
    scene: p.scenes?.total || 0,
    prop: p.props?.total || 0,
    storyboard: p.shots?.total || 0,
    audio: p.audios?.total || 0,
    edit: p.shots?.completed || 0,
  };
  const done = progressFor(project);
  const meta = stepMeta;
  const nodes = meta.map((step) => {
    const saved = savedLayout[step.id];
    return {
      id: step.id,
      position: saved || { x: step.x, y: step.y },
      data: { label: `${step.label}\n${counts[step.id] ?? 0}${done[step.id] ? " ✓" : ""}` },
      style: nodeStyle(Boolean(done[step.id]), false),
    };
  });
  const edges = [
    { id: "e1", source: "script", target: "character" },
    { id: "e2", source: "script", target: "scene" },
    { id: "e3", source: "script", target: "prop" },
    { id: "e4", source: "character", target: "storyboard" },
    { id: "e5", source: "scene", target: "storyboard" },
    { id: "e6", source: "prop", target: "storyboard" },
    { id: "e7", source: "storyboard", target: "audio" },
    { id: "e8", source: "audio", target: "edit" },
  ]
    .filter((edge) => meta.some((s) => s.id === edge.source) && meta.some((s) => s.id === edge.target))
    .map((edge) => ({
      ...edge,
      animated: true,
      style: { stroke: "#7c6cff" },
    }));
  return { nodes, edges };
}

function loadLayout(projectId) {
  try {
    const all = JSON.parse(localStorage.getItem(LAYOUT_KEY) || "{}") || {};
    return all[projectId] || {};
  } catch {
    return {};
  }
}

function saveLayout(projectId, nodes) {
  try {
    const all = JSON.parse(localStorage.getItem(LAYOUT_KEY) || "{}") || {};
    const map = {};
    for (const n of nodes || []) map[n.id] = n.position;
    all[projectId] = map;
    localStorage.setItem(LAYOUT_KEY, JSON.stringify(all));
  } catch {
    /* ignore */
  }
}

export function CanvasPage({ projects, config, onOpenProject }) {
  const stepMeta = config?.canvasSteps || [];
  const [projectId, setProjectId] = useState(projects?.[0]?.id || "");
  const [loading, setLoading] = useState(false);
  const [bundle, setBundle] = useState(null);
  const initial = useMemo(
    () => buildGraph(projects?.[0], stepMeta, loadLayout(projects?.[0]?.id || "")),
    [projects, stepMeta],
  );
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
          audios: { total: (data.audios || []).length },
        },
      };
      const next = buildGraph(project, stepMeta, loadLayout(id));
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

  useEffect(() => {
    if (!projectId || !nodes?.length) return;
    const t = window.setTimeout(() => saveLayout(projectId, nodes), 400);
    return () => window.clearTimeout(t);
  }, [nodes, projectId]);

  return (
    <PageShell
      eyebrow="Canvas"
      title="无限画布"
      description="把当前项目的生产线可视化为可拖拽节点图。节点按进度着色，点击进入对应工坊步骤。"
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
      {!projects?.length ? (
        <div className="panel flex flex-col items-center justify-center gap-4 py-24 text-center">
          <p className="text-sm text-[var(--muted)]">还没有项目。先用创作 Agent 或影视工坊新建一个，再回来查看六步图谱。</p>
        </div>
      ) : (
        <>
          <div className="panel h-[70vh] overflow-hidden">
            <ReactFlow
              nodes={nodes}
              edges={edges}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              onConnect={onConnect}
              onNodeClick={(_, node) => {
                if (projectId) onOpenProject?.(projectId, node?.id);
              }}
              fitView
              colorMode="dark"
            >
              <Background gap={18} color="rgba(255,255,255,0.06)" />
              <MiniMap pannable zoomable />
              <Controls />
            </ReactFlow>
          </div>
          {bundle?.project ? (
            <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-xs text-[var(--muted)]">
              <p>
                当前项目：{bundle.project.title} · {bundle.project.ratio} · {bundle.project.genre}
                · 绿色节点表示已有产出 · 布局已自动保存
              </p>
              <button type="button" className="btn-secondary !min-h-8 !px-3" onClick={() => onOpenProject?.(projectId, "script")}>
                从剧本步骤进入
              </button>
            </div>
          ) : null}
        </>
      )}
    </PageShell>
  );
}
