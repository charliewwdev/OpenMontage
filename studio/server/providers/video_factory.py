"""Video backends. Register a new clip provider here; callers look up by id."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from .registry import Registry


def _secret(name: str, default: str = "") -> str:
    try:
        from settings_store import get_secret

        return (get_secret(name, default) or default or "").strip()
    except Exception:
        return default


class VideoBackend(Protocol):
    id: str

    def configured(self) -> bool: ...

    def unavailable_message(self) -> str: ...

    def resolve_model(self, requested: str) -> str: ...

    def submit(self, **kwargs: Any) -> None: ...


VIDEO_BACKENDS: Registry[VideoBackend] = Registry()
VIDEO_JOBS: Registry[Any] = Registry()


class ComfyVideoBackend:
    id = "comfyui"

    def configured(self) -> bool:
        try:
            from .comfyui import configured as comfy_ok

            return bool(comfy_ok(capability="video") or comfy_ok())
        except Exception:
            return False

    def unavailable_message(self) -> str:
        return "顶部已选择 ComfyUI 出片，但租机地址不可用。请检查 COMFYUI_SERVER_URL。"

    def resolve_model(self, requested: str) -> str:
        req = (requested or "").strip()
        if req.lower().startswith("comfyui:"):
            return req.split(":", 1)[-1]
        return _secret("COMFYUI_VIDEO_MODEL") or "MiniMax-Hailuo-02 / H3"

    def submit(self, **kwargs: Any) -> None:
        from job_queue import enqueue

        enqueue("shot_video", kwargs["payload"])

    def render_file(
        self,
        *,
        prompt: str,
        ratio: str,
        duration: float | int,
        out_path: Path,
        reference_path: Path | None = None,
        end_reference_path: Path | None = None,
        resolution: str = "720p",
        use_turbo: bool = True,
    ) -> dict:
        """Sync render. Does not re-read STUDIO_VIDEO_BACKEND (a flaky probe must not swap providers)."""
        from .comfyui import generate_video as comfy_generate

        path, model_label = comfy_generate(
            prompt=prompt,
            ratio=ratio,
            duration=duration,
            out_path=out_path,
            reference_path=reference_path,
            end_reference_path=end_reference_path,
            resolution=resolution,
            use_turbo=use_turbo,
        )
        return {
            "backend": self.id,
            "path": path,
            "providerTaskId": None,
            "model": model_label or "minimax-h3",
            "duration": float(duration),
            "resolution": resolution,
        }


class SeedanceVideoBackend:
    id = "seedance"

    def configured(self) -> bool:
        try:
            from . import seedance_configured

            return bool(seedance_configured())
        except Exception:
            return False

    def unavailable_message(self) -> str:
        return "顶部已选择 Seedance 出片，但火山 Key 不可用。请续费/换 Key，或主动切换到 ComfyUI。"

    def resolve_model(self, requested: str) -> str:
        req = (requested or "").strip()
        if req and not req.lower().startswith("comfyui:"):
            return req.split(":", 1)[-1] if req.startswith("seedance:") else req
        return _secret("SEEDANCE_MODEL") or ""

    def submit(self, **kwargs: Any) -> None:
        from job_queue import enqueue
        from .seedance import create_task

        store = kwargs["store"]
        shot = kwargs["shot"]
        state = kwargs["state"]
        payload = kwargs["payload"]
        task_id = create_task(
            model=kwargs["model"],
            content=kwargs["content"],
            ratio=kwargs["ratio"],
            resolution=kwargs["resolution"],
            duration=kwargs["duration"],
        )
        shot["providerTaskId"] = task_id
        from drama_service import _now

        shot["updatedAt"] = _now()
        store.save(state)
        payload["seedanceTaskId"] = task_id
        enqueue("shot_video", payload)


VIDEO_BACKENDS.register(ComfyVideoBackend.id, ComfyVideoBackend(), priority=20)
VIDEO_BACKENDS.register(SeedanceVideoBackend.id, SeedanceVideoBackend(), priority=10)


def resolve_video_backend() -> tuple[str, VideoBackend | None]:
    preferred = (_secret("STUDIO_VIDEO_BACKEND") or "auto").lower()
    pinned = VIDEO_BACKENDS.get(preferred) if preferred not in {"", "auto"} else None
    if preferred not in {"", "auto"} and pinned is not None:
        return preferred, pinned if pinned.configured() else None
    for backend in VIDEO_BACKENDS.all():
        if backend.configured():
            return preferred, backend
    return preferred, None


def video_backend() -> str:
    _preferred, backend = resolve_video_backend()
    return backend.id if backend is not None else "none"


def require_video_backend(backend_id: str) -> VideoBackend:
    backend = VIDEO_BACKENDS.get(backend_id)
    if backend is None:
        raise RuntimeError(f"未注册的出片后端: {backend_id}")
    return backend


def resolve_video_model(requested: str = "") -> str:
    _preferred, backend = resolve_video_backend()
    if backend is None:
        return (requested or "").strip()
    return backend.resolve_model(requested)


def generate_video_file(
    *,
    prompt: str,
    ratio: str,
    duration: float | int,
    out_path: Path,
    reference_path: Path | None = None,
    end_reference_path: Path | None = None,
    resolution: str = "720p",
    use_turbo: bool = True,
) -> dict:
    backend = VIDEO_BACKENDS.get("comfyui")
    if backend is None or not hasattr(backend, "render_file"):
        raise RuntimeError("ComfyUI 视频后端未注册")
    return backend.render_file(
        prompt=prompt,
        ratio=ratio,
        duration=duration,
        out_path=out_path,
        reference_path=reference_path,
        end_reference_path=end_reference_path,
        resolution=resolution,
        use_turbo=use_turbo,
    )


def register_video_job(backend_id: str, runner: Any) -> None:
    VIDEO_JOBS.register(backend_id, runner, priority=0)


def run_registered_video_job(backend_id: str, **kwargs: Any) -> None:
    from .video_jobs import ensure_registered

    ensure_registered()
    key = (backend_id or "").strip().lower()
    runner = VIDEO_JOBS.get(key)
    if runner is None:
        _fail_unknown(kwargs.get("store"), kwargs.get("project_id"), kwargs.get("shot_id"), key)
        return
    runner(**kwargs)


def _fail_unknown(store: Any, project_id: str | None, shot_id: str | None, backend_id: str) -> None:
    if store is None or not project_id or not shot_id:
        raise RuntimeError(f"未注册的出片后端: {backend_id or 'none'}")
    from drama_service import _now, _propagate_segment_video

    st = store.load(project_id)
    sh = next((x for x in (st.get("shots") or []) if x["id"] == shot_id), None) if st else None
    if not sh:
        return
    sh["status"] = "failed"
    sh["error"] = f"未注册的出片后端: {backend_id or 'none'}"
    sh["updatedAt"] = _now()
    _propagate_segment_video(st, sh)
    store.save(st)
