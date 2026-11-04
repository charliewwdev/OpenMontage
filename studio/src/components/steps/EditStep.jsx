import { useEffect, useEffectEvent, useMemo, useRef, useState } from "react";
import {
  ChevronLeft,
  ChevronRight,
  Download,
  Expand,
  Film,
  Loader2,
  Maximize2,
  Pause,
  Play,
  Save,
  Scissors,
  Volume2,
  VolumeX,
  X,
} from "lucide-react";
import { api } from "../../api";
import { toast } from "../../lib/toast";
import { ModalOverlay } from "../ModalPortal";

import { tr, useLocale } from "../../lib/i18n";

function clipId() {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random()}`;
}

function fullClip(shot) {
  return {
    id: clipId(),
    shotId: shot.id,
    enabled: true,
    start: 0,
    end: shot.selectedVideo?.duration || shot.duration || 5,
  };
}

function clipDuration(clip) {
  return Math.max(0.1, Number(clip.end || 0) - Number(clip.start || 0));
}

function parseRefNames(prompt = "") {
  return [...String(prompt).matchAll(/@([^\s@,，。；;（）()]+)/g)].map((m) => m[1].split("-")[0]);
}

function parseDialogue(raw = "") {
  const text = String(raw || "").trim();
  if (!text) return null;
  const m = text.match(/^([^：:\n]{1,24})\s*[：:]\s*(.+)$/s);
  if (m) return { speaker: m[1].trim(), line: m[2].trim() };
  return { speaker: "", line: text };
}

function originalBeat(content = "", shotOrder) {
  const src = String(content || "");
  if (!src) return "";
  const n = Number(shotOrder) || 0;
  const re = new RegExp(`\\[${n}\\]([\\s\\S]*?)(?=\\[\\d+\\]|$)`);
  const m = src.match(re);
  if (m) return m[0].trim();
  const lines = src.split(/\n+/).filter(Boolean);
  return lines[n - 1] || src.slice(0, 280);
}

function inferTimeOfDay(shot) {
  const blob = `${shot?.prompt || ""} ${shot?.action || ""} ${shot?.sceneName || ""}`;
  if (/夜|深夜|夜晚|霓虹|月光/.test(blob)) return tr("ui_edit_night");
  if (/黄昏|夕阳|傍晚/.test(blob)) return tr("ui_edit_dusk");
  if (/清晨|黎明|破晓/.test(blob)) return tr("ui_edit_dawn");
  if (/白天|午后|晴/.test(blob)) return tr("ui_edit_day");
  return "—";
}

function PromptWithChips({ prompt, entityByName, activeNames }) {
  useLocale();
  const parts = String(prompt || "").split(/(@[^\s@,，。；;（）()]+)/g);
  return (
    <p className="text-[13px] leading-6 text-[var(--ink)]/90">
      {parts.map((part, i) => {
        if (!part.startsWith("@")) return <span key={i}>{part}</span>;
        const name = part.slice(1).split("-")[0];
        const ent = entityByName.get(name);
        const on = activeNames.has(name) || [...activeNames].some((n) => name.includes(n) || n.includes(name));
        return (
          <span
            key={i}
            className={`mx-0.5 inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 align-middle text-[12px] font-medium ${
              on ? "bg-[var(--projector)]/20 text-[var(--projector)]" : "bg-black/5 text-[var(--ink)]"
            }`}
            title={ent?.kind || "asset"}
          >
            {ent?.selectedImage?.url ? (
              <img src={ent.selectedImage.url} alt="" className="h-4 w-4 rounded object-cover" />
            ) : null}
            {name}
          </span>
        );
      })}
    </p>
  );
}

function DialogueCard({ dialogue, entityByName }) {
  useLocale();
  const parsed = parseDialogue(dialogue);
  if (!parsed?.line) return null;
  const ent = parsed.speaker ? entityByName.get(parsed.speaker) : null;
  return (
    <div className="mt-3 flex gap-2.5 rounded-xl border border-[var(--line)] bg-white/[.04] p-3">
      <div className="h-10 w-10 shrink-0 overflow-hidden rounded-lg bg-black/30">
        {ent?.selectedImage?.url ? (
          <img
            src={ent.selectedImage.url}
            alt=""
            className="h-full w-full object-contain object-center bg-black/40"
          />
        ) : (
          <div className="flex h-full items-center justify-center text-[10px] text-[var(--muted)]">
            {(parsed.speaker || "?").slice(0, 1)}
          </div>
        )}
      </div>
      <div className="min-w-0 flex-1">
        <div className="mb-1 flex items-center gap-2 text-[11px] text-[var(--muted)]">
          <span className="font-semibold text-[var(--ink)]">{parsed.speaker || tr("ui_edit_dialogue")}</span>
          <span>{tr("ui_edit_line")}</span>
        </div>
        <p className="text-sm font-medium leading-6 text-[var(--ink)]">「{parsed.line.replace(/^「|」$/g, "")}」</p>
      </div>
    </div>
  );
}

export function EditStep({ projectId, bundle, setBusyMsg, onBundle, onRefresh, focusEpisodeId, onFocusEpisode }) {
  useLocale();
  const episodes = useMemo(
    () => [...(bundle?.episodes || [])].sort((a, b) => a.episodeNumber - b.episodeNumber),
    [bundle?.episodes],
  );
  const [episodeId, setEpisodeId] = useState(focusEpisodeId || episodes[0]?.id || "");
  const [clips, setClips] = useState([]);
  const [selectedClipId, setSelectedClipId] = useState(null);
  const [saving, setSaving] = useState(false);
  const [rendering, setRendering] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [continuous, setContinuous] = useState(true);
  const [muted, setMuted] = useState(false);
  const [bgmOn, setBgmOn] = useState(true);
  const [localTime, setLocalTime] = useState(0);
  const [scriptTab, setScriptTab] = useState("lens"); // lens | original
  const [editMode, setEditMode] = useState("trim"); // trim | visual | line
  const [draftStart, setDraftStart] = useState(0);
  const [draftEnd, setDraftEnd] = useState(5);
  const [previewFinalOpen, setPreviewFinalOpen] = useState(false);
  const videoRef = useRef(null);
  const bgmRef = useRef(null);
  const shotListRef = useRef(null);
  const filmstripRef = useRef(null);
  const advancingRef = useRef(false);
  const pendingSeekRef = useRef(null);
  const monitorRef = useRef(null);

  const episode = episodes.find((item) => item.id === episodeId);
  const readyShots = useMemo(
    () =>
      (bundle?.shots || [])
        .filter((shot) => shot.episodeId === episodeId && !shot.deletedAt && shot.selectedVideo?.url)
        .sort((a, b) => a.shotOrder - b.shotOrder),
    [bundle?.shots, episodeId],
  );
  const draft = (bundle?.edits || []).find((edit) => edit.episodeId === episodeId);
  const bgm = (bundle?.audios || []).find((a) => a.episodeId === episodeId && a.kind === "bgm" && a.url);

  const enabledClips = useMemo(() => clips.filter((c) => c.enabled !== false), [clips]);
  const timeline = useMemo(() => {
    let cursor = 0;
    return enabledClips.map((clip) => {
      const dur = clipDuration(clip);
      const item = { clip, start: cursor, end: cursor + dur, duration: dur };
      cursor += dur;
      return item;
    });
  }, [enabledClips]);
  const totalDuration = timeline.length ? timeline[timeline.length - 1].end : 0;

  const selectedClip = clips.find((clip) => clip.id === selectedClipId) || enabledClips[0] || clips[0] || null;
  const selectedShot = selectedClip
    ? readyShots.find((shot) => shot.id === selectedClip.shotId) || null
    : null;
  const selectedTl = timeline.find((t) => t.clip.id === selectedClip?.id);
  const selectedIndex = enabledClips.findIndex((c) => c.id === selectedClip?.id);
  const globalTime = (selectedTl?.start || 0) + localTime;
  const ratio = bundle?.project?.ratio || "9:16";
  const mediaMax =
    selectedShot?.selectedVideo?.duration || selectedShot?.duration || Number(selectedClip?.end || 5);

  const episodeEntities = useMemo(() => {
    const epNum = episode?.episodeNumber;
    return (bundle?.entities || []).filter(
      (e) => !e.deletedAt && (!e.episodes?.length || (epNum != null && e.episodes.includes(epNum))),
    );
  }, [bundle?.entities, episode?.episodeNumber]);

  const entityByName = useMemo(() => {
    const map = new Map();
    for (const e of episodeEntities) map.set(e.name, e);
    return map;
  }, [episodeEntities]);

  const activeRefNames = useMemo(() => {
    const names = new Set(parseRefNames(selectedShot?.prompt || ""));
    for (const c of selectedShot?.characters || []) names.add(String(c));
    if (selectedShot?.sceneName) names.add(String(selectedShot.sceneName));
    const dlg = parseDialogue(selectedShot?.dialogue || "");
    if (dlg?.speaker) names.add(dlg.speaker);
    return names;
  }, [selectedShot]);

  useEffect(() => {
    if (focusEpisodeId && episodes.some((item) => item.id === focusEpisodeId) && focusEpisodeId !== episodeId) {
      setEpisodeId(focusEpisodeId);
    }
  }, [focusEpisodeId, episodes, episodeId]);

  useEffect(() => {
    if (episodeId && !episodes.some((item) => item.id === episodeId)) {
      setEpisodeId(episodes[0]?.id || "");
    }
  }, [episodes, episodeId]);

  useEffect(() => {
    const existing = (bundle?.edits || []).find((edit) => edit.episodeId === episodeId);
    const next = existing?.clips?.length ? existing.clips : readyShots.map(fullClip);
    setClips(next);
    setSelectedClipId(next.find((c) => c.enabled !== false)?.id || next[0]?.id || null);
    setPlaying(false);
    setLocalTime(0);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [episodeId]);

  useEffect(() => {
    if (!selectedClip) return;
    setDraftStart(Number(selectedClip.start || 0));
    setDraftEnd(Number(selectedClip.end || mediaMax));
  }, [selectedClip?.id, selectedClip?.start, selectedClip?.end, mediaMax]);

  const onClipEnded = useEffectEvent(() => {
    if (advancingRef.current) return;
    advancingRef.current = true;
    window.setTimeout(() => {
      advancingRef.current = false;
    }, 250);
    if (!continuous || !playing) {
      setPlaying(false);
      return;
    }
    const idx = enabledClips.findIndex((c) => c.id === selectedClip?.id);
    const next = enabledClips[idx + 1];
    if (next) {
      setSelectedClipId(next.id);
      setLocalTime(0);
    } else {
      setPlaying(false);
    }
  });

  useEffect(() => {
    const el = videoRef.current;
    if (!el || !selectedShot?.selectedVideo?.url) return;
    const start = Number(selectedClip?.start || 0);
    const pending = pendingSeekRef.current;
    pendingSeekRef.current = null;
    const offset = pending?.clipId === selectedClip?.id ? pending.local : 0;
    el.currentTime = start + offset;
    setLocalTime(offset);
    if (playing) {
      void el.play().catch(() => setPlaying(false));
    } else {
      el.pause();
    }
  }, [selectedClip?.id, selectedShot?.selectedVideo?.url, selectedClip?.start, playing]);

  useEffect(() => {
    const bgmEl = bgmRef.current;
    if (!bgmEl || !bgm?.url) return;
    bgmEl.volume = 0.18;
    if (playing && bgmOn && !muted) {
      void bgmEl.play().catch(() => {});
    } else {
      bgmEl.pause();
    }
  }, [playing, bgmOn, muted, bgm?.url, selectedClip?.id]);

  useEffect(() => {
    const node = shotListRef.current?.querySelector(`[data-clip-id="${selectedClipId}"]`);
    node?.scrollIntoView({ block: "nearest", behavior: "smooth" });
    const thumb = filmstripRef.current?.querySelector(`[data-clip-id="${selectedClipId}"]`);
    thumb?.scrollIntoView({ inline: "center", block: "nearest", behavior: "smooth" });
  }, [selectedClipId]);

  useEffect(() => {
    const onKey = (e) => {
      if (e.target?.closest?.("input, textarea, select, [contenteditable]")) return;
      if (e.key === "ArrowUp" || e.key === "ArrowLeft") {
        e.preventDefault();
        jumpClip(-1);
      } else if (e.key === "ArrowDown" || e.key === "ArrowRight") {
        e.preventDefault();
        jumpClip(1);
      } else if (e.key === " ") {
        e.preventDefault();
        togglePlay();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedClip?.id, enabledClips, playing]);

  const apply = (res) => {
    if (res?.bundle) onBundle?.(res.bundle);
    else onRefresh?.();
  };

  const updateClip = (id, fields) => {
    setClips((current) => current.map((clip) => (clip.id === id ? { ...clip, ...fields } : clip)));
  };

  const save = async (quiet = false) => {
    if (!episode) return null;
    setSaving(true);
    setBusyMsg?.(quiet ? "" : tr("ui_edit_saving_edit_draft"));
    try {
      const res = await api(`/api/projects/${encodeURIComponent(projectId)}/edits`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "save", episodeId: episode.id, clips }),
      });
      apply(res);
      if (!quiet) toast.success(tr("ui_edit_edit_draft_saved"));
      return res.edit;
    } catch (error) {
      toast.error(String(error.message || error));
      return null;
    } finally {
      setSaving(false);
      setBusyMsg?.("");
    }
  };

  const render = async () => {
    if (!episode || !clips.some((clip) => clip.enabled !== false)) {
      return toast.error(tr("ui_edit_enable_at_least_one_segment"));
    }
    setRendering(true);
    setBusyMsg?.(tr("ui_edit_exporting_with_ffmpeg"));
    try {
      await save(true);
      const res = await api(`/api/projects/${encodeURIComponent(projectId)}/edits`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "export", episodeId: episode.id }),
      });
      apply(res);
      toast.success(tr("ui_edit_episode_cut_exported"));
    } catch (error) {
      toast.error(String(error.message || error));
    } finally {
      setRendering(false);
      setBusyMsg?.("");
    }
  };

  const resetFromShots = () => {
    const next = readyShots.map(fullClip);
    setClips(next);
    setSelectedClipId(next[0]?.id || null);
    setPlaying(false);
  };

  const seekGlobal = (t) => {
    const target = Math.max(0, Math.min(totalDuration, t));
    const hit = timeline.find((item) => target >= item.start && target < item.end) || timeline[timeline.length - 1];
    if (!hit) return;
    const local = Math.max(0, target - hit.start);
    pendingSeekRef.current = { clipId: hit.clip.id, local };
    setLocalTime(local);
    if (hit.clip.id === selectedClip?.id) {
      const el = videoRef.current;
      if (el) el.currentTime = Number(hit.clip.start || 0) + local;
      pendingSeekRef.current = null;
    } else {
      setSelectedClipId(hit.clip.id);
    }
  };

  const jumpClip = (delta) => {
    const idx = enabledClips.findIndex((c) => c.id === selectedClip?.id);
    const next = enabledClips[idx + delta];
    if (!next) return;
    setSelectedClipId(next.id);
    setLocalTime(0);
  };

  const selectClip = (id, { play = false } = {}) => {
    setSelectedClipId(id);
    setLocalTime(0);
    if (!play) setPlaying(false);
  };

  const togglePlay = () => {
    if (!selectedShot?.selectedVideo?.url) return;
    setPlaying((p) => !p);
  };

  const applyTrim = (mode = "keep") => {
    if (!selectedClip) return;
    const max = Math.max(0.2, Number(mediaMax) || 5);
    let start = Math.max(0, Math.min(draftStart, max - 0.1));
    let end = Math.max(start + 0.1, Math.min(draftEnd, max));
    if (mode === "drop") {
      // invert selection: keep outside range as one contiguous prefers start-side for simplicity
      if (start <= 0.05) {
        start = end;
        end = max;
      } else {
        end = start;
        start = 0;
      }
    }
    updateClip(selectedClip.id, { start, end, enabled: true });
    setDraftStart(start);
    setDraftEnd(end);
    toast.success(mode === "drop" ? tr("ui_edit_in_out_points_updated_from_the") : tr("ui_edit_trim_range_saved"));
  };

  const nudge = (which, delta) => {
    const max = Math.max(0.2, Number(mediaMax) || 5);
    if (which === "start") {
      setDraftStart((v) => Math.max(0, Math.min(v + delta, draftEnd - 0.1)));
    } else {
      setDraftEnd((v) => Math.max(draftStart + 0.1, Math.min(v + delta, max)));
    }
  };

  const previewTrim = () => {
    if (!selectedClip) return;
    pendingSeekRef.current = { clipId: selectedClip.id, local: 0 };
    updateClip(selectedClip.id, { start: draftStart, end: draftEnd });
    setPlaying(true);
  };

  const toggleFullscreen = () => {
    const node = monitorRef.current;
    if (!node) return;
    if (document.fullscreenElement) void document.exitFullscreen();
    else void node.requestFullscreen?.();
  };

  const characters = episodeEntities.filter((e) => e.kind === "character");
  const scenes = episodeEntities.filter((e) => e.kind === "scene");
  const props = episodeEntities.filter((e) => e.kind === "prop");

  return (
    <div className="mx-auto max-w-[1680px] space-y-3">
      <section className="panel flex flex-col gap-3 p-4 md:flex-row md:items-center md:justify-between md:p-4">
        <div className="min-w-0">
          <div className="label">Episode desk</div>
          <h3 className="display-type truncate text-xl font-semibold md:text-2xl">{tr("ui_edit_ep", {
              0: episode?.episodeNumber || "—"
            })}{" "}{episode?.title || tr("ui_edit_cut_editor")}
          </h3>
          <p className="mt-0.5 text-xs text-[var(--muted)]">{tr("ui_edit_segments_assets_script_timeline_trim_area", {
              length: enabledClips.length,
              length2: clips.length
            })}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button type="button" className="btn-secondary" disabled={saving || !episode} onClick={() => void save()}>
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}{" "}{tr("ui_edit_save")}</button>
          {draft?.outputUrl ? (
            <button type="button" className="btn-secondary" title={tr("ui_edit_preview_cut_in_a_popup")} onClick={() => setPreviewFinalOpen(true)}>
              <Film className="h-4 w-4" />{" "}{tr("ui_edit_view_cut")}</button>
          ) : null}
          <button
            type="button"
            className="btn-primary"
            disabled={rendering || !enabledClips.length}
            onClick={() => void render()}
          >
            {rendering ? <Loader2 className="h-4 w-4 animate-spin" /> : <Film className="h-4 w-4" />}
            {rendering ? tr("ui_edit_exporting") : tr("ui_edit_export_cut")}
          </button>
        </div>
      </section>

      {!episode ? (
        <div className="panel py-24 text-center text-sm text-[var(--muted)]">{tr("ui_edit_select_an_episode_on_the_left")}</div>
      ) : readyShots.length === 0 ? (
        <div className="panel flex flex-col items-center border-dashed py-24 text-center">
          <Scissors className="mb-4 h-10 w-10 text-[var(--projector)]" />
          <strong>{tr("ui_edit_no_playable_video_in_this_episode")}</strong>
          <p className="mt-2 text-sm text-[var(--muted)]">{tr("ui_edit_generate_and_pick_videos_in_the")}</p>
        </div>
      ) : (
        <>
          <div className="grid gap-3 xl:grid-cols-[220px_minmax(0,1fr)_minmax(340px,400px)]">
            {/* ── Asset library ── */}
            <aside className="panel max-h-[min(78vh,860px)] overflow-y-auto p-3">
              <div className="mb-3 flex items-center justify-between">
                <h4 className="text-sm font-semibold">{tr("ui_edit_asset_library")}</h4>
                <span className="text-[10px] text-[var(--muted)]">{tr("ui_edit_highlights_during_playback")}</span>
              </div>
              {[
                { kind: "character", label: tr("ui_edit_characters"), list: characters },
                { kind: "scene", label: tr("ui_edit_scenes"), list: scenes },
                { kind: "prop", label: tr("ui_edit_items"), list: props },
              ].map((block) =>
                block.list.length ? (
                  <div key={block.kind} className="mb-4">
                    <div className="mb-2 text-[11px] font-medium text-[var(--muted)]">{block.label}</div>
                    <div className={`grid gap-2 ${block.kind === "character" ? "grid-cols-2" : "grid-cols-2"}`}>
                      {block.list.map((ent) => {
                        const active = [...activeRefNames].some(
                          (n) => n === ent.name || String(ent.name).includes(n) || n.includes(ent.name),
                        );
                        return (
                          <div
                            key={ent.id}
                            className={`overflow-hidden rounded-xl border transition ${
                              active
                                ? "border-[var(--projector)] shadow-[0_0_0_1px_var(--projector)]"
                                : "border-[var(--line)] opacity-80"
                            }`}
                          >
                            <div
                              className={`flex items-center justify-center overflow-hidden bg-[#11131a] ${
                                block.kind === "character"
                                  ? "aspect-[3/4]"
                                  : block.kind === "prop"
                                    ? "aspect-square"
                                    : "aspect-video"
                              }`}
                            >
                              {ent.selectedImage?.url ? (
                                <img
                                  src={ent.selectedImage.url}
                                  alt=""
                                  className="h-full w-full object-cover object-top"
                                />
                              ) : null}
                            </div>
                            <div className="truncate px-1.5 py-1 text-center text-[11px] font-medium">{ent.name}</div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                ) : null,
              )}
              {!episodeEntities.length ? <p className="text-xs text-[var(--muted)]">{tr("ui_edit_no_assets_in_this_episode")}</p> : null}
            </aside>

            {/* ── Script / shots ── */}
            <section className="panel flex max-h-[min(78vh,860px)] flex-col overflow-hidden">
              <div className="flex flex-wrap items-center gap-2 border-b border-[var(--line)] px-3 py-2.5">
                <button type="button" className="btn-quiet !min-h-8 !px-2" disabled={selectedIndex <= 0} onClick={() => jumpClip(-1)}>
                  <ChevronLeft className="h-4 w-4" />
                </button>
                <div className="scrollbar-thin flex max-w-full gap-1.5 overflow-x-auto py-0.5">
                  {enabledClips.map((clip, i) => {
                    const shot = readyShots.find((s) => s.id === clip.shotId);
                    const active = clip.id === selectedClipId;
                    return (
                      <button
                        key={clip.id}
                        type="button"
                        onClick={() => selectClip(clip.id)}
                        className={`flex h-8 min-w-8 items-center justify-center rounded-full px-2.5 text-xs font-semibold transition ${
                          active
                            ? "bg-[var(--projector)] text-white"
                            : "bg-black/5 text-[var(--muted)] hover:bg-black/10 hover:text-[var(--ink)]"
                        }`}
                        title={shot?.dialogue || tr("ui_edit_segment", {
                          0: i + 1
                        })}
                      >
                        {i + 1}
                      </button>
                    );
                  })}
                </div>
                <button
                  type="button"
                  className="btn-quiet !min-h-8 !px-2"
                  disabled={selectedIndex < 0 || selectedIndex >= enabledClips.length - 1}
                  onClick={() => jumpClip(1)}
                >
                  <ChevronRight className="h-4 w-4" />
                </button>
                <div className="ml-auto flex items-center gap-1 rounded-lg bg-black/5 p-0.5">
                  <button
                    type="button"
                    className={`rounded-md px-2.5 py-1 text-xs ${scriptTab === "lens" ? "bg-[var(--panel)] font-semibold shadow-sm" : "text-[var(--muted)]"}`}
                    onClick={() => setScriptTab("lens")}
                  >{tr("ui_edit_shot")}</button>
                  <button
                    type="button"
                    className={`rounded-md px-2.5 py-1 text-xs ${scriptTab === "original" ? "bg-[var(--panel)] font-semibold shadow-sm" : "text-[var(--muted)]"}`}
                    onClick={() => setScriptTab("original")}
                  >{tr("ui_edit_source")}</button>
                </div>
                <button type="button" className="btn-quiet !min-h-8 !px-2 text-xs" onClick={resetFromShots}>{tr("ui_edit_reset_to_storyboard")}</button>
              </div>

              <div className="border-b border-[var(--line)] px-4 py-3">
                <div className="flex flex-wrap items-center gap-2 text-xs">
                  <span className="rounded-md bg-black/50 px-2 py-0.5 font-medium text-white">{tr("ui_edit_segment", {
                      0: selectedIndex >= 0 ? selectedIndex + 1 : "—"
                    })}</span>
                  <span className="text-[var(--muted)]">{clipDuration(selectedClip || { start: 0, end: 0 }).toFixed(1)}s</span>
                  <span className="rounded-full bg-emerald-500/15 px-2 py-0.5 text-[10px] font-medium text-emerald-600">
                    {selectedShot?.status === "success" ? tr("ui_edit_done") : selectedShot?.status || tr("ui_edit_ready")}
                  </span>
                </div>
                <div className="mt-2 grid gap-1 text-[12px] text-[var(--muted)] sm:grid-cols-2">
                  <div>
                    <span className="text-[var(--ink)]/50">{tr("ui_edit_location")}</span>
                    {selectedShot?.sceneName || "—"}
                  </div>
                  <div>
                    <span className="text-[var(--ink)]/50">{tr("ui_edit_time")}</span>
                    {inferTimeOfDay(selectedShot)}
                  </div>
                  <div className="sm:col-span-2">
                    <span className="text-[var(--ink)]/50">{tr("ui_edit_action")}</span>
                    {selectedShot?.action || "—"}
                  </div>
                </div>
              </div>

              <div ref={shotListRef} className="scrollbar-thin flex-1 space-y-3 overflow-y-auto p-3">
                {(() => {
                  let cursor = 0;
                  return clips.map((clip, index) => {
                    const shot = readyShots.find((item) => item.id === clip.shotId);
                    if (!shot) return null;
                    const active = selectedClipId === clip.id;
                    const dur = clipDuration(clip);
                    const tlStart = clip.enabled === false ? null : cursor;
                    if (clip.enabled !== false) cursor += dur;
                    const beat = originalBeat(episode?.content, shot.shotOrder);
                    return (
                      <article
                        key={clip.id}
                        data-clip-id={clip.id}
                        onClick={() => selectClip(clip.id)}
                        className={`cursor-pointer rounded-2xl border p-4 transition ${
                          active
                            ? "border-[var(--projector)] bg-[var(--projector)]/8 shadow-[0_0_0_1px_var(--projector)]"
                            : "border-[var(--line)] bg-white/[.02] hover:border-white/20"
                        } ${clip.enabled === false ? "opacity-45" : ""}`}
                      >
                        <div className="mb-2 flex flex-wrap items-center gap-2">
                          <span className="rounded bg-black/55 px-2 py-0.5 text-[11px] font-semibold text-white">{tr("ui_edit_shot_s", {
                              shotOrder: shot.shotOrder,
                              1: dur.toFixed(1)
                            })}</span>
                          {tlStart != null ? (
                            <span className="text-[10px] text-[var(--muted)]">{tr("ui_edit_timeline_s", {
                                0: tlStart.toFixed(1)
                              })}</span>
                          ) : (
                            <span className="text-[10px] text-[var(--muted)]">{tr("ui_edit_disabled")}</span>
                          )}
                          <label
                            className="ml-auto flex items-center gap-1 text-[10px] text-[var(--muted)]"
                            onClick={(e) => e.stopPropagation()}
                          >
                            <input
                              type="checkbox"
                              checked={clip.enabled !== false}
                              onChange={(e) => updateClip(clip.id, { enabled: e.target.checked })}
                            />{tr("ui_edit_enable")}</label>
                        </div>

                        {scriptTab === "lens" ? (
                          <>
                            <PromptWithChips
                              prompt={shot.prompt || shot.action || tr("ui_edit_no_shot_prompt")}
                              entityByName={entityByName}
                              activeNames={active ? activeRefNames : new Set(parseRefNames(shot.prompt || ""))}
                            />
                            <DialogueCard dialogue={shot.dialogue} entityByName={entityByName} />
                          </>
                        ) : (
                          <pre className="whitespace-pre-wrap font-sans text-[13px] leading-6 text-[var(--ink)]/85">
                            {beat || tr("ui_edit_no_matching_source_text")}
                          </pre>
                        )}
                      </article>
                    );
                  });
                })()}
              </div>
            </section>

            {/* ── Monitor + trim ── */}
            <aside className="space-y-3">
              <div ref={monitorRef} className="overflow-hidden rounded-[18px] bg-[var(--navy)] p-3 text-white">
                <div className="timecode mb-2 flex items-center justify-between text-[10px] text-white/45">
                  <span>{tr("ui_edit_segment_2", {
                      0: selectedIndex >= 0 ? selectedIndex + 1 : "—",
                      length: enabledClips.length
                    })}</span>
                  <span>
                    {globalTime.toFixed(1)} / {totalDuration.toFixed(1)}s · {ratio}
                  </span>
                </div>
                <div className="flex justify-center rounded-xl bg-black/40">
                  <div
                    className={`relative overflow-hidden rounded-xl bg-black ${
                      ratio === "9:16"
                        ? "aspect-[9/16] h-[min(52vh,420px)] w-auto max-w-full"
                        : "aspect-video w-full"
                    }`}
                  >
                  {selectedShot?.selectedVideo?.url ? (
                    <>
                      <video
                        ref={videoRef}
                        key={selectedClip?.id || selectedShot.id}
                        src={selectedShot.selectedVideo.url}
                        muted={muted}
                        playsInline
                        className="absolute inset-0 h-full w-full object-contain"
                        onTimeUpdate={(e) => {
                          const start = Number(selectedClip?.start || 0);
                          const end = Number(selectedClip?.end || e.currentTarget.duration || start + 1);
                          const t = e.currentTarget.currentTime;
                          setLocalTime(Math.max(0, t - start));
                          if (t >= end - 0.05) {
                            e.currentTarget.pause();
                            onClipEnded();
                          }
                        }}
                        onEnded={() => onClipEnded()}
                        onClick={togglePlay}
                      />
                      {selectedShot.dialogue ? (
                        <div className="pointer-events-none absolute inset-x-3 bottom-12 rounded-md bg-black/70 px-3 py-2 text-center text-xs leading-5">
                          {selectedShot.dialogue}
                        </div>
                      ) : null}
                    </>
                  ) : (
                    <div className="absolute inset-0 flex items-center justify-center">
                      <Film className="h-10 w-10 text-white/15" />
                    </div>
                  )}
                  </div>
                </div>

                {bgm?.url ? <audio ref={bgmRef} src={bgm.url} loop preload="metadata" /> : null}

                <div className="mt-3 space-y-2">
                  <input
                    type="range"
                    min={0}
                    max={Math.max(0.1, totalDuration)}
                    step={0.05}
                    value={Math.min(globalTime, totalDuration)}
                    onChange={(e) => seekGlobal(Number(e.target.value))}
                    className="w-full accent-[var(--projector)]"
                    aria-label={tr("ui_edit_episode_progress")}
                  />
                  <div className="flex flex-wrap items-center justify-center gap-1.5">
                    <button type="button" className="btn-quiet !min-h-9 !px-2.5 text-white/80" onClick={() => jumpClip(-1)}>
                      <ChevronLeft className="h-4 w-4" />
                    </button>
                    <button type="button" className="btn-primary !min-h-9 !rounded-full !px-4" onClick={togglePlay}>
                      {playing ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
                      {playing ? tr("ui_edit_pause") : tr("ui_edit_play")}
                    </button>
                    <button type="button" className="btn-quiet !min-h-9 !px-2.5 text-white/80" onClick={() => jumpClip(1)}>
                      <ChevronRight className="h-4 w-4" />
                    </button>
                    <button type="button" className="btn-quiet !min-h-9 !px-2.5 text-white/80" onClick={() => setMuted((m) => !m)}>
                      {muted ? <VolumeX className="h-4 w-4" /> : <Volume2 className="h-4 w-4" />}
                    </button>
                    <button type="button" className="btn-quiet !min-h-9 !px-2.5 text-white/80" onClick={toggleFullscreen} title={tr("ui_edit_fullscreen")}>
                      <Maximize2 className="h-4 w-4" />
                    </button>
                  </div>
                  <div className="flex flex-wrap items-center justify-center gap-4 text-xs text-white/70">
                    <label className="flex items-center gap-1.5">
                      <input type="checkbox" checked={continuous} onChange={(e) => setContinuous(e.target.checked)} />{tr("ui_edit_continuous_play")}</label>
                    <label className={`flex items-center gap-1.5 ${bgm?.url ? "" : "opacity-40"}`}>
                      <input
                        type="checkbox"
                        checked={bgmOn && !!bgm?.url}
                        disabled={!bgm?.url}
                        onChange={(e) => setBgmOn(e.target.checked)}
                      />{tr("ui_edit_score")}</label>
                  </div>
                </div>
              </div>

              {/* Trim / edit tools */}
              <div className="panel space-y-3 p-3">
                <div className="flex flex-wrap gap-1.5">
                  {[
                    { id: "visual", label: tr("ui_edit_ai_repaint"), enabled: false },
                    { id: "line", label: tr("ui_edit_edit_line"), enabled: false },
                    { id: "trim", label: tr("ui_edit_trim"), enabled: true },
                  ].map((m) => (
                    <button
                      key={m.id}
                      type="button"
                      disabled={!m.enabled}
                      onClick={() => setEditMode(m.id)}
                      className={`rounded-full px-3 py-1.5 text-xs font-medium transition ${
                        editMode === m.id
                          ? "bg-[var(--projector)] text-white"
                          : m.enabled
                            ? "bg-black/5 text-[var(--ink)] hover:bg-black/10"
                            : "cursor-not-allowed bg-black/5 text-[var(--muted)] opacity-50"
                      }`}
                    >
                      {m.label}
                    </button>
                  ))}
                </div>

                {editMode === "trim" ? (
                  <>
                    <div className="flex gap-2 text-xs">
                      <button
                        type="button"
                        className="rounded-lg border border-[var(--projector)] bg-[var(--projector)]/10 px-3 py-1.5 font-medium"
                        onClick={() => applyTrim("keep")}
                      >{tr("ui_edit_keep")}</button>
                      <button
                        type="button"
                        className="rounded-lg border border-[var(--line)] px-3 py-1.5 text-[var(--muted)] hover:border-white/30"
                        onClick={() => applyTrim("drop")}
                      >{tr("ui_edit_cut")}</button>
                    </div>
                    <div className="space-y-2 text-xs">
                      <label className="block">
                        <span className="mb-1 flex justify-between text-[var(--muted)]">
                          <span>{tr("ui_edit_in")}</span>
                          <span className="timecode">{draftStart.toFixed(2)}s</span>
                        </span>
                        <input
                          type="range"
                          min={0}
                          max={Math.max(0.1, mediaMax)}
                          step={0.05}
                          value={draftStart}
                          onChange={(e) => setDraftStart(Math.min(Number(e.target.value), draftEnd - 0.1))}
                          className="w-full accent-[var(--projector)]"
                          aria-label={tr("ui_edit_in")}
                        />
                      </label>
                      <label className="block">
                        <span className="mb-1 flex justify-between text-[var(--muted)]">
                          <span>{tr("ui_edit_out")}</span>
                          <span className="timecode">{draftEnd.toFixed(2)}s</span>
                        </span>
                        <input
                          type="range"
                          min={0}
                          max={Math.max(0.1, mediaMax)}
                          step={0.05}
                          value={draftEnd}
                          onChange={(e) => setDraftEnd(Math.max(Number(e.target.value), draftStart + 0.1))}
                          className="w-full accent-[var(--projector)]"
                          aria-label={tr("ui_edit_out")}
                        />
                      </label>
                    </div>
                    <div className="grid grid-cols-2 gap-1.5">
                      <button type="button" className="btn-quiet !min-h-8 text-xs" onClick={() => nudge("start", -0.5)}>{tr("ui_edit_in_0_5s")}</button>
                      <button type="button" className="btn-quiet !min-h-8 text-xs" onClick={() => nudge("start", 0.5)}>{tr("ui_edit_in_0_5s_2")}</button>
                      <button type="button" className="btn-quiet !min-h-8 text-xs" onClick={() => nudge("end", -0.5)}>{tr("ui_edit_out_0_5s")}</button>
                      <button type="button" className="btn-quiet !min-h-8 text-xs" onClick={() => nudge("end", 0.5)}>{tr("ui_edit_out_0_5s_2")}</button>
                    </div>
                    <button type="button" className="btn-secondary w-full !min-h-9 text-xs" onClick={previewTrim}>
                      <Expand className="h-3.5 w-3.5" />{" "}{tr("ui_edit_preview_the_kept_part")}</button>
                    <button
                      type="button"
                      className="btn-primary w-full !min-h-9 text-xs"
                      onClick={() => {
                        applyTrim("keep");
                        void save(true);
                      }}
                    >
                      <Save className="h-3.5 w-3.5" />{" "}{tr("ui_edit_save_trim")}</button>
                  </>
                ) : (
                  <p className="py-6 text-center text-xs text-[var(--muted)]">
                    {editMode === "visual" ? tr("ui_edit_ai_repaint") : tr("ui_edit_edit_line")}{tr("ui_edit_coming_in_a_later_version_for")}</p>
                )}
              </div>

              {draft?.outputUrl ? (
                <div className="panel p-3">
                  <div className="label mb-2">{tr("ui_edit_cut_exported")}</div>
                  <video
                    src={draft.outputUrl}
                    controls
                    preload="metadata"
                    className="aspect-video w-full rounded-xl bg-black object-contain"
                  />
                  <a href={draft.outputUrl} download={tr("ui_edit_episode_download_filename", { n: episode.episodeNumber })} className="btn-secondary mt-2 w-full">
                    <Download className="h-4 w-4" />{" "}{tr("ui_edit_download")}</a>
                </div>
              ) : null}
            </aside>
          </div>

          {/* Bottom filmstrip */}
          <section className="panel p-3">
            <div className="mb-2 flex items-center justify-between gap-2">
              <div className="timecode text-[10px] text-[var(--muted)]">{tr("ui_edit_timeline_segments_click_to_jump_follows", {
                  length: enabledClips.length
                })}</div>
              <div className="text-[10px] text-[var(--muted)]">{totalDuration.toFixed(1)}s</div>
            </div>
            <div ref={filmstripRef} className="scrollbar-thin flex gap-2 overflow-x-auto pb-1">
              {timeline.map((item, i) => {
                const shot = readyShots.find((s) => s.id === item.clip.shotId);
                if (!shot) return null;
                const active = selectedClipId === item.clip.id;
                const progress =
                  active && item.duration > 0 ? Math.min(1, localTime / item.duration) : active ? 1 : 0;
                return (
                  <button
                    key={item.clip.id}
                    type="button"
                    data-clip-id={item.clip.id}
                    onClick={() => selectClip(item.clip.id)}
                    className={`relative w-[112px] shrink-0 overflow-hidden rounded-lg border text-left transition ${
                      active ? "border-[var(--projector)] ring-1 ring-[var(--projector)]" : "border-[var(--line)]"
                    }`}
                  >
                    <div className="relative aspect-video overflow-hidden bg-black">
                      <video
                        src={shot.selectedVideo.url}
                        muted
                        preload="metadata"
                        className="absolute inset-0 h-full w-full object-cover object-center"
                      />
                    </div>
                    <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/85 to-transparent px-1.5 pb-1.5 pt-5">
                      <div className="timecode text-[9px] text-white">
                        {i + 1} · {item.duration.toFixed(0)}s
                      </div>
                    </div>
                    {active ? (
                      <div className="absolute inset-x-0 bottom-0 h-0.5 bg-white/20">
                        <div className="h-full bg-[var(--projector)]" style={{ width: `${progress * 100}%` }} />
                      </div>
                    ) : null}
                  </button>
                );
              })}
            </div>
          </section>
        </>
      )}

      {previewFinalOpen && draft?.outputUrl ? (
        <ModalOverlay
          onClose={() => setPreviewFinalOpen(false)}
          className="bg-black/80"
          zClass="z-[200]"
          role="dialog"
        >
          <div
            className="relative my-auto w-fit max-w-[min(92vw,720px)]"
            onMouseDown={(e) => e.stopPropagation()}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mb-2 flex items-center justify-between gap-2 px-0.5">
              <p className="text-sm font-medium text-white/90">{tr("ui_edit_cut_preview")}</p>
              <button
                type="button"
                className="rounded-full bg-white/10 p-1.5 text-white hover:bg-white/20"
                aria-label={tr("ui_edit_close")}
                onClick={() => setPreviewFinalOpen(false)}
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <video
              key={draft.outputUrl}
              src={draft.outputUrl}
              controls
              autoPlay
              playsInline
              className="block max-h-[min(78dvh,78vh)] w-auto max-w-full rounded-xl bg-black shadow-2xl"
            />
          </div>
        </ModalOverlay>
      ) : null}
    </div>
  );
}
