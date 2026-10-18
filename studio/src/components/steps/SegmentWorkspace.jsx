import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ChevronLeft,
  ChevronRight,
  Clapperboard,
  FileText,
  Film,
  Loader2,
  Maximize2,
  Mic2,
  Pause,
  Play,
  Save,
  Sparkles,
  Video,
  Volume2,
  VolumeX,
} from "lucide-react";
import { api } from "../../api";
import {
  blockersFromError,
  entityStillPasses,
  formatEntityQaBlockers,
  isEntityQaBlockedError,
  listEntityQaBlockers,
} from "../../lib/entityQaGate";
import { requireCapability, toastMaybeKeys } from "../../lib/keys";
import { toast } from "../../lib/toast";
import { useTimer } from "../../lib/useTimer";
import { AssetDetailModal } from "../AssetDetailModal";
import { ConfirmDialog } from "../ConfirmDialog";

function parseDialogue(raw = "") {
  const text = String(raw || "").trim();
  if (!text) return null;
  const m = text.match(/^([^：:\n]{1,24})\s*[：:]\s*(.+)$/s);
  if (m) return { speaker: m[1].trim(), line: m[2].trim() };
  return { speaker: "", line: text };
}

function parseRefNames(prompt = "") {
  return [...String(prompt).matchAll(/@([^\s@,，。；;（）()]+)/g)].map((m) => m[1].split("-")[0]);
}

function entityThumb(ent) {
  if (ent?.selectedImage?.url) return ent.selectedImage.url;
  const imgs = ent?.images || [];
  for (let i = imgs.length - 1; i >= 0; i -= 1) {
    if (imgs[i]?.url) return imgs[i].url;
  }
  return "";
}

function stillLooksReady(ent) {
  return entityStillPasses(ent);
}

function isDefaultVariant(ent) {
  const v = String(ent?.variant || "").trim();
  return !v || v === "默认形象" || v === "默认造型" || v === "default";
}

/** Same name can have many variants — never let a failed「受伤后」steal the default slot. */
function pickEntityByName(entities, name) {
  const matches = entities.filter((e) => e.name === name);
  if (!matches.length) return null;
  return (
    matches.find((e) => isDefaultVariant(e) && stillLooksReady(e)) ||
    matches.find((e) => stillLooksReady(e)) ||
    matches.find((e) => isDefaultVariant(e)) ||
    matches[0]
  );
}

function collectSegmentEntities(seg, entities) {
  if (!seg) return { characters: [], scenes: [], props: [], names: new Set(), referenced: [] };
  const byId = new Map(entities.map((e) => [e.id, e]));
  const names = new Set();
  const referenced = new Map();
  const display = new Map();

  for (const shot of seg.shots) {
    for (const id of shot.referenceEntityIds || []) {
      const ent = byId.get(id);
      if (ent) {
        referenced.set(ent.id, ent);
        display.set(ent.id, ent);
        names.add(ent.name);
      }
    }
    for (const name of parseRefNames(shot.prompt || "")) {
      names.add(name);
      const ent = pickEntityByName(entities, name);
      if (ent) display.set(ent.id, ent);
    }
    const dlg = parseDialogue(shot.dialogue || "");
    if (dlg?.speaker) {
      names.add(dlg.speaker);
      const ent = pickEntityByName(entities, dlg.speaker);
      if (ent) display.set(ent.id, ent);
    }
    if (shot.sceneName) {
      names.add(shot.sceneName);
      const ent =
        pickEntityByName(entities, shot.sceneName) ||
        entities.find((e) => e.kind === "scene" && e.name === shot.sceneName);
      if (ent) display.set(ent.id, ent);
    }
  }

  const list = [...display.values()];
  const referencedList = [...referenced.values()];
  return {
    characters: list.filter((e) => e.kind === "character"),
    scenes: list.filter((e) => e.kind === "scene"),
    props: list.filter((e) => e.kind === "prop"),
    names,
    all: list,
    // Out-gate only cares about ids actually bound on the shots.
    referenced: referencedList,
  };
}

function buildSegments(shots) {
  const map = new Map();
  for (const shot of shots) {
    const so = Number(shot.segmentOrder || shot.shotOrder || 1);
    if (!map.has(so)) map.set(so, []);
    map.get(so).push(shot);
  }
  return [...map.entries()]
    .sort((a, b) => a[0] - b[0])
    .map(([segmentOrder, group]) => {
      const sorted = [...group].sort(
        (a, b) => (a.beatIndex || a.shotOrder) - (b.beatIndex || b.shotOrder),
      );
      const lead = sorted.find((s) => s.isSegmentLead) || sorted[0];
      const duration =
        Number(lead?.segmentDuration || 0) ||
        sorted.reduce((sum, s) => sum + Number(s.duration || 0), 0);
      const video =
        lead?.selectedVideo?.url
          ? lead.selectedVideo
          : (lead?.videos || []).find((v) => v.url || v.path) || null;
      return { segmentOrder, shots: sorted, lead, duration, video };
    });
}

function PromptWithChips({ prompt, entityByName, activeNames, onOpenEntity }) {
  const parts = String(prompt || "").split(/(@[^\s@,，。；;（）()]+)/g);
  return (
    <p className="text-[13px] leading-6 text-white/85">
      {parts.map((part, i) => {
        if (!part.startsWith("@")) return <span key={i}>{part}</span>;
        const name = part.slice(1).split("-")[0];
        const ent = entityByName.get(name);
        const on = activeNames.has(name) || [...activeNames].some((n) => name.includes(n) || n.includes(name));
        const Chip = ent && onOpenEntity ? "button" : "span";
        return (
          <Chip
            key={i}
            type={Chip === "button" ? "button" : undefined}
            onClick={ent && onOpenEntity ? () => onOpenEntity(ent) : undefined}
            className={`mx-0.5 inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 align-middle text-[12px] font-medium ${
              on ? "bg-[#7c6cff]/25 text-[#c4b5fd]" : "bg-white/5 text-white/80"
            } ${ent && onOpenEntity ? "cursor-pointer hover:bg-[#7c6cff]/40" : ""}`}
          >
            {entityThumb(ent) ? <img src={entityThumb(ent)} alt="" className="h-4 w-4 rounded object-cover" /> : null}
            {name}
          </Chip>
        );
      })}
    </p>
  );
}

function DialogueCard({ dialogue, entityByName, onOpenEntity }) {
  const parsed = parseDialogue(dialogue);
  if (!parsed?.line) return null;
  const ent = parsed.speaker ? entityByName.get(parsed.speaker) : null;
  return (
    <div className="mt-3 flex gap-2.5 rounded-xl border border-white/10 bg-white/[.04] p-3">
      <button
        type="button"
        disabled={!ent || !onOpenEntity}
        onClick={() => ent && onOpenEntity?.(ent)}
        className={`h-10 w-10 shrink-0 overflow-hidden rounded-lg bg-black/40 ${
          ent && onOpenEntity ? "cursor-pointer ring-offset-2 hover:ring-2 hover:ring-[#7c6cff]/60" : ""
        }`}
        title={ent ? `查看 ${ent.name}` : undefined}
      >
        {entityThumb(ent) ? (
          <img src={entityThumb(ent)} alt="" className="h-full w-full object-cover" />
        ) : (
          <div className="flex h-full items-center justify-center text-[10px] text-white/40">
            {(parsed.speaker || "?").slice(0, 1)}
          </div>
        )}
      </button>
      <div className="min-w-0 flex-1">
        <div className="mb-1 flex items-center gap-2 text-[11px] text-white/45">
          {ent && onOpenEntity ? (
            <button
              type="button"
              className="font-semibold text-white/85 hover:text-[#c4b5fd] hover:underline"
              onClick={() => onOpenEntity(ent)}
            >
              {parsed.speaker || "对白"}
            </button>
          ) : (
            <span className="font-semibold text-white/85">{parsed.speaker || "对白"}</span>
          )}
          <span>台词</span>
        </div>
        <p className="text-sm font-medium leading-6 text-white/90">「{parsed.line.replace(/^「|」$/g, "")}」</p>
      </div>
    </div>
  );
}

/**
 * SceneMixer-style episode desk: left assets · center segment · right preview · bottom strip.
 * Characters / props / dialogue / dubbing live inside the active segment — not separate wizard steps.
 */
export function SegmentWorkspace({
  projectId,
  bundle,
  config,
  setBusyMsg,
  onBundle,
  onRefresh,
  onNeedKeys,
  onRequireAuth,
  readOnly = false,
  focusEpisodeId,
  setStep,
}) {
  const caps = config?.capabilities || {};
  // Video model comes from top StudioModelBar (ComfyUI H3 / Seedance) — do not force Seedance.
  const videoReady = Boolean(caps.videoReady || caps.seedance || caps.comfyui);
  const confirmedEpisodes = useMemo(
    () =>
      [...(bundle?.episodes || [])]
        .filter((e) => e.status === "confirmed")
        .sort((a, b) => a.episodeNumber - b.episodeNumber),
    [bundle?.episodes],
  );
  const [episodeId, setEpisodeId] = useState(focusEpisodeId || confirmedEpisodes[0]?.id || "");
  const [segmentOrder, setSegmentOrder] = useState(1);
  const [resolution, setResolution] = useState("720p");
  const [scriptTab, setScriptTab] = useState("lens");
  const [splitting, setSplitting] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [audioBusy, setAudioBusy] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [confirmSplit, setConfirmSplit] = useState(false);
  const [forceQaDialog, setForceQaDialog] = useState(null); // { blockers, opts }
  const [fillingStills, setFillingStills] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [continuous, setContinuous] = useState(true);
  const [muted, setMuted] = useState(false);
  const [bgmOn, setBgmOn] = useState(true);
  const [editMode, setEditMode] = useState("visual"); // visual | line | trim
  const [editingShotId, setEditingShotId] = useState("");
  const [draftDialogue, setDraftDialogue] = useState("");
  const [savingLine, setSavingLine] = useState(false);
  const [visualNote, setVisualNote] = useState("");
  const [pendingRegen, setPendingRegen] = useState(false);
  const [trimStart, setTrimStart] = useState(0);
  const [trimEnd, setTrimEnd] = useState(5);
  const [savingTrim, setSavingTrim] = useState(false);
  const [clipDraft, setClipDraft] = useState(null); // { id, shotId, start, end, enabled }
  const [inspectEntityId, setInspectEntityId] = useState("");
  const [modelPromptBusy, setModelPromptBusy] = useState(false);
  const [modelPromptData, setModelPromptData] = useState(null);
  const videoRef = useRef(null);
  const bgmRef = useRef(null);
  const monitorRef = useRef(null);
  const boundRefsRef = useRef("");
  const { formatted: splitElapsedTime } = useTimer(splitting);

  useEffect(() => {
    if (focusEpisodeId && focusEpisodeId !== episodeId) {
      setEpisodeId(focusEpisodeId);
      setSegmentOrder(1);
      setPlaying(false);
      setPendingRegen(false);
      setVisualNote("");
    }
  }, [focusEpisodeId, episodeId]);

  useEffect(() => {
    setPendingRegen(false);
    setVisualNote("");
    setEditingShotId("");
  }, [segmentOrder]);

  useEffect(() => {
    if (!["480p", "720p", "1080p"].includes(resolution)) setResolution("720p");
  }, [resolution]);

  const episode = (bundle?.episodes || []).find((e) => e.id === episodeId);
  const shots = useMemo(
    () =>
      (bundle?.shots || [])
        .filter((s) => s.episodeId === episodeId && !s.deletedAt)
        .sort((a, b) => a.shotOrder - b.shotOrder),
    [bundle?.shots, episodeId],
  );
  const segments = useMemo(() => buildSegments(shots), [shots]);
  const hasSegmentLayout = segments.some((g) => g.shots.some((s) => Number(s.segmentOrder || 0) > 0));

  // Prefer episode-tagged entities, but keep all names so stale episodes[] still resolve.
  const allEntities = useMemo(
    () => (bundle?.entities || []).filter((entity) => !entity.deletedAt),
    [bundle?.entities],
  );
  const episodeEntities = useMemo(() => {
    if (!episode) return allEntities;
    const tagged = allEntities.filter(
      (entity) => !entity.episodes?.length || entity.episodes.includes(episode.episodeNumber),
    );
    return tagged.length ? tagged : allEntities;
  }, [allEntities, episode]);
  const entityByName = useMemo(() => {
    const buckets = new Map();
    for (const e of [...allEntities, ...episodeEntities]) {
      if (!e?.name) continue;
      const list = buckets.get(e.name) || [];
      list.push(e);
      buckets.set(e.name, list);
    }
    const map = new Map();
    for (const [name, list] of buckets) {
      const uniq = [...new Map(list.map((e) => [e.id, e])).values()];
      const picked = pickEntityByName(uniq, name);
      if (picked) map.set(name, picked);
    }
    return map;
  }, [allEntities, episodeEntities]);
  const entityById = useMemo(() => new Map(allEntities.map((e) => [e.id, e])), [allEntities]);
  const inspectEntity = inspectEntityId ? entityById.get(inspectEntityId) || null : null;
  const openEntity = useCallback((ent) => {
    if (ent?.id) setInspectEntityId(ent.id);
  }, []);

  const activeSeg =
    segments.find((s) => s.segmentOrder === segmentOrder) || segments[0] || null;

  useEffect(() => {
    if (!segments.length) return;
    if (!segments.some((s) => s.segmentOrder === segmentOrder)) {
      setSegmentOrder(segments[0].segmentOrder);
    }
  }, [segments, segmentOrder]);

  // Legacy boards: auto-assign segmentOrder
  useEffect(() => {
    if (readOnly || !episodeId || !shots.length || splitting) return;
    const needsMigrate = shots.some((s) => !Number(s.segmentOrder || 0));
    if (!needsMigrate) return;
    let cancelled = false;
    (async () => {
      try {
        const res = await api(`/api/projects/${encodeURIComponent(projectId)}/storyboard`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ action: "migrate-segments", episodeId }),
        });
        if (!cancelled && res?.bundle) onBundle?.(res.bundle);
      } catch {
        /* keep flat */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [readOnly, episodeId, projectId, shots, splitting, onBundle]);

  // Bind cast/prop/scene names into referenceEntityIds once per episode load.
  useEffect(() => {
    if (readOnly || !episodeId || !shots.length || splitting) return;
    const needsBind = shots.some((s) => !(s.referenceEntityIds || []).length);
    const key = `${episodeId}:${shots.length}:${needsBind ? "need" : "ok"}`;
    if (!needsBind || boundRefsRef.current === key) return;
    let cancelled = false;
    (async () => {
      try {
        const res = await api(`/api/projects/${encodeURIComponent(projectId)}/storyboard`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ action: "bind-refs", episodeId }),
        });
        if (!cancelled) {
          boundRefsRef.current = key;
          if (res?.bundle) onBundle?.(res.bundle);
        }
      } catch {
        boundRefsRef.current = key;
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [readOnly, episodeId, projectId, shots, splitting, onBundle]);

  const segAssets = useMemo(
    () => collectSegmentEntities(activeSeg, allEntities),
    [activeSeg, allEntities],
  );
  const segEntityQaBlockers = useMemo(() => {
    // Prefer shot-bound ids. If none, only gate on default/ready name matches — never ep10 injury variants.
    const pool = segAssets.referenced?.length
      ? segAssets.referenced
      : (segAssets.all || []).filter((e) => stillLooksReady(e) || isDefaultVariant(e));
    return listEntityQaBlockers(pool);
  }, [segAssets]);

  const audios = bundle?.audios || [];
  const episodeAudio = audios.find((a) => a.episodeId === episodeId && a.kind !== "bgm");
  const bgm = audios.find((a) => a.episodeId === episodeId && a.kind === "bgm");
  const segmentDialogues = useMemo(() => {
    if (!activeSeg) return [];
    return activeSeg.shots
      .map((s) => ({ shot: s, parsed: parseDialogue(s.dialogue || "") }))
      .filter((x) => x.parsed?.line);
  }, [activeSeg]);

  const generatingIds = shots
    .filter((s) => s.status === "generating")
    .map((s) => s.id)
    .join(",");

  useEffect(() => {
    if (!generatingIds) return undefined;
    let cancelled = false;
    const poll = async () => {
      let changed = false;
      await Promise.all(
        generatingIds.split(",").filter(Boolean).map(async (id) => {
          try {
            const shot = await api(
              `/api/projects/${encodeURIComponent(projectId)}/shots/${encodeURIComponent(id)}`,
            );
            if (shot.status !== "generating") changed = true;
          } catch {
            /* next */
          }
        }),
      );
      if (changed && !cancelled) await onRefresh?.();
    };
    void poll();
    const timer = setInterval(() => void poll(), 5000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [generatingIds, projectId, onRefresh]);

  const apply = (res) => {
    if (res?.bundle) onBundle?.(res.bundle);
    else onRefresh?.();
  };

  const checkConsistency = async () => {
    if (onRequireAuth && !onRequireAuth()) return;
    if (!episode) return;
    setBusyMsg?.("正在核对提示词与对白、资产…");
    try {
      const res = await api(`/api/projects/${encodeURIComponent(projectId)}/storyboard`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "check-consistency", episodeId: episode.id, repair: true }),
      });
      apply(res);
      const fail = Number(res?.fail || 0);
      const repaired = (res?.results || []).filter((r) => r.repaired).length;
      if (!fail && !repaired) toast.success("本集提示词与对白、角色、场景、道具一致");
      else if (!fail) toast.success(`已按对白修正 ${repaired} 条提示词`);
      else toast.error(`仍有 ${fail} 条对不齐，已标在分镜上`);
    } catch (error) {
      toast.error(String(error.message || error));
    } finally {
      setBusyMsg?.("");
    }
  };

  const split = async () => {
    if (onRequireAuth && !onRequireAuth()) return;
    if (!episode) return;
    if (shots.some((s) => s.status === "generating")) {
      toast.info("请等待视频任务完成后再重新拆分");
      return;
    }
    if (shots.length && !confirmSplit) {
      setConfirmSplit(true);
      return;
    }
    if (!requireCapability(caps, "deepseek", onNeedKeys, "文本大模型 Key")) return;
    setConfirmSplit(false);
    setSplitting(true);
    setBusyMsg?.("AI 按片段拆镜中…");
    try {
      const res = await api(`/api/projects/${encodeURIComponent(projectId)}/storyboard`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "generate", episodeId: episode.id }),
      });
      apply(res);
      setSegmentOrder(1);
      toast.success("本集已拆成片段");
    } catch (error) {
      toastMaybeKeys(error, onNeedKeys);
      toast.error(String(error.message || error));
    } finally {
      setSplitting(false);
      setBusyMsg?.("");
    }
  };

  const openModelPromptTab = async () => {
    if (!episode || !activeSeg) return;
    setScriptTab("prompt");
    const cacheKey = `${episode.id}:${activeSeg.segmentOrder}`;
    if (modelPromptData?._cacheKey === cacheKey) return;
    setModelPromptBusy(true);
    try {
      const res = await api(`/api/projects/${encodeURIComponent(projectId)}/storyboard`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "effective-prompt",
          episodeId: episode.id,
          segmentOrder: activeSeg.segmentOrder,
        }),
      });
      setModelPromptData({ ...res, _cacheKey: cacheKey });
    } catch (e) {
      toast.error(String(e.message || e));
      setScriptTab("lens");
    } finally {
      setModelPromptBusy(false);
    }
  };

  useEffect(() => {
    setModelPromptData(null);
    setScriptTab((tab) => (tab === "prompt" ? "lens" : tab));
  }, [segmentOrder, episodeId]);

  const fillSegmentStills = async () => {
    if (!episodeId || !activeSeg) return;
    if (onRequireAuth && !onRequireAuth()) return;
    setFillingStills(true);
    setBusyMsg?.(`按 drama-entity-still 补本段角色/场景图…`);
    try {
      const res = await api(`/api/projects/${encodeURIComponent(projectId)}/entities`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "fill-stills",
          episodeId,
          segmentOrder: activeSeg.segmentOrder,
          kinds: ["character", "scene"],
          onlyMissing: true,
        }),
      });
      apply(res);
      const queued = res?.queued ?? 0;
      const attempted = res?.attempted ?? 0;
      if (res?.async || res?.queued) {
        toast.success("补图任务已提交后台队列（有界池限流，页面可继续浏览）");
        const started = Date.now();
        while (Date.now() - started < 20 * 60 * 1000) {
          await new Promise((r) => setTimeout(r, 5000));
          const snap = await api(`/api/projects/${encodeURIComponent(projectId)}`);
          if (snap) apply({ bundle: snap });
          const still = (snap?.entities || []).filter(
            (e) => !e.deletedAt && e.imageStatus === "generating",
          );
          if (!still.length) {
            toast.success("本段补图任务已结束，请核对质检结果");
            break;
          }
          setBusyMsg?.(`补图进行中…剩余 ${still.length} 项`);
        }
        return;
      }
      if (!attempted) toast.success("本段角色/场景图已齐，无需补图");
      else if (queued > 0) {
        toast.success(`已排队补图 ${queued || attempted} 项（有界线程池后台跑，页面可继续操作）`);
        // Light poll until no segment asset stays generating.
        const started = Date.now();
        while (Date.now() - started < 20 * 60 * 1000) {
          await new Promise((r) => setTimeout(r, 5000));
          const snap = await api(`/api/projects/${encodeURIComponent(projectId)}`);
          if (snap) apply({ bundle: snap });
          const still = (snap?.entities || []).filter(
            (e) => !e.deletedAt && e.imageStatus === "generating",
          );
          if (!still.length) {
            toast.success("本段补图任务已结束，请核对质检结果");
            break;
          }
          setBusyMsg?.(`补图进行中…剩余 ${still.length} 项`);
        }
      } else {
        const ok = res?.pass ?? 0;
        const fail = res?.fail ?? 0;
        if (fail === 0) toast.success(`已补齐 ${ok} 张定妆图（质检通过）`);
        else toast.error(`补图完成：${ok} 通过，${fail} 未过质检（可点卡片重试）`);
      }
    } catch (error) {
      toastMaybeKeys(error, onNeedKeys);
      toast.error(String(error.message || error));
    } finally {
      setFillingStills(false);
      setBusyMsg?.("");
    }
  };

  const generateSegment = async ({
    instruction = "",
    syncOnly = false,
    forceEntityQa = false,
    skipClientGate = false,
  } = {}) => {
    if (!activeSeg) return;
    if (onRequireAuth && !onRequireAuth()) return;
    if (!videoReady) {
      toast.error("请先在顶部选择可用的视频模型（ComfyUI / Seedance）");
      onNeedKeys?.();
      return;
    }
    const opts = { instruction, syncOnly, forceEntityQa };
    if (!forceEntityQa && !skipClientGate && segEntityQaBlockers.length) {
      setForceQaDialog({ blockers: segEntityQaBlockers, opts });
      return;
    }
    setGenerating(true);
    setBusyMsg?.(
      instruction
        ? `按调整重生片段 ${activeSeg.segmentOrder}…`
        : forceEntityQa
          ? `强制出片片段 ${activeSeg.segmentOrder}…`
          : `生成片段 ${activeSeg.segmentOrder}…`,
    );
    try {
      const useRevise = Boolean(instruction) || pendingRegen || syncOnly;
      const res = await api(`/api/projects/${encodeURIComponent(projectId)}/storyboard`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(
          useRevise
            ? {
                action: "revise-segment",
                episodeId,
                segmentOrder: activeSeg.segmentOrder,
                instruction: instruction || "",
                resolution,
                startVideo: true,
                forceEntityQa: Boolean(forceEntityQa),
              }
            : {
                action: "video-segment",
                episodeId,
                segmentOrder: activeSeg.segmentOrder,
                resolution,
                forceEntityQa: Boolean(forceEntityQa),
              },
        ),
      });
      apply(res);
      setPendingRegen(false);
      setVisualNote("");
      setForceQaDialog(null);
      toast.success(
        instruction
          ? `片段 ${activeSeg.segmentOrder} 已按调整提交重生`
          : forceEntityQa
            ? `片段 ${activeSeg.segmentOrder} 已强制出片（未过检素材仍作参考）`
            : `片段 ${activeSeg.segmentOrder} 出片已提交`,
      );
    } catch (error) {
      if (isEntityQaBlockedError(error) && !forceEntityQa) {
        setForceQaDialog({
          blockers: blockersFromError(error).length ? blockersFromError(error) : segEntityQaBlockers,
          opts,
        });
        toast.error("素材质检未过，已阻断出片");
      } else {
        toastMaybeKeys(error, onNeedKeys);
        toast.error(String(error.message || error));
      }
    } finally {
      setGenerating(false);
      setBusyMsg?.("");
    }
  };

  const generateAudio = async () => {
    if (!episode) return;
    if (onRequireAuth && !onRequireAuth()) return;
    setAudioBusy(true);
    setBusyMsg?.("正在合成配音…");
    try {
      const res = await api(`/api/projects/${encodeURIComponent(projectId)}/audio`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "generate", episodeId: episode.id }),
      });
      apply(res);
      toast.success("本集配音已生成（导出时混入）");
    } catch (error) {
      toast.error(String(error.message || error));
      if (/Key|TTS|edge-tts|配置/i.test(String(error.message || error))) onNeedKeys?.();
    } finally {
      setAudioBusy(false);
      setBusyMsg?.("");
    }
  };

  const exportEpisode = async () => {
    if (!episode) return;
    if (onRequireAuth && !onRequireAuth()) return;
    setExporting(true);
    setBusyMsg?.("导出成片中…");
    try {
      const res = await api(`/api/projects/${encodeURIComponent(projectId)}/edits`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "export", episodeId: episode.id }),
      });
      apply(res);
      const url = res?.edit?.outputUrl || res?.bundle?.edits?.find((e) => e.episodeId === episode.id)?.outputUrl;
      if (url) toast.success("成片已导出");
      else toast.success("导出任务已完成");
    } catch (error) {
      toast.error(String(error.message || error));
    } finally {
      setExporting(false);
      setBusyMsg?.("");
    }
  };

  const startEditDialogue = (shot) => {
    setEditMode("line");
    setEditingShotId(shot.id);
    setDraftDialogue(shot.dialogue || "");
  };

  const saveDialogue = async (shotId, { regenerate = false } = {}) => {
    if (!shotId) return;
    if (onRequireAuth && !onRequireAuth()) return;
    setSavingLine(true);
    try {
      const res = await api(`/api/projects/${encodeURIComponent(projectId)}/storyboard`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "patch",
          shotId,
          patch: { dialogue: draftDialogue },
        }),
      });
      apply(res);
      try {
        const bind = await api(`/api/projects/${encodeURIComponent(projectId)}/storyboard`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ action: "bind-refs", episodeId }),
        });
        if (bind?.bundle) onBundle?.(bind.bundle);
      } catch {
        /* optional */
      }
      setEditingShotId("");
      if (regenerate) {
        setPendingRegen(false);
        setSavingLine(false);
        await generateSegment({ syncOnly: true });
        return;
      }
      setPendingRegen(true);
      toast.success("台词已保存 · 可重生本段让口型生效");
    } catch (error) {
      toast.error(String(error.message || error));
    } finally {
      setSavingLine(false);
    }
  };

  // Keep trim clip in sync with active segment lead video.
  useEffect(() => {
    if (!episodeId || !activeSeg?.lead?.id) {
      setClipDraft(null);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const existing = (bundle?.edits || []).find((e) => e.episodeId === episodeId);
        let edit = existing;
        if ((!edit || !(edit.clips || []).length) && !readOnly) {
          const res = await api(`/api/projects/${encodeURIComponent(projectId)}/edits`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ action: "ensure", episodeId }),
          });
          if (cancelled) return;
          if (res?.bundle) onBundle?.(res.bundle);
          edit = res?.edit || (res?.bundle?.edits || []).find((e) => e.episodeId === episodeId);
        }
        const clip =
          (edit?.clips || []).find((c) => c.shotId === activeSeg.lead.id) ||
          (edit?.clips || []).find((c) => {
            const shot = shots.find((s) => s.id === c.shotId);
            return Number(shot?.segmentOrder) === activeSeg.segmentOrder;
          });
        if (!clip) {
          setClipDraft(null);
          return;
        }
        const mediaMax = Number(activeSeg.video?.duration || activeSeg.duration || clip.end || 5);
        setClipDraft(clip);
        setTrimStart(Number(clip.start || 0));
        setTrimEnd(Math.min(Number(clip.end || mediaMax), mediaMax));
      } catch {
        if (!cancelled) setClipDraft(null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [
    readOnly,
    episodeId,
    projectId,
    activeSeg?.lead?.id,
    activeSeg?.segmentOrder,
    activeSeg?.video?.url,
    activeSeg?.video?.duration,
    activeSeg?.duration,
    bundle?.edits,
    shots,
    onBundle,
  ]);

  const mediaMax = Math.max(
    0.5,
    Number(activeSeg?.video?.duration || activeSeg?.duration || trimEnd || 5),
  );

  const previewTrim = () => {
    const el = videoRef.current;
    if (!el || !activeSeg?.video?.url) return;
    el.currentTime = trimStart;
    void el.play();
    setPlaying(true);
    const stopAt = trimEnd;
    const onTime = () => {
      if (el.currentTime >= stopAt - 0.05) {
        el.pause();
        setPlaying(false);
        el.removeEventListener("timeupdate", onTime);
      }
    };
    el.addEventListener("timeupdate", onTime);
  };

  const saveTrim = async () => {
    if (!episode || !clipDraft) {
      return toast.info("本段还没有可裁剪的成片，请先生成本段");
    }
    setSavingTrim(true);
    try {
      const existing = (bundle?.edits || []).find((e) => e.episodeId === episodeId);
      let clips = [...(existing?.clips || [])];
      if (!clips.length) {
        const res = await api(`/api/projects/${encodeURIComponent(projectId)}/edits`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ action: "ensure", episodeId }),
        });
        if (res?.bundle) onBundle?.(res.bundle);
        clips = [...(res?.edit?.clips || [])];
      }
      const nextClips = clips.map((c) =>
        c.id === clipDraft.id || c.shotId === activeSeg?.lead?.id
          ? { ...c, start: trimStart, end: trimEnd, enabled: true }
          : c,
      );
      const res = await api(`/api/projects/${encodeURIComponent(projectId)}/edits`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "save", episodeId: episode.id, clips: nextClips }),
      });
      apply(res);
      setClipDraft((prev) => (prev ? { ...prev, start: trimStart, end: trimEnd } : prev));
      toast.success("裁剪已保存（导出成片时生效）");
    } catch (error) {
      toast.error(String(error.message || error));
    } finally {
      setSavingTrim(false);
    }
  };

  const goSeg = useCallback(
    (delta) => {
      if (!segments.length) return;
      const idx = segments.findIndex((s) => s.segmentOrder === (activeSeg?.segmentOrder || segmentOrder));
      const next = segments[Math.max(0, Math.min(segments.length - 1, idx + delta))];
      if (next) {
        setSegmentOrder(next.segmentOrder);
        setPlaying(false);
      }
    },
    [segments, activeSeg, segmentOrder],
  );

  const togglePlay = () => {
    const el = videoRef.current;
    if (!el || !activeSeg?.video?.url) return;
    if (el.paused) {
      void el.play();
      setPlaying(true);
    } else {
      el.pause();
      setPlaying(false);
    }
  };

  const onSegEnded = () => {
    if (!continuous) {
      setPlaying(false);
      return;
    }
    const idx = segments.findIndex((s) => s.segmentOrder === activeSeg?.segmentOrder);
    for (let i = idx + 1; i < segments.length; i += 1) {
      if (segments[i].video?.url) {
        setSegmentOrder(segments[i].segmentOrder);
        setPlaying(true);
        return;
      }
    }
    setPlaying(false);
  };

  useEffect(() => {
    const el = videoRef.current;
    if (!el || !activeSeg?.video?.url) return;
    if (playing) void el.play().catch(() => setPlaying(false));
    else el.pause();
  }, [activeSeg?.segmentOrder, activeSeg?.video?.url, playing]);

  useEffect(() => {
    const audio = bgmRef.current;
    if (!audio) return;
    if (bgmOn && bgm?.url && playing) {
      void audio.play().catch(() => {});
    } else {
      audio.pause();
    }
  }, [bgmOn, bgm?.url, playing]);

  useEffect(() => {
    const onKey = (e) => {
      if (e.target?.closest?.("input, textarea, select, [contenteditable]")) return;
      if (e.code === "Space") {
        e.preventDefault();
        const el = videoRef.current;
        if (!el || !activeSeg?.video?.url) return;
        if (el.paused) {
          void el.play();
          setPlaying(true);
        } else {
          el.pause();
          setPlaying(false);
        }
      } else if (e.code === "ArrowLeft") goSeg(-1);
      else if (e.code === "ArrowRight") goSeg(1);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [goSeg, activeSeg?.video?.url]);

  const ratio = bundle?.project?.ratio || "9:16";
  const editDraft = (bundle?.edits || []).find((e) => e.episodeId === episodeId);
  const segReady = Boolean(activeSeg?.video?.url);
  const segVideoQa = activeSeg?.video?.qa || {};
  // Soft-skipped QA (JSON/vision errors) must not read as green「已完成」.
  const segQaPass = activeSeg?.video?.qaPass === true && !segVideoQa.skipped;
  const segQaFail =
    segReady &&
    (activeSeg?.video?.qaPass === false ||
      Boolean(segVideoQa.skipped) ||
      activeSeg?.lead?.status === "failed" ||
      String(activeSeg?.lead?.error || "").includes("质检"));
  const segGenerating = activeSeg?.shots?.some((s) => s.status === "generating");
  const totalDur = segments.reduce((sum, s) => sum + Number(s.duration || 0), 0);
  const readyCount = segments.filter((s) => s.video?.url).length;

  if (!episode || !confirmedEpisodes.some((e) => e.id === episodeId)) {
    return (
      <div className="panel py-24 text-center text-sm text-white/50">
        请先在「剧本」定稿分集，再进入片段工作台。
        {typeof setStep === "function" ? (
          <div className="mt-4">
            <button type="button" className="btn-primary" onClick={() => setStep("script")}>
              去剧本
            </button>
          </div>
        ) : null}
      </div>
    );
  }

  if (!shots.length) {
    return (
      <div className="panel flex flex-col items-center border-dashed py-24 text-center">
        <Clapperboard className="mb-4 h-10 w-10 text-[#7c6cff]" />
        <strong className="text-lg">本集还没有片段</strong>
        <p className="mt-2 max-w-md text-sm text-white/50">
          按 SceneMixer 方式拆成约 10–15 秒的片段，每段含 3–4 个分镜节拍；角色、道具、台词都挂在段上。
        </p>
        <button type="button" className="btn-primary mt-5" disabled={splitting} onClick={() => void split()}>
          {splitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
          {splitting ? `拆分中 · ${splitElapsedTime}` : "AI 拆成片段"}
        </button>
        <ConfirmDialog
          open={confirmSplit}
          title="重新拆分本集？"
          message="现有镜头与视频版本记录将被替换。"
          confirmLabel="重新拆分"
          onCancel={() => setConfirmSplit(false)}
          onConfirm={() => void split()}
        />
      </div>
    );
  }

  return (
    <div className="flex h-full min-h-0 flex-col gap-3">
      {/* Single toolbar: title + segment pager + actions (model switch lives in shell bar). */}
      <div className="flex shrink-0 flex-wrap items-center gap-3 rounded-xl border border-white/10 bg-[#0c0e14] px-3 py-2.5">
        <div className="min-w-0 shrink">
          <h2 className="truncate text-base font-semibold text-white">
            工作台
            <span className="ml-2 text-sm font-normal text-white/45">
              · 第{episode.episodeNumber}集「{episode.title || "未命名"}」
            </span>
          </h2>
          <p className="mt-0.5 text-[11px] text-white/45">
            {segments.length} 片段 · {readyCount}/{segments.length} 已出片 · 约 {Math.round(totalDur)}s
          </p>
        </div>
        {segments.length ? (
          <div className="flex min-w-0 items-center gap-1" aria-label="片段导航">
            <button
              type="button"
              className="btn-quiet !min-h-8 !px-2"
              disabled={segments[0]?.segmentOrder === activeSeg?.segmentOrder}
              onClick={() => goSeg(-1)}
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <div className="scrollbar-thin flex max-w-[min(100%,28rem)] gap-1.5 overflow-x-auto py-0.5">
              {segments.map((seg) => {
                const active = seg.segmentOrder === activeSeg?.segmentOrder;
                return (
                  <button
                    key={seg.segmentOrder}
                    type="button"
                    onClick={() => {
                      setSegmentOrder(seg.segmentOrder);
                      setPlaying(false);
                    }}
                    className={`flex h-8 min-w-8 items-center justify-center rounded-full px-2.5 text-xs font-semibold transition ${
                      active ? "bg-[#7c6cff] text-white" : "bg-white/5 text-white/50 hover:bg-white/10 hover:text-white"
                    }`}
                    title={`片段 ${seg.segmentOrder}`}
                  >
                    {seg.segmentOrder}
                  </button>
                );
              })}
            </div>
            <button
              type="button"
              className="btn-quiet !min-h-8 !px-2"
              disabled={segments[segments.length - 1]?.segmentOrder === activeSeg?.segmentOrder}
              onClick={() => goSeg(1)}
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        ) : null}
        <div className="ml-auto flex flex-wrap items-center gap-2">
          <button type="button" className="btn-secondary !min-h-9 text-xs" disabled={splitting || generating} onClick={() => void checkConsistency()}>
            校验提示词
          </button>
          <button type="button" className="btn-secondary !min-h-9 text-xs" disabled={splitting || generating} onClick={() => void split()}>
            {splitting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />}
            重新拆分
          </button>
          {editDraft?.outputUrl ? (
            <a href={editDraft.outputUrl} className="btn-secondary !min-h-9 text-xs" target="_blank" rel="noreferrer">
              <Film className="h-3.5 w-3.5" /> 查看成片
            </a>
          ) : (
            <button type="button" className="btn-secondary !min-h-9 text-xs" disabled={exporting || !readyCount} onClick={() => void exportEpisode()}>
              {exporting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Film className="h-3.5 w-3.5" />}
              导出成片
            </button>
          )}
        </div>
      </div>

      {/* Main 3-column desk — scrolls; filmstrip stays pinned below */}
      <div className="grid min-h-0 flex-1 gap-3 overflow-hidden xl:grid-cols-[200px_minmax(0,1fr)_minmax(300px,360px)]">
        {/* Left: assets — highlight those belonging to this segment */}
        <aside className="scrollbar-thin min-h-0 overflow-y-auto rounded-xl border border-white/10 bg-[#0c0e14] p-3 xl:h-full">
          <div className="mb-3 flex items-center justify-between">
            <h4 className="text-sm font-semibold text-white">本段资产</h4>
            <button
              type="button"
              className="inline-flex items-center gap-1 text-[10px] text-[#a78bfa] hover:underline disabled:opacity-40"
              disabled={fillingStills || generating || splitting}
              title="按 Skill「drama-entity-still」为本段无图/未过检的角色与场景出图并质检"
              onClick={() => void fillSegmentStills()}
            >
              {fillingStills ? <Loader2 className="h-3 w-3 animate-spin" /> : null}
              {fillingStills ? "补图中…" : "补图"}
            </button>
          </div>
          {[
            {
              kind: "character",
              label: "角色",
              list: segAssets.characters.length
                ? segAssets.characters
                : episodeEntities.filter((e) => e.kind === "character").slice(0, 6),
            },
            {
              kind: "scene",
              label: "场景",
              list: segAssets.scenes.length
                ? segAssets.scenes
                : episodeEntities.filter((e) => e.kind === "scene").slice(0, 4),
            },
            {
              kind: "prop",
              label: "道具",
              list: segAssets.props.length
                ? segAssets.props
                : episodeEntities.filter((e) => e.kind === "prop").slice(0, 4),
            },
          ].map((block) =>
            block.list.length ? (
              <div key={block.kind} className="mb-4">
                <div className="mb-2 text-[11px] font-medium text-white/45">{block.label}</div>
                <div className="grid grid-cols-2 gap-2">
                  {block.list.map((ent) => {
                    const inSeg = segAssets.all.some((x) => x.id === ent.id) || segAssets.names.has(ent.name);
                    return (
                      <button
                        key={ent.id}
                        type="button"
                        onClick={() => openEntity(ent)}
                        title={`查看${block.label}详情`}
                        className={`overflow-hidden rounded-xl border text-left transition hover:brightness-110 ${
                          inSeg ? "border-[#7c6cff] shadow-[0_0_0_1px_rgba(124,108,255,.4)]" : "border-white/10 opacity-55 hover:opacity-90"
                        }`}
                      >
                        <div className={`bg-black/40 ${block.kind === "character" ? "aspect-[3/4]" : "aspect-video"}`}>
                          {entityThumb(ent) ? (
                            <img
                              src={entityThumb(ent)}
                              alt=""
                              className={`h-full w-full object-cover ${block.kind === "character" ? "object-top" : ""}`}
                            />
                          ) : (
                            <div className="flex h-full items-center justify-center text-[10px] text-white/30">无图</div>
                          )}
                        </div>
                        <div className="truncate px-1.5 py-1 text-center text-[11px] font-medium text-white/80">
                          {ent.name}
                          {ent.variant && ent.variant !== "默认形象" && ent.variant !== "默认造型" ? (
                            <span className="block truncate text-[9px] font-normal text-white/40">{ent.variant}</span>
                          ) : null}
                          {ent.imageStatus === "generating" ? (
                            <span className="block text-[9px] font-normal text-[#a78bfa]">生成中…</span>
                          ) : !entityStillPasses(ent) && (ent.imageStatus === "failed" || ent.qaFailed || ent.selectedImage?.qaPass === false) ? (
                            <span className="block text-[9px] font-normal text-amber-300/80">质检未过</span>
                          ) : null}
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>
            ) : null,
          )}
          {!segAssets.all.length && !allEntities.length ? (
            <p className="text-xs text-white/40">
              本集尚无资产。可先去补角色/场景图，或直接按提示词出片。
            </p>
          ) : null}

          {/* Inline dubbing for this episode, scoped next to segment dialogues */}
          <div className="mt-2 border-t border-white/10 pt-3">
            <div className="mb-2 flex items-center justify-between">
              <span className="text-[11px] font-medium text-white/45">本集配音</span>
              <button
                type="button"
                className="btn-secondary !min-h-7 !px-2 text-[10px]"
                disabled={audioBusy}
                onClick={() => void generateAudio()}
              >
                {audioBusy ? <Loader2 className="h-3 w-3 animate-spin" /> : <Mic2 className="h-3 w-3" />}
                {episodeAudio ? "重生成" : "生成"}
              </button>
            </div>
            {episodeAudio?.url ? (
              <audio controls src={episodeAudio.url} className="w-full" preload="metadata" />
            ) : (
              <p className="text-[10px] leading-4 text-white/35">对白跟在分镜里；点生成后整集 TTS 会挂到成片。</p>
            )}
          </div>
        </aside>

        {/* Center: focused segment + beats */}
        <section className="flex min-h-0 flex-col overflow-hidden rounded-xl border border-white/10 bg-[#0c0e14] xl:h-full">
          <div className="flex flex-wrap items-center gap-2 border-b border-white/10 px-3 py-2.5">
            <div className="flex items-center gap-1 rounded-lg bg-white/5 p-0.5">
              <button
                type="button"
                className={`rounded-md px-2.5 py-1 text-xs ${scriptTab === "lens" ? "bg-white/10 font-semibold text-white" : "text-white/45"}`}
                onClick={() => setScriptTab("lens")}
              >
                镜头
              </button>
              <button
                type="button"
                className={`rounded-md px-2.5 py-1 text-xs ${scriptTab === "line" ? "bg-white/10 font-semibold text-white" : "text-white/45"}`}
                onClick={() => setScriptTab("line")}
              >
                台词
              </button>
              <button
                type="button"
                className={`inline-flex items-center gap-1 rounded-md px-2.5 py-1 text-xs ${
                  scriptTab === "prompt" ? "bg-white/10 font-semibold text-white" : "text-white/45"
                }`}
                onClick={() => void openModelPromptTab()}
                title="查看本段实际发给视频大模型的合并提示词"
              >
                <FileText className="h-3 w-3" /> 提示词
              </button>
            </div>
          </div>

          <div className="border-b border-white/10 px-4 py-3">
            <div className="flex flex-wrap items-center gap-2 text-xs">
              <span className="rounded-md bg-black/60 px-2 py-0.5 font-medium text-white">
                片段 {activeSeg?.segmentOrder ?? "—"}
              </span>
              <span className="text-white/45">{activeSeg?.duration || 0}s · {activeSeg?.shots?.length || 0} 镜</span>
              {segGenerating ? (
                <span className="rounded-full bg-[#7c6cff]/20 px-2 py-0.5 text-[10px] font-medium text-[#c4b5fd]">生成中</span>
              ) : segQaFail ? (
                <span
                  className="rounded-full bg-rose-500/15 px-2 py-0.5 text-[10px] font-medium text-rose-300"
                  title={activeSeg?.lead?.error || activeSeg?.video?.qa?.reason || "质检未达标"}
                >
                  质检未过
                </span>
              ) : segReady && segQaPass ? (
                <span className="rounded-full bg-emerald-500/15 px-2 py-0.5 text-[10px] font-medium text-emerald-300">已完成</span>
              ) : segReady ? (
                <span className="rounded-full bg-amber-500/15 px-2 py-0.5 text-[10px] font-medium text-amber-200">已出片·待复核</span>
              ) : (
                <span className="rounded-full bg-white/10 px-2 py-0.5 text-[10px] text-white/45">待出片</span>
              )}
              <button
                type="button"
                className="btn-primary ml-auto !min-h-8 !px-3 text-xs"
                disabled={generating || segGenerating || splitting}
                onClick={() => void generateSegment(pendingRegen ? { syncOnly: true } : {})}
              >
                {generating || segGenerating ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Video className="h-3.5 w-3.5" />}
                {pendingRegen ? "重生本段" : segReady ? "再生成" : "生成本段"}
              </button>
            </div>
            {segEntityQaBlockers.length ? (
              <div className="mt-2 rounded-lg border border-rose-500/35 bg-rose-500/10 px-3 py-2 text-[11px] text-rose-100">
                <div className="font-medium">
                  本段有 {segEntityQaBlockers.length} 项素材未过质检，默认禁止出片
                </div>
                <ul className="mt-1 space-y-0.5 text-rose-100/80">
                  {segEntityQaBlockers.slice(0, 4).map((b) => (
                    <li key={b.entityId}>
                      {b.kindLabel}「{b.name}」· {b.reason}
                    </li>
                  ))}
                  {segEntityQaBlockers.length > 4 ? (
                    <li>…另有 {segEntityQaBlockers.length - 4} 项</li>
                  ) : null}
                </ul>
                <p className="mt-1 text-rose-100/65">可先回素材步重生/复核；紧急时可在确认框选择「强制出片」。</p>
              </div>
            ) : null}
            {pendingRegen ? (
              <div className="mt-2 flex flex-wrap items-center justify-between gap-2 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-[11px] text-amber-100">
                <span>台词或画面已改，成片可能过期。</span>
                <button
                  type="button"
                  className="btn-primary !min-h-7 !px-2.5 text-[10px]"
                  disabled={generating || segGenerating}
                  onClick={() => void generateSegment({ syncOnly: true })}
                >
                  一键重生本段
                </button>
              </div>
            ) : null}
            <div className="mt-2 grid gap-1 text-[12px] text-white/45 sm:grid-cols-2">
              <div>
                <span className="text-white/30">地点：</span>
                {activeSeg?.lead?.location || activeSeg?.lead?.sceneName || "—"}
              </div>
              <div>
                <span className="text-white/30">时间：</span>
                {activeSeg?.lead?.timeOfDay || "—"}
              </div>
              <div>
                <span className="text-white/30">天气：</span>
                {activeSeg?.lead?.weather || "—"}
              </div>
              <div className="sm:col-span-2">
                <span className="text-white/30">起始状态：</span>
                {activeSeg?.lead?.openingState || "—"}
              </div>
            </div>
          </div>

          <div className="scrollbar-thin flex-1 space-y-3 overflow-y-auto p-3">
            {scriptTab === "prompt" ? (
              <div className="space-y-3 rounded-2xl border border-white/10 bg-white/[.03] p-4 text-sm">
                {modelPromptBusy ? (
                  <div className="flex items-center justify-center gap-2 py-16 text-white/50">
                    <Loader2 className="h-4 w-4 animate-spin" /> 加载发给模型的提示词…
                  </div>
                ) : (
                  <>
                    <p className="text-[11px] leading-5 text-white/45">
                      {modelPromptData?.note ||
                        "以下为合并后提交给 Seedance / Comfy 的正文；参考图按 references 列表另附。"}
                    </p>
                    <div>
                      <div className="mb-1 text-[11px] font-medium text-white/40">合并视频提示词</div>
                      <pre className="whitespace-pre-wrap rounded-xl border border-white/10 bg-black/40 p-3 text-[12px] leading-5 text-white/85">
                        {modelPromptData?.videoPrompt || "（无）"}
                      </pre>
                    </div>
                    {(modelPromptData?.references || []).length ? (
                      <div>
                        <div className="mb-1 text-[11px] font-medium text-white/40">
                          参考资产 · {modelPromptData.references.length}
                        </div>
                        <ul className="space-y-1.5 rounded-xl border border-white/10 bg-white/[.03] p-3 text-[12px] text-white/75">
                          {modelPromptData.references.map((r) => (
                            <li key={r.id}>
                              <span className="text-white/40">[{r.kind}]</span> {r.name}
                              {r.variant ? ` / ${r.variant}` : ""}
                              {r.hasImage ? "" : " · 无图"}
                              {r.description ? (
                                <div className="mt-0.5 text-[11px] text-white/40">{r.description}</div>
                              ) : null}
                            </li>
                          ))}
                        </ul>
                      </div>
                    ) : null}
                    {(modelPromptData?.shots || []).length ? (
                      <div>
                        <div className="mb-1 text-[11px] font-medium text-white/40">分镜原文 / 台词</div>
                        <div className="space-y-2">
                          {modelPromptData.shots.map((s) => (
                            <div key={s.shotId} className="rounded-xl border border-white/10 bg-black/30 p-3">
                              <div className="mb-1 text-[10px] font-semibold text-white/50">分镜 {s.beatIndex}</div>
                              <pre className="whitespace-pre-wrap text-[12px] leading-5 text-white/80">
                                {s.prompt || "（无镜头词）"}
                              </pre>
                              {s.dialogue ? (
                                <p className="mt-2 border-t border-white/10 pt-2 text-[12px] text-[#c4b5fd]">
                                  台词：{s.dialogue}
                                </p>
                              ) : null}
                            </div>
                          ))}
                        </div>
                      </div>
                    ) : null}
                  </>
                )}
              </div>
            ) : null}
            {scriptTab !== "prompt"
              ? (activeSeg?.shots || []).map((shot) => {
              const dlg = parseDialogue(shot.dialogue || "");
              const editing = editingShotId === shot.id;
              return (
                <article key={shot.id} className="rounded-2xl border border-white/10 bg-white/[.03] p-4">
                  <div className="mb-2 flex flex-wrap items-center gap-2">
                    <span className="rounded bg-black/55 px-2 py-0.5 text-[11px] font-semibold text-white">
                      分镜{shot.beatIndex || shot.shotOrder} · {shot.duration || 3}s
                    </span>
                    {dlg?.speaker ? (
                      <button
                        type="button"
                        className="inline-flex items-center gap-1 rounded-full border border-white/10 px-2 py-0.5 text-[10px] text-white/60 hover:border-[#7c6cff]/50 hover:text-[#c4b5fd]"
                        onClick={() => {
                          const ent = entityByName.get(dlg.speaker);
                          if (ent) openEntity(ent);
                        }}
                        title={`查看 ${dlg.speaker}`}
                      >
                        {entityThumb(entityByName.get(dlg.speaker)) ? (
                          <img src={entityThumb(entityByName.get(dlg.speaker))} alt="" className="h-3.5 w-3.5 rounded-full object-cover" />
                        ) : null}
                        {dlg.speaker}
                      </button>
                    ) : null}
                    {(shot.promptConsistency?.issues || []).length ? (
                      <span
                        className="rounded bg-amber-400/15 px-2 py-0.5 text-[10px] text-amber-200"
                        title={(shot.promptConsistency.issues || []).map((i) => i.detail).join("；")}
                      >
                        提示词不一致
                      </span>
                    ) : null}
                    <button
                      type="button"
                      className="ml-auto text-[10px] text-[#a78bfa] hover:underline"
                      onClick={() => startEditDialogue(shot)}
                    >
                      改台词
                    </button>
                  </div>
                  {scriptTab === "lens" ? (
                    <>
                      <div className="mb-1 text-[10px] font-medium uppercase tracking-wide text-white/35">镜头提示词</div>
                      <PromptWithChips
                        prompt={shot.prompt || shot.action || "（无镜头提示词）"}
                        entityByName={entityByName}
                        activeNames={segAssets.names}
                        onOpenEntity={openEntity}
                      />
                      {!editing ? (
                        <DialogueCard dialogue={shot.dialogue} entityByName={entityByName} onOpenEntity={openEntity} />
                      ) : null}
                    </>
                  ) : !editing ? (
                    <>
                      <div className="mb-1 text-[10px] font-medium uppercase tracking-wide text-white/35">台词</div>
                      <DialogueCard
                        dialogue={shot.dialogue || "（本镜无台词）"}
                        entityByName={entityByName}
                        onOpenEntity={openEntity}
                      />
                    </>
                  ) : null}
                  {editing ? (
                    <div className="mt-3 space-y-2">
                      <textarea
                        className="field min-h-20 resize-y text-sm"
                        value={draftDialogue}
                        onChange={(e) => setDraftDialogue(e.target.value)}
                        placeholder="角色名：台词内容"
                      />
                      <div className="flex flex-wrap gap-2">
                        <button
                          type="button"
                          className="btn-secondary !min-h-8 text-xs"
                          disabled={savingLine || generating}
                          onClick={() => void saveDialogue(shot.id)}
                        >
                          {savingLine ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />}
                          仅保存
                        </button>
                        <button
                          type="button"
                          className="btn-primary !min-h-8 text-xs"
                          disabled={savingLine || generating || segGenerating}
                          onClick={() => void saveDialogue(shot.id, { regenerate: true })}
                        >
                          {savingLine || generating ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Video className="h-3.5 w-3.5" />}
                          保存并重生本段
                        </button>
                        <button type="button" className="btn-quiet !min-h-8 text-xs" onClick={() => setEditingShotId("")}>
                          取消
                        </button>
                      </div>
                    </div>
                  ) : null}
                  {(shot.referenceEntityIds || []).length ? (
                    <div className="mt-3 flex flex-wrap gap-1.5">
                      {(shot.referenceEntityIds || []).map((id) => {
                        const ent = entityById.get(id) || allEntities.find((e) => e.id === id);
                        if (!ent) return null;
                        return (
                          <button
                            key={id}
                            type="button"
                            onClick={() => openEntity(ent)}
                            className="inline-flex items-center gap-1 rounded-md border border-white/10 bg-black/30 px-1.5 py-0.5 text-[10px] text-white/70 hover:border-[#7c6cff]/50 hover:text-white"
                            title={`查看 ${ent.name}`}
                          >
                            {entityThumb(ent) ? <img src={entityThumb(ent)} alt="" className="h-4 w-4 rounded object-cover" /> : null}
                            {ent.name}
                            <span className="text-white/30">{ent.kind === "character" ? "角" : ent.kind === "prop" ? "道" : "景"}</span>
                          </button>
                        );
                      })}
                    </div>
                  ) : null}
                </article>
              );
            })
              : null}
          </div>
        </section>

        {/* Right: preview */}
        <aside className="scrollbar-thin min-h-0 space-y-3 overflow-y-auto xl:h-full">
          <div ref={monitorRef} className="overflow-hidden rounded-[18px] bg-[#08090d] p-3 text-white">
            <div className="mb-2 flex items-center justify-between text-[10px] text-white/45">
              <span>
                片段 {activeSeg?.segmentOrder ?? "—"} / {segments.length}
              </span>
              <span>
                {activeSeg?.duration || 0}s · {ratio}
              </span>
            </div>
            <div
              className={`relative flex items-center justify-center overflow-hidden rounded-xl bg-black ${
                ratio === "9:16" ? "mx-auto aspect-[9/16] max-h-[380px]" : "aspect-video"
              }`}
            >
              {segReady ? (
                <>
                  <video
                    ref={videoRef}
                    key={`${activeSeg.segmentOrder}-${activeSeg.video.url}`}
                    src={activeSeg.video.url}
                    muted={muted}
                    playsInline
                    className="h-full w-full object-contain"
                    onEnded={onSegEnded}
                    onClick={togglePlay}
                  />
                  {segmentDialogues[0]?.parsed?.line ? (
                    <div className="pointer-events-none absolute inset-x-3 bottom-10 rounded-md bg-black/70 px-3 py-2 text-center text-xs leading-5">
                      {segmentDialogues[0].parsed.speaker
                        ? `${segmentDialogues[0].parsed.speaker}：${segmentDialogues[0].parsed.line}`
                        : segmentDialogues[0].parsed.line}
                    </div>
                  ) : null}
                </>
              ) : (
                <div className="flex flex-col items-center gap-2 px-4 text-center">
                  <Film className="h-10 w-10 text-white/15" />
                  <p className="text-xs text-white/40">本段尚未出片</p>
                  <button
                    type="button"
                    className="btn-primary !min-h-8 text-xs"
                    disabled={generating || segGenerating}
                    onClick={() => void generateSegment(pendingRegen ? { syncOnly: true } : {})}
                  >
                    {generating || segGenerating ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Video className="h-3.5 w-3.5" />}
                    {pendingRegen ? "重生本段" : "生成本段"}
                  </button>
                </div>
              )}
            </div>
            {bgm?.url ? <audio ref={bgmRef} src={bgm.url} loop preload="metadata" /> : null}
            <div className="mt-3 flex flex-wrap items-center justify-center gap-1.5">
              <button type="button" className="btn-quiet !min-h-9 !px-2.5 text-white/80" onClick={() => goSeg(-1)}>
                <ChevronLeft className="h-4 w-4" />
              </button>
              <button type="button" className="btn-primary !min-h-9 !rounded-full !px-4" disabled={!segReady} onClick={togglePlay}>
                {playing ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
                {playing ? "暂停" : "播放"}
              </button>
              <button type="button" className="btn-quiet !min-h-9 !px-2.5 text-white/80" onClick={() => goSeg(1)}>
                <ChevronRight className="h-4 w-4" />
              </button>
              <button type="button" className="btn-quiet !min-h-9 !px-2.5 text-white/80" onClick={() => setMuted((m) => !m)}>
                {muted ? <VolumeX className="h-4 w-4" /> : <Volume2 className="h-4 w-4" />}
              </button>
              <button
                type="button"
                className="btn-quiet !min-h-9 !px-2.5 text-white/80"
                onClick={() => {
                  const node = monitorRef.current;
                  if (!node) return;
                  if (document.fullscreenElement) void document.exitFullscreen();
                  else void node.requestFullscreen?.();
                }}
              >
                <Maximize2 className="h-4 w-4" />
              </button>
            </div>
            <div className="mt-2 flex flex-wrap items-center justify-center gap-4 text-xs text-white/60">
              <label className="flex items-center gap-1.5">
                <input type="checkbox" checked={continuous} onChange={(e) => setContinuous(e.target.checked)} />
                连续播放
              </label>
              <label className={`flex items-center gap-1.5 ${bgm?.url ? "" : "opacity-40"}`}>
                <input type="checkbox" checked={bgmOn && !!bgm?.url} disabled={!bgm?.url} onChange={(e) => setBgmOn(e.target.checked)} />
                配乐
              </label>
            </div>
          </div>

          {/* Segment tools: 改台词 / 剪一刀 */}
          <div className="rounded-xl border border-white/10 bg-[#0c0e14] p-3">
            <div className="mb-2 flex flex-wrap gap-1.5">
              {[
                { id: "visual", label: "AI 改画面" },
                { id: "line", label: "改台词" },
                { id: "trim", label: "剪一刀" },
              ].map((m) => (
                <button
                  key={m.id}
                  type="button"
                  onClick={() => setEditMode(m.id)}
                  className={`rounded-full px-3 py-1.5 text-xs font-medium transition ${
                    editMode === m.id ? "bg-[#7c6cff] text-white" : "bg-white/5 text-white/60 hover:bg-white/10"
                  }`}
                >
                  {m.label}
                </button>
              ))}
            </div>

            {editMode === "visual" ? (
              <div className="space-y-2">
                <p className="text-[11px] leading-4 text-white/45">
                  用自然语言描述要改的画面（光影、天气、动作、情绪等），会改写本段分镜并重新出片。
                </p>
                <textarea
                  className="field min-h-24 resize-y text-sm"
                  value={visualNote}
                  onChange={(e) => setVisualNote(e.target.value)}
                  placeholder="例：雨再大一点，霓虹偏冷青；林晚推门时肩膀更湿、更急"
                />
                <div className="flex flex-wrap gap-1.5">
                  {["雨更大、霓虹更冷", "动作更急促", "灯光更暖更柔", "表情更克制"].map((hint) => (
                    <button
                      key={hint}
                      type="button"
                      className="rounded-full border border-white/10 px-2 py-1 text-[10px] text-white/55 hover:border-white/25 hover:text-white/80"
                      onClick={() => setVisualNote((cur) => (cur ? `${cur}；${hint}` : hint))}
                    >
                      {hint}
                    </button>
                  ))}
                </div>
                <button
                  type="button"
                  className="btn-primary w-full !min-h-9 text-xs"
                  disabled={!visualNote.trim() || generating || segGenerating}
                  onClick={() => void generateSegment({ instruction: visualNote.trim() })}
                >
                  {generating || segGenerating ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />}
                  应用并重生本段
                </button>
              </div>
            ) : editMode === "line" ? (
              <>
                <div className="mb-2 text-[11px] font-medium text-white/45">本段台词 · {segmentDialogues.length} 句</div>
                {segmentDialogues.length ? (
                  <ul className="max-h-44 space-y-2 overflow-y-auto text-xs leading-5">
                    {segmentDialogues.map(({ shot, parsed }) => (
                      <li key={shot.id} className="rounded-lg border border-white/5 bg-black/20 px-2.5 py-2">
                        <div className="flex items-start justify-between gap-2">
                          <div className="min-w-0">
                            <span className="font-semibold text-white/80">{parsed.speaker || "旁白"}</span>
                            <span className="text-white/50"> · </span>
                            <span className="text-white/70">{parsed.line}</span>
                          </div>
                          <button
                            type="button"
                            className="shrink-0 text-[10px] text-[#a78bfa] hover:underline"
                            onClick={() => startEditDialogue(shot)}
                          >
                            编辑
                          </button>
                        </div>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-[11px] text-white/35">本段无对白。可在中栏分镜点「改台词」添加。</p>
                )}
              </>
            ) : (
              <div className="space-y-2 text-xs">
                {!segReady ? (
                  <p className="py-4 text-center text-white/35">先生成本段视频，再裁剪入点出点。</p>
                ) : (
                  <>
                    <label className="block">
                      <span className="mb-1 flex justify-between text-white/45">
                        <span>起点</span>
                        <span className="timecode">{trimStart.toFixed(2)}s</span>
                      </span>
                      <input
                        type="range"
                        min={0}
                        max={mediaMax}
                        step={0.05}
                        value={trimStart}
                        onChange={(e) => setTrimStart(Math.min(Number(e.target.value), trimEnd - 0.1))}
                        className="w-full accent-[#7c6cff]"
                      />
                    </label>
                    <label className="block">
                      <span className="mb-1 flex justify-between text-white/45">
                        <span>终点</span>
                        <span className="timecode">{trimEnd.toFixed(2)}s</span>
                      </span>
                      <input
                        type="range"
                        min={0}
                        max={mediaMax}
                        step={0.05}
                        value={trimEnd}
                        onChange={(e) => setTrimEnd(Math.max(Number(e.target.value), trimStart + 0.1))}
                        className="w-full accent-[#7c6cff]"
                      />
                    </label>
                    <div className="grid grid-cols-2 gap-1.5">
                      <button type="button" className="btn-quiet !min-h-8 text-xs" onClick={() => setTrimStart((v) => Math.max(0, v - 0.5))}>
                        起点 −0.5s
                      </button>
                      <button type="button" className="btn-quiet !min-h-8 text-xs" onClick={() => setTrimStart((v) => Math.min(v + 0.5, trimEnd - 0.1))}>
                        起点 +0.5s
                      </button>
                      <button type="button" className="btn-quiet !min-h-8 text-xs" onClick={() => setTrimEnd((v) => Math.max(trimStart + 0.1, v - 0.5))}>
                        终点 −0.5s
                      </button>
                      <button type="button" className="btn-quiet !min-h-8 text-xs" onClick={() => setTrimEnd((v) => Math.min(mediaMax, v + 0.5))}>
                        终点 +0.5s
                      </button>
                    </div>
                    <button type="button" className="btn-secondary w-full !min-h-9 text-xs" onClick={previewTrim}>
                      预览留下的部分
                    </button>
                    <button
                      type="button"
                      className="btn-primary w-full !min-h-9 text-xs"
                      disabled={savingTrim}
                      onClick={() => void saveTrim()}
                    >
                      {savingTrim ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />}
                      保存裁剪
                    </button>
                  </>
                )}
              </div>
            )}
          </div>
        </aside>
      </div>

      {/* Bottom filmstrip — pinned; does not scroll away with the desk */}
      <div className="z-20 shrink-0 rounded-xl border border-white/10 bg-[#0c0e14] px-3 py-2.5 shadow-[0_-8px_24px_rgba(0,0,0,.35)]">
        <div className="mb-2 flex items-center justify-between text-[11px] text-white/45">
          <span>全集时间轴 · {segments.length} 片段 · {Math.round(totalDur)}s</span>
          <span>{hasSegmentLayout ? "按片段出片" : "迁移中…"}</span>
        </div>
        <div className="scrollbar-thin flex gap-2 overflow-x-auto pb-1">
          {segments.map((seg) => {
            const active = seg.segmentOrder === activeSeg?.segmentOrder;
            const ready = Boolean(seg.video?.url);
            return (
              <button
                key={seg.segmentOrder}
                type="button"
                onClick={() => {
                  setSegmentOrder(seg.segmentOrder);
                  setPlaying(false);
                }}
                className={`w-[104px] shrink-0 overflow-hidden rounded-lg border text-left transition ${
                  active ? "border-[#7c6cff] ring-1 ring-[#7c6cff]/50" : "border-white/10 hover:border-white/25"
                }`}
              >
                <div className="relative aspect-video bg-black/50">
                  {ready ? (
                    <video src={seg.video.url} muted preload="metadata" className="h-full w-full object-cover" />
                  ) : (
                    <div className="flex h-full items-center justify-center text-[10px] text-white/30">
                      {seg.shots.some((s) => s.status === "generating") ? "生成中" : "待出片"}
                    </div>
                  )}
                  <span className="absolute left-1 top-1 rounded bg-black/70 px-1.5 py-0.5 text-[10px] font-semibold text-white">
                    {seg.segmentOrder}
                  </span>
                </div>
                <div className="px-1.5 py-1 text-[10px] text-white/55">
                  {seg.duration}s · {seg.shots.length}镜
                </div>
              </button>
            );
          })}
        </div>
      </div>

      <ConfirmDialog
        open={confirmSplit}
        title="重新拆分本集？"
        message="现有镜头与视频版本记录将被替换；本地文件仍保留。"
        confirmLabel="重新拆分"
        onCancel={() => setConfirmSplit(false)}
        onConfirm={() => void split()}
      />

      <ConfirmDialog
        open={Boolean(forceQaDialog)}
        title="素材质检未过，已阻断出片"
        message={
          forceQaDialog
            ? `${formatEntityQaBlockers(forceQaDialog.blockers)}\n\n建议先重生/复核上述素材。若仍要出片，将继续使用未过检参考图，成片质量可能更差。`
            : ""
        }
        confirmLabel="强制出片"
        cancelLabel="先去修素材"
        danger
        maxWidthClass="max-w-lg"
        onCancel={() => setForceQaDialog(null)}
        onConfirm={() => {
          const opts = forceQaDialog?.opts || {};
          setForceQaDialog(null);
          void generateSegment({ ...opts, forceEntityQa: true, skipClientGate: true });
        }}
      />

      <AssetDetailModal
        entity={inspectEntity}
        projectId={projectId}
        config={config}
        onClose={() => setInspectEntityId("")}
        onBundle={onBundle}
        onRefresh={onRefresh}
        onNeedKeys={onNeedKeys}
      />
    </div>
  );
}
