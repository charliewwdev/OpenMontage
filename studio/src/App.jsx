import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "./api";
import { AuthPage, SKIP_AUTO_DEMO_KEY } from "./components/AuthPage";
import { clearSession, getStoredUser, getToken, setSession } from "./lib/auth";
import { LocaleProvider } from "./lib/i18n";
import { toast } from "./lib/toast";
import { Library } from "./components/Library";
import { CreateProjectPage } from "./components/CreateProjectPage";
import { StudioShell } from "./components/StudioShell";
import { PlatformShell } from "./components/PlatformShell";
import { AssetsPage } from "./components/platform/AssetsPage";
import { SkillsPage } from "./components/platform/SkillsPage";
import { ToolsPage } from "./components/platform/ToolsPage";
import { AgentPage } from "./components/platform/AgentPage";
import { CanvasPage } from "./components/platform/CanvasPage";
import { InspirePage } from "./components/platform/InspirePage";
import { TvPage } from "./components/platform/TvPage";
import { ChallengePage } from "./components/platform/ChallengePage";
import { ResourcesPage } from "./components/platform/ResourcesPage";
import { KeysSettings } from "./components/platform/KeysSettings";
import { HelpPage } from "./components/platform/HelpPage";
import { CreditsPage } from "./components/platform/CreditsPage";
import { ReferPage } from "./components/platform/ReferPage";

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
  const [agentSeed, setAgentSeed] = useState("");
  const [user, setUser] = useState(() => getStoredUser());
  const [authReady, setAuthReady] = useState(false);
  const [authed, setAuthed] = useState(false);

  const messages = useMemo(() => config?.i18n?.messages || { zh: {}, en: {} }, [config]);
  const defaultLocale = config?.i18n?.defaultLocale || "zh";
  const authRequired = config?.auth?.required !== false;

  const refreshConfig = useCallback(async () => {
    try {
      const data = await api("/api/config");
      setConfig(data);
      return data;
    } catch {
      return null;
    }
  }, []);

  const refreshProjects = useCallback(async () => {
    const d = await api("/api/projects");
    setProjects(d.projects || []);
    return d.projects || [];
  }, []);

  const verifySession = useCallback(async (cfg) => {
    const required = cfg?.auth?.required !== false;
    const token = getToken();
    if (!required) {
      setAuthed(true);
      setAuthReady(true);
      return true;
    }
    if (!token) {
      setAuthed(false);
      setAuthReady(true);
      return false;
    }
    try {
      const res = await api("/api/auth/me");
      const profile = res?.data || res;
      const nextUser = {
        userId: profile?.id || profile?.userId,
        username: profile?.username || profile?.nickname || getStoredUser()?.username || "user",
        avatar: profile?.avatar || "",
      };
      setUser(nextUser);
      setSession({ token, user: nextUser });
      setAuthed(true);
      setAuthReady(true);
      return true;
    } catch {
      clearSession();
      setUser(null);
      setAuthed(false);
      setAuthReady(true);
      return false;
    }
  }, []);

  const loadProject = useCallback(async (id, quiet = false, openStep = "script") => {
    if (!quiet) setLoading(true);
    setProjectId(id);
    try {
      const b = await api(`/api/projects/${encodeURIComponent(id)}`);
      setBundle(b);
      if (!quiet) setStep(openStep);
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
    (async () => {
      const cfg = await refreshConfig();
      const ok = await verifySession(cfg);
      if (ok) {
        refreshProjects().catch(() => {});
      }
    })();
  }, [refreshConfig, refreshProjects, verifySession]);

  const goKeys = () => {
    setNav("keys");
    setScreen("platform");
  };

  const onNavigate = (id) => {
    setNav(id);
    if (id === "workshop") {
      setScreen("library");
      return;
    }
    setScreen("platform");
  };

  const onKeysUpdated = async (data) => {
    if (data?.capabilities) {
      setConfig((current) => ({ ...(current || {}), capabilities: data.capabilities }));
    }
    await refreshConfig();
  };

  const onLogout = async () => {
    try {
      await api("/api/auth/logout", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
    } catch {
      /* ignore upstream logout errors */
    }
    try {
      sessionStorage.setItem(SKIP_AUTO_DEMO_KEY, "1");
    } catch {
      /* ignore */
    }
    clearSession();
    setUser(null);
    setAuthed(false);
    setProjects([]);
    setBundle(null);
    setProjectId("");
    setScreen("library");
  };

  const onAuthed = async (data) => {
    setUser({
      userId: data?.userId,
      username: data?.username,
      avatar: data?.avatar || "",
    });
    setAuthed(true);
    await refreshProjects().catch(() => {});
  };

  let body;
  if (screen === "create") {
    body = (
      <CreateProjectPage
        config={config}
        onBack={() => {
          setScreen("library");
          setNav("workshop");
        }}
        onCreated={(id) => {
          void loadProject(id);
          void refreshProjects();
        }}
        onNeedKeys={goKeys}
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
          setNav("workshop");
          void refreshProjects();
        }}
        onRefresh={() => void refreshBundle()}
        onBundle={(b) => {
          if (b) setBundle(b);
        }}
        onNeedKeys={goKeys}
      />
    );
  } else if (screen === "platform") {
    if (nav === "assets") body = <AssetsPage />;
    else if (nav === "skills") body = <SkillsPage />;
    else if (nav === "tools") {
      body = (
        <ToolsPage
          config={config}
          onOpenTool={(tool) => {
            if (tool.nav === "workshop") {
              setNav("workshop");
              setScreen("library");
              if (tool.step) setStep(tool.step);
            } else {
              onNavigate(tool.nav);
            }
          }}
        />
      );
    } else if (nav === "agent") {
      body = (
        <AgentPage
          config={config}
          seedPrompt={agentSeed}
          onCreated={(id) => {
            setAgentSeed("");
            void loadProject(id);
            void refreshProjects();
          }}
          onNeedKeys={goKeys}
        />
      );
    } else if (nav === "canvas") {
      body = (
        <CanvasPage
          config={config}
          projects={projects}
          onOpenProject={(id) => void loadProject(id)}
        />
      );
    } else if (nav === "inspire") {
      body = (
        <InspirePage
          config={config}
          onUsePrompt={(text) => {
            setAgentSeed(text);
            onNavigate("agent");
          }}
        />
      );
    } else if (nav === "tv") {
      body = <TvPage onOpenProject={(id) => void loadProject(id, false, "edit")} />;
    } else if (nav === "cup") {
      body = (
        <ChallengePage
          config={config}
          onStart={(challenge) => {
            setAgentSeed(challenge.brief);
            toast.info(`已载入挑战：${challenge.title}`);
            onNavigate("agent");
          }}
        />
      );
    } else if (nav === "nav") {
      body = <ResourcesPage config={config} onNavigate={onNavigate} />;
    } else if (nav === "keys") {
      body = <KeysSettings config={config} onUpdated={(data) => void onKeysUpdated(data)} />;
    } else if (nav === "help") {
      body = <HelpPage config={config} onNeedKeys={goKeys} />;
    } else if (nav === "credits") {
      body = <CreditsPage config={config} />;
    } else if (nav === "refer") {
      body = <ReferPage config={config} />;
    } else {
      body = (
        <Library
          projects={projects}
          config={config}
          onOpen={(id) => void loadProject(id)}
          onCreate={() => setScreen("create")}
          onNeedKeys={goKeys}
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
  } else {
    body = (
      <Library
        projects={projects}
        config={config}
        onOpen={(id) => void loadProject(id)}
        onCreate={() => setScreen("create")}
        onNeedKeys={goKeys}
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
    <LocaleProvider messages={messages} defaultLocale={defaultLocale}>
      {!authReady ? (
        <div className="flex min-h-screen items-center justify-center bg-[var(--stage)] text-sm text-white/50">
          Loading…
        </div>
      ) : authRequired && !authed ? (
        <AuthPage brand={config?.brand} tagline={config?.tagline} authConfig={config?.auth} onAuthed={onAuthed} />
      ) : (
        <PlatformShell active={nav} config={config} user={user} onNavigate={onNavigate} onLogout={onLogout}>
          {body}
        </PlatformShell>
      )}
    </LocaleProvider>
  );
}
