import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "./api";
import { AuthPage, SKIP_AUTO_DEMO_KEY } from "./components/AuthPage";
import { MaintenancePage } from "./components/MaintenancePage";
import { clearSession, getStoredUser, getToken, setSession } from "./lib/auth";
import { LocaleProvider } from "./lib/i18n";
import { toast } from "./lib/toast";
import { Library } from "./components/Library";
import { CreateProjectPage } from "./components/CreateProjectPage";
import { StudioShell } from "./components/StudioShell";
import { PlatformShell } from "./components/PlatformShell";
import { AppContextMenu } from "./components/AppContextMenu";
import { AssetsPage } from "./components/platform/AssetsPage";
import { SkillsPage } from "./components/platform/SkillsPage";
import { ToolsPage } from "./components/platform/ToolsPage";
import { AgentPage } from "./components/platform/AgentPage";
import { CanvasPage } from "./components/platform/CanvasPage";
import { InspirePage } from "./components/platform/InspirePage";
import { TvPage } from "./components/platform/TvPage";
import { ChallengePage } from "./components/platform/ChallengePage";
import { ResourcesPage } from "./components/platform/ResourcesPage";
import { KeysSettings, UsageSettings } from "./components/platform/KeysSettings";
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
  const [createMode, setCreateMode] = useState(null);
  const [user, setUser] = useState(() => getStoredUser());
  const [authReady, setAuthReady] = useState(false);
  const [authed, setAuthed] = useState(false);
  const [showAuth, setShowAuth] = useState(false);
  const [apiDown, setApiDown] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsedState] = useState(() => {
    try {
      return localStorage.getItem("om.nav.collapsed.v1") === "1";
    } catch {
      return false;
    }
  });
  const setSidebarCollapsed = useCallback((next) => {
    setSidebarCollapsedState((prev) => {
      const value = typeof next === "function" ? next(prev) : Boolean(next);
      try {
        localStorage.setItem("om.nav.collapsed.v1", value ? "1" : "0");
      } catch {
        /* ignore */
      }
      return value;
    });
  }, []);

  const messages = useMemo(() => config?.i18n?.messages || { zh: {}, en: {} }, [config]);
  const defaultLocale = config?.i18n?.defaultLocale || "zh";
  const gateApp = config?.auth?.gateApp === true;
  const authRequired = config?.auth?.required !== false;

  const refreshConfig = useCallback(async () => {
    try {
      const data = await api("/api/config");
      setConfig(data);
      setApiDown(false);
      return data;
    } catch {
      setApiDown(true);
      return null;
    }
  }, []);

  const refreshProjects = useCallback(async () => {
    try {
      const d = await api("/api/projects");
      setProjects(d.projects || []);
      return d.projects || [];
    } catch {
      setProjects([]);
      return [];
    }
  }, []);

  const requireAuth = useCallback(() => {
    if (authed) return true;
    setShowAuth(true);
    toast.info(messages?.zh?.auth_page_need_login || "请先登录后再继续");
    return false;
  }, [authed, messages]);

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
      if (!cfg) {
        setAuthReady(true);
        return;
      }
      const landing = cfg?.auth?.defaultNav || "workshop";
      if (!getToken()) {
        setNav(landing);
        setScreen(landing === "workshop" ? "library" : "platform");
      } else {
        setNav(landing);
        setScreen(landing === "workshop" ? "library" : "platform");
      }
      await verifySession(cfg);
      // Browse-first: always try to load public/seed projects, even when logged out.
      refreshProjects().catch(() => {});
    })();
  }, [refreshConfig, refreshProjects, verifySession]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    const ref = params.get("ref");
    if (!ref) return;
    try {
      if (sessionStorage.getItem("om.refer.captured") === ref) return;
      sessionStorage.setItem("om.refer.captured", ref);
    } catch {
      /* ignore */
    }
    api("/api/settings/credits/referral", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ref }),
    }).catch(() => {});
  }, []);

  const goKeys = () => {
    setNav("keys");
    setScreen("platform");
  };

  const leaveStudio = useCallback(() => {
    setProjectId("");
    setBundle(null);
    setScreen("library");
    setNav("workshop");
    void refreshProjects().catch(() => {});
  }, [refreshProjects]);

  const onNavigate = (id) => {
    // Left nav is always browsable; auth is only required when calling models / mutating.
    // Leaving any studio project must restore the main shell (sidebar + workshop home).
    if (screen === "studio" || screen === "create") {
      setProjectId("");
      setBundle(null);
      setCreateMode(null);
    }
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
    setShowAuth(false);
    setBundle(null);
    setProjectId("");
    const landing = config?.auth?.defaultNav || "workshop";
    setNav(landing);
    setScreen(landing === "workshop" ? "library" : "platform");
    await refreshProjects().catch(() => {});
  };

  const onAuthed = async (data) => {
    setUser({
      userId: data?.userId,
      username: data?.username,
      avatar: data?.avatar || "",
    });
    setAuthed(true);
    setShowAuth(false);
    await refreshProjects().catch(() => {});
  };

  const onRetryApi = useCallback(async () => {
    const cfg = await refreshConfig();
    if (cfg) {
      await verifySession(cfg);
      await refreshProjects().catch(() => {});
    }
  }, [refreshConfig, refreshProjects, verifySession]);

  let body;
  if (screen === "create") {
    if (!authed) {
      body = null;
    } else {
      body = (
        <CreateProjectPage
          config={config}
          entryMode={createMode}
          onBack={() => {
            setCreateMode(null);
            setScreen("library");
            setNav("workshop");
          }}
          onCreated={(id) => {
            setCreateMode(null);
            void loadProject(id);
            void refreshProjects();
          }}
          onNeedKeys={goKeys}
        />
      );
    }
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
        onBack={leaveStudio}
        onRefresh={() => void refreshBundle()}
        onBundle={(b) => {
          if (b) setBundle(b);
        }}
        onNeedKeys={goKeys}
      />
    );
  } else if (screen === "platform") {
    if (nav === "assets") {
      body = (
        <AssetsPage
          onUsePrompt={(text) => {
            setAgentSeed(text);
            onNavigate("agent");
          }}
        />
      );
    }
    else if (nav === "skills") {
      body = (
        <SkillsPage
          config={config}
          onUsePrompt={(text) => {
            setAgentSeed(text);
            onNavigate("agent");
          }}
        />
      );
    }
    else if (nav === "tools") {
      body = (
        <ToolsPage
          config={config}
          onNavigate={onNavigate}
          onStartCreate={(text) => {
            setAgentSeed(text);
            onNavigate("agent");
          }}
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
          onRequireAuth={requireAuth}
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
          onOpenProject={(id, openStep) => void loadProject(id, false, openStep || "script")}
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
    } else if (nav === "usage") {
      body = <UsageSettings />;
    } else if (nav === "help") {
      body = <HelpPage config={config} onNeedKeys={goKeys} onNavigate={onNavigate} />;
    } else if (nav === "credits") {
      body = <CreditsPage config={config} onNeedKeys={goKeys} />;
    } else if (nav === "refer") {
      body = <ReferPage config={config} />;
    } else {
      body = (
        <Library
          projects={projects}
          config={config}
          onOpen={(id) => void loadProject(id)}
          onCreate={(mode, card) => {
            if (!requireAuth()) return;
            setCreateMode({ id: mode || "drama", ...(card || {}) });
            setScreen("create");
          }}
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
        onCreate={(mode, card) => {
          if (!requireAuth()) return;
          setCreateMode({ id: mode || "drama", ...(card || {}) });
          setScreen("create");
        }}
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

  const hardGate = gateApp && authRequired && !authed;

  return (
    <LocaleProvider messages={messages} defaultLocale={defaultLocale}>
      {!authReady ? (
        <div className="flex min-h-screen items-center justify-center bg-[var(--stage)] text-sm text-white/50">
          Loading…
        </div>
      ) : apiDown ? (
        <MaintenancePage brand={config?.brand || "OpenMontage"} onRetry={() => void onRetryApi()} />
      ) : hardGate ? (
        <AuthPage brand={config?.brand} tagline={config?.tagline} authConfig={config?.auth} onAuthed={onAuthed} />
      ) : (
        <>
          <PlatformShell
            active={nav}
            config={config}
            user={user}
            onNavigate={onNavigate}
            onLogout={onLogout}
            onLogin={() => setShowAuth(true)}
            immersive={false}
            collapsed={sidebarCollapsed}
            onCollapsedChange={setSidebarCollapsed}
          >
            {body}
          </PlatformShell>
          <AppContextMenu
            onNavigate={onNavigate}
            sidebarCollapsed={sidebarCollapsed}
            onToggleSidebar={() => setSidebarCollapsed((v) => !v)}
          />
          {showAuth || (screen === "create" && !authed) ? (
            <AuthPage
              mode="modal"
              brand={config?.brand}
              tagline={config?.tagline}
              authConfig={config?.auth}
              onAuthed={onAuthed}
              onClose={() => {
                setShowAuth(false);
                if (screen === "create" && !authed) {
                  setScreen("library");
                  setNav("workshop");
                }
              }}
            />
          ) : null}
        </>
      )}
    </LocaleProvider>
  );
}
