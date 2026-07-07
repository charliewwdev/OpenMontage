"""Kling official API lip-sync provider."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from tools._kling.account import account_usage_hint_for_error, get_account_costs
from tools._kling.callbacks import validate_callback_url
from tools._kling.client import KlingClient
from tools._kling.errors import KlingAPIError
from tools._kling.media import (
    extension_from_url,
    normalize_media_input,
    numbered_output_path,
    output_path_with_suffix,
)
from tools._kling.schemas import LIP_SYNC_OPERATIONS
from tools.base_tool import (
    BaseTool,
    DependencyError,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    RetryPolicy,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolTier,
)
from tools.video._shared import probe_output


class KlingLipSync(BaseTool):
    name = "kling_lip_sync"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "avatar"
    provider = "kling_official"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = ["env:KLING_API_KEY"]
    install_instructions = (
        "Set KLING_API_KEY in .env for the official Kling API. "
        "Use identify_face first for multi-person clips, then pass face_choose or face_id."
    )
    agent_skills = ["kling-official", "avatar-video"]

    capabilities = ["lip_sync", "identify_face", "audio_video_alignment"]
    supports = {
        "lip_sync": True,
        "face_selection": True,
        "offline": False,
        "cloud_render": True,
    }
    best_for = [
        "official Kling cloud lip-sync for existing presenter video",
        "dubbing workflows that can use Kling face identification",
        "manual or explicit automatic face selection before paid lip-sync generation",
    ]
    not_good_for = [
        "fully offline lip-sync",
        "silent first-face selection in multi-person footage",
        "replacing local lip_sync behavior implicitly",
    ]
    fallback_tools = ["lip_sync"]

    input_schema = {
        "type": "object",
        "properties": {
            "operation": {"type": "string", "enum": LIP_SYNC_OPERATIONS, "default": "advanced_lip_sync"},
            "video_id": {"type": "string"},
            "video_url": {"type": "string"},
            "video_path": {
                "type": "string",
                "description": "Not silently uploaded. Provide video_url unless an official upload path is added.",
            },
            "session_id": {"type": "string"},
            "face_id": {"type": "string"},
            "face_choose": {"type": "array"},
            "auto_select_face": {
                "type": "boolean",
                "default": False,
                "description": "Explicitly allow largest-face automatic selection after identify_face.",
            },
            "audio_id": {"type": "string"},
            "sound_file": {
                "type": "string",
                "description": "Official Kling sound_file value or raw base64 audio.",
            },
            "sound_file_url": {"type": "string"},
            "sound_file_path": {"type": "string"},
            "audio_path": {
                "type": "string",
                "description": "Alias for sound_file_path for compatibility with local lip_sync.",
            },
            "faces_artifact_path": {"type": "string"},
            "callback_url": {"type": "string"},
            "external_task_id": {"type": "string"},
            "include_account_usage": {
                "type": "boolean",
                "default": False,
                "description": "Optional low-frequency account usage diagnostic; not used by default.",
            },
            "timeout_seconds": {"type": "integer", "default": 900},
            "poll_interval": {"type": "number", "default": 5.0},
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=512, vram_mb=0, disk_mb=500, network_required=True
    )
    retry_policy = RetryPolicy(
        max_retries=2,
        backoff_seconds=2.0,
        retryable_errors=["1302", "1303", "5000", "5001", "5002"],
    )
    idempotency_key_fields = ["video_id", "video_url", "session_id", "face_id", "audio_id", "sound_file_path"]
    side_effects = [
        "paid remote generation via official Kling API",
        "writes face selection artifact",
        "writes lip-synced video to output_path",
    ]
    user_visible_verification = ["Watch output video to verify the selected face matches the new audio"]
    quality_score = 0.80
    latency_p50_seconds = 240.0

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        operation = str(inputs.get("operation", "advanced_lip_sync"))
        if operation == "identify_face":
            return 0.02
        if operation == "full_lip_sync":
            return 0.34
        return 0.32

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        if inputs.get("operation") == "identify_face":
            return 15.0
        return 240.0

    def dry_run(self, inputs: dict[str, Any]) -> dict[str, Any]:
        result = super().dry_run(inputs)
        result.update(
            {
                "paid_api": True,
                "cost_estimate_confidence": "low",
                "cost_estimate_basis": "Conservative OpenMontage estimate for identify-face plus advanced lip-sync.",
            }
        )
        return result

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        try:
            self.check_dependencies()
        except DependencyError as exc:
            return ToolResult(success=False, error=str(exc))

        operation = str(inputs.get("operation") or "advanced_lip_sync")
        start = time.time()
        client = KlingClient()
        try:
            if operation == "identify_face":
                identify = self._identify_faces(client, inputs)
                return self._identify_result(inputs, identify, start)
            if operation == "full_lip_sync":
                identify = self._identify_faces(client, inputs)
                artifact_path = self._write_faces_artifact(inputs, identify)
                face_choose, selection = self._face_selection(identify["faces"], inputs)
                artifact_path = self._write_faces_artifact(inputs, identify, selection=selection)
                if selection["selection_method"] == "requires_user_selection":
                    return ToolResult(
                        success=False,
                        data={
                            "provider": self.provider,
                            "operation": operation,
                            "session_id": identify["session_id"],
                            "faces": identify["faces"],
                            "requires_face_selection": True,
                            "selection_reason": selection["selection_reason"],
                            "faces_artifact_path": str(artifact_path),
                        },
                        artifacts=[str(artifact_path)],
                        error="Multiple faces detected. Pass face_id/face_choose or set auto_select_face=True.",
                        cost_usd=self.estimate_cost({"operation": "identify_face"}),
                        duration_seconds=round(time.time() - start, 2),
                        model="kling-official-lip-sync",
                    )
                merged = {**inputs, "session_id": identify["session_id"], "face_choose": face_choose}
                request = self._build_advanced_request(merged)
                result = self._run_advanced_lip_sync(client, merged, request, start)
                result.data["faces_artifact_path"] = str(artifact_path)
                result.data["face_selection"] = selection
                result.artifacts.append(str(artifact_path))
                return result
            if operation == "advanced_lip_sync":
                request = self._build_advanced_request(inputs)
                return self._run_advanced_lip_sync(client, inputs, request, start)
            raise ValueError(f"Unsupported Kling lip-sync operation: {operation}")
        except (KlingAPIError, TimeoutError, ValueError, KeyError, FileNotFoundError) as exc:
            data: dict[str, Any] = {"provider": self.provider}
            if isinstance(exc, KlingAPIError):
                data.update(
                    {
                        "error_code": exc.code,
                        "request_id": exc.request_id,
                        "http_status": exc.http_status,
                        "account_usage_diagnostic": account_usage_hint_for_error(exc),
                    }
                )
            return ToolResult(success=False, data=data, error=f"Kling official lip-sync failed: {exc}")
        except Exception as exc:
            return ToolResult(success=False, data={"provider": self.provider}, error=f"Kling official lip-sync failed: {exc}")

    def _identify_faces(self, client: KlingClient, inputs: dict[str, Any]) -> dict[str, Any]:
        request = self._build_identify_request(inputs)
        data = client.post(request["path"], request["payload"])
        payload = data.get("data") or {}
        session_id = payload.get("session_id")
        if not session_id:
            raise ValueError(f"Kling identify-face response missing data.session_id: {data}")
        faces = (
            payload.get("faces")
            or payload.get("face_list")
            or payload.get("face_infos")
            or payload.get("faces_info")
            or []
        )
        if not isinstance(faces, list):
            raise ValueError("Kling identify-face response face list is not a list")
        if not faces:
            raise ValueError("Kling identify-face response contained no faces")
        return {
            "session_id": str(session_id),
            "faces": faces,
            "raw_response": data,
            "request": request,
        }

    def _identify_result(self, inputs: dict[str, Any], identify: dict[str, Any], start: float) -> ToolResult:
        artifact_path = self._write_faces_artifact(inputs, identify)
        return ToolResult(
            success=True,
            data={
                "provider": self.provider,
                "model": "kling-official-lip-sync",
                "operation": "identify_face",
                "session_id": identify["session_id"],
                "faces": identify["faces"],
                "face_count": len(identify["faces"]),
                "faces_artifact_path": str(artifact_path),
            },
            artifacts=[str(artifact_path)],
            cost_usd=self.estimate_cost({"operation": "identify_face"}),
            duration_seconds=round(time.time() - start, 2),
            model="kling-official-lip-sync",
        )

    def _run_advanced_lip_sync(
        self,
        client: KlingClient,
        inputs: dict[str, Any],
        request: dict[str, Any],
        start: float,
    ) -> ToolResult:
        task_id = client.create_classic_task(request["path"], request["payload"])
        outputs = client.poll_classic(
            request["path"],
            task_id,
            "videos",
            timeout_seconds=int(inputs.get("timeout_seconds", 900)),
            poll_interval=float(inputs.get("poll_interval", 5.0)),
        )
        paths = self._download_videos(client, outputs, inputs)
        probed = probe_output(paths[0])
        return ToolResult(
            success=True,
            data={
                "provider": self.provider,
                "model": "kling-official-lip-sync",
                "task_id": task_id,
                "operation": request["operation"],
                "session_id": request["payload"]["session_id"],
                "face_choose": request["payload"]["face_choose"],
                "audio_source": request["audio_source"],
                "remote_outputs": outputs,
                "output": str(paths[0]),
                "output_path": str(paths[0]),
                "video_paths": [str(path) for path in paths],
                "format": "mp4",
                "cost_estimate_confidence": "low",
                "cost_estimate_basis": "Conservative estimate pending official account-usage reconciliation.",
                **self._account_usage_result(inputs, client),
                **self._callback_result_data(inputs, task_id),
                **probed,
            },
            artifacts=[str(path) for path in paths],
            cost_usd=self.estimate_cost(inputs),
            duration_seconds=round(time.time() - start, 2),
            model="kling-official-lip-sync",
        )

    def _build_identify_request(self, inputs: dict[str, Any]) -> dict[str, Any]:
        if inputs.get("video_path") and not (inputs.get("video_url") or inputs.get("video_id")):
            raise ValueError("Kling identify_face requires video_url or video_id; local video paths cannot be silently uploaded.")
        payload: dict[str, Any] = {}
        if inputs.get("video_id"):
            payload["video_id"] = str(inputs["video_id"])
        if inputs.get("video_url"):
            payload["video_url"] = str(inputs["video_url"])
        if not payload:
            raise ValueError("Kling identify_face requires video_id or video_url")
        return {
            "path": "/v1/videos/identify-face",
            "payload": payload,
            "operation": "identify_face",
        }

    def _build_advanced_request(self, inputs: dict[str, Any]) -> dict[str, Any]:
        session_id = str(inputs.get("session_id") or "").strip()
        if not session_id:
            raise ValueError("advanced_lip_sync requires session_id")
        face_choose = self._normalize_face_choose(inputs)
        if not face_choose:
            raise ValueError("advanced_lip_sync requires face_choose or face_id")
        payload: dict[str, Any] = {
            "session_id": session_id,
            "face_choose": face_choose,
        }
        audio_source = self._copy_audio_input(inputs, payload)
        self._copy_common_task_fields(inputs, payload)
        return {
            "protocol": "classic",
            "path": "/v1/videos/advanced-lip-sync",
            "payload": payload,
            "operation": "advanced_lip_sync",
            "model": "kling-official-lip-sync",
            "audio_source": audio_source,
        }

    @staticmethod
    def _normalize_face_choose(inputs: dict[str, Any]) -> list[dict[str, Any]]:
        if inputs.get("face_choose"):
            raw = inputs["face_choose"]
            if isinstance(raw, dict):
                raw = [raw]
            if not isinstance(raw, list):
                raise ValueError("face_choose must be a list of face choice objects")
            normalized: list[dict[str, Any]] = []
            for item in raw:
                if isinstance(item, str):
                    normalized.append({"face_id": item})
                elif isinstance(item, dict):
                    if not (item.get("face_id") or item.get("id")):
                        raise ValueError("face_choose items must include face_id")
                    record = dict(item)
                    if "face_id" not in record and record.get("id"):
                        record["face_id"] = record.pop("id")
                    normalized.append(record)
                else:
                    raise ValueError("face_choose items must be strings or objects")
            return normalized
        if inputs.get("face_id"):
            return [{"face_id": str(inputs["face_id"])}]
        return []

    def _face_selection(
        self,
        faces: list[dict[str, Any]],
        inputs: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        explicit = self._normalize_face_choose(inputs)
        if explicit:
            return explicit, {
                "selection_method": "user_selected",
                "selection_reason": "face_choose or face_id was provided",
                "selected_face": explicit,
            }
        if len(faces) == 1:
            choice = [self._face_to_choice(faces[0])]
            return choice, {
                "selection_method": "single_face",
                "selection_reason": "Only one face was returned by identify_face",
                "selected_face": choice,
            }
        if not inputs.get("auto_select_face"):
            return [], {
                "selection_method": "requires_user_selection",
                "selection_reason": "Multiple faces detected and auto_select_face was not enabled",
                "face_count": len(faces),
            }
        selected = max(faces, key=self._face_area)
        choice = [self._face_to_choice(selected)]
        return choice, {
            "selection_method": "auto_selected",
            "selection_reason": "auto_select_face=True selected the largest detected face area",
            "selected_face": choice,
        }

    @staticmethod
    def _face_to_choice(face: dict[str, Any]) -> dict[str, Any]:
        face_id = face.get("face_id") or face.get("id")
        if not face_id:
            raise ValueError(f"Cannot select face without face_id/id: {face}")
        return {"face_id": str(face_id)}

    @staticmethod
    def _face_area(face: dict[str, Any]) -> float:
        for key in ("bbox", "box"):
            value = face.get(key)
            if isinstance(value, list) and len(value) >= 4:
                third = float(value[2])
                fourth = float(value[3])
                width_height_area = max(third, 0.0) * max(fourth, 0.0)
                corner_width = third - float(value[0])
                corner_height = fourth - float(value[1])
                corner_area = (
                    corner_width * corner_height
                    if corner_width > 0 and corner_height > 0
                    else 0.0
                )
                if corner_area and width_height_area:
                    return min(corner_area, width_height_area)
                return corner_area or width_height_area
            if isinstance(value, dict):
                width = value.get("width") or value.get("w")
                height = value.get("height") or value.get("h")
                if width is not None and height is not None:
                    return max(float(width), 0.0) * max(float(height), 0.0)
        width = face.get("width") or face.get("w")
        height = face.get("height") or face.get("h")
        if width is not None and height is not None:
            return max(float(width), 0.0) * max(float(height), 0.0)
        return 0.0

    @staticmethod
    def _copy_audio_input(inputs: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
        audio_id = str(inputs.get("audio_id") or "").strip()
        if audio_id:
            payload["audio_id"] = audio_id
            return {"type": "audio_id", "value": audio_id}

        sound_path = inputs.get("sound_file_path") or inputs.get("audio_path")
        sound_file = normalize_media_input(
            url=inputs.get("sound_file_url"),
            path=sound_path,
            value=inputs.get("sound_file"),
            label="Lip-sync audio file",
        )
        if not sound_file:
            raise ValueError("advanced_lip_sync requires audio_id, sound_file, sound_file_url, sound_file_path, or audio_path")
        payload["sound_file"] = sound_file
        return {
            "type": "sound_file",
            "source": inputs.get("sound_file_url") or sound_path or "inline",
        }

    def _download_videos(
        self,
        client: KlingClient,
        outputs: list[dict[str, Any]],
        inputs: dict[str, Any],
    ) -> list[Path]:
        if not outputs:
            raise ValueError("Kling lip-sync response contained no videos")
        base_path = Path(inputs.get("output_path", "kling_lip_sync.mp4"))
        paths: list[Path] = []
        for index, item in enumerate(outputs):
            url = self._output_url(item)
            suffix = extension_from_url(url, ".mp4")
            output_path = numbered_output_path(output_path_with_suffix(base_path, suffix), index, suffix)
            client.download(url, output_path)
            paths.append(output_path)
        return paths

    @staticmethod
    def _output_url(item: dict[str, Any]) -> str:
        url = item.get("url") or item.get("video_url") or item.get("resource_url")
        if url:
            return str(url)
        resource = item.get("resource") or {}
        if isinstance(resource, dict) and resource.get("url"):
            return str(resource["url"])
        raise ValueError(f"Kling lip-sync response item contained no downloadable URL: {item}")

    @staticmethod
    def _copy_common_task_fields(inputs: dict[str, Any], payload: dict[str, Any]) -> None:
        callback_url = validate_callback_url(inputs.get("callback_url"))
        if callback_url:
            payload["callback_url"] = callback_url
        if inputs.get("external_task_id"):
            payload["external_task_id"] = inputs["external_task_id"]

    @staticmethod
    def _callback_result_data(inputs: dict[str, Any], task_id: str) -> dict[str, Any]:
        callback_url = inputs.get("callback_url")
        if not callback_url:
            return {}
        return {
            "callback_url": str(callback_url),
            "callback_requested": True,
            "polling_used": True,
            "task_id": task_id,
        }

    @staticmethod
    def _account_usage_result(inputs: dict[str, Any], client: KlingClient) -> dict[str, Any]:
        if not inputs.get("include_account_usage"):
            return {}
        try:
            usage = get_account_costs(client=client)
            return {
                "account_usage": usage,
                "cost_source": "estimate_with_account_usage_context",
                "reconciled_cost_usd": None,
            }
        except Exception as exc:
            return {
                "account_usage_error": str(exc),
                "cost_source": "estimate",
                "reconciled_cost_usd": None,
            }

    def _write_faces_artifact(
        self,
        inputs: dict[str, Any],
        identify: dict[str, Any],
        selection: dict[str, Any] | None = None,
    ) -> Path:
        if inputs.get("faces_artifact_path"):
            artifact_path = Path(inputs["faces_artifact_path"])
        elif inputs.get("output_path"):
            artifact_path = Path(inputs["output_path"]).with_name("kling_lip_sync_faces.json")
        else:
            artifact_path = Path("kling_lip_sync_faces.json")
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact = {
            "provider": self.provider,
            "operation": "identify_face",
            "session_id": identify["session_id"],
            "faces": identify["faces"],
            "face_count": len(identify["faces"]),
            "selection": selection,
        }
        artifact_path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return artifact_path
