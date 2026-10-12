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

const LEDGER_KEYS = ["pending", "running", "succeeded", "rewriting", "failed", "needs_review"];

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

function NewProjectModal({ open, onClose, onCreated }) {
  const [title, setTitle] = useState("");
  const [source, setSource] = useState("");
  const [aspect, setAspect] = useState("9:16");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  if (!open) return null;

  const submit = async () => {
    setBusy(true);
    setErr("");
    try {
      const res = await api("/api/projects", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title, source_text: source, aspect_ratio: aspect }),
      });
      onCreated(res.created.name, res.bundle);
      onClose();
      setTitle("");
      setSource("");
    } catch (e) {
      setErr(String(e.message || e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <header>
          <h2>新建短剧项目</h2>
          <p>粘贴小说/剧本正文，自动拆场次、角色、分镜与镜头账本</p>
        </header>
        <label>
          片名
          <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="例如：午夜短信" />
        </label>
        <label>
          画幅
          <select value={aspect} onChange={(e) => setAspect(e.target.value)}>
            <option value="9:16">竖屏 9:16</option>
            <option value="16:9">横屏 16:9</option>
            <option value="1:1">方屏 1:1</option>
          </select>
        </label>
        <label>
          源文本
          <textarea
            rows={12}
            value={source}
            onChange={(e) => setSource(e.target.value)}
            placeholder={"支持对白格式：林夏：别回那通电话。\n\n空行分段即场次。"}
          />
        </label>
        {err ? <p className="form-error">{err}</p> : null}
        <footer>
          <button type="button" className="btn ghost" onClick={onClose}>
            取消
          </button>
          <button type="button" className="btn" disabled={busy || !title || source.length < 20} onClick={submit}>
            {busy ? "创建中…" : "创建并拆解"}
          </button>
        </footer>
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
  const [canvasSource, setCanvasSource] = useState("shots");
  const [showNew, setShowNew] = useState(false);
  const [caps, setCaps] = useState(null);
  const [editDraft, setEditDraft] = useState("");
  const [timeline, setTimeline] = useState(null);
  const [genState, setGenState] = useState(null);

  const storyboard = bundle?.artifacts?.storyboard || null;
  const ledger = bundle?.artifacts?.ledger || null;
  const bible = bundle?.artifacts?.character_bible || null;
  const script = bundle?.artifacts?.script || null;
  const breakdown = bundle?.artifacts?.episode_breakdown || null;

  const refreshProjects = useCallback(async () => {
    const d = await api("/api/projects");
    setProjects(d.projects || []);
    return d.projects || [];
  }, []);

  const loadProject = useCallback(async (name) => {
    setProject(name);
    setSelected(null);
    setTimeline(null);
    setStatusMsg("");
    try {
      const b = await api(`/api/project/bundle?name=${encodeURIComponent(name)}`);
      setBundle(b);
      const first = (b.steps || []).find((s) => s.state !== "empty");
      if (first) setStep(first.id);
    } catch (e) {
      setBundle(null);
      setStatusMsg(String(e.message || e));
    }
  }, []);

  useEffect(() => {
    api("/api/pipeline/short-drama").then(setPipeline).catch((e) => setStatusMsg(String(e)));
    api("/api/subgraphs")
      .then((d) => setSubgraphs(d.subgraphs || []))
      .catch(() => {});
    api("/api/config")
      .then((c) => setCaps(c.capabilities))
      .catch(() => {});
    refreshProjects()
      .then((list) => {
        if (list.length) loadProject(list[0]);
      })
      .catch(() => {});
  }, [loadProject, refreshProjects]);

  useEffect(() => {
    if (!selectedSubgraph) {
      setSubgraphDoc(null);
      return;
    }
    api(`/api/subgraphs/${selectedSubgraph}/graph`)
      .then((d) => setSubgraphDoc(d.document))
      .catch((e) => setStatusMsg(String(e.message || e)));
  }, [selectedSubgraph]);

  useEffect(() => {
    if (!selected) {
      setEditDraft("");
      return;
    }
    setEditDraft(
      selected.description ||
        selected.appearance ||
        selected.text ||
        selected.dialogue ||
        JSON.stringify(selected, null, 2)
    );
  }, [selected]);

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

  const selectedShot =
    selected && storyboard?.shots?.some((s) => s.id === selected.id) ? selected : null;

  const saveShotPatch = async (patch) => {
    if (!project || !selectedShot) return;
    const res = await api("/api/project/storyboard/patch", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ project, shot_id: selectedShot.id, patch }),
    });
    setBundle((b) => ({
      ...b,
      artifacts: { ...(b?.artifacts || {}), storyboard: res.storyboard },
    }));
    const updated = res.storyboard.shots.find((s) => s.id === selectedShot.id);
    if (updated) setSelected(updated);
    await api("/api/project/ledger/invalidate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ project, shot_id: selectedShot.id }),
    });
    const b = await api(`/api/project/bundle?name=${encodeURIComponent(project)}`);
    setBundle(b);
    setStatusMsg(`已保存 ${selectedShot.id}`);
  };

  const syncLedger = async () => {
    if (!project) return;
    await api("/api/project/ledger/sync", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ project }),
    });
    await loadProject(project);
    setStatusMsg("镜头账本已从分镜重建");
  };

  const exportTimeline = async () => {
    if (!project) return;
    const res = await api(`/api/project/export/timeline?name=${encodeURIComponent(project)}`);
    setTimeline(res.timeline);
    setStatusMsg(`时间线导出：${res.timeline.total_duration_sec}s / ${res.timeline.clips.length} 镜`);
  };

  const markShot = async (status) => {
    if (!project || !selectedShot) return;
    await api("/api/project/ledger/mark", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ project, shot_id: selectedShot.id, status }),
    });
    await loadProject(project);
    setStatusMsg(`${selectedShot.id} → ${status}`);
  };

  const runGenerate = async () => {
    if (!project) return;
    try {
      await api("/api/project/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ project, limit: 4 }),
      });
      setStatusMsg("镜头生成已启动（离线分镜板）");
      const poll = async () => {
        const s = await api("/api/project/generate/status");
        setGenState(s.state);
        if (s.state?.running) {
          setTimeout(poll, 600);
        } else {
          await loadProject(project);
          setStatusMsg(
            s.state?.last_error
              ? `生成失败：${s.state.last_error}`
              : `生成完成：${s.state?.processed || 0} 镜`
          );
        }
      };
      poll();
    } catch (e) {
      setStatusMsg(String(e.message || e));
    }
  };

  const selectedJob = selectedShot
    ? (ledger?.jobs || []).find((j) => j.shot_id === selectedShot.id)
    : null;
  const keyframeUrl =
    selectedJob?.keyframe_path && project
      ? `/api/media/${encodeURIComponent(project)}/${selectedJob.keyframe_path}`
      : null;

  const saveBibleItem = async () => {
    if (!project || !selected || selectedShot) return;
    const entity =
      step === "characters" ? "character" : step === "locations" ? "location" : step === "props" ? "prop" : null;
    if (!entity) return;
    try {
      const item = { ...selected };
      if (editDraft && !editDraft.trim().startsWith("{")) {
        if (entity === "character") item.appearance = editDraft;
        else item.description = editDraft;
      } else if (editDraft.trim().startsWith("{")) {
        Object.assign(item, JSON.parse(editDraft));
      }
      const res = await api("/api/project/bible/upsert", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ project, entity, item }),
      });
      setBundle((b) => ({
        ...b,
        artifacts: { ...(b?.artifacts || {}), character_bible: res.bible },
      }));
      setSelected(item);
      setStatusMsg(`已保存 ${entity} ${item.id}`);
    } catch (e) {
      setStatusMsg(String(e.message || e));
    }
  };

  const sendChat = async () => {
    const text = chat.trim();
    if (!text) return;
    if (project && selectedShot) {
      const patch = {};
      const dur = text.match(/(\d+(?:\.\d+)?)\s*秒|duration\s*[:=]?\s*(\d+(?:\.\d+)?)/i);
      if (dur) patch.duration_sec = Number(dur[1] || dur[2]);
      if (/仰拍|low\s*angle/i.test(text)) {
        patch.shot_language = { ...(selectedShot.shot_language || {}), camera_movement: "tilt_up" };
        patch.description = `${selectedShot.description || ""} (仰拍)`.trim();
      }
      if (/特写|close.?up/i.test(text)) {
        patch.shot_language = { ...(selectedShot.shot_language || {}), shot_size: "close_up" };
      }
      if (Object.keys(patch).length) {
        try {
          await saveShotPatch(patch);
        } catch (e) {
          setStatusMsg(String(e.message || e));
        }
      } else {
        setStatusMsg("可用指令：仰拍 / 特写 / 时长 4 秒");
      }
    } else {
      setStatusMsg("先选项目与镜头");
    }
    setChat("");
  };

  const episode = (breakdown?.episodes || [])[0];

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark">
            OpenMontage <span>Drama</span>
          </div>
          <div className="brand-sub">真实可用短剧制片台</div>
        </div>

        <label className="project-select">
          <span>项目</span>
          <select value={project} onChange={(e) => e.target.value && loadProject(e.target.value)}>
            <option value="">选择项目…</option>
            {projects.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
        </label>
        <button type="button" className="btn compact" onClick={() => setShowNew(true)}>
          新建
        </button>

        <div className="desk-toggle">
          {DESKS.map((d) => (
            <button
              key={d.id}
              type="button"
              className={desk === d.id ? "active" : ""}
              onClick={() => {
                setDesk(d.id);
                if (d.id === "edit") setStep("edit");
              }}
            >
              {d.label}
            </button>
          ))}
        </div>

        <div className="spacer" />
        {caps ? (
          <div className="cap-chip" title={caps.keys.map((k) => `${k.label}:${k.configured ? "✓" : "–"}`).join("\n")}>
            {caps.mode === "online" ? "在线能力" : "离线拆解"} {caps.configured}/{caps.total}
          </div>
        ) : null}
        {statusMsg ? <div className="status-toast">{statusMsg}</div> : null}
      </header>

      <nav className="step-rail" aria-label="六步工作流">
        {STEPS.map((s, i) => {
          const meta = (bundle?.steps || []).find((x) => x.id === s.id);
          const state = meta?.state || "empty";
          return (
            <button
              key={s.id}
              type="button"
              className={`step-chip ${step === s.id ? "active" : ""} ${state}`}
              onClick={() => {
                setStep(s.id);
                setDesk(s.id === "edit" ? "edit" : desk === "canvas" ? "canvas" : "director");
              }}
            >
              <span className="step-num">{i + 1}</span>
              <span className="step-label">{s.label}</span>
              <span className={`step-dot ${state}`} />
            </button>
          );
        })}
      </nav>

      <div className="main">
        <aside className="rail">
          {desk === "canvas" ? (
            <>
              <h3>画布源</h3>
              <button type="button" className={`item ${canvasSource === "shots" ? "active" : ""}`} onClick={() => setCanvasSource("shots")}>
                镜头 DAG
              </button>
              <button type="button" className={`item ${canvasSource === "pipeline" ? "active" : ""}`} onClick={() => setCanvasSource("pipeline")}>
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
              <button type="button" className="item accent" onClick={() => setShowNew(true)}>
                + 新建项目
              </button>
              {projects.map((p) => (
                <button key={p} type="button" className={`item ${project === p ? "active" : ""}`} onClick={() => loadProject(p)}>
                  {p}
                </button>
              ))}
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
                  <button type="button" className="btn block" onClick={syncLedger}>
                    从分镜同步账本
                  </button>
                  <button
                    type="button"
                    className="btn block accent"
                    onClick={runGenerate}
                    disabled={!!genState?.running}
                  >
                    {genState?.running ? "生成中…" : "生成镜头（离线板）"}
                  </button>
                  {genState ? (
                    <p className="hint tiny">
                      {genState.running ? "running" : "idle"} · done {genState.processed || 0}
                      {genState.failed ? ` · fail ${genState.failed}` : ""}
                    </p>
                  ) : null}
                </>
              ) : null}
            </>
          )}
        </aside>

        <div className="workspace">
          {desk === "director" && project ? (
            <div className="desk-panel">
              {step === "script" ? (
                <>
                  <header className="desk-head">
                    <h2>{script?.title || breakdown?.series_title || "剧本"}</h2>
                    <p>{episode?.logline || "分集结构与对白"}</p>
                  </header>
                  <div className="script-layout">
                    <aside className="scene-list">
                      <h3>场次</h3>
                      {(episode?.scenes || []).map((sc) => (
                        <button key={sc.id} type="button" className={`item ${selected?.id === sc.id ? "active" : ""}`} onClick={() => setSelected(sc)}>
                          <span className="mono">{sc.id}</span>
                          <strong>{sc.title}</strong>
                        </button>
                      ))}
                    </aside>
                    <article className="script-body">
                      <h3>对白节拍</h3>
                      <div className="dialogue-list">
                        {(script?.dialogue_beats || []).map((d) => (
                          <button
                            key={d.id}
                            type="button"
                            className={`dialogue-row ${selected?.id === d.id ? "active" : ""}`}
                            onClick={() => setSelected(d)}
                          >
                            <span className="spk">{d.speaker_id}</span>
                            <span>{d.text}</span>
                          </button>
                        ))}
                      </div>
                    </article>
                  </div>
                </>
              ) : null}

              {step === "characters" || step === "locations" || step === "props" ? (
                <>
                  <header className="desk-head">
                    <h2>{step === "characters" ? "角色" : step === "locations" ? "场景" : "道具"}</h2>
                    <p>{bible?.visual_style || "资产一致性"}</p>
                  </header>
                  <div className="asset-grid">
                    {(step === "characters"
                      ? bible?.characters || []
                      : step === "locations"
                        ? bible?.locations || []
                        : bible?.props || []
                    ).map((item) => (
                      <button
                        key={item.id}
                        type="button"
                        className={`asset-card ${selected?.id === item.id ? "active" : ""}`}
                        onClick={() => setSelected(item)}
                      >
                        <div className="asset-thumb" />
                        <div className="asset-body">
                          <strong>{item.display_name || item.name || item.id}</strong>
                          <p>{item.appearance || item.description || item.role || "—"}</p>
                        </div>
                      </button>
                    ))}
                    {step === "props" && !(bible?.props || []).length ? (
                      <div className="empty-block">
                        <h3>暂无道具</h3>
                        <p className="hint">可在右侧检视区用 JSON 追加到 character_bible.props</p>
                      </div>
                    ) : null}
                  </div>
                </>
              ) : null}

              {step === "storyboard" ? (
                <>
                  <header className="desk-head row">
                    <div>
                      <h2>分镜导演台</h2>
                      <p>
                        {storyboard?.episode_id} · {storyboard?.aspect_ratio} · {storyboard?.shots?.length || 0} 镜
                      </p>
                    </div>
                    <div className="btn-row">
                      <button type="button" className="btn ghost" onClick={syncLedger}>
                        同步账本
                      </button>
                      <button type="button" className="btn" onClick={runGenerate} disabled={!!genState?.running}>
                        {genState?.running ? "生成中…" : "批量生成"}
                      </button>
                    </div>
                  </header>
                  <div className="shot-grid">
                    {(storyboard?.shots || []).map((shot) => {
                      const st = (ledger?.jobs || []).find((j) => j.shot_id === shot.id)?.status || "pending";
                      return (
                        <button
                          key={shot.id}
                          type="button"
                          className={`shot-tile ${selected?.id === shot.id ? "active" : ""}`}
                          onClick={() => setSelected(shot)}
                        >
                          <div className="shot-frame">
                            <span className="shot-index">#{shot.index}</span>
                            <span className={`status-pill ${st}`}>{st}</span>
                          </div>
                          <strong>{shot.description}</strong>
                          <div className="shot-meta">
                            <span>{shot.shot_intent}</span>
                            <span>{shot.duration_sec}s</span>
                          </div>
                          {shot.dialogue ? <p className="dialogue">「{shot.dialogue}」</p> : null}
                        </button>
                      );
                    })}
                  </div>
                </>
              ) : null}

              {step === "edit" ? (
                <p className="hint">请切换到「剪辑室」工作台。</p>
              ) : null}
            </div>
          ) : null}

          {desk === "edit" && project ? (
            <div className="desk-panel edit-desk">
              <header className="desk-head row">
                <div>
                  <h2>剪辑室</h2>
                  <p>时间线编排 · 导出 concat</p>
                </div>
                <button type="button" className="btn" onClick={exportTimeline}>
                  导出时间线
                </button>
              </header>
              <div className="preview-stage">
                <div className="phone-frame">
                  {keyframeUrl ? (
                    <img className="preview-media" src={keyframeUrl} alt={selectedShot?.id || "keyframe"} />
                  ) : selectedShot ? (
                    <div className="preview-copy">
                      <span className="eyebrow-text">{selectedShot.id}</span>
                      <h3>{selectedShot.description}</h3>
                      {selectedShot.dialogue ? <p className="dialogue">「{selectedShot.dialogue}」</p> : null}
                      <p className="hint">尚未生成关键帧 · 点「批量生成」</p>
                    </div>
                  ) : (
                    <div className="preview-copy">
                      <h3>选择时间线片段</h3>
                    </div>
                  )}
                </div>
              </div>
              <div className="timeline">
                <div className="timeline-track">
                  {(storyboard?.shots || []).map((shot) => {
                    const st = (ledger?.jobs || []).find((j) => j.shot_id === shot.id)?.status || "pending";
                    return (
                      <button
                        key={shot.id}
                        type="button"
                        className={`tl-clip ${st} ${selectedShot?.id === shot.id ? "active" : ""}`}
                        style={{ flex: Math.max(Number(shot.duration_sec) || 1, 1) }}
                        onClick={() => setSelected(shot)}
                      >
                        <span>{shot.id.replace(/^ep\d+_/, "")}</span>
                      </button>
                    );
                  })}
                </div>
              </div>
              {timeline ? (
                <pre className="script-dump">
                  {JSON.stringify(
                    { total: timeline.total_duration_sec, clips: timeline.clips.length, ffmpeg: timeline.ffmpeg_concat },
                    null,
                    2
                  )}
                </pre>
              ) : null}
            </div>
          ) : null}

          {desk === "canvas" ? (
            <div className="canvas-wrap">
              <ReactFlow
                key={`${canvasSource}-${selectedSubgraph || "x"}-${project || "none"}`}
                nodes={labNodesEdges.nodes}
                edges={labNodesEdges.edges}
                nodeTypes={nodeTypes}
                fitView
                onNodeClick={(_e, node) => {
                  if (node.type === "shot" && node.data.shot) {
                    setSelected(node.data.shot);
                    setStep("storyboard");
                  }
                }}
                proOptions={{ hideAttribution: true }}
                defaultEdgeOptions={{ type: "smoothstep" }}
              >
                <FitOnChange deps={[canvasSource, selectedSubgraph, project, labNodesEdges.nodes.length]} />
                <Background gap={18} size={1} color="rgba(21,32,43,0.08)" />
                <Controls />
                <MiniMap pannable zoomable nodeColor={() => "#0d8a7c"} maskColor="rgba(238,241,244,0.72)" />
              </ReactFlow>
            </div>
          ) : null}

          {!project ? (
            <div className="empty-canvas">
              <div>
                <h2>从小说到成片</h2>
                <p className="hint">新建项目粘贴正文，或打开已有 projects/</p>
                <button type="button" className="btn" onClick={() => setShowNew(true)}>
                  新建短剧项目
                </button>
              </div>
            </div>
          ) : null}
        </div>

        <aside className="inspector">
          <h3>检视 / 编辑</h3>
          {selectedShot ? (
            <>
              <p className="title">{selectedShot.id}</p>
              {keyframeUrl ? <img className="inspect-thumb" src={keyframeUrl} alt="" /> : null}
              <label className="field">
                描述
                <textarea
                  rows={3}
                  value={editDraft}
                  onChange={(e) => setEditDraft(e.target.value)}
                />
              </label>
              <div className="meta-row">
                <span className="meta-pill">{selectedShot.shot_intent}</span>
                <span className="meta-pill">{selectedShot.duration_sec}s</span>
                {selectedJob ? <span className={`meta-pill ${selectedJob.status}`}>{selectedJob.status}</span> : null}
              </div>
              <button
                type="button"
                className="btn"
                onClick={() => saveShotPatch({ description: editDraft })}
              >
                保存镜头
              </button>
              <button type="button" className="btn" onClick={runGenerate} disabled={!!genState?.running}>
                生成队列
              </button>
              <button type="button" className="btn ghost" onClick={() => markShot("succeeded")}>
                标记成功
              </button>
              <button type="button" className="btn ghost" onClick={() => markShot("needs_review")}>
                待审
              </button>
              <button type="button" className="btn ghost" onClick={() => markShot("failed")}>
                标记失败
              </button>
              <button
                type="button"
                className="btn ghost"
                onClick={async () => {
                  await api("/api/project/ledger/invalidate", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ project, shot_id: selectedShot.id }),
                  });
                  await loadProject(project);
                  setStatusMsg(`已作废 ${selectedShot.id}`);
                }}
              >
                重跑镜头
              </button>
            </>
          ) : selected ? (
            <>
              <p className="title">{selected.display_name || selected.name || selected.title || selected.id}</p>
              <label className="field">
                外观 / 描述
                <textarea rows={5} value={editDraft} onChange={(e) => setEditDraft(e.target.value)} />
              </label>
              <button type="button" className="btn" onClick={saveBibleItem}>
                保存资产
              </button>
              <pre className="inspect-json">{JSON.stringify(selected, null, 2)}</pre>
            </>
          ) : (
            <p className="hint">选择资产或镜头以编辑。</p>
          )}
        </aside>
      </div>

      <div className="chat">
        <div className="chat-label">Agent</div>
        <input
          value={chat}
          onChange={(e) => setChat(e.target.value)}
          placeholder="手术式修改：仰拍 / 特写 / 时长 4 秒"
          onKeyDown={(e) => e.key === "Enter" && sendChat()}
        />
        <button type="button" onClick={sendChat}>
          发送
        </button>
      </div>

      <NewProjectModal
        open={showNew}
        onClose={() => setShowNew(false)}
        onCreated={async (name) => {
          await refreshProjects();
          await loadProject(name);
          setDesk("director");
          setStep("script");
          setStatusMsg(`已创建 ${name}`);
        }}
      />
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
