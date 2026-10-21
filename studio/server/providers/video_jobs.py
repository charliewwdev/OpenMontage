"""Shot-video job runners. One function per backend, registered by id."""

from __future__ import annotations

from pathlib import Path
from typing import Any

_READY = False


def ensure_registered() -> None:
    global _READY
    if _READY:
        return
    from .video_factory import register_video_job

    register_video_job("comfyui", run_comfy_shot)
    register_video_job("seedance", run_seedance_shot)
    _READY = True


def run_comfy_shot(
    *,
    store: Any,
    project_id: str,
    shot_id: str,
    model: str,
    resolution: str,
    base_prompt: str = "",
    ratio: str = "9:16",
    duration: int = 5,
    ref_path: str | None = None,
    end_ref_path: str | None = None,
    use_turbo: bool = True,
    **_: Any,
) -> None:
    from drama_service import _judge_video_file, _now, _propagate_segment_video, new_id
    from media_qa import assert_media_ok
    from providers.media import generate_video_file

    try:
        vid_id = new_id("vid_")
        rel = f"media/videos/{vid_id}.mp4"
        dest = store._dir(project_id) / rel
        ref = Path(ref_path) if ref_path else None
        end_ref = Path(end_ref_path) if end_ref_path else None
        result = generate_video_file(
            prompt=base_prompt,
            ratio=ratio or "9:16",
            duration=int(duration or 5),
            out_path=dest,
            reference_path=ref if ref and ref.is_file() else None,
            end_reference_path=end_ref if end_ref and end_ref.is_file() else None,
            resolution=resolution or "720p",
            use_turbo=bool(use_turbo),
        )
        assert_media_ok(dest, unlink_on_fail=True)
        if dest.is_file():
            store.persist_media(project_id, rel)
        st = store.load(project_id)
        sh = next((x for x in (st.get("shots") or []) if x["id"] == shot_id), None) if st else None
        if not sh:
            return
        prompt_used = base_prompt or sh.get("prompt") or ""
        ents_alive = [e for e in (st.get("entities") or []) if not e.get("deletedAt")]
        by_id = {e["id"]: e for e in ents_alive}
        ref_ents = [by_id[eid] for eid in (sh.get("referenceEntityIds") or []) if eid in by_id]
        # First/last-frame idlock is identity-locked by construction — skip vision QA gate.
        portrait = (
            (st.get("project") or {}).get("workflow") == "portrait-match"
            or sh.get("idlock")
            or sh.get("skipVideoQa")
            or bool(end_ref and end_ref.is_file())
        )
        if portrait:
            # Intentional bypass (idlock) — do NOT set skipped=True; UI treats skipped as soft-fail「质检未过」.
            qa = {
                "pass": True,
                "score": 1.0,
                "reason": "portrait-idlock",
                "skipped": False,
                "qaPass": True,
                "bypass": "portrait-idlock",
            }
        else:
            qa = _judge_video_file(dest, prompt=prompt_used, entities=ref_ents)
        version = {
            "id": vid_id,
            "shotId": shot_id,
            "path": rel if dest.is_file() else None,
            "providerTaskId": None,
            "model": result.get("model") or "minimax-h3",
            "backend": "comfyui",
            "duration": float(result.get("duration") or duration),
            "resolution": result.get("resolution") or resolution,
            "prompt": prompt_used,
            "qa": qa,
            "qaPass": bool(qa.get("qaPass")),
            "rating": None,
            "note": "",
            "createdAt": _now(),
        }
        sh.setdefault("videos", []).append(version)
        sh["selectedVideoId"] = vid_id
        sh["providerTaskId"] = None
        sh["staleReason"] = None
        sh["updatedAt"] = _now()
        sh.pop("_segmentPromptOverride", None)
        sh.pop("_segmentDurationOverride", None)
        if version["qaPass"]:
            sh["status"] = "success"
            sh["error"] = None
        else:
            sh["status"] = "failed"
            sh["error"] = f"质检未达标: {qa.get('reason') or 'mismatch'}"
        _propagate_segment_video(st, sh)
        store.save(st)
        if version.get("qaPass") and version.get("path"):
            try:
                from cover_service import maybe_set_cover_from_shot_video

                maybe_set_cover_from_shot_video(store, project_id, version.get("path"))
            except Exception:
                pass
    except Exception as exc:
        st = store.load(project_id)
        sh = next((x for x in (st.get("shots") or []) if x["id"] == shot_id), None) if st else None
        if sh:
            sh["status"] = "failed"
            sh["error"] = str(exc)
            sh["updatedAt"] = _now()
            _propagate_segment_video(st, sh)
            store.save(st)


def run_seedance_shot(
    *,
    store: Any,
    project_id: str,
    shot_id: str,
    model: str,
    resolution: str,
    base_prompt: str = "",
    seedance_task_id: str | None = None,
    **_: Any,
) -> None:
    import time

    from drama_service import _download, _judge_video_file, _now, _propagate_segment_video, new_id
    from providers.seedance import query_task

    task_id = seedance_task_id
    if not task_id:
        st0 = store.load(project_id)
        sh0 = next((x for x in (st0.get("shots") or []) if x["id"] == shot_id), None) if st0 else None
        task_id = (sh0 or {}).get("providerTaskId")
    if not task_id:
        st = store.load(project_id)
        sh = next((x for x in (st.get("shots") or []) if x["id"] == shot_id), None) if st else None
        if sh:
            sh["status"] = "failed"
            sh["error"] = "missing seedance task id"
            sh["updatedAt"] = _now()
            _propagate_segment_video(st, sh)
            store.save(st)
        return

    for _ in range(120):
        try:
            st = store.load(project_id)
            sh = next((x for x in (st.get("shots") or []) if x["id"] == shot_id), None) if st else None
            if not sh:
                return
            result = query_task(task_id)
            status = result.get("status")
            if status in {"succeeded"}:
                vid_id = new_id("vid_")
                rel = f"media/videos/{vid_id}.mp4"
                dest = store._dir(project_id) / rel
                if result.get("videoUrl"):
                    _download(result["videoUrl"], dest)
                    if dest.is_file():
                        store.persist_media(project_id, rel)
                prompt_used = (sh.get("_segmentPromptOverride") or sh.get("prompt") or base_prompt or "").strip()
                ents_alive = [e for e in (st.get("entities") or []) if not e.get("deletedAt")]
                by_id = {e["id"]: e for e in ents_alive}
                ref_ents = [by_id[eid] for eid in (sh.get("referenceEntityIds") or []) if eid in by_id]
                qa = (
                    _judge_video_file(dest, prompt=prompt_used, entities=ref_ents)
                    if dest.is_file()
                    else {
                        "pass": False,
                        "score": 0,
                        "reason": "missing_file",
                        "skipped": False,
                        "qaPass": False,
                    }
                )
                version = {
                    "id": vid_id,
                    "shotId": shot_id,
                    "path": rel if dest.is_file() else None,
                    "providerTaskId": task_id,
                    "model": model,
                    "backend": "seedance",
                    "duration": float(result.get("duration") or sh.get("duration") or 5),
                    "resolution": result.get("resolution") or resolution,
                    "prompt": prompt_used,
                    "qa": qa,
                    "qaPass": bool(qa.get("qaPass")),
                    "rating": None,
                    "note": "",
                    "createdAt": _now(),
                }
                sh.setdefault("videos", []).append(version)
                sh["selectedVideoId"] = vid_id
                sh["staleReason"] = None
                sh["providerTaskId"] = task_id
                sh["updatedAt"] = _now()
                sh.pop("_segmentPromptOverride", None)
                sh.pop("_segmentDurationOverride", None)
                if version["qaPass"]:
                    sh["status"] = "success"
                    sh["error"] = None
                else:
                    sh["status"] = "failed"
                    sh["error"] = f"质检未达标: {qa.get('reason') or 'mismatch'}"
                _propagate_segment_video(st, sh)
                store.save(st)
                if version.get("qaPass") and version.get("path"):
                    try:
                        from cover_service import maybe_set_cover_from_shot_video

                        maybe_set_cover_from_shot_video(store, project_id, version.get("path"))
                    except Exception:
                        pass
                return
            if status in {"failed", "expired", "cancelled"}:
                sh["status"] = "failed"
                sh["error"] = result.get("error") or status
                sh["updatedAt"] = _now()
                _propagate_segment_video(st, sh)
                store.save(st)
                return
        except Exception as exc:
            st = store.load(project_id)
            sh = next((x for x in (st.get("shots") or []) if x["id"] == shot_id), None) if st else None
            if sh:
                sh["status"] = "failed"
                sh["error"] = str(exc)
                sh["updatedAt"] = _now()
                _propagate_segment_video(st, sh)
                store.save(st)
            return
        time.sleep(5)

    st = store.load(project_id)
    sh = next((x for x in (st.get("shots") or []) if x["id"] == shot_id), None) if st else None
    if sh and sh.get("status") == "generating":
        sh["status"] = "failed"
        sh["error"] = "生成超时"
        sh["updatedAt"] = _now()
        _propagate_segment_video(st, sh)
        store.save(st)
