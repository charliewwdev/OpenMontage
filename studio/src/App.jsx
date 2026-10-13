import { useCallback, useEffect, useState } from "react";
import { api } from "./api";
import { toast } from "./lib/toast";
import { Library } from "./components/Library";
import { CreateProjectPage } from "./components/CreateProjectPage";
import { StudioShell } from "./components/StudioShell";
import { PlatformShell } from "./components/PlatformShell";

export default function App() {
  const [screen, setScreen] = useState("library");
  const [projects, setProjects] = useState([]);
  const [projectId, setProjectId] = useState("");
  const [bundle, setBundle] = useState(null);
  const [loading, setLoading] = useState(false);
  const [step, setStep] = useState("script");
  const [config, setConfig] = useState(null);
  const [busyMsg, setBusyMsg] = useState("");
  const [nav, setNav] = useState("workshop");

  const refreshProjects = useCallback(async () => {
    const d = await api("/api/projects");
    setProjects(d.projects || []);
    return d.projects || [];
  }, []);

  const loadProject = useCallback(async (id, quiet = false) => {
    if (!quiet) setLoading(true);
    setProjectId(id);
    try {
      const b = await api(`/api/projects/${encodeURIComponent(id)}`);
      setBundle(b);
      if (!quiet) setStep("script");
      setScreen("studio");
      setNav("workshop");
    } catch (e) {
      setBundle(null);
      toast.error(String(e.message || e));
    } finally {
      if (!quiet) setLoading(false);
    }
  }, []);

  const refreshBundle = useCallback(async () => {
    if (!projectId) return null;
    const b = await api(`/api/projects/${encodeURIComponent(projectId)}`);
    setBundle(b);
    return b;
  }, [projectId]);

  useEffect(() => {
    api("/api/config")
      .then(setConfig)
      .catch(() => {});
    refreshProjects().catch(() => {});
  }, [refreshProjects]);

  const onNavigate = (id, item) => {
    setNav(id);
    if (!item?.available) {
      toast.info(`${item?.label || id} 即将上线`);
      return;
    }
    if (id === "workshop") {
      setScreen("library");
    }
  };

  let body;
  if (screen === "create") {
    body = (
      <CreateProjectPage
        config={config}
        onBack={() => setScreen("library")}
        onCreated={(id) => {
          void loadProject(id);
          void refreshProjects();
        }}
      />
    );
  } else if (screen === "studio") {
    body = (
      <StudioShell
        projectId={projectId}
        bundle={bundle}
        loading={loading}
        step={step}
        setStep={setStep}
        config={config}
        busyMsg={busyMsg}
        setBusyMsg={setBusyMsg}
        onBack={() => {
          setScreen("library");
          void refreshProjects();
        }}
        onRefresh={() => void refreshBundle()}
        onBundle={(b) => {
          if (b) setBundle(b);
        }}
      />
    );
  } else {
    body = (
      <Library
        projects={projects}
        config={config}
        onOpen={(id) => void loadProject(id)}
        onCreate={() => setScreen("create")}
        onDeleted={(id) => {
          setProjects((list) => list.filter((p) => p.id !== id));
          if (projectId === id) {
            setProjectId("");
            setBundle(null);
          }
        }}
        onRefresh={() => void refreshProjects()}
      />
    );
  }

  return (
    <PlatformShell active={nav} onNavigate={onNavigate}>
      {body}
    </PlatformShell>
  );
}
