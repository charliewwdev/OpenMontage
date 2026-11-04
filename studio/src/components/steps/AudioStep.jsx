import { useEffect, useMemo, useState } from "react";
import { Loader2, Mic2, SkipForward, Volume2 } from "lucide-react";
import { api } from "../../api";
import { extractDialogueLines } from "../../lib/dialogue";
import { toast } from "../../lib/toast";

import { tr, useLocale } from "../../lib/i18n";

// Speaker names come from the script parser (lib/dialogue.js); only its two
// generic placeholders are display-mapped, real character names stay as written.
const SPEAKER_LABEL_KEYS = { 旁白: "ui_audio_speaker_narration", 对白: "ui_audio_speaker_dialogue" };
function speakerLabel(speaker) {
  const key = SPEAKER_LABEL_KEYS[speaker];
  return key ? tr(key) : speaker;
}

export function AudioStep({
  projectId,
  bundle,
  setBusyMsg,
  onBundle,
  onRefresh,
  onNeedKeys,
  focusEpisodeId,
  setStep,
}) {
  useLocale();
  const episodes = useMemo(
    () => [...(bundle?.episodes || [])].sort((a, b) => a.episodeNumber - b.episodeNumber),
    [bundle?.episodes],
  );
  const audios = bundle?.audios || [];
  const [busy, setBusy] = useState(false);

  const episode = useMemo(
    () => episodes.find((e) => e.id === focusEpisodeId) || episodes[0] || null,
    [episodes, focusEpisodeId],
  );

  useEffect(() => {
    if (focusEpisodeId && !episodes.some((e) => e.id === focusEpisodeId) && episodes[0]) {
      /* shell will re-focus; keep local render safe */
    }
  }, [focusEpisodeId, episodes]);

  const audio = audios.find(
    (a) => a.episodeId === (episode?.id || "") && a.kind !== "bgm",
  );
  const bgm = audios.find(
    (a) => a.episodeId === (episode?.id || "") && a.kind === "bgm",
  );
  const dialogueLines = useMemo(
    () => extractDialogueLines(episode?.content || episode?.script || ""),
    [episode?.content, episode?.script],
  );
  const shotDialogues = useMemo(() => {
    const epId = episode?.id;
    if (!epId) return [];
    return (bundle?.shots || [])
      .filter((s) => s.episodeId === epId && !s.deletedAt && String(s.dialogue || "").trim())
      .sort((a, b) => a.shotOrder - b.shotOrder)
      .map((s) => ({ shotOrder: s.shotOrder, text: String(s.dialogue).trim() }));
  }, [bundle?.shots, episode?.id]);

  const generate = async () => {
    if (!episode) return toast.error(tr("ui_audio_generate_episodes_in_the_script_step"));
    if (!dialogueLines.length && !shotDialogues.length) {
      return toast.error(tr("ui_audio_no_dialogue_detected_in_this_episode"));
    }
    setBusy(true);
    setBusyMsg?.(tr("ui_audio_synthesizing_voice_over"));
    try {
      const res = await api(`/api/projects/${encodeURIComponent(projectId)}/audio`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "generate", episodeId: episode.id }),
      });
      if (res.bundle) onBundle?.(res.bundle);
      else onRefresh?.();
      toast.success(tr("ui_audio_per_character_dialogue_generated_bgm_is"));
    } catch (error) {
      const msg = String(error.message || error);
      toast.error(msg);
      if (/Key|TTS|edge-tts|配置/i.test(msg)) onNeedKeys?.();
    } finally {
      setBusy(false);
      setBusyMsg?.("");
    }
  };

  return (
    <div className="space-y-5">
      <section className="panel p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="label">Dubbing</div>
            <h2 className="text-xl font-semibold">{tr("ui_audio_per_character_dialogue_bgm")}</h2>
            <p className="mt-1 max-w-2xl text-sm text-[var(--muted)]">{tr("ui_audio_extracts_dialogue_in_character_line_form")}</p>
          </div>
          <button type="button" className="btn-secondary" onClick={() => toast.info(tr("ui_audio_voice_over_skipped_you_can_go"))}>
            <SkipForward className="h-4 w-4" />{" "}{tr("ui_audio_skip_this_step")}</button>
        </div>

        {!episodes.length ? (
          <div className="mt-6 rounded-xl border border-dashed border-[var(--line)] px-4 py-10 text-center text-sm text-[var(--muted)]">{tr("ui_audio_no_episodes_yet_generate_and_confirm")}{typeof setStep === "function" ? (
              <div className="mt-3">
                <button type="button" className="btn-primary !min-h-8 !px-3" onClick={() => setStep("script")}>{tr("ui_audio_go_to_script")}</button>
              </div>
            ) : null}
          </div>
        ) : !episode ? (
          <div className="mt-6 rounded-xl border border-dashed border-[var(--line)] px-4 py-10 text-center text-sm text-[var(--muted)]">{tr("ui_audio_select_an_episode_on_the_left")}</div>
        ) : (
          <div className="mt-5 rounded-2xl border border-[var(--line)] bg-black/20 p-5">
            <div className="flex items-center gap-2 text-sm font-semibold">
              <Mic2 className="h-4 w-4 text-[#fb923c]" />{tr("ui_audio_episode_detected_lines", {
                episodeNumber: episode.episodeNumber,
                1: episode.title ? ` · ${episode.title}` : ""
              })}</div>

            {dialogueLines.length || shotDialogues.length ? (
              <ul className="mt-3 max-h-56 space-y-2 overflow-auto text-xs leading-6">
                {dialogueLines.map((line, i) => (
                  <li key={`d-${i}`} className="rounded-lg bg-white/[.04] px-3 py-2 text-white/80">
                    <span className="font-semibold text-[#fb923c]">{speakerLabel(line.speaker)}</span>
                    <span className="text-white/40"> · </span>
                    {line.text}
                  </li>
                ))}
                {shotDialogues.map((line) => (
                  <li key={`s-${line.shotOrder}`} className="rounded-lg bg-white/[.04] px-3 py-2 text-white/70">
                    <span className="font-semibold text-white/45">{tr("ui_audio_shot", {
                        shotOrder: line.shotOrder
                      })}</span>
                    <span className="text-white/40"> · </span>
                    {line.text}
                  </li>
                ))}
              </ul>
            ) : (
              <div className="mt-3 rounded-xl border border-dashed border-white/15 px-3 py-6 text-xs leading-6 text-white/45">{tr("ui_audio_no_dialogue_detected_in_the_script")}</div>
            )}

            <div className="mt-5 flex flex-wrap items-center gap-2">
              <button type="button" className="btn-primary" disabled={busy || !episode} onClick={() => void generate()}>
                {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Volume2 className="h-4 w-4" />}
                {busy ? tr("ui_audio_synthesizing") : audio ? tr("ui_audio_regenerate_voice_over") : tr("ui_audio_generate_voice_over")}
              </button>
              {audio?.url ? (
                <audio controls className="h-9 max-w-full" src={audio.url} preload="metadata">
                  <track kind="captions" />
                </audio>
              ) : null}
            </div>
            {audio ? (
              <p className="mt-3 text-[11px] text-[var(--muted)]">
                {audio.mode === "dialogue" ? tr("ui_audio_per_character_dialogue") : tr("ui_audio_voice_over")} · {audio.provider || "tts"}
                {audio.lines ? ` ${tr("ui_audio_lines", {
  lines: audio.lines
})}` : ""}
                {audio.bytes ? ` · ${(audio.bytes / 1024).toFixed(1)} KB` : ""}
                {bgm ? ` ${tr("ui_audio_bgm_generated")}` : ""}
                {` ${tr("ui_audio_auto_mixed_on_export")}`}
              </p>
            ) : null}
            {bgm?.url ? (
              <audio controls className="mt-2 h-9 max-w-full" src={bgm.url} preload="metadata">
                <track kind="captions" />
              </audio>
            ) : null}
          </div>
        )}
      </section>
    </div>
  );
}
