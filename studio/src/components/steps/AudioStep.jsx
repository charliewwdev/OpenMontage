import { useEffect, useMemo, useState } from "react";
import { Loader2, Mic2, SkipForward, Volume2 } from "lucide-react";
import { api } from "../../api";
import { extractDialogueLines } from "../../lib/dialogue";
import { toast } from "../../lib/toast";

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
    if (!episode) return toast.error("请先在剧本步生成分集");
    if (!dialogueLines.length && !shotDialogues.length) {
      return toast.error("本集未识别到对白。请在剧本中使用「角色：台词」或「…」格式，或在分镜填写 dialogue。");
    }
    setBusy(true);
    setBusyMsg?.("正在合成配音…");
    try {
      const res = await api(`/api/projects/${encodeURIComponent(projectId)}/audio`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "generate", episodeId: episode.id }),
      });
      if (res.bundle) onBundle?.(res.bundle);
      else onRefresh?.();
      toast.success("分角色对白已生成，导出时会混入 BGM");
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
    <div className="space-y-3">
      <section className="panel p-3 md:p-3.5">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <div className="label">Dubbing</div>
            <h2 className="text-[1.15rem] font-semibold md:text-[1.3rem]">分角色对白 + BGM</h2>
            <p className="mt-0.5 max-w-2xl text-[12px] text-[var(--muted)]">
              按「角色：台词」抽取对白，用不同音色分角色朗读（不是解说旁白）。同时生成轻量配乐，剪辑导出时与画面混音。场景描写不会进配音。
            </p>
          </div>
          <button type="button" className="btn-secondary" onClick={() => toast.info("已跳过配音，可直接去剪辑")}>
            <SkipForward className="h-4 w-4" /> 跳过本步
          </button>
        </div>

        {!episodes.length ? (
          <div className="mt-3 rounded-lg border border-dashed border-[var(--line)] px-3 py-6 text-center text-[12px] text-[var(--muted)]">
            还没有分集。请先在「剧本」步生成并确认剧集。
            {typeof setStep === "function" ? (
              <div className="mt-2">
                <button type="button" className="btn-primary !min-h-8 !px-3" onClick={() => setStep("script")}>
                  去剧本
                </button>
              </div>
            ) : null}
          </div>
        ) : !episode ? (
          <div className="mt-3 rounded-lg border border-dashed border-[var(--line)] px-3 py-6 text-center text-[12px] text-[var(--muted)]">
            请在左侧选择一个分集。
          </div>
        ) : (
          <div className="mt-3 rounded-xl border border-[var(--line)] bg-black/20 p-3">
            <div className="flex items-center gap-2 text-[13px] font-semibold">
              <Mic2 className="h-4 w-4 text-[#fb923c]" />
              第 {episode.episodeNumber} 集{episode.title ? ` · ${episode.title}` : ""} · 识别到的台词
            </div>

            {dialogueLines.length || shotDialogues.length ? (
              <ul className="mt-3 max-h-56 space-y-2 overflow-auto text-xs leading-6">
                {dialogueLines.map((line, i) => (
                  <li key={`d-${i}`} className="rounded-lg bg-white/[.04] px-3 py-2 text-white/80">
                    <span className="font-semibold text-[#fb923c]">{line.speaker}</span>
                    <span className="text-white/40"> · </span>
                    {line.text}
                  </li>
                ))}
                {shotDialogues.map((line) => (
                  <li key={`s-${line.shotOrder}`} className="rounded-lg bg-white/[.04] px-3 py-2 text-white/70">
                    <span className="font-semibold text-white/45">镜 {line.shotOrder}</span>
                    <span className="text-white/40"> · </span>
                    {line.text}
                  </li>
                ))}
              </ul>
            ) : (
              <div className="mt-3 rounded-xl border border-dashed border-white/15 px-3 py-6 text-xs leading-6 text-white/45">
                未识别到对白。请在剧本使用「角色名：台词」或中文引号「…」，不要只写场景描写。
              </div>
            )}

            <div className="mt-5 flex flex-wrap items-center gap-2">
              <button type="button" className="btn-primary" disabled={busy || !episode} onClick={() => void generate()}>
                {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Volume2 className="h-4 w-4" />}
                {busy ? "合成中…" : audio ? "重新生成配音" : "生成配音"}
              </button>
              {audio?.url ? (
                <audio controls className="h-9 max-w-full" src={audio.url} preload="metadata">
                  <track kind="captions" />
                </audio>
              ) : null}
            </div>
            {audio ? (
              <p className="mt-3 text-[11px] text-[var(--muted)]">
                {audio.mode === "dialogue" ? "分角色对白" : "配音"} · {audio.provider || "tts"}
                {audio.lines ? ` · ${audio.lines} 句` : ""}
                {audio.bytes ? ` · ${(audio.bytes / 1024).toFixed(1)} KB` : ""}
                {bgm ? " · 已生成 BGM" : ""}
                {" · 导出时自动混音"}
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
