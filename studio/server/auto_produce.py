"""One-click short-drama pipeline: brief/script → script → assets → shots → audio → export."""

from __future__ import annotations

import threading
import time
from datetime import datetime, timezone
from typing import Any

from store import ProjectStore, _now, new_id

_STEP_DEFS = [
    ("brief", "优化创作需求"),
    ("script", "生成剧本"),
    ("confirm", "定稿首集"),
    ("entities", "生成角色/场景图"),
    ("storyboard", "拆分镜"),
    ("videos", "生成分镜视频"),
    ("audio", "合成配音"),
    ("export", "剪辑导出成片"),
]

# project_id → live worker thread (process-local; lost on container restart)
_WORKERS: dict[str, threading.Thread] = {}
_WORKERS_LOCK = threading.Lock()
_STALE_RESUME_SECONDS = 75


def _empty_job(options: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "id": new_id("ap_"),
        "status": "queued",
        "step": "",
        "steps": [{"id": sid, "label": label, "status": "pending", "detail": ""} for sid, label in _STEP_DEFS],
        "logs": [],
        "episodeId": "",
        "episodeIds": [],
        "exportUrl": "",
        "exportPath": "",
        "exports": [],
        "seriesUrl": "",
        "seriesPath": "",
        "error": None,
        "options": options or {},
        "startedAt": _now(),
        "updatedAt": _now(),
    }


def get_job(store: ProjectStore, project_id: str) -> dict[str, Any] | None:
    state = store.load(project_id)
    if not state:
        return None
    return (state.get("project") or {}).get("autoProduce")


def _parse_ts(value: Any) -> float | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


def _step_finished(job: dict[str, Any], step_id: str) -> bool:
    for step in job.get("steps") or []:
        if step.get("id") == step_id:
            return step.get("status") in {"done", "skipped"}
    return False


def _sorted_episodes(state: dict[str, Any] | None) -> list[dict[str, Any]]:
    return sorted(
        [e for e in ((state or {}).get("episodes") or []) if not e.get("deletedAt")],
        key=lambda e: int(e.get("episodeNumber") or 0),
    )


def _target_episodes(state: dict[str, Any] | None, opts: dict[str, Any], job: dict[str, Any]) -> list[dict[str, Any]]:
    """Episodes to produce for this job (1–10).

    Prefer contiguous episodes by number once enough exist. Stale job.episodeIds
    from a mid-script resume must not drop later episodes.
    """
    episodes = _sorted_episodes(state)
    want = max(1, min(10, int(opts.get("episodeCount") or 1)))
    if len(episodes) >= want:
        return episodes[:want]
    saved_ids = [str(x) for x in (job.get("episodeIds") or []) if x]
    if saved_ids:
        by_id = {str(e.get("id")): e for e in episodes}
        picked = [by_id[i] for i in saved_ids if i in by_id]
        if picked:
            return picked[:want]
    return episodes[:want]


def _concat_series_exports(
    store: ProjectStore,
    project_id: str,
    exports: list[dict[str, Any]],
) -> dict[str, str] | None:
    """Join per-episode finals into one continuous-play MP4 (episode order)."""
    import shutil
    import subprocess
    import tempfile
    from pathlib import Path

    if len(exports) < 2:
        return None
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return None
    root = store._dir(project_id)
    if not root:
        return None
    ordered = sorted(exports, key=lambda x: int(x.get("episodeNumber") or 0))
    paths: list[Path] = []
    for item in ordered:
        rel = str(item.get("path") or "").strip()
        if not rel:
            continue
        ensured = store.ensure_media(project_id, rel)
        p = Path(ensured) if ensured else (root / rel)
        if p.is_file() and p.stat().st_size > 0:
            paths.append(p)
    if len(paths) < 2:
        return None
    out_rel = "media/exports/series-full.mp4"
    out_path = root / out_rel
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="om-series-") as tmp:
        list_file = Path(tmp) / "concat.txt"
        # Re-encode lightly via concat demuxer copy first; fall back to re-encode if needed.
        list_file.write_text(
            "".join(f"file '{p.resolve().as_posix()}'\n" for p in paths),
            encoding="utf-8",
        )
        cmd = [
            ffmpeg,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_file),
            "-c",
            "copy",
            str(out_path),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0 or not out_path.is_file() or out_path.stat().st_size <= 0:
            cmd_re = [
                ffmpeg,
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(list_file),
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "20",
                "-c:a",
                "aac",
                "-movflags",
                "+faststart",
                str(out_path),
            ]
            proc2 = subprocess.run(cmd_re, capture_output=True, text=True)
            if proc2.returncode != 0 or not out_path.is_file():
                return None
    try:
        store.persist_media(project_id, out_rel)
    except Exception:
        pass
    return {
        "path": out_rel,
        "url": f"/api/media/{project_id}/{out_rel}",
    }


def _worker_alive(project_id: str) -> bool:
    with _WORKERS_LOCK:
        thread = _WORKERS.get(project_id)
        return bool(thread and thread.is_alive())


def _spawn_worker(store: ProjectStore, project_id: str, job_id: str) -> None:
    thread = threading.Thread(
        target=_run_pipeline,
        args=(store, project_id, job_id),
        name=f"auto-produce-{project_id}",
        daemon=True,
    )
    with _WORKERS_LOCK:
        _WORKERS[project_id] = thread
    thread.start()


def ensure_auto_produce_worker(store: ProjectStore, project_id: str) -> dict[str, Any] | None:
    """If a running job has no live worker (e.g. after deploy), resume from current step."""
    job = get_job(store, project_id)
    if not job or job.get("status") != "running":
        return job
    if _worker_alive(project_id):
        return job
    updated = _parse_ts(job.get("updatedAt")) or 0
    age = time.time() - updated
    if age < _STALE_RESUME_SECONDS:
        return job
    _log(job, f"检测到任务中断（约 {int(age)}s 无进度），正在从「{job.get('step') or '当前步骤'}」续跑…")
    _save_job(store, project_id, job)
    _spawn_worker(store, project_id, str(job.get("id") or ""))
    return get_job(store, project_id)


def cancel_auto_produce(
    store: ProjectStore,
    project_id: str,
    *,
    reason: str = "已暂停：先修好剧本/分镜/定妆再出片",
) -> dict[str, Any]:
    """Stop idle resume loops so entity fixes can run without the video worker thrashing."""
    job = get_job(store, project_id)
    if not job:
        raise FileNotFoundError("no auto-produce job")
    if job.get("status") not in {"running", "queued"}:
        return job
    job["status"] = "paused"
    job["error"] = reason
    _set_step(job, str(job.get("step") or "videos"), "pending", reason)
    _log(job, reason, ok=False)
    _save_job(store, project_id, job)
    return job


def _job_cancelled(store: ProjectStore, project_id: str, job_id: str) -> bool:
    fresh = get_job(store, project_id) or {}
    if str(fresh.get("id") or "") != str(job_id or ""):
        return True
    return fresh.get("status") in {"paused", "cancelled", "failed"}


def _save_job(store: ProjectStore, project_id: str, job: dict[str, Any]) -> dict[str, Any]:
    state = store.load(project_id)
    if not state:
        raise FileNotFoundError("project not found")
    job["updatedAt"] = _now()
    state.setdefault("project", {})["autoProduce"] = job
    state["project"]["updatedAt"] = job["updatedAt"]
    store.save(state)
    return job


def _log(job: dict[str, Any], text: str, ok: bool = True) -> None:
    job.setdefault("logs", []).append({"at": _now(), "text": text, "ok": ok})
    if len(job["logs"]) > 200:
        job["logs"] = job["logs"][-200:]


def _set_step(job: dict[str, Any], step_id: str, status: str, detail: str = "") -> None:
    job["step"] = step_id
    now = _now()
    for step in job.get("steps") or []:
        if step.get("id") != step_id:
            continue
        prev = step.get("status")
        step["status"] = status
        if detail:
            step["detail"] = detail
        if status == "running" and prev != "running":
            step["startedAt"] = now
            step.pop("endedAt", None)
        if status in {"done", "failed", "skipped"}:
            step["endedAt"] = now
            started = _parse_ts(step.get("startedAt"))
            ended = _parse_ts(now)
            if started is not None and ended is not None:
                step["elapsedMs"] = int(max(0, (ended - started) * 1000))
        break


def _privacy_error(err: str | None) -> bool:
    text = (err or "").lower()
    return any(
        token in text
        for token in (
            "privacy",
            "sensitive",
            "inputimagesensitive",
            "copyright",
            "版权",
            "真人",
            "实人",
        )
    )


def _wait_shots(
    store: ProjectStore,
    project_id: str,
    shot_ids: list[str],
    timeout_s: int = 900,
    job: dict[str, Any] | None = None,
) -> list[dict]:
    from drama_service import poll_shot

    deadline = time.time() + timeout_s
    wanted = set(shot_ids)
    last_beat = 0.0
    while time.time() < deadline:
        state = store.load(project_id) or {}
        shots = [s for s in (state.get("shots") or []) if s.get("id") in wanted and not s.get("deletedAt")]
        # Re-attach polling after container restart (daemon poll threads die).
        for sh in shots:
            if sh.get("status") == "generating" and sh.get("providerTaskId"):
                try:
                    poll_shot(store, project_id, sh["id"])
                except Exception:
                    pass
        state = store.load(project_id) or {}
        shots = [s for s in (state.get("shots") or []) if s.get("id") in wanted and not s.get("deletedAt")]
        ok_n = sum(1 for s in shots if s.get("status") == "success")
        gen_n = sum(1 for s in shots if s.get("status") == "generating")
        fail_n = sum(1 for s in shots if s.get("status") == "failed")
        if job is not None and time.time() - last_beat >= 20:
            _set_step(job, "videos", "running", f"成功 {ok_n} · 生成中 {gen_n} · 失败 {fail_n}")
            _save_job(store, project_id, job)
            last_beat = time.time()
        if shots and all(s.get("status") in {"success", "failed"} for s in shots):
            return shots
        time.sleep(5)
    state = store.load(project_id) or {}
    return [s for s in (state.get("shots") or []) if s.get("id") in wanted and not s.get("deletedAt")]


def start_auto_produce(store: ProjectStore, project_id: str, options: dict[str, Any] | None = None) -> dict[str, Any]:
    state = store.load(project_id)
    if not state:
        raise FileNotFoundError("project not found")
    existing = (state.get("project") or {}).get("autoProduce") or {}
    if existing.get("status") == "running":
        raise RuntimeError("全流程任务已在运行中")

    opts = {
        # Full short-drama series: up to 10 episodes (not a single sample clip).
        "episodeCount": max(1, min(10, int((options or {}).get("episodeCount") or 1))),
        # SceneMixer density: 12–30 shots / ep (default 24 ≈ 3–5 min @ 6–12s).
        "maxShots": max(12, min(30, int((options or {}).get("maxShots") or 24))),
        "maxCharacters": max(1, min(48, int((options or {}).get("maxCharacters") or 24))),
        "maxScenes": max(1, min(48, int((options or {}).get("maxScenes") or 24))),
        "maxProps": max(0, min(48, int((options or {}).get("maxProps") or 24))),
        "forceDubbing": bool((options or {}).get("forceDubbing", False)),
        "optimizeBrief": bool((options or {}).get("optimizeBrief", True)),
        "generateEntities": bool((options or {}).get("generateEntities", True)),
        "textOnlyVideo": bool((options or {}).get("textOnlyVideo", False)),
        # Short-drama defaults: cinematic locks + 720p (not flat illustration / 480p).
        "forceIllustration": bool((options or {}).get("forceIllustration", False)),
        "resolution": str((options or {}).get("resolution") or "720p"),
        "model": str((options or {}).get("model") or ""),
        "skipAudio": bool((options or {}).get("skipAudio", False)),
        "skipExport": bool((options or {}).get("skipExport", False)),
        "requireEntityQa": bool((options or {}).get("requireEntityQa", True)),
        "requireVideoQa": bool((options or {}).get("requireVideoQa", True)),
    }

    # Resume a failed/paused job from the first unfinished step, keeping prior done work.
    if (options or {}).get("resume") and existing.get("status") in {"failed", "paused"} and existing.get("steps"):
        job = dict(existing)
        job["options"] = {**(existing.get("options") or {}), **opts}
        job["status"] = "running"
        job["error"] = None
        for step in job.get("steps") or []:
            if step.get("status") in {"failed", "pending"} and step.get("id") == (existing.get("step") or step.get("id")):
                step["status"] = "pending"
                if "暂停" in str(step.get("detail") or "") or "先修" in str(step.get("detail") or ""):
                    step["detail"] = ""
            if step.get("status") == "failed":
                step["status"] = "pending"
                step["detail"] = ""
        _log(job, "从暂停/失败步骤续跑全流程…")
        _save_job(store, project_id, job)
        _spawn_worker(store, project_id, str(job.get("id") or ""))
        return job

    job = _empty_job(opts)
    job["status"] = "running"
    _log(job, "已排队，开始全流程短剧制作")
    _save_job(store, project_id, job)
    _spawn_worker(store, project_id, job["id"])
    return job


def _run_pipeline(store: ProjectStore, project_id: str, job_id: str) -> None:
    from drama_service import (
        ensure_edit_draft,
        ensure_segment_video_qa,
        export_edit_mp4,
        generate_entity_image,
        generate_script,
        generate_storyboard,
        group_shots_by_segment,
        optimize_brief,
        set_episode_status,
        start_shot_video,
    )
    from platform_config import seedance_models
    from script_parse import dialogue_lines_for_episode
    from audio_tts import generate_bgm_mp3, synthesize_dialogue_mp3, synthesize_mp3
    from providers.media import resolve_video_model

    state = store.load(project_id)
    if not state:
        return
    job = (state.get("project") or {}).get("autoProduce") or {}
    if job.get("id") != job_id:
        return
    opts = job.get("options") or {}

    try:
        brief = str((state.get("project") or {}).get("brief") or "").strip()
        if not brief:
            raise RuntimeError("请先填写一句话想法或粘贴剧本")

        # Resolve target episodes early so resumed jobs can skip completed head steps.
        state = store.load(project_id) or state
        target_eps = _target_episodes(state, opts, job)
        episode = target_eps[0] if target_eps else None
        episode_id = str(job.get("episodeId") or (episode or {}).get("id") or "")
        if target_eps:
            job["episodeIds"] = [str(e.get("id")) for e in target_eps if e.get("id")]
            job["episodeId"] = str(target_eps[0].get("id") or episode_id)

        # 1) brief optimize (short ideas only, or forced)
        if not _step_finished(job, "brief"):
            should_optimize = bool(opts.get("optimizeBrief")) and len(brief) < 800
            if should_optimize:
                _set_step(job, "brief", "running")
                _log(job, "正在优化创作需求…")
                _save_job(store, project_id, job)
                try:
                    proj = state.get("project") or {}
                    result = optimize_brief(
                        store,
                        {
                            "title": proj.get("title") or "",
                            "brief": brief,
                            "genre": proj.get("genre") or "",
                            "visualStyle": proj.get("visualStyle") or "",
                            "ratio": proj.get("ratio") or "",
                        },
                    )
                    new_brief = str(result.get("brief") or "").strip()
                    if new_brief and new_brief != brief:
                        state = store.load(project_id) or state
                        state.setdefault("project", {})["brief"] = new_brief
                        store.save(state)
                        brief = new_brief
                        _log(job, "创作需求已扩写")
                    else:
                        _log(job, "创作需求已足够完整，跳过扩写")
                    _set_step(job, "brief", "done", "已优化")
                except Exception as exc:
                    _log(job, f"需求优化失败，继续用原文：{exc}", ok=False)
                    _set_step(job, "brief", "skipped", str(exc)[:120])
            else:
                _set_step(job, "brief", "skipped", "已有较长文本或关闭优化")
                _log(job, "跳过需求优化，直接生成剧本")
            _save_job(store, project_id, job)

        # 2) script — generate full series (1–10 episodes) in ≤3-ep batches
        want_eps = max(1, min(10, int(opts.get("episodeCount") or 1)))
        if not _step_finished(job, "script"):
            _set_step(job, "script", "running")
            _log(job, f"正在生成 {want_eps} 集完整短剧剧本（每批最多 3 集）…")
            _save_job(store, project_id, job)
            # Prefer incremental batches with live logs (resume-safe if some eps already exist).
            state = store.load(project_id) or {}
            have = len([e for e in (state.get("episodes") or []) if not e.get("deletedAt")])
            if have <= 0:
                first = min(3, want_eps)
                _log(job, f"剧本批次：生成第 1–{first} 集…")
                _save_job(store, project_id, job)
                generate_script(store, project_id, first, planned=want_eps)
            state = store.load(project_id) or {}
            have = len([e for e in (state.get("episodes") or []) if not e.get("deletedAt")])
            while have < want_eps:
                # After first batch, continue 1 ep at a time — large JSON batches truncate/break often.
                chunk = 1 if have >= 3 else min(3, want_eps - have)
                chunk = min(chunk, want_eps - have)
                _log(job, f"剧本批次：续写第 {have + 1}–{have + chunk} 集…")
                _set_step(job, "script", "running", f"{have}/{want_eps}")
                _save_job(store, project_id, job)
                from drama_service import continue_script as _continue_script

                last_exc: Exception | None = None
                for attempt in range(1, 4):
                    try:
                        _continue_script(
                            store,
                            project_id,
                            chunk,
                            instruction=(
                                f"续写第 {have + 1}–{have + chunk} 集，承接已有剧情，共计划 {want_eps} 集。"
                                "只输出精简合法 JSON（episodes/entities），每集 content 控制在 800 字内。"
                            ),
                            as_finale=have + chunk >= want_eps,
                        )
                        last_exc = None
                        break
                    except Exception as exc:  # noqa: BLE001
                        last_exc = exc
                        _log(job, f"剧本续写失败（尝试 {attempt}/3）：{exc}", ok=False)
                        _save_job(store, project_id, job)
                        time.sleep(2 * attempt)
                if last_exc is not None:
                    raise last_exc
                state = store.load(project_id) or {}
                now = len([e for e in (state.get("episodes") or []) if not e.get("deletedAt")])
                if now <= have:
                    raise RuntimeError(f"剧本续写未增加集数（仍为 {have}/{want_eps}）")
                have = now
                _log(job, f"剧本进度：已完成 {have}/{want_eps} 集")
            state = store.load(project_id) or {}
            target_eps = _target_episodes(state, opts, job)
            if not target_eps:
                raise RuntimeError("剧本生成后没有集数")
            job["episodeIds"] = [str(e.get("id")) for e in target_eps if e.get("id")]
            episode = target_eps[0]
            episode_id = str(episode["id"])
            job["episodeId"] = episode_id
            titles = "、".join(
                f"第{e.get('episodeNumber')}集《{e.get('title') or ''}》" for e in target_eps[:3]
            )
            more = f" 等{len(target_eps)}集" if len(target_eps) > 3 else f" 共{len(target_eps)}集"
            _set_step(job, "script", "done", f"{titles}{more}")
            _log(job, f"剧本就绪：共 {len(target_eps)} 集")
            _save_job(store, project_id, job)
        else:
            state = store.load(project_id) or {}
            target_eps = _target_episodes(state, opts, job)
            if not target_eps:
                raise RuntimeError("续跑失败：找不到剧本集")
            job["episodeIds"] = [str(e.get("id")) for e in target_eps if e.get("id")]
            episode = target_eps[0]
            episode_id = str(episode["id"])
            job["episodeId"] = episode_id

        # 3) confirm — lock all target episodes (re-run if any still draft after expansion)
        need_confirm = [e for e in target_eps if str(e.get("status") or "") != "confirmed"]
        if need_confirm or not _step_finished(job, "confirm"):
            _set_step(job, "confirm", "running")
            _save_job(store, project_id, job)
            ids = [str(e["id"]) for e in target_eps if e.get("id")]
            set_episode_status(store, project_id, ids, "confirmed")
            job["episodeIds"] = ids
            _set_step(job, "confirm", "done", f"{len(ids)} 集")
            _log(job, f"已定稿 {len(ids)} 集")
            _save_job(store, project_id, job)

        # 4) entity images — full cast / scenes / props with QA bar
        if not _step_finished(job, "entities"):
            if opts.get("generateEntities"):
                _set_step(job, "entities", "running")
                _log(job, "正在生成角色/场景/道具参考图（质检不达标将自动强化重试）…")
                _save_job(store, project_id, job)
                state = store.load(project_id) or {}
                entities = [e for e in (state.get("entities") or []) if not e.get("deletedAt")]
                ep_nums = {int(e.get("episodeNumber") or 0) for e in target_eps}
                scoped = [
                    e
                    for e in entities
                    if not e.get("episodes")
                    or any(int(n) in ep_nums for n in (e.get("episodes") or []))
                ]
                chars = [e for e in scoped if e.get("kind") == "character"][
                    : int(opts.get("maxCharacters") or 24)
                ]
                scenes = [e for e in scoped if e.get("kind") == "scene"][
                    : int(opts.get("maxScenes") or 24)
                ]
                props = [e for e in scoped if e.get("kind") == "prop"][
                    : int(opts.get("maxProps") or 24)
                ]
                targets = chars + scenes + props
                total_n = len(targets)
                _log(
                    job,
                    f"素材出图共 {total_n} 张（角色 {len(chars)} + 场景 {len(scenes)} + 道具 {len(props)}）",
                )
                _set_step(job, "entities", "running", f"0/{total_n}")
                _save_job(store, project_id, job)

                def _ent_live(eid: str) -> dict[str, Any] | None:
                    st2 = store.load(project_id) or {}
                    return next(
                        (
                            x
                            for x in (st2.get("entities") or [])
                            if x.get("id") == eid and not x.get("deletedAt")
                        ),
                        None,
                    )

                def _ent_qa_ok(ent: dict[str, Any] | None) -> bool:
                    if not ent or not ent.get("selectedImageId"):
                        return False
                    img = next(
                        (
                            i
                            for i in (ent.get("images") or [])
                            if i.get("id") == ent.get("selectedImageId")
                        ),
                        None,
                    )
                    if not img:
                        return False
                    if img.get("qaPass") is True:
                        return True
                    if not opts.get("requireEntityQa", True):
                        return True
                    qa = img.get("qa") or {}
                    if qa.get("skipped"):
                        return True
                    return False

                ok_n = sum(1 for e in targets if _ent_qa_ok(_ent_live(str(e.get("id")))))
                for idx, ent in enumerate(targets, start=1):
                    eid = str(ent.get("id") or "")
                    name = ent.get("name") or eid
                    kind_label = {"character": "角色", "scene": "场景", "prop": "道具"}.get(
                        ent.get("kind"), "素材"
                    )
                    live = _ent_live(eid)
                    if _ent_qa_ok(live):
                        _log(job, f"素材图已达标，跳过 {idx}/{total_n}：{name}")
                        _set_step(job, "entities", "running", f"{ok_n}/{total_n} · 已有「{name}」")
                        _save_job(store, project_id, job)
                        continue
                    # Injury ladder already exhausted — do not burn more attempts on re-runs.
                    live_img = None
                    if live and live.get("selectedImageId"):
                        live_img = next(
                            (
                                i
                                for i in (live.get("images") or [])
                                if i.get("id") == live.get("selectedImageId")
                            ),
                            None,
                        )
                    if live and live.get("qaFailed") and ((live_img or {}).get("qa") or {}).get(
                        "ladderExhausted"
                    ):
                        _log(
                            job,
                            f"素材策略梯已用尽，跳过重试 {idx}/{total_n}：{name}",
                            ok=False,
                        )
                        _set_step(job, "entities", "running", f"{ok_n}/{total_n} · 「{name}」已用尽")
                        _save_job(store, project_id, job)
                        continue
                    t0 = time.time()
                    _set_step(
                        job,
                        "entities",
                        "running",
                        f"{idx - 1}/{total_n} · 正在生成{kind_label}「{name}」",
                    )
                    _log(job, f"开始出图 {idx}/{total_n}：{kind_label}「{name}」…")
                    _save_job(store, project_id, job)
                    try:
                        version = generate_entity_image(
                            store,
                            project_id,
                            eid,
                            force_illustration=bool(opts.get("forceIllustration")),
                        )
                        took = int(time.time() - t0)
                        qa = (version or {}).get("qa") or {}
                        if (version or {}).get("qaPass"):
                            ok_n += 1
                            _log(
                                job,
                                f"素材图达标 {idx}/{total_n}：{name}（{took}s, score={qa.get('score')}, attempts={qa.get('attempts')}）",
                            )
                        else:
                            _log(
                                job,
                                f"素材图未达标 {idx}/{total_n}：{name}（{took}s, reason={qa.get('reason')}）",
                                ok=False,
                            )
                        _set_step(job, "entities", "running", f"{ok_n}/{total_n} · 「{name}」")
                        _save_job(store, project_id, job)
                    except Exception as exc:
                        took = int(time.time() - t0)
                        _log(job, f"素材图失败 {idx}/{total_n}（{name}，{took}s）：{exc}", ok=False)
                        _set_step(job, "entities", "running", f"{ok_n}/{total_n} · 「{name}」失败")
                        _save_job(store, project_id, job)

                ok_n = sum(1 for e in targets if _ent_qa_ok(_ent_live(str(e.get("id")))))
                char_ok = sum(1 for e in chars if _ent_qa_ok(_ent_live(str(e.get("id")))))
                if total_n and ok_n < total_n:
                    if opts.get("requireEntityQa", True) and char_ok < 1:
                        _set_step(job, "entities", "failed", f"{ok_n}/{total_n}")
                        raise RuntimeError(
                            f"素材质检未达标（{ok_n}/{total_n}，角色达标 {char_ok}/{len(chars)}）。"
                            "已阻断出片；请检查 Comfy 出图/视觉 QA 后重试。"
                        )
                    _log(
                        job,
                        f"素材出图部分达标（{ok_n}/{total_n}，角色 {char_ok}/{len(chars)}），继续分镜",
                        ok=False,
                    )
                    _set_step(job, "entities", "done", f"{ok_n}/{total_n} partial")
                else:
                    _set_step(job, "entities", "done", f"{ok_n}/{total_n}")
            else:
                _set_step(job, "entities", "skipped")
                _log(job, "跳过素材出图，后续视频将尽量纯文本生成")
            _save_job(store, project_id, job)

        target_ids = {str(e.get("id")) for e in target_eps if e.get("id")}
        max_shots = max(12, min(30, int(opts.get("maxShots") or 24)))

        # 5) storyboard — every target episode
        if not _step_finished(job, "storyboard"):
            _set_step(job, "storyboard", "running")
            _log(job, f"正在为 {len(target_eps)} 集拆分镜…")
            _save_job(store, project_id, job)
            total_shots = 0
            # SceneMixer floor: skip only when an episode already has a dense board.
            density_floor = max(12, min(max_shots, 12))
            for ep in target_eps:
                eid = str(ep.get("id") or "")
                if not eid:
                    continue
                state = store.load(project_id) or {}
                existing = [
                    s
                    for s in (state.get("shots") or [])
                    if s.get("episodeId") == eid and not s.get("deletedAt")
                ]
                existing_dur = sum(int(s.get("duration") or 0) for s in existing)
                if existing and len(existing) >= density_floor and existing_dur >= 180:
                    total_shots += min(len(existing), max_shots)
                    _log(
                        job,
                        f"第{ep.get('episodeNumber')}集已有密分镜（{len(existing)} 镜 / {existing_dur}s），跳过",
                    )
                    continue
                if existing:
                    _log(
                        job,
                        f"第{ep.get('episodeNumber')}集原分镜过稀（{len(existing)} 镜 / {existing_dur}s），按 12–30 镜 / 3–6 分钟重拆…",
                    )
                _log(job, f"拆分镜：第{ep.get('episodeNumber')}集《{ep.get('title') or ''}》…")
                _set_step(job, "storyboard", "running", f"第{ep.get('episodeNumber')}集")
                _save_job(store, project_id, job)
                shots = generate_storyboard(store, project_id, eid)
                if len(shots) > max_shots:
                    keep_ids = {s["id"] for s in shots[:max_shots]}
                    state = store.load(project_id) or {}
                    trimmed = []
                    for s in state.get("shots") or []:
                        if s.get("episodeId") != eid:
                            trimmed.append(s)
                        elif s.get("id") in keep_ids:
                            trimmed.append(s)
                        else:
                            trimmed.append({**s, "deletedAt": _now()})
                    state["shots"] = trimmed
                    store.save(state)
                    shots = shots[:max_shots]
                    _log(job, f"第{ep.get('episodeNumber')}集仅保留前 {max_shots} 镜")
                shot_dur = sum(int(s.get("duration") or 0) for s in shots)
                total_shots += len(shots)
                _log(
                    job,
                    f"第{ep.get('episodeNumber')}集分镜完成：{len(shots)} 镜 / 约 {shot_dur}s",
                )
            _set_step(job, "storyboard", "done", f"{len(target_eps)} 集 / {total_shots} 镜")
            _log(job, f"全部分镜完成：{len(target_eps)} 集共 {total_shots} 镜")
            _save_job(store, project_id, job)

        state = store.load(project_id) or {}
        shots = [
            s
            for s in (state.get("shots") or [])
            if s.get("episodeId") in target_ids and not s.get("deletedAt")
        ]
        # Cap per episode for resume / video stage.
        by_ep: dict[str, list[dict[str, Any]]] = {}
        for s in shots:
            by_ep.setdefault(str(s.get("episodeId")), []).append(s)
        capped: list[dict[str, Any]] = []
        for eid, group in by_ep.items():
            group.sort(key=lambda x: int(x.get("shotOrder") or 0))
            capped.extend(group[:max_shots])
        shots = capped

        # 6) videos — segment leads with prompt-fit QA revise loop
        if not _step_finished(job, "videos"):
            _set_step(job, "videos", "running")
            models = seedance_models() or []
            model = str(opts.get("model") or "").strip()
            if not model:
                try:
                    model = resolve_video_model("")
                except Exception:
                    model = ""
            if not model:
                pro = next(
                    (
                        m
                        for m in models
                        if "fast" not in str(m.get("id") or "").lower()
                        and "mini" not in str(m.get("id") or "").lower()
                    ),
                    None,
                )
                fast = next((m for m in models if "fast" in str(m.get("id") or "")), None)
                model = (pro or fast or (models[0] if models else {})).get("id") or "MiniMax-Hailuo-02 / H3"
            resolution = str(opts.get("resolution") or "720p")
            text_only = bool(opts.get("textOnlyVideo"))
            require_vqa = bool(opts.get("requireVideoQa", True))

            # Prefer segment-level generation (SceneMixer desk); fall back to per-shot.
            segment_jobs: list[dict[str, Any]] = []
            for ep in target_eps:
                eid = str(ep.get("id") or "")
                if not eid:
                    continue
                ep_shots = [
                    s
                    for s in shots
                    if str(s.get("episodeId") or "") == eid and not s.get("deletedAt")
                ]
                segs = group_shots_by_segment(ep_shots)
                if segs:
                    for seg in segs:
                        segment_jobs.append(
                            {
                                "episodeId": eid,
                                "episodeNumber": ep.get("episodeNumber"),
                                "segmentOrder": int(seg.get("segmentOrder") or 0),
                                "leadId": str((seg.get("lead") or {}).get("id") or ""),
                            }
                        )
                else:
                    for s in ep_shots:
                        if s.get("isSegmentLead") or int(s.get("beatIndex") or 0) in {0, 1}:
                            segment_jobs.append(
                                {
                                    "episodeId": eid,
                                    "episodeNumber": ep.get("episodeNumber"),
                                    "segmentOrder": int(s.get("segmentOrder") or s.get("shotOrder") or 0),
                                    "leadId": str(s.get("id") or ""),
                                    "shotOnly": True,
                                }
                            )

            total_segs = len(segment_jobs) or len(shots)
            _log(
                job,
                f"开始生成视频：{len(target_eps)} 集 / {total_segs} 段"
                f"（model={model}, {resolution}, QA={'on' if require_vqa else 'off'}）…",
            )
            _save_job(store, project_id, job)

            ok_vids = 0
            fail_vids = 0
            if segment_jobs and require_vqa:
                from drama_service import entity_ref_qa_blockers, fill_entity_stills

                remaining = list(segment_jobs)
                cycles = 0
                while remaining:
                    if _job_cancelled(store, project_id, job_id):
                        _log(job, "全流程已暂停，停止出片循环")
                        return
                    cycles += 1
                    deferred: list[dict[str, Any]] = []
                    state = store.load(project_id) or {}
                    entities = {
                        e["id"]: e for e in (state.get("entities") or []) if not e.get("deletedAt")
                    }
                    for job_seg in remaining:
                        if _job_cancelled(store, project_id, job_id):
                            _log(job, "全流程已暂停，停止出片循环")
                            return
                        so = int(job_seg.get("segmentOrder") or 0)
                        eid = str(job_seg.get("episodeId") or "")
                        epn = job_seg.get("episodeNumber")
                        ep_shots = [
                            s
                            for s in (state.get("shots") or [])
                            if str(s.get("episodeId") or "") == eid
                            and int(s.get("segmentOrder") or 0) == so
                            and not s.get("deletedAt")
                        ]
                        ref_ids: list[str] = []
                        for s in ep_shots:
                            for rid in s.get("referenceEntityIds") or []:
                                if rid not in ref_ids:
                                    ref_ids.append(rid)
                        blockers = entity_ref_qa_blockers(entities, ref_ids) if not text_only else []
                        if blockers:
                            try:
                                fill_entity_stills(
                                    store,
                                    project_id,
                                    entity_ids=[str(b.get("entityId") or "") for b in blockers],
                                    kinds=["character", "scene", "prop"],
                                    only_missing=True,
                                    wait_generate=False,
                                )
                            except Exception as exc:
                                _log(job, f"第{epn}集段{so} 出图提交失败：{exc}", ok=False)
                            names = "、".join(
                                str(b.get("name") or b.get("entityId") or "") for b in blockers[:4]
                            )
                            deferred.append(job_seg)
                            _set_step(
                                job,
                                "videos",
                                "running",
                                f"先出图 {len(remaining) - len(deferred)}/{total_segs} · 第{epn}集段{so} 等 {names}",
                            )
                            _save_job(store, project_id, job)
                            continue
                        _set_step(job, "videos", "running", f"出片 {ok_vids}/{total_segs} · 第{epn}集段{so}")
                        _log(job, f"出片+质检：第{epn}集 · 片段 {so}…")
                        _save_job(store, project_id, job)
                        try:
                            if job_seg.get("shotOnly") and job_seg.get("leadId"):
                                start_shot_video(
                                    store,
                                    project_id,
                                    str(job_seg["leadId"]),
                                    model=model,
                                    resolution=resolution,
                                    skip_refs=text_only,
                                )
                                finished = _wait_shots(
                                    store,
                                    project_id,
                                    [str(job_seg["leadId"])],
                                    timeout_s=1200,
                                    job=job,
                                )
                                lead = finished[0] if finished else {}
                                if lead.get("status") == "success":
                                    ok_vids += 1
                                else:
                                    fail_vids += 1
                                    deferred.append(job_seg)
                                    _log(
                                        job,
                                        f"片段失败 第{epn}集段{so}：{lead.get('error')}",
                                        ok=False,
                                    )
                            else:
                                ensure_segment_video_qa(
                                    store,
                                    project_id,
                                    eid,
                                    so,
                                    model=model,
                                    resolution=resolution,
                                    skip_refs=text_only,
                                )
                                ok_vids += 1
                                _log(job, f"片段达标：第{epn}集 · 片段 {so}")
                        except Exception as exc:
                            fail_vids += 1
                            deferred.append(job_seg)
                            _log(job, f"片段未达标：第{epn}集段{so} — {exc}", ok=False)
                        _set_step(job, "videos", "running", f"{ok_vids}/{total_segs}")
                        _save_job(store, project_id, job)
                        state = store.load(project_id) or state
                        entities = {
                            e["id"]: e
                            for e in (state.get("entities") or [])
                            if not e.get("deletedAt")
                        }
                    if not deferred:
                        break
                    _log(
                        job,
                        f"本轮还有 {len(deferred)}/{total_segs} 段未达标，继续出图或重试（第 {cycles} 轮）",
                        ok=False,
                    )
                    _set_step(job, "videos", "running", f"循环 {ok_vids}/{total_segs} · 剩余 {len(deferred)}")
                    _save_job(store, project_id, job)
                    remaining = deferred
                    time.sleep(20)
            else:
                # Legacy per-shot path (no segment QA)
                shot_ids = [s["id"] for s in shots]
                wait_s = min(7200, max(1200, 180 * max(1, len(shot_ids))))
                for shot in shots:
                    status = shot.get("status")
                    if status in {"success", "generating"} and (
                        shot.get("selectedVideoId") or shot.get("providerTaskId")
                    ):
                        continue
                    try:
                        start_shot_video(
                            store,
                            project_id,
                            shot["id"],
                            model=model,
                            resolution=resolution,
                            skip_refs=text_only,
                        )
                    except Exception as exc:
                        _log(job, f"提交镜头失败：{exc}", ok=False)
                    time.sleep(1.5)
                finished = _wait_shots(store, project_id, shot_ids, timeout_s=wait_s, job=job)
                ok_vids = sum(
                    1 for s in finished if s.get("status") == "success" and s.get("selectedVideoId")
                )
                fail_vids = sum(1 for s in finished if s.get("status") == "failed")
                total_segs = len(shot_ids)

            _log(job, f"视频阶段结束：成功 {ok_vids}/{total_segs}，失败 {fail_vids}")
            if ok_vids <= 0:
                _set_step(job, "videos", "failed", f"成功 {ok_vids}/{total_segs}")
                raise RuntimeError(
                    f"分镜视频全部失败（成功 {ok_vids}/{total_segs}），已停止配音与导出。"
                )
            if ok_vids < total_segs:
                _log(
                    job,
                    f"部分片段失败（成功 {ok_vids}/{total_segs}），继续用成功片段配音/导出",
                    ok=False,
                )
            _set_step(job, "videos", "done", f"{ok_vids}/{total_segs}")
            _save_job(store, project_id, job)

        # 7) audio — BGM per episode (optional forced TTS dub)
        if not _step_finished(job, "audio"):
            if not opts.get("skipAudio"):
                _set_step(job, "audio", "running")
                force_dub = bool(opts.get("forceDubbing"))
                try:
                    for ep in target_eps:
                        eid = str(ep.get("id") or "")
                        if not eid:
                            continue
                        state = store.load(project_id) or {}
                        ep_shots = [
                            s
                            for s in (state.get("shots") or [])
                            if s.get("episodeId") == eid and not s.get("deletedAt")
                        ]
                        if not ep_shots:
                            continue
                        has_inline = any(str(s.get("dialogue") or "").strip() for s in ep_shots)
                        audios = [a for a in (state.get("audios") or []) if a.get("episodeId") != eid]
                        total_dur = sum(max(4, int(s.get("duration") or 7)) for s in ep_shots) or 40
                        bgm_rel = f"media/audio/{eid}-bgm.mp3"
                        bgm_meta = generate_bgm_mp3(
                            store._dir(project_id) / bgm_rel,
                            duration_sec=max(24.0, float(total_dur) + 6),
                            mood="drama",
                        )
                        store.persist_media(project_id, bgm_rel)
                        audios.append(
                            {
                                "id": f"{eid}-bgm",
                                "episodeId": eid,
                                "kind": "bgm",
                                "path": bgm_rel,
                                "url": f"/api/media/{project_id}/{bgm_rel}",
                                "provider": bgm_meta.get("provider"),
                                "bytes": bgm_meta.get("bytes"),
                                "updatedAt": _now(),
                            }
                        )
                        if force_dub and not has_inline:
                            lines = dialogue_lines_for_episode((ep or {}).get("content") or "", ep_shots)
                            if lines:
                                _log(job, f"第{ep.get('episodeNumber')}集：合成分角色配音…")
                                rel = f"media/audio/{eid}.mp3"
                                out = store._dir(project_id) / rel
                                meta = synthesize_dialogue_mp3(lines, out)
                                store.persist_media(project_id, rel)
                                audios.append(
                                    {
                                        "id": eid,
                                        "episodeId": eid,
                                        "kind": "dialogue",
                                        "path": rel,
                                        "url": f"/api/media/{project_id}/{rel}",
                                        "lines": len(lines),
                                        "mode": meta.get("mode") or "dialogue",
                                        "voices": meta.get("voices") or [],
                                        "provider": meta.get("provider"),
                                        "bytes": meta.get("bytes"),
                                        "updatedAt": _now(),
                                    }
                                )
                        state = store.load(project_id) or {}
                        state["audios"] = audios
                        store.save(state)
                        _log(job, f"第{ep.get('episodeNumber')}集配乐完成")
                    _set_step(job, "audio", "done", f"{len(target_eps)} 集 BGM")
                    _log(job, f"配乐完成：{len(target_eps)} 集")
                except Exception as exc:
                    _set_step(job, "audio", "failed", str(exc)[:120])
                    raise RuntimeError(f"配乐未完成，已停止导出：{exc}") from exc
            else:
                _set_step(job, "audio", "skipped")
            _save_job(store, project_id, job)

        # 8) export — one final cut per episode
        if not _step_finished(job, "export"):
            if not opts.get("skipExport"):
                _set_step(job, "export", "running")
                _log(job, f"正在剪辑导出 {len(target_eps)} 集成片…")
                _save_job(store, project_id, job)
                exports: list[dict[str, Any]] = list(job.get("exports") or [])
                exported_ids = {str(x.get("episodeId")) for x in exports if x.get("episodeId")}
                for ep in target_eps:
                    eid = str(ep.get("id") or "")
                    if not eid:
                        continue
                    if eid in exported_ids:
                        _log(job, f"第{ep.get('episodeNumber')}集已有成片，跳过")
                        continue
                    state = store.load(project_id) or {}
                    ep_shots = [
                        s
                        for s in (state.get("shots") or [])
                        if s.get("episodeId") == eid and not s.get("deletedAt")
                    ]
                    ready = [
                        s
                        for s in ep_shots
                        if s.get("status") == "success" and s.get("selectedVideoId")
                    ]
                    if not ready:
                        _log(
                            job,
                            f"第{ep.get('episodeNumber')}集无可用视频，跳过导出",
                            ok=False,
                        )
                        continue
                    if len(ready) < len(ep_shots):
                        _log(
                            job,
                            f"第{ep.get('episodeNumber')}集部分镜头无视频（{len(ready)}/{len(ep_shots)}），仅用成功镜头导出",
                            ok=False,
                        )
                    _set_step(job, "export", "running", f"第{ep.get('episodeNumber')}集")
                    _save_job(store, project_id, job)
                    ensure_edit_draft(store, project_id, eid)
                    result = export_edit_mp4(store, project_id, eid)
                    if not (result.get("path") or result.get("url")):
                        _log(job, f"第{ep.get('episodeNumber')}集导出未返回路径", ok=False)
                        continue
                    item = {
                        "episodeId": eid,
                        "episodeNumber": ep.get("episodeNumber"),
                        "title": ep.get("title") or "",
                        "path": result.get("path") or "",
                        "url": result.get("url") or "",
                    }
                    exports.append(item)
                    exported_ids.add(eid)
                    job["exports"] = exports
                    job["exportPath"] = item["path"]
                    job["exportUrl"] = item["url"]
                    _log(job, f"第{ep.get('episodeNumber')}集成片：{item['url'] or item['path']}")
                    _save_job(store, project_id, job)
                if not exports:
                    raise RuntimeError("导出失败：没有任何成片")
                job["exports"] = exports
                job["exportPath"] = exports[0].get("path") or ""
                job["exportUrl"] = exports[0].get("url") or ""
                # Continuous play: stitch all episode finals into one series file.
                if len(exports) >= 2:
                    _log(job, f"正在拼接 {len(exports)} 集为连续播放成片…")
                    _save_job(store, project_id, job)
                    series = _concat_series_exports(store, project_id, exports)
                    if series:
                        job["seriesPath"] = series["path"]
                        job["seriesUrl"] = series["url"]
                        job["exportPath"] = series["path"]
                        job["exportUrl"] = series["url"]
                        _log(job, f"连续播放成片已就绪：{series['url']}")
                    else:
                        _log(job, "连续拼接未完成（将保留分集成片）", ok=False)
                _set_step(job, "export", "done", f"{len(exports)}/{len(target_eps)} 集成片")
                _log(job, f"成片导出完成：{len(exports)}/{len(target_eps)} 集")
            else:
                _set_step(job, "export", "skipped")

        job["status"] = "success"
        job["error"] = None
        n_done = len(job.get("exports") or []) or len(target_eps)
        _log(job, f"全流程完成：{n_done} 集短剧" + (f"；连续播放 {job.get('seriesUrl')}" if job.get("seriesUrl") else ""))
        _save_job(store, project_id, job)
    except Exception as exc:
        job["status"] = "failed"
        job["error"] = str(exc)
        if job.get("step"):
            _set_step(job, str(job["step"]), "failed", str(exc)[:160])
        _log(job, f"全流程失败：{exc}", ok=False)
        try:
            _save_job(store, project_id, job)
        except Exception:
            pass
    finally:
        with _WORKERS_LOCK:
            current = _WORKERS.get(project_id)
            if current is threading.current_thread():
                _WORKERS.pop(project_id, None)
