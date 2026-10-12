import { useCallback, useEffect, useState } from "react";
import { api } from "./api";
import { Library } from "./components/Library";
import { NewProjectModal } from "./components/NewProjectModal";
import { StudioShell } from "./components/StudioShell";

export default function App() {
  const [screen, setScreen] = useState("library");
  const [projects, setProjects] = useState([]);
  const [previewBundles, setPreviewBundles] = useState({});
  const [project, setProject] = useState("");
  const [bundle, setBundle] = useState(null);
  const [loading, setLoading] = useState(false);
  const [desk, setDesk] = useState("director");
  const [step, setStep] = useState("script");
  const [showNew, setShowNew] = useState(false);
  const [pipeline, setPipeline] = useState(null);
  const [subgraphs, setSubgraphs] = useState([]);
  const [selectedSubgraph, setSelectedSubgraph] = useState(null);
  const [subgraphDoc, setSubgraphDoc] = useState(null);
  const [canvasSource, setCanvasSource] = useState("shots");
  const [caps, setCaps] = useState(null);
  const [genState, setGenState] = useState(null);

  const refreshProjects = useCallback(async () => {
    const d = await api("/api/projects");
    const list = d.projects || [];
    setProjects(list);
    const previews = {};
    await Promise.all(
      list.slice(0, 12).map(async (name) => {
        try {
          previews[name] = await api(`/api/project/bundle?name=${encodeURIComponent(name)}`);
        } catch {
          /* ignore preview failures */
        }
      }),
    );
    setPreviewBundles(previews);
    return list;
  }, []);

  const loadProject = useCallback(async (name, quiet = false) => {
    if (!quiet) setLoading(true);
    setProject(name);
    try {
      const b = await api(`/api/project/bundle?name=${encodeURIComponent(name)}`);
      setBundle(b);
      setPreviewBundles((prev) => ({ ...prev, [name]: b }));
      const first = (b.steps || []).find((s) => s.state !== "empty");
      if (first && !quiet) setStep(first.id);
      setScreen("studio");
    } catch (e) {
      setBundle(null);
      window.alert(String(e.message || e));
    } finally {
      if (!quiet) setLoading(false);
    }
  }, []);

  useEffect(() => {
    api("/api/pipeline/short-drama").then(setPipeline).catch(() => {});
    api("/api/subgraphs")
      .then((d) => setSubgraphs(d.subgraphs || []))
      .catch(() => {});
    api("/api/config")
      .then((c) => setCaps(c.capabilities || c))
      .catch(() => {});
    refreshProjects().catch(() => {});
  }, [refreshProjects]);

  useEffect(() => {
    if (!selectedSubgraph) {
      setSubgraphDoc(null);
      return;
    }
    api(`/api/subgraphs/${selectedSubgraph}/graph`)
      .then((d) => setSubgraphDoc(d.document))
      .catch(() => setSubgraphDoc(null));
  }, [selectedSubgraph]);

  useEffect(() => {
    if (!project || !genState?.running) return undefined;
    const t = setInterval(async () => {
      try {
        const st = await api(`/api/project/generate/status?name=${encodeURIComponent(project)}`);
        setGenState(st);
        if (!st.running) {
          const b = await api(`/api/project/bundle?name=${encodeURIComponent(project)}`);
          setBundle(b);
        }
      } catch {
        /* ignore */
      }
    }, 1200);
    return () => clearInterval(t);
  }, [project, genState?.running]);

  const runGenerate = async () => {
    if (!project) return;
    try {
      const res = await api("/api/project/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ project }),
      });
      setGenState(res.status || { running: true });
    } catch (e) {
      window.alert(String(e.message || e));
    }
  };

  return (
    <>
      {screen === "library" ? (
        <Library
          projects={projects}
          bundles={previewBundles}
          caps={caps}
          onOpen={(name) => void loadProject(name)}
          onCreate={() => setShowNew(true)}
          onDeleted={(id) => {
            setProjects((list) => list.filter((p) => p !== id));
            setPreviewBundles((prev) => {
              const next = { ...prev };
              delete next[id];
              return next;
            });
            if (project === id) {
              setProject("");
              setBundle(null);
            }
          }}
        />
      ) : (
        <StudioShell
          project={project}
          bundle={bundle}
          loading={loading}
          desk={desk}
          setDesk={setDesk}
          step={step}
          setStep={setStep}
          onBack={() => {
            setScreen("library");
            void refreshProjects();
          }}
          onRefresh={() => void loadProject(project, true)}
          onBundle={(b) => {
            if (b?.artifacts) setBundle(b);
            else if (b) setBundle(b);
          }}
          pipeline={pipeline}
          subgraphs={subgraphs}
          selectedSubgraph={selectedSubgraph}
          setSelectedSubgraph={setSelectedSubgraph}
          subgraphDoc={subgraphDoc}
          canvasSource={canvasSource}
          setCanvasSource={setCanvasSource}
          genState={genState}
          onGenerate={runGenerate}
          caps={caps}
        />
      )}

      <NewProjectModal
        open={showNew}
        onClose={() => setShowNew(false)}
        onCreated={(name, createdBundle) => {
          setProjects((list) => (list.includes(name) ? list : [name, ...list]));
          if (createdBundle) {
            setPreviewBundles((prev) => ({ ...prev, [name]: createdBundle }));
            setBundle(createdBundle);
          }
          setProject(name);
          setDesk("director");
          setStep("script");
          setScreen("studio");
          void refreshProjects();
        }}
      />
    </>
  );
}
