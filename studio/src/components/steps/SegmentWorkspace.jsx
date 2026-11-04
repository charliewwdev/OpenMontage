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
  Share2,
  Sparkles,
  Video,
  Volume2,
  VolumeX,
  X,
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
import { shareVideoToX } from "../../lib/shareToX";
import { toast } from "../../lib/toast";
import { useTimer } from "../../lib/useTimer";
import { AssetDetailModal } from "../AssetDetailModal";
import { SkillExpertBadge } from "../SkillExpertBadge";
import { ConfirmDialog } from "../ConfirmDialog";
import { ModalOverlay } from "../ModalPortal";

import { tr, useLocale } from "../../lib/i18n";

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
  useLocale();
  const parts = String(prompt || "").split(/(@[^\s@,，。；;（）()]+)/g);
  return (
    <p className="text-[11px] leading-snug text-white/85">
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
  useLocale();
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
        title={ent ? tr("ui_segment_workspace_view", {
          name: ent.name
        }) : undefined}
      >
        {entityThumb(ent) ? (
          <img src={entityThumb(ent)} alt="" className="h-full w-full object-contain object-center bg-black/60" />
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
              {parsed.speaker || tr("ui_segment_workspace_dialogue")}
            </button>
          ) : (
            <span className="font-semibold text-white/85">{parsed.speaker || tr("ui_segment_workspace_dialogue")}</span>
          )}
          <span>{tr("ui_segment_workspace_line")}</span>
        </div>
        <p className="text-[12px] font-medium leading-snug text-white/90">「{parsed.line.replace(/^「|」$/g, "")}」</p>
      </div>
    </div>
  );
}

/**
 * Episode desk: left assets · center segment · right preview · bottom strip.
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
  useLocale();
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
  const [previewFinalOpen, setPreviewFinalOpen] = useState(false);
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

  // 极像质量堆叠：写真对标默认 1080p 出片
  useEffect(() => {
    if (bundle?.project?.workflow === "portrait-match") setResolution("1080p");
  }, [bundle?.project?.workflow]);

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

  // Portrait: ensure 角色/场景走 drama-entity-still，提示词结构化达标。
  useEffect(() => {
    if (readOnly || bundle?.project?.workflow !== "portrait-match") return;
    if (bundle?.project?.portraitMatchMode === "reshoot") return;
    let cancelled = false;
    (async () => {
      try {
        const res = await api(`/api/projects/${encodeURIComponent(projectId)}/portrait-match/prepare-assets`, {
          method: "POST",
        });
        if (!cancelled && res?.bundle) onBundle?.(res.bundle);
      } catch {
        /* non-blocking */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [readOnly, projectId, bundle?.project?.workflow, bundle?.project?.portraitMatchMode, onBundle]);

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
    setBusyMsg?.(tr("ui_segment_workspace_checking_prompts_against_dialogue_and_assets"));
    try {
      const res = await api(`/api/projects/${encodeURIComponent(projectId)}/storyboard`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "check-consistency", episodeId: episode.id, repair: true }),
      });
      apply(res);
      const fail = Number(res?.fail || 0);
      const repaired = (res?.results || []).filter((r) => r.repaired).length;
      if (!fail && !repaired) toast.success(tr("ui_segment_workspace_prompts_in_this_episode_match_the"));
      else if (!fail) toast.success(tr("ui_segment_workspace_fixed_prompts_to_match_the_dialogue", {
        repaired: repaired
      }));
      else toast.error(tr("ui_segment_workspace_still_don_t_line_up_marked", {
        fail: fail
      }));
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
      toast.info(tr("ui_segment_workspace_wait_for_video_jobs_to_finish"));
      return;
    }
    if (shots.length && !confirmSplit) {
      setConfirmSplit(true);
      return;
    }
    if (!requireCapability(caps, "deepseek", onNeedKeys, tr("ui_segment_workspace_text_llm_key"))) return;
    setConfirmSplit(false);
    setSplitting(true);
    setBusyMsg?.(tr("ui_segment_workspace_ai_is_splitting_shots_into_segments"));
    try {
      const res = await api(`/api/projects/${encodeURIComponent(projectId)}/storyboard`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "generate", episodeId: episode.id }),
      });
      apply(res);
      setSegmentOrder(1);
      toast.success(tr("ui_segment_workspace_episode_split_into_segments"));
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
    setBusyMsg?.(tr("ui_segment_workspace_unifying_full_body_character_framing_for"));
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
          // Old stills may already qaPass but be extreme close-up / full-body — force cast regen.
          forceRefreshKinds: ["character"],
        }),
      });
      apply(res);
      const queued = res?.queued ?? 0;
      const attempted = res?.attempted ?? 0;
      if (res?.async || res?.queued) {
        toast.success(tr("ui_segment_workspace_image_fill_jobs_submitted_to_the"));
        const started = Date.now();
        while (Date.now() - started < 20 * 60 * 1000) {
          await new Promise((r) => setTimeout(r, 5000));
          const snap = await api(`/api/projects/${encodeURIComponent(projectId)}`);
          if (snap) apply({ bundle: snap });
          const still = (snap?.entities || []).filter(
            (e) => !e.deletedAt && e.imageStatus === "generating",
          );
          if (!still.length) {
            toast.success(tr("ui_segment_workspace_image_fill_for_this_segment_finished"));
            break;
          }
          setBusyMsg?.(tr("ui_segment_workspace_filling_images_left", {
            length: still.length
          }));
        }
        return;
      }
      if (!attempted) toast.success(tr("ui_segment_workspace_character_scene_images_for_this_segment"));
      else if (queued > 0) {
        toast.success(tr("ui_segment_workspace_queued_for_unified_framing_characters_re", {
          0: queued || attempted
        }));
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
            toast.success(tr("ui_segment_workspace_image_fill_for_this_segment_finished"));
            break;
          }
          setBusyMsg?.(tr("ui_segment_workspace_filling_images_left", {
            length: still.length
          }));
        }
      } else {
        const ok = res?.pass ?? 0;
        const fail = res?.fail ?? 0;
        if (fail === 0) toast.success(tr("ui_segment_workspace_filled_look_images_qa_passed", {
          ok: ok
        }));
        else toast.error(tr("ui_segment_workspace_image_fill_done_passed_failed_qa", {
          ok: ok,
          fail: fail
        }));
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
      toast.error(tr("ui_segment_workspace_select_an_available_video_model_at"));
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
        ? tr("ui_segment_workspace_regenerating_segment_with_changes", {
        segmentOrder: activeSeg.segmentOrder
      })
        : forceEntityQa
          ? tr("ui_segment_workspace_force_rendering_segment", {
        segmentOrder: activeSeg.segmentOrder
      })
          : tr("ui_segment_workspace_generating_segment", {
        segmentOrder: activeSeg.segmentOrder
      }),
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
          ? tr("ui_segment_workspace_segment_submitted_for_regeneration_with_changes", {
          segmentOrder: activeSeg.segmentOrder
        })
          : forceEntityQa
            ? tr("ui_segment_workspace_segment_force_rendered_assets_that_failed", {
          segmentOrder: activeSeg.segmentOrder
        })
            : tr("ui_segment_workspace_segment_render_submitted", {
          segmentOrder: activeSeg.segmentOrder
        }),
      );
    } catch (error) {
      if (isEntityQaBlockedError(error) && !forceEntityQa) {
        setForceQaDialog({
          blockers: blockersFromError(error).length ? blockersFromError(error) : segEntityQaBlockers,
          opts,
        });
        toast.error(tr("ui_segment_workspace_assets_failed_qa_rendering_blocked"));
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
    setBusyMsg?.(tr("ui_segment_workspace_synthesizing_voice_over"));
    try {
      const res = await api(`/api/projects/${encodeURIComponent(projectId)}/audio`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "generate", episodeId: episode.id }),
      });
      apply(res);
      toast.success(tr("ui_segment_workspace_episode_voice_over_generated_mixed_in"));
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
    setBusyMsg?.(tr("ui_segment_workspace_exporting_cut"));
    try {
      const isPortrait = bundle?.project?.workflow === "portrait-match";
      // Portrait idlock: use end-of-clip × gap assemble so adjacent beats share the junction pose.
      const res = isPortrait
        ? await api(`/api/projects/${encodeURIComponent(projectId)}/portrait-match/assemble`, {
            method: "POST",
          })
        : await api(`/api/projects/${encodeURIComponent(projectId)}/edits`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ action: "export", episodeId: episode.id }),
          });
      apply(res);
      const url =
        res?.edit?.outputUrl ||
        res?.bundle?.edits?.slice(-1)?.[0]?.outputUrl ||
        res?.bundle?.edits?.find((e) => e.episodeId === episode.id)?.outputUrl;
      if (url) toast.success(isPortrait ? tr("ui_segment_workspace_benchmark_cut_exported_v3_intro_beat") : tr("ui_segment_workspace_cut_exported"));
      else toast.success(tr("ui_segment_workspace_export_job_finished"));
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
      toast.success(tr("ui_segment_workspace_lines_saved_regenerate_the_segment_to"));
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
      return toast.info(tr("ui_segment_workspace_this_segment_has_no_cut_to"));
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
      toast.success(tr("ui_segment_workspace_trim_saved_applied_when_exporting"));
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
  const editDraft = useMemo(() => {
    const edits = bundle?.edits || [];
    const hasOut = (e) => Boolean(e && (e.outputUrl || e.outputPath));
    // Prefer any edit that actually has a finished file (never an empty episode stub).
    const byEp = edits.find((e) => e.episodeId === episodeId && hasOut(e));
    if (byEp) return byEp;
    // Portrait assemble writes kind=portrait-assemble (often without episodeId).
    const assembled = [...edits]
      .reverse()
      .find((e) => (e.kind === "portrait-assemble" || e.kind === "assemble") && hasOut(e));
    if (assembled) return assembled;
    // Last resort: any edit with output for this project.
    return [...edits].reverse().find(hasOut) || null;
  }, [bundle?.edits, episodeId]);
  const editOutputUrl = useMemo(() => {
    if (!editDraft) return "";
    if (editDraft.outputUrl) return String(editDraft.outputUrl);
    if (editDraft.outputPath && projectId) {
      const rel = String(editDraft.outputPath).replace(/^\//, "");
      return `/api/media/${encodeURIComponent(projectId)}/${rel}`;
    }
    return "";
  }, [editDraft, projectId]);
  const segReady = Boolean(activeSeg?.video?.url);
  const segVideoQa = activeSeg?.video?.qa || {};
  const portraitBypass =
    Boolean(segVideoQa.bypass === "portrait-idlock" || segVideoQa.reason === "portrait-idlock") ||
    Boolean(bundle?.project?.workflow === "portrait-match") ||
    Boolean(activeSeg?.lead?.idlock || activeSeg?.lead?.skipVideoQa);
  // Soft-skipped QA (JSON/vision errors) must not read as green「已完成」.
  // Portrait idlock sets qaPass intentionally — never treat that as「质检未过」.
  const segQaPass =
    activeSeg?.video?.qaPass === true && (!segVideoQa.skipped || portraitBypass);
  const segQaFail =
    segReady &&
    !portraitBypass &&
    (activeSeg?.video?.qaPass === false ||
      Boolean(segVideoQa.skipped) ||
      activeSeg?.lead?.status === "failed" ||
      String(activeSeg?.lead?.error || "").includes("质检"));
  const segGenerating = activeSeg?.shots?.some((s) => s.status === "generating");
  const totalDur = segments.reduce((sum, s) => sum + Number(s.duration || 0), 0);
  const readyCount = segments.filter((s) => s.video?.url).length;

  if (!episode || !confirmedEpisodes.some((e) => e.id === episodeId)) {
    return (
      <div className="panel py-24 text-center text-sm text-white/50">{tr("ui_segment_workspace_lock_episodes_in_the_script_step")}{typeof setStep === "function" ? (
          <div className="mt-4">
            <button type="button" className="btn-primary" onClick={() => setStep("script")}>{tr("ui_segment_workspace_go_to_script")}</button>
          </div>
        ) : null}
      </div>
    );
  }

  if (!shots.length) {
    return (
      <div className="panel flex flex-col items-center border-dashed py-24 text-center">
        <Clapperboard className="mb-4 h-10 w-10 text-[#7c6cff]" />
        <strong className="text-lg">{tr("ui_segment_workspace_no_segments_in_this_episode_yet")}</strong>
        <p className="mt-2 max-w-md text-sm text-white/50">{tr("ui_segment_workspace_splits_the_episode_into_segments_of")}</p>
        <SkillExpertBadge skillId="drama-shot-prompt" className="mt-4" />
        <button type="button" className="btn-primary mt-5" disabled={splitting} onClick={() => void split()}>
          {splitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
          {splitting ? tr("ui_segment_workspace_splitting", {
            splitElapsedTime: splitElapsedTime
          }) : tr("ui_segment_workspace_ai_split_into_segments")}
        </button>
        <ConfirmDialog
          open={confirmSplit}
          title={tr("ui_segment_workspace_re_split_this_episode")}
          message={tr("ui_segment_workspace_existing_shots_and_video_version_history")}
          confirmLabel={tr("ui_segment_workspace_re_split")}
          onCancel={() => setConfirmSplit(false)}
          onConfirm={() => void split()}
        />
      </div>
    );
  }

  return (
    <div className="flex h-full min-h-0 flex-col gap-1.5 text-[12px] leading-snug">
      {/* Compact toolbar — compact density */}
      <div className="flex shrink-0 flex-wrap items-center gap-2 rounded-lg border border-white/10 bg-[#0c0e14] px-2 py-1.5">
        <div className="min-w-0 shrink">
          <h2 className="truncate text-[13px] font-semibold text-white">{tr("ui_segment_workspace_workspace")}<span className="ml-1.5 text-[11px] font-normal text-white/45">{tr("ui_segment_workspace_ep", {
                episodeNumber: episode.episodeNumber
              })}{episode.title || tr("ui_segment_workspace_untitled")}」
                          </span>
          </h2>
          <p className="text-[10px] text-white/40">{tr("ui_segment_workspace_segments_rendered_about_s", {
              length: segments.length,
              readyCount: readyCount,
              length2: segments.length,
              3: Math.round(totalDur)
            })}</p>
          <SkillExpertBadge skillId="drama-shot-prompt" className="mt-1" />
        </div>
        {segments.length ? (
          <div className="flex min-w-0 items-center gap-0.5" aria-label={tr("ui_segment_workspace_segment_nav")}>
            <button
              type="button"
              className="btn-quiet !min-h-7 !px-1.5"
              disabled={segments[0]?.segmentOrder === activeSeg?.segmentOrder}
              onClick={() => goSeg(-1)}
            >
              <ChevronLeft className="h-3.5 w-3.5" />
            </button>
            <div className="scrollbar-thin flex max-w-[min(100%,22rem)] gap-1 overflow-x-auto py-0.5">
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
                    className={`flex h-6 min-w-6 items-center justify-center rounded-full px-2 text-[11px] font-semibold transition ${
                      active ? "bg-[#7c6cff] text-white" : "bg-white/5 text-white/50 hover:bg-white/10 hover:text-white"
                    }`}
                    title={tr("ui_segment_workspace_segment_3", {
                      segmentOrder: seg.segmentOrder
                    })}
                  >
                    {seg.segmentOrder}
                  </button>
                );
              })}
            </div>
            <button
              type="button"
              className="btn-quiet !min-h-7 !px-1.5"
              disabled={segments[segments.length - 1]?.segmentOrder === activeSeg?.segmentOrder}
              onClick={() => goSeg(1)}
            >
              <ChevronRight className="h-3.5 w-3.5" />
            </button>
          </div>
        ) : null}
        <div className="ml-auto flex flex-wrap items-center gap-1.5">
          <button type="button" className="btn-secondary !min-h-7 text-[11px]" disabled={splitting || generating} onClick={() => void checkConsistency()}>{tr("ui_segment_workspace_check_prompts")}</button>
          <button type="button" className="btn-secondary !min-h-7 text-[11px]" disabled={splitting || generating} onClick={() => void split()}>
            {splitting ? <Loader2 className="h-3 w-3 animate-spin" /> : <Sparkles className="h-3 w-3" />}{tr("ui_segment_workspace_re_split")}</button>
          {editOutputUrl ? (
            <>
              <button
                type="button"
                className="btn-secondary !min-h-7 text-[11px]"
                title={tr("ui_segment_workspace_preview_cut_in_a_popup")}
                onClick={() => setPreviewFinalOpen(true)}
              >
                <Film className="h-3 w-3" />{" "}{tr("ui_segment_workspace_view_cut")}</button>
              <button
                type="button"
                className="btn-secondary !min-h-7 text-[11px]"
                title={tr("ui_segment_workspace_open_x_with_promo_copy_and")}
                onClick={() => {
                  const res = shareVideoToX({
                    project: bundle?.project,
                    projectId,
                    outputUrl: editOutputUrl,
                    outputPath: editDraft?.outputPath,
                    episodeId: episode?.id,
                    durationSec: editDraft?.visualDur || editDraft?.targetDur || null,
                  });
                  if (res.ok) toast.success(res.message);
                  else toast.error(res.message || tr("ui_segment_workspace_couldn_t_open_x"));
                }}
              >
                <Share2 className="h-3 w-3" />{" "}{tr("ui_segment_workspace_share_to_x")}</button>
            </>
          ) : (
            <button type="button" className="btn-secondary !min-h-7 text-[11px]" disabled={exporting || !readyCount} onClick={() => void exportEpisode()}>
              {exporting ? <Loader2 className="h-3 w-3 animate-spin" /> : <Film className="h-3 w-3" />}{tr("ui_segment_workspace_export_cut")}</button>
          )}
        </div>
      </div>

      {bundle?.project?.workflow === "portrait-match" ? (
        <p className="shrink-0 rounded-md border border-amber-400/20 bg-amber-400/5 px-2.5 py-1.5 text-[11px] leading-relaxed text-amber-100/80">
          {bundle?.project?.portraitMatchMode === "reshoot" ? (
            <>{tr("ui_segment_workspace_original_reshoot_shoot_with_a_real")}</>
          ) : (
            <>{tr("ui_segment_workspace_look_alike_quality_stack_h3_is")}</>
          )}
        </p>
      ) : null}

      {/* Desk: stack → main+monitor → assets+main+monitor. Height-driven portrait avoids aspect/max-h squash. */}
      <div className="grid min-h-0 flex-1 grid-cols-1 gap-1.5 overflow-hidden lg:grid-cols-[minmax(0,1fr)_minmax(200px,260px)] xl:grid-cols-[176px_minmax(0,1fr)_minmax(200px,260px)]">
        {/* Left: compact asset library — dense grid/list like production desks */}
        <aside className="scrollbar-thin order-3 max-h-[36vh] min-h-0 overflow-y-auto rounded-lg border border-white/10 bg-[#0c0e14] p-1.5 lg:col-span-2 lg:max-h-[28vh] xl:order-1 xl:col-span-1 xl:h-full xl:max-h-none">
          <div className="mb-1.5 flex items-center justify-between px-0.5">
            <h4 className="text-[12px] font-semibold text-white">{tr("ui_segment_workspace_asset_library")}</h4>
            <button
              type="button"
              className="inline-flex items-center gap-1 text-[10px] text-[#a78bfa] hover:underline disabled:opacity-40"
              disabled={fillingStills || generating || splitting}
              title={tr("ui_segment_workspace_fill_missing_images_characters_in_this")}
              onClick={() => void fillSegmentStills()}
            >
              {fillingStills ? <Loader2 className="h-3 w-3 animate-spin" /> : null}
              {fillingStills ? tr("ui_segment_workspace_filling_images") : tr("ui_segment_workspace_unify_framing")}
            </button>
          </div>
          {[
            {
              kind: "character",
              label: tr("ui_segment_workspace_characters"),
              list: segAssets.characters.length
                ? segAssets.characters
                : episodeEntities.filter((e) => e.kind === "character").slice(0, 9),
            },
            {
              kind: "scene",
              label: tr("ui_segment_workspace_scenes"),
              list: segAssets.scenes.length
                ? segAssets.scenes
                : episodeEntities.filter((e) => e.kind === "scene").slice(0, 6),
            },
            {
              kind: "prop",
              label: tr("ui_segment_workspace_props"),
              list: segAssets.props.length
                ? segAssets.props
                : episodeEntities.filter((e) => e.kind === "prop").slice(0, 8),
            },
          ].map((block) =>
            block.list.length ? (
              <div key={block.kind} className="mb-2.5">
                <div className="mb-1 text-[10px] font-medium text-white/45">{block.label}</div>
                {block.kind === "character" ? (
                  <div className="grid grid-cols-3 gap-1.5">
                    {block.list.map((ent) => {
                      const inSeg = segAssets.all.some((x) => x.id === ent.id) || segAssets.names.has(ent.name);
                      return (
                        <button
                          key={ent.id}
                          type="button"
                          onClick={() => openEntity(ent)}
                          title={ent.name}
                          className={`overflow-hidden rounded-lg border text-left transition hover:brightness-110 ${
                            inSeg ? "border-[#7c6cff]" : "border-white/10 opacity-60 hover:opacity-100"
                          }`}
                        >
                          <div
                            className={`flex aspect-[3/4] items-center justify-center overflow-hidden ${
                              block.kind === "scene" ? "bg-[#11131a]" : "asset-cutout-bg"
                            }`}
                          >
                            {entityThumb(ent) ? (
                              <img
                                src={entityThumb(ent)}
                                alt=""
                                className="h-full w-full object-cover object-top"
                              />
                            ) : (
                              <span className="text-[9px] text-white/25">{tr("ui_segment_workspace_no_image")}</span>
                            )}
                          </div>
                          <div className="truncate px-0.5 py-0.5 text-center text-[9px] text-white/75">{ent.name}</div>
                        </button>
                      );
                    })}
                  </div>
                ) : (
                  <div className="flex flex-col gap-1">
                    {block.list.map((ent) => {
                      const inSeg = segAssets.all.some((x) => x.id === ent.id) || segAssets.names.has(ent.name);
                      return (
                        <button
                          key={ent.id}
                          type="button"
                          onClick={() => openEntity(ent)}
                          title={ent.name}
                          className={`flex items-center gap-2 rounded-lg border px-1 py-1 text-left transition hover:brightness-110 ${
                            inSeg ? "border-[#7c6cff]/70 bg-[#7c6cff]/5" : "border-white/10 opacity-70 hover:opacity-100"
                          }`}
                        >
                          <div
                            className={`flex shrink-0 items-center justify-center overflow-hidden rounded-md ${
                              block.kind === "scene" ? "bg-[#11131a]" : "asset-cutout-bg"
                            } ${block.kind === "prop" ? "h-9 w-9" : "h-9 w-14"}`}
                          >
                            {entityThumb(ent) ? (
                              <img
                                src={entityThumb(ent)}
                                alt=""
                                className="h-full w-full object-cover object-center"
                              />
                            ) : (
                              <span className="text-[8px] text-white/25">—</span>
                            )}
                          </div>
                          <span className="min-w-0 flex-1 truncate text-[11px] text-white/80">{ent.name}</span>
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>
            ) : null,
          )}
          {!segAssets.all.length && !allEntities.length ? (
            <p className="text-xs text-white/40">{tr("ui_segment_workspace_no_assets_in_this_episode_yet")}</p>
          ) : null}

          {/* Inline dubbing for this episode, scoped next to segment dialogues */}
          <div className="mt-2 border-t border-white/10 pt-3">
            <div className="mb-2 flex items-center justify-between">
              <span className="text-[11px] font-medium text-white/45">{tr("ui_segment_workspace_episode_voice_over")}</span>
              <button
                type="button"
                className="btn-secondary !min-h-7 !px-2 text-[10px]"
                disabled={audioBusy}
                onClick={() => void generateAudio()}
              >
                {audioBusy ? <Loader2 className="h-3 w-3 animate-spin" /> : <Mic2 className="h-3 w-3" />}
                {episodeAudio ? tr("ui_segment_workspace_regenerate") : tr("ui_segment_workspace_generate")}
              </button>
            </div>
            {episodeAudio?.url ? (
              <audio controls src={episodeAudio.url} className="w-full" preload="metadata" />
            ) : (
              <p className="text-[10px] leading-4 text-white/35">{tr("ui_segment_workspace_dialogue_follows_the_storyboard_after_you")}</p>
            )}
          </div>
        </aside>

        {/* Center: focused segment + beats */}
        <section className="order-1 flex min-h-[220px] flex-col overflow-hidden rounded-xl border border-white/10 bg-[#0c0e14] lg:min-h-0 xl:order-2 xl:h-full">
          <div className="flex flex-wrap items-center gap-1.5 border-b border-white/10 px-2 py-1.5">
            <div className="flex items-center gap-0.5 rounded-md bg-white/5 p-0.5">
              <button
                type="button"
                className={`rounded px-2 py-0.5 text-[11px] ${scriptTab === "lens" ? "bg-white/10 font-semibold text-white" : "text-white/45"}`}
                onClick={() => setScriptTab("lens")}
              >{tr("ui_segment_workspace_shot")}</button>
              <button
                type="button"
                className={`rounded px-2 py-0.5 text-[11px] ${scriptTab === "line" ? "bg-white/10 font-semibold text-white" : "text-white/45"}`}
                onClick={() => setScriptTab("line")}
              >{tr("ui_segment_workspace_line")}</button>
              <button
                type="button"
                className={`inline-flex items-center gap-1 rounded px-2 py-0.5 text-[11px] ${
                  scriptTab === "prompt" ? "bg-white/10 font-semibold text-white" : "text-white/45"
                }`}
                onClick={() => void openModelPromptTab()}
                title={tr("ui_segment_workspace_see_the_merged_prompt_this_segment")}
              >
                <FileText className="h-3 w-3" />{" "}{tr("ui_segment_workspace_prompt")}</button>
            </div>
          </div>

          <div className="border-b border-white/10 px-2.5 py-2">
            <div className="flex flex-wrap items-center gap-1.5 text-[11px]">
              <span className="rounded bg-black/60 px-1.5 py-0.5 font-medium text-white">{tr("ui_segment_workspace_segment", {
                  0: activeSeg?.segmentOrder ?? "—"
                })}</span>
              <span className="text-white/45">{tr("ui_segment_workspace_s_shots", {
                  0: activeSeg?.duration || 0,
                  1: activeSeg?.shots?.length || 0
                })}</span>
              {segGenerating ? (
                <span className="rounded-full bg-[#7c6cff]/20 px-2 py-0.5 text-[10px] font-medium text-[#c4b5fd]">{tr("ui_segment_workspace_generating")}</span>
              ) : segQaFail ? (
                <span
                  className="rounded-full bg-rose-500/15 px-2 py-0.5 text-[10px] font-medium text-rose-300"
                  title={activeSeg?.lead?.error || activeSeg?.video?.qa?.reason || tr("ui_segment_workspace_qa_not_passed")}
                >{tr("ui_segment_workspace_qa_failed")}</span>
              ) : segReady && segQaPass ? (
                <span className="rounded-full bg-emerald-500/15 px-2 py-0.5 text-[10px] font-medium text-emerald-300">{tr("ui_segment_workspace_done")}</span>
              ) : segReady ? (
                <span className="rounded-full bg-amber-500/15 px-2 py-0.5 text-[10px] font-medium text-amber-200">{tr("ui_segment_workspace_rendered_needs_review")}</span>
              ) : (
                <span className="rounded-full bg-white/10 px-2 py-0.5 text-[10px] text-white/45">{tr("ui_segment_workspace_not_rendered")}</span>
              )}
              {bundle?.project?.portraitMatchMode === "reshoot" ? (
                <span className="ml-auto rounded-full bg-sky-500/15 px-2 py-0.5 text-[10px] text-sky-100">{tr("ui_segment_workspace_reshoot_reference_not_generated")}</span>
              ) : (
                <button
                  type="button"
                  className="btn-primary ml-auto !min-h-7 !px-2.5 text-[11px]"
                  disabled={generating || segGenerating || splitting}
                  onClick={() => void generateSegment(pendingRegen ? { syncOnly: true } : {})}
                >
                  {generating || segGenerating ? <Loader2 className="h-3 w-3 animate-spin" /> : <Video className="h-3 w-3" />}
                  {pendingRegen ? tr("ui_segment_workspace_regenerate_segment") : segReady ? tr("ui_segment_workspace_generate_again") : tr("ui_segment_workspace_generate_segment")}
                </button>
              )}
            </div>
            {segEntityQaBlockers.length ? (
              <div className="mt-1.5 rounded-md border border-rose-500/35 bg-rose-500/10 px-2 py-1.5 text-[10px] leading-snug text-rose-100">
                <div className="font-medium">{tr("ui_segment_workspace_assets_in_this_segment_failed_qa", {
                    length: segEntityQaBlockers.length
                  })}</div>
                <ul className="mt-1 space-y-0.5 text-rose-100/80">
                  {segEntityQaBlockers.slice(0, 4).map((b) => (
                    <li key={b.entityId}>
                      {b.kindLabel}「{b.name}」· {b.reason}
                    </li>
                  ))}
                  {segEntityQaBlockers.length > 4 ? (
                    <li>{tr("ui_segment_workspace_and_more", {
                        0: segEntityQaBlockers.length - 4
                      })}</li>
                  ) : null}
                </ul>
                <p className="mt-1 text-rose-100/65">{tr("ui_segment_workspace_go_back_to_the_assets_step")}</p>
              </div>
            ) : null}
            {pendingRegen ? (
              <div className="mt-2 flex flex-wrap items-center justify-between gap-2 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-[11px] text-amber-100">
                <span>{tr("ui_segment_workspace_lines_or_visuals_changed_the_cut")}</span>
                <button
                  type="button"
                  className="btn-primary !min-h-7 !px-2.5 text-[10px]"
                  disabled={generating || segGenerating}
                  onClick={() => void generateSegment({ syncOnly: true })}
                >{tr("ui_segment_workspace_regenerate_this_segment")}</button>
              </div>
            ) : null}
            <div className="mt-1.5 grid gap-0.5 text-[11px] leading-snug text-white/50 sm:grid-cols-2">
              <div>
                <span className="text-white/30">{tr("ui_segment_workspace_location")}</span>
                {activeSeg?.lead?.location || activeSeg?.lead?.sceneName || "—"}
              </div>
              <div>
                <span className="text-white/30">{tr("ui_segment_workspace_time")}</span>
                {activeSeg?.lead?.timeOfDay || "—"}
              </div>
              <div>
                <span className="text-white/30">{tr("ui_segment_workspace_weather")}</span>
                {activeSeg?.lead?.weather || "—"}
              </div>
              <div className="sm:col-span-2 line-clamp-2">
                <span className="text-white/30">{tr("ui_segment_workspace_starting_state")}</span>
                {activeSeg?.lead?.openingState || "—"}
              </div>
            </div>
          </div>

          <div className="scrollbar-thin flex-1 space-y-2 overflow-y-auto p-2">
            {scriptTab === "prompt" ? (
              <div className="space-y-2 rounded-xl border border-white/10 bg-white/[.03] p-2.5 text-[11px] leading-snug">
                {modelPromptBusy ? (
                  <div className="flex items-center justify-center gap-2 py-16 text-white/50">
                    <Loader2 className="h-4 w-4 animate-spin" />{" "}{tr("ui_segment_workspace_loading_the_prompt_sent_to_the")}</div>
                ) : (
                  <>
                    <p className="text-[11px] leading-5 text-white/45">
                      {modelPromptData?.note ||
                        tr("ui_segment_workspace_below_is_the_merged_text_sent")}
                    </p>
                    <div>
                      <div className="mb-1 text-[11px] font-medium text-white/40">{tr("ui_segment_workspace_merged_video_prompt")}</div>
                      <pre className="whitespace-pre-wrap rounded-xl border border-white/10 bg-black/40 p-3 text-[12px] leading-5 text-white/85">
                        {modelPromptData?.videoPrompt || tr("ui_segment_workspace_none")}
                      </pre>
                    </div>
                    {(modelPromptData?.references || []).length ? (
                      <div>
                        <div className="mb-1 text-[11px] font-medium text-white/40">{tr("ui_segment_workspace_reference_assets", {
                            length: modelPromptData.references.length
                          })}</div>
                        <ul className="space-y-1.5 rounded-xl border border-white/10 bg-white/[.03] p-3 text-[12px] text-white/75">
                          {modelPromptData.references.map((r) => (
                            <li key={r.id}>
                              <span className="text-white/40">[{r.kind}]</span> {r.name}
                              {r.variant ? ` / ${r.variant}` : ""}
                              {r.hasImage ? "" : ` ${tr("ui_segment_workspace_no_image_2")}`}
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
                        <div className="mb-1 text-[11px] font-medium text-white/40">{tr("ui_segment_workspace_storyboard_source_lines")}</div>
                        <div className="space-y-2">
                          {modelPromptData.shots.map((s) => (
                            <div key={s.shotId} className="rounded-xl border border-white/10 bg-black/30 p-3">
                              <div className="mb-1 text-[10px] font-semibold text-white/50">{tr("ui_segment_workspace_shot_2", {
                                  beatIndex: s.beatIndex
                                })}</div>
                              <pre className="whitespace-pre-wrap text-[12px] leading-5 text-white/80">
                                {s.prompt || tr("ui_segment_workspace_no_shot_words")}
                              </pre>
                              {s.dialogue ? (
                                <p className="mt-2 border-t border-white/10 pt-2 text-[12px] text-[#c4b5fd]">{tr("ui_segment_workspace_line_2", {
                                    dialogue: s.dialogue
                                  })}</p>
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
                <article key={shot.id} className="rounded-lg border border-white/10 bg-white/[.03] p-2.5">
                  <div className="mb-1 flex flex-wrap items-center gap-1.5">
                    <span className="rounded bg-black/55 px-1.5 py-0.5 text-[10px] font-semibold text-white">{tr("ui_segment_workspace_shot_s", {
                        0: shot.beatIndex || shot.shotOrder,
                        1: shot.duration || 3
                      })}</span>
                    {dlg?.speaker ? (
                      <button
                        type="button"
                        className="inline-flex items-center gap-1 rounded-full border border-white/10 px-2 py-0.5 text-[10px] text-white/60 hover:border-[#7c6cff]/50 hover:text-[#c4b5fd]"
                        onClick={() => {
                          const ent = entityByName.get(dlg.speaker);
                          if (ent) openEntity(ent);
                        }}
                        title={tr("ui_segment_workspace_view_2", {
                          speaker: dlg.speaker
                        })}
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
                      >{tr("ui_segment_workspace_prompt_mismatch")}</span>
                    ) : null}
                    <button
                      type="button"
                      className="ml-auto text-[10px] text-[#a78bfa] hover:underline"
                      onClick={() => startEditDialogue(shot)}
                    >{tr("ui_segment_workspace_edit_line")}</button>
                  </div>
                  {scriptTab === "lens" ? (
                    <>
                      {bundle?.project?.workflow === "portrait-match" ? (
                        <div className="mb-2 flex flex-wrap gap-1.5 text-[10px]">
                          <span className="rounded bg-white/8 px-1.5 py-0.5 text-white/70">{tr("ui_segment_workspace_action", {
                              0: shot.actionZh || shot.action || "—"
                            })}</span>
                          <span className="rounded bg-white/8 px-1.5 py-0.5 text-white/70">{tr("ui_segment_workspace_camera")}{" "}{shot.camera || tr("ui_segment_workspace_lock_slight_follow")}
                          </span>
                          <span className="rounded bg-white/8 px-1.5 py-0.5 text-white/70">{tr("ui_segment_workspace_transition")}{" "}{shot.transition || tr("ui_segment_workspace_hard_cut_on_beat")}
                          </span>
                        </div>
                      ) : null}
                      <div className="mb-1 text-[10px] font-medium uppercase tracking-wide text-white/35">{tr("ui_segment_workspace_shot_prompt")}</div>
                      <PromptWithChips
                        prompt={shot.prompt || shot.action || tr("ui_segment_workspace_no_shot_prompt")}
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
                      <div className="mb-1 text-[10px] font-medium uppercase tracking-wide text-white/35">{tr("ui_segment_workspace_line")}</div>
                      <DialogueCard
                        dialogue={shot.dialogue || tr("ui_segment_workspace_no_lines_in_this_shot")}
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
                        placeholder={tr("ui_segment_workspace_character_line")}
                      />
                      <div className="flex flex-wrap gap-2">
                        <button
                          type="button"
                          className="btn-secondary !min-h-8 text-xs"
                          disabled={savingLine || generating}
                          onClick={() => void saveDialogue(shot.id)}
                        >
                          {savingLine ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />}{tr("ui_segment_workspace_save_only")}</button>
                        <button
                          type="button"
                          className="btn-primary !min-h-8 text-xs"
                          disabled={savingLine || generating || segGenerating}
                          onClick={() => void saveDialogue(shot.id, { regenerate: true })}
                        >
                          {savingLine || generating ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Video className="h-3.5 w-3.5" />}{tr("ui_segment_workspace_save_and_regenerate_segment")}</button>
                        <button type="button" className="btn-quiet !min-h-8 text-xs" onClick={() => setEditingShotId("")}>{tr("ui_segment_workspace_cancel")}</button>
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
                            title={tr("ui_segment_workspace_view", {
                              name: ent.name
                            })}
                          >
                            {entityThumb(ent) ? <img src={entityThumb(ent)} alt="" className="h-4 w-4 rounded object-cover" /> : null}
                            {ent.name}
                            <span className="text-white/30">{ent.kind === "character" ? tr("ui_segment_workspace_c") : ent.kind === "prop" ? tr("ui_segment_workspace_p") : tr("ui_segment_workspace_s")}</span>
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
        <aside className="scrollbar-thin order-2 min-h-0 space-y-2 overflow-y-auto xl:order-3 xl:h-full">
          <div ref={monitorRef} className="overflow-hidden rounded-xl bg-[#08090d] p-2 text-white">
            <div className="mb-1 flex items-center justify-between text-[10px] text-white/45">
              <span>{tr("ui_segment_workspace_segment_2", {
                  0: activeSeg?.segmentOrder ?? "—",
                  length: segments.length
                })}</span>
              <span>
                {activeSeg?.duration || 0}s · {ratio}
              </span>
            </div>
            {/* Height-led portrait (or width-led landscape): never pair aspect-ratio with a conflicting max-h on the same box. */}
            <div className="flex justify-center bg-black/40">
              <div
                className={`relative overflow-hidden rounded-lg bg-black ${
                  ratio === "9:16"
                    ? "aspect-[9/16] h-[min(42vh,300px)] w-auto max-w-full"
                    : "aspect-video w-full max-w-full"
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
                    className="absolute inset-0 h-full w-full object-contain"
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
                <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 px-4 text-center">
                  <Film className="h-10 w-10 text-white/15" />
                  <p className="text-xs text-white/40">{tr("ui_segment_workspace_this_segment_hasn_t_been_rendered")}</p>
                  <button
                    type="button"
                    className="btn-primary !min-h-8 text-xs"
                    disabled={generating || segGenerating}
                    onClick={() => void generateSegment(pendingRegen ? { syncOnly: true } : {})}
                  >
                    {generating || segGenerating ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Video className="h-3.5 w-3.5" />}
                    {pendingRegen ? tr("ui_segment_workspace_regenerate_segment") : tr("ui_segment_workspace_generate_segment")}
                  </button>
                </div>
              )}
              </div>
            </div>
            {bgm?.url ? <audio ref={bgmRef} src={bgm.url} loop preload="metadata" /> : null}
            <div className="mt-2 flex flex-wrap items-center justify-center gap-1">
              <button type="button" className="btn-quiet !min-h-7 !px-2 text-white/80" onClick={() => goSeg(-1)}>
                <ChevronLeft className="h-3.5 w-3.5" />
              </button>
              <button type="button" className="btn-primary !min-h-7 !rounded-full !px-3 text-[11px]" disabled={!segReady} onClick={togglePlay}>
                {playing ? <Pause className="h-3.5 w-3.5" /> : <Play className="h-3.5 w-3.5" />}
                {playing ? tr("ui_segment_workspace_pause") : tr("ui_segment_workspace_play")}
              </button>
              <button type="button" className="btn-quiet !min-h-7 !px-2 text-white/80" onClick={() => goSeg(1)}>
                <ChevronRight className="h-3.5 w-3.5" />
              </button>
              <button type="button" className="btn-quiet !min-h-7 !px-2 text-white/80" onClick={() => setMuted((m) => !m)}>
                {muted ? <VolumeX className="h-3.5 w-3.5" /> : <Volume2 className="h-3.5 w-3.5" />}
              </button>
              <button
                type="button"
                className="btn-quiet !min-h-7 !px-2 text-white/80"
                onClick={() => {
                  const node = monitorRef.current;
                  if (!node) return;
                  if (document.fullscreenElement) void document.exitFullscreen();
                  else void node.requestFullscreen?.();
                }}
              >
                <Maximize2 className="h-3.5 w-3.5" />
              </button>
            </div>
            <div className="mt-1.5 flex flex-wrap items-center justify-center gap-3 text-[10px] text-white/55">
              <label className="flex items-center gap-1.5">
                <input type="checkbox" checked={continuous} onChange={(e) => setContinuous(e.target.checked)} />{tr("ui_segment_workspace_continuous_play")}</label>
              <label className={`flex items-center gap-1.5 ${bgm?.url ? "" : "opacity-40"}`}>
                <input type="checkbox" checked={bgmOn && !!bgm?.url} disabled={!bgm?.url} onChange={(e) => setBgmOn(e.target.checked)} />{tr("ui_segment_workspace_score")}</label>
            </div>
          </div>

          {/* Segment tools: 改台词 / 剪一刀 */}
          <div className="rounded-xl border border-white/10 bg-[#0c0e14] p-3">
            <div className="mb-2 flex flex-wrap gap-1.5">
              {[
                { id: "visual", label: tr("ui_segment_workspace_ai_repaint") },
                { id: "line", label: tr("ui_segment_workspace_edit_line") },
                { id: "trim", label: tr("ui_segment_workspace_trim") },
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
                <p className="text-[11px] leading-4 text-white/45">{tr("ui_segment_workspace_describe_the_visual_change_in_plain")}</p>
                <textarea
                  className="field min-h-24 resize-y text-sm"
                  value={visualNote}
                  onChange={(e) => setVisualNote(e.target.value)}
                  placeholder={tr("ui_segment_workspace_e_g_heavier_rain_cooler_cyan")}
                />
                <div className="flex flex-wrap gap-1.5">
                  {[tr("ui_segment_workspace_heavier_rain_colder_neon"), tr("ui_segment_workspace_more_urgent_action"), tr("ui_segment_workspace_warmer_softer_light"), tr("ui_segment_workspace_more_restrained_expression")].map((hint) => (
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
                  {generating || segGenerating ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />}{tr("ui_segment_workspace_apply_and_regenerate_segment")}</button>
              </div>
            ) : editMode === "line" ? (
              <>
                <div className="mb-2 text-[11px] font-medium text-white/45">{tr("ui_segment_workspace_segment_lines", {
                    length: segmentDialogues.length
                  })}</div>
                {segmentDialogues.length ? (
                  <ul className="max-h-44 space-y-2 overflow-y-auto text-xs leading-5">
                    {segmentDialogues.map(({ shot, parsed }) => (
                      <li key={shot.id} className="rounded-lg border border-white/5 bg-black/20 px-2.5 py-2">
                        <div className="flex items-start justify-between gap-2">
                          <div className="min-w-0">
                            <span className="font-semibold text-white/80">{parsed.speaker || tr("ui_segment_workspace_narrator")}</span>
                            <span className="text-white/50"> · </span>
                            <span className="text-white/70">{parsed.line}</span>
                          </div>
                          <button
                            type="button"
                            className="shrink-0 text-[10px] text-[#a78bfa] hover:underline"
                            onClick={() => startEditDialogue(shot)}
                          >{tr("ui_segment_workspace_edit")}</button>
                        </div>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-[11px] text-white/35">{tr("ui_segment_workspace_no_dialogue_in_this_segment_add")}</p>
                )}
              </>
            ) : (
              <div className="space-y-2 text-xs">
                {!segReady ? (
                  <p className="py-4 text-center text-white/35">{tr("ui_segment_workspace_generate_this_segment_s_video_first")}</p>
                ) : (
                  <>
                    <label className="block">
                      <span className="mb-1 flex justify-between text-white/45">
                        <span>{tr("ui_segment_workspace_in")}</span>
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
                        <span>{tr("ui_segment_workspace_out")}</span>
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
                      <button type="button" className="btn-quiet !min-h-8 text-xs" onClick={() => setTrimStart((v) => Math.max(0, v - 0.5))}>{tr("ui_segment_workspace_in_0_5s")}</button>
                      <button type="button" className="btn-quiet !min-h-8 text-xs" onClick={() => setTrimStart((v) => Math.min(v + 0.5, trimEnd - 0.1))}>{tr("ui_segment_workspace_in_0_5s_2")}</button>
                      <button type="button" className="btn-quiet !min-h-8 text-xs" onClick={() => setTrimEnd((v) => Math.max(trimStart + 0.1, v - 0.5))}>{tr("ui_segment_workspace_out_0_5s")}</button>
                      <button type="button" className="btn-quiet !min-h-8 text-xs" onClick={() => setTrimEnd((v) => Math.min(mediaMax, v + 0.5))}>{tr("ui_segment_workspace_out_0_5s_2")}</button>
                    </div>
                    <button type="button" className="btn-secondary w-full !min-h-9 text-xs" onClick={previewTrim}>{tr("ui_segment_workspace_preview_the_kept_part")}</button>
                    <button
                      type="button"
                      className="btn-primary w-full !min-h-9 text-xs"
                      disabled={savingTrim}
                      onClick={() => void saveTrim()}
                    >
                      {savingTrim ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />}{tr("ui_segment_workspace_save_trim")}</button>
                  </>
                )}
              </div>
            )}
          </div>
        </aside>
      </div>

      {/* Bottom filmstrip — short landscape thumbs (full frame via contain, no tall empty pillars) */}
      <div className="z-20 shrink-0 rounded-xl border border-white/10 bg-[#0c0e14] px-2.5 py-2 shadow-[0_-8px_24px_rgba(0,0,0,.35)]">
        <div className="mb-1.5 flex items-center justify-between text-[10px] text-white/45">
          <span>{tr("ui_segment_workspace_episode_timeline_segments_s", {
              length: segments.length,
              1: Math.round(totalDur)
            })}</span>
          <span>{hasSegmentLayout ? tr("ui_segment_workspace_render_by_segment") : tr("ui_segment_workspace_migrating")}</span>
        </div>
        <div className="scrollbar-thin flex gap-1.5 overflow-x-auto pb-0.5">
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
                className={`w-[88px] shrink-0 overflow-hidden rounded-md border text-left transition sm:w-[100px] ${
                  active ? "border-[#7c6cff] ring-1 ring-[#7c6cff]/50" : "border-white/10 hover:border-white/25"
                }`}
              >
                <div className="relative aspect-video overflow-hidden bg-black">
                  {ready ? (
                    <video
                      src={seg.video.url}
                      muted
                      preload="metadata"
                      className="absolute inset-0 h-full w-full object-cover object-center"
                    />
                  ) : (
                    <div className="absolute inset-0 flex items-center justify-center text-[9px] text-white/30">
                      {seg.shots.some((s) => s.status === "generating") ? tr("ui_segment_workspace_generating") : tr("ui_segment_workspace_not_rendered")}
                    </div>
                  )}
                  <span className="absolute left-1 top-1 rounded bg-black/70 px-1 py-0.5 text-[9px] font-semibold text-white">
                    {seg.segmentOrder}
                  </span>
                </div>
                <div className="px-1 py-0.5 text-[9px] text-white/55">{tr("ui_segment_workspace_s_shots_2", {
                    duration: seg.duration,
                    length: seg.shots.length
                  })}</div>
              </button>
            );
          })}
        </div>
      </div>

      <ConfirmDialog
        open={confirmSplit}
        title={tr("ui_segment_workspace_re_split_this_episode")}
        message={tr("ui_segment_workspace_existing_shots_and_video_version_history_2")}
        confirmLabel={tr("ui_segment_workspace_re_split")}
        onCancel={() => setConfirmSplit(false)}
        onConfirm={() => void split()}
      />

      <ConfirmDialog
        open={Boolean(forceQaDialog)}
        title={tr("ui_segment_workspace_assets_failed_qa_rendering_blocked")}
        message={
          forceQaDialog
            ? tr("ui_segment_workspace_regenerate_review_the_assets_above_first", {
            0: formatEntityQaBlockers(forceQaDialog.blockers)
          })
            : ""
        }
        confirmLabel={tr("ui_segment_workspace_force_render")}
        cancelLabel={tr("ui_segment_workspace_fix_assets_first")}
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

      {previewFinalOpen && editOutputUrl ? (
        <ModalOverlay
          onClose={() => setPreviewFinalOpen(false)}
          className="bg-black/80"
          zClass="z-[200]"
          role="dialog"
        >
          <div
            className="relative my-auto w-fit max-w-[min(92vw,420px)]"
            onMouseDown={(e) => e.stopPropagation()}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mb-2 flex items-center justify-between gap-2 px-0.5">
              <p className="text-sm font-medium text-white/90">{tr("ui_segment_workspace_cut_preview")}</p>
              <button
                type="button"
                className="rounded-full bg-white/10 p-1.5 text-white hover:bg-white/20"
                aria-label={tr("ui_segment_workspace_close")}
                onClick={() => setPreviewFinalOpen(false)}
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <video
              key={editOutputUrl}
              src={editOutputUrl}
              controls
              autoPlay
              playsInline
              className="block max-h-[min(78dvh,78vh)] w-auto max-w-full rounded-xl bg-black shadow-2xl"
              style={{ aspectRatio: "9 / 16" }}
            />
          </div>
        </ModalOverlay>
      ) : null}
    </div>
  );
}
