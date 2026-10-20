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
import { PortraitMatchPage } from "./components/platform/PortraitMatchPage";
import { TvPage } from "./components/platform/TvPage";
import { ChallengePage } from "./components/platform/ChallengePage";
import { ResourcesPage } from "./components/platform/ResourcesPage";
import { KeysSettings, UsageSettings } from "./components/platform/KeysSettings";
import { JobsPage } from "./components/platform/JobsPage";
import { HelpPage } from "./components/platform/HelpPage";
import { CreditsPage } from "./components/platform/CreditsPage";
import { ReferPage } from "./components/platform/ReferPage";

const STUDIO_STEPS = new Set([
  "script",
  "character",
  "scene",
  "prop",
  "workspace",
  "storyboard",
  "audio",
  "edit",
]);

function normalizeStudioStep(stepRaw) {
  if (stepRaw === "storyboard" || stepRaw === "audio" || stepRaw === "edit") return "workspace";
  return STUDIO_STEPS.has(stepRaw) ? stepRaw : "workspace";
}

function readAppRoute() {
  if (typeof window === "undefined") {
    return { projectId: "", step: "workspace", episodeId: "", nav: "", screen: "" };
  }
  const params = new URLSearchParams(window.location.search);
  const projectId = (params.get("project") || params.get("p") || "").trim();
  const stepRaw = (params.get("step") || "").trim();
  const step = normalizeStudioStep(stepRaw);
  const episodeId = (params.get("ep") || "").trim();
  const nav = (params.get("nav") || "").trim();
  let screen = (params.get("screen") || "").trim();
  if (projectId && screen !== "portrait") screen = "studio";
  else if (screen === "create") screen = "create";
  else if (screen === "portrait") screen = "portrait";
  else if (nav && nav !== "workshop") screen = "platform";
  else if (!screen) screen = "";
  return { projectId, step, episodeId, nav, screen };
}

function writeAppRoute({ projectId = "", step = "", episodeId = "", nav = "", screen = "" } = {}) {
  if (typeof window === "undefined") return;
  const params = new URLSearchParams(window.location.search);
  // Keep unrelated query keys (e.g. ref) intact.
  for (const key of ["project", "p", "step", "ep", "nav", "screen"]) params.delete(key);
  if (screen === "portrait") {
    params.set("screen", "portrait");
    if (projectId) params.set("project", projectId);
  } else if (projectId) {
    params.set("project", projectId);
    if (step && STUDIO_STEPS.has(step)) params.set("step", step);
    if (episodeId) params.set("ep", episodeId);
  } else if (screen === "create") {
    params.set("screen", "create");
  } else if (nav && nav !== "workshop") {
    params.set("nav", nav);
  }
  const qs = params.toString();
  const next = `${window.location.pathname}${qs ? `?${qs}` : ""}${window.location.hash || ""}`;
  const cur = `${window.location.pathname}${window.location.search}${window.location.hash || ""}`;
  if (next !== cur) window.history.replaceState(null, "", next);
}

export default function App() {
  const bootRoute = useMemo(() => readAppRoute(), []);
  const [screen, setScreen] = useState("library");
  const [projects, setProjects] = useState([]);
  const [projectId, setProjectId] = useState("");
  const [bundle, setBundle] = useState(null);
  const [loading, setLoading] = useState(false);
  const [step, setStep] = useState(() => bootRoute.step || "workspace");
  const [focusEpisodeId, setFocusEpisodeId] = useState(() => bootRoute.episodeId || "");
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
      setApiDown(false);
      return d.projects || [];
    } catch {
      // Keep last-known list on transient outages (avoid「项目全没了」闪空).
      return null;
    }
  }, []);

  const requireAuth = useCallback(() => {
    if (authed) return true;
    setShowAuth(true);
    toast.info(messages?.zh?.auth_page_need_login || "请先登录后再继续");
    return false;
  }, [authed, messages]);

  useEffect(() => {
    const onNeedAuth = () => {
      setShowAuth(true);
      toast.info(messages?.zh?.auth_page_need_login || "请先登录后再继续");
    };
    window.addEventListener("om:need-auth", onNeedAuth);
    return () => window.removeEventListener("om:need-auth", onNeedAuth);
  }, [messages]);

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
        demo: Boolean(profile?.demo || profile?.id === "demo" || profile?.userId === "demo"),
      };
      setUser(nextUser);
      setSession({ token, user: nextUser });
      setAuthed(true);
      setAuthReady(true);
      setApiDown(false);
      return true;
    } catch (err) {
      const status = Number(err?.status || err?.response?.status || 0);
      // Only drop session on real auth rejection. Network / 5xx must not wipe workshop.
      if (status === 401 || status === 403) {
        clearSession();
        setUser(null);
        setAuthed(false);
        setAuthReady(true);
        return false;
      }
      const cached = getStoredUser();
      if (cached) {
        setUser(cached);
        setAuthed(true);
        setAuthReady(true);
        return true;
      }
      setUser(null);
      setAuthed(false);
      setAuthReady(true);
      return false;
    }
  }, []);

  const loadProject = useCallback(async (id, quiet = false, openStep = "workspace", openEpisodeId = "", opts = {}) => {
    if (!quiet) setLoading(true);
    setProjectId(id);
    try {
      const b = await api(`/api/projects/${encodeURIComponent(id)}`);
      setBundle(b);
      if ((b?.project || {}).workflow === "portrait-match" && !opts.forceStudio) {
        setScreen("portrait");
        setNav("workshop");
        return;
      }
      if (!quiet) {
        const nextStep = normalizeStudioStep(openStep || "workspace");
        setStep(nextStep);
        if (openEpisodeId) setFocusEpisodeId(openEpisodeId);
        else {
          const eps = [...(b?.episodes || [])].sort((a, c) => a.episodeNumber - c.episodeNumber);
          if (eps[0]?.id) setFocusEpisodeId(eps[0].id);
        }
      }
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
      const route = readAppRoute();
      await verifySession(cfg);
      // Anonymous may browse showcase projects; generate actions open the login modal.
      await refreshProjects().catch(() => {});

      if (route.projectId) {
        setNav("workshop");
        await loadProject(route.projectId, false, route.step || "workspace", route.episodeId || "");
        return;
      }
      if (route.screen === "create") {
        setNav("workshop");
        setScreen("create");
        return;
      }
      if (route.screen === "portrait") {
        setNav("workshop");
        setScreen("portrait");
        return;
      }
      if (route.nav && route.nav !== "workshop") {
        setNav(route.nav);
        setScreen("platform");
        return;
      }
      setNav(landing);
      setScreen(landing === "workshop" ? "library" : "platform");
    })();
  }, [refreshConfig, refreshProjects, verifySession, loadProject]);

  // Keep deep-link in the address bar so refresh returns to the same studio page.
  useEffect(() => {
    if (!authReady) return;
    writeAppRoute({
      projectId: screen === "studio" || screen === "portrait" ? projectId : "",
      step: screen === "studio" ? step : "",
      episodeId: screen === "studio" ? focusEpisodeId : "",
      nav: screen === "studio" || screen === "portrait" ? "workshop" : nav,
      screen:
        screen === "create"
          ? "create"
          : screen === "portrait"
            ? "portrait"
            : screen === "studio"
              ? "studio"
              : "",
    });
  }, [authReady, screen, projectId, step, focusEpisodeId, nav]);

  useEffect(() => {
    if (typeof window === "undefined") return undefined;
    const onPop = () => {
      const route = readAppRoute();
      if (route.projectId) {
        void loadProject(route.projectId, true, route.step || step, route.episodeId || focusEpisodeId);
        setStep(route.step || "workspace");
        if (route.episodeId) setFocusEpisodeId(route.episodeId);
        setScreen("studio");
        setNav("workshop");
        return;
      }
      if (route.nav && route.nav !== "workshop") {
        setProjectId("");
        setBundle(null);
        setNav(route.nav);
        setScreen("platform");
        return;
      }
      setProjectId("");
      setBundle(null);
      setNav(route.nav || "workshop");
      setScreen("library");
    };
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, [loadProject, step, focusEpisodeId]);

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
    setFocusEpisodeId("");
    setScreen("library");
    setNav("workshop");
    writeAppRoute({ nav: "workshop" });
    void refreshProjects().catch(() => {});
  }, [refreshProjects]);

  const onNavigate = (id) => {
    // Left nav is always browsable; auth is only required when calling models / mutating.
    // Leaving any studio project must restore the main shell (sidebar + workshop home).
    if (screen === "studio" || screen === "create") {
      setProjectId("");
      setBundle(null);
      setFocusEpisodeId("");
      setCreateMode(null);
    }
    setNav(id);
    if (id === "workshop") {
      setScreen("library");
      writeAppRoute({ nav: "workshop" });
      return;
    }
    setScreen("platform");
    writeAppRoute({ nav: id });
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
  } else if (screen === "portrait") {
    body = (
      <PortraitMatchPage
        config={config}
        projectId={projectId}
        preferredTemplate={createMode?.templateId || createMode?.preset?.templateId || ""}
        onBack={() => {
          setCreateMode(null);
          setProjectId("");
          setBundle(null);
          setScreen("library");
          setNav("workshop");
          void refreshProjects();
        }}
        onOpenDrama={(id) => {
          void loadProject(id, false, "workspace", "", { forceStudio: true });
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
        focusEpisodeId={focusEpisodeId}
        onFocusEpisode={setFocusEpisodeId}
        config={config}
        busyMsg={busyMsg}
        setBusyMsg={setBusyMsg}
        onBack={leaveStudio}
        onRefresh={() => void refreshBundle()}
        onBundle={(b) => {
          if (b) setBundle(b);
        }}
        onNeedKeys={goKeys}
        onRequireAuth={requireAuth}
        readOnly={!authed}
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
          onOpenProject={(id, openStep) => void loadProject(id, false, openStep || "workspace")}
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
          onStartPortrait={(scenario) => {
            if (!requireAuth()) return;
            setCreateMode({
              id: "portrait-match",
              templateId: scenario?.templateId || "ref1",
              ...(scenario || {}),
            });
            setProjectId("");
            setBundle(null);
            setScreen("portrait");
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
    } else if (nav === "jobs") {
      body = (
        <JobsPage
          onOpenProject={(id) => {
            if (!id) return;
            void loadProject(id, false, "workspace");
          }}
        />
      );
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
          authed={authed}
          onRequireAuth={requireAuth}
          onOpen={(id) => void loadProject(id)}
          onCreate={(mode, card) => {
            if (!requireAuth()) return;
            const next = { id: mode || "drama", ...(card || {}) };
            setCreateMode(next);
            if (mode === "portrait-match" || card?.workflow === "portrait-match") {
              setProjectId("");
              setBundle(null);
              setScreen("portrait");
              return;
            }
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
        authed={authed}
        onRequireAuth={requireAuth}
        onOpen={(id) => void loadProject(id)}
        onCreate={(mode, card) => {
          if (!requireAuth()) return;
          const next = { id: mode || "drama", ...(card || {}) };
          setCreateMode(next);
          if (mode === "portrait-match" || card?.workflow === "portrait-match") {
            setProjectId("");
            setBundle(null);
            setScreen("portrait");
            return;
          }
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
            immersive={screen === "studio"}
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
