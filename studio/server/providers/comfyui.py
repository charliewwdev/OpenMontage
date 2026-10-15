"""ComfyUI adapter for Drama Studio (gpuhome rented GPU / any ComfyUI server).

Uses the standard ComfyUI REST API (POST /prompt, GET /history, GET /view).
No third-party deps beyond urllib — works inside the studio Docker image.
"""

from __future__ import annotations

import json
import os
import random
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any


class ComfyUIError(RuntimeError):
    pass


def _secret(name: str, default: str = "") -> str:
    try:
        from settings_store import get_secret

        return get_secret(name, default)
    except Exception:
        return (os.environ.get(name) or default or "").strip()


def server_url(*, capability: str | None = None) -> str:
    if capability:
        specific = _secret(f"COMFYUI_{capability.upper()}_SERVER_URL")
        if specific:
            return specific.rstrip("/")
    return (_secret("COMFYUI_SERVER_URL") or "").rstrip("/")


def configured(*, capability: str | None = None) -> bool:
    return bool(server_url(capability=capability))


def _http_json(method: str, url: str, body: dict | None = None, timeout: int = 60) -> Any:
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8") or "{}"
            return json.loads(raw)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise ComfyUIError(f"ComfyUI HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise ComfyUIError(f"ComfyUI 无法连接: {exc.reason}") from exc


def _http_bytes(url: str, timeout: int = 120) -> bytes:
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        raise ComfyUIError(f"ComfyUI 下载失败 ({exc.code}): {detail}") from exc
    except urllib.error.URLError as exc:
        raise ComfyUIError(f"ComfyUI 下载失败: {exc.reason}") from exc


def ping(base: str | None = None) -> dict[str, Any]:
    """Health probe — returns system_stats snippet or raises."""
    root = (base or server_url()).rstrip("/")
    if not root:
        raise ComfyUIError("未配置 COMFYUI_SERVER_URL")
    stats = _http_json("GET", f"{root}/system_stats", timeout=8)
    devices = ((stats.get("devices") or [{}])[0]) if isinstance(stats, dict) else {}
    return {
        "ok": True,
        "serverUrl": root,
        "deviceName": devices.get("name") or "",
        "vramTotal": devices.get("vram_total") or devices.get("vram_total_mb") or 0,
        "comfyuiVersion": (stats.get("system") or {}).get("comfyui_version")
        if isinstance(stats, dict)
        else "",
    }


_NON_SD_CKPT_MARKERS = (
    "sdpose",
    "pose",
    "controlnet",
    "ip-adapter",
    "ipadapter",
    "instantid",
    "insightface",
    "rt_detr",
    "yolo",
    "depth",
    "openpose",
)


def _is_likely_sd_checkpoint(name: str) -> bool:
    """Filter pose/detector weights that show up in CheckpointLoader but lack CLIP."""
    lower = (name or "").lower()
    if not lower.endswith((".safetensors", ".ckpt", ".pt", ".pth")):
        return False
    return not any(m in lower for m in _NON_SD_CKPT_MARKERS)


def list_checkpoints(base: str | None = None) -> list[str]:
    root = (base or server_url()).rstrip("/")
    if not root:
        return []
    try:
        data = _http_json("GET", f"{root}/object_info/CheckpointLoaderSimple", timeout=15)
        opts = (
            data.get("CheckpointLoaderSimple", {})
            .get("input", {})
            .get("required", {})
            .get("ckpt_name", [[]])[0]
        )
        raw = [str(x) for x in opts] if isinstance(opts, list) else []
        return [n for n in raw if _is_likely_sd_checkpoint(n)]
    except Exception:
        return []


def _list_model_folder(root: str, folder: str) -> list[str]:
    try:
        data = _http_json("GET", f"{root}/models/{folder}", timeout=15)
        return [str(x) for x in data] if isinstance(data, list) else []
    except Exception:
        return []


def list_diffusion_models(base: str | None = None) -> list[str]:
    root = (base or server_url()).rstrip("/")
    return _list_model_folder(root, "diffusion_models") if root else []


def list_text_encoders(base: str | None = None) -> list[str]:
    root = (base or server_url()).rstrip("/")
    return _list_model_folder(root, "text_encoders") if root else []


def list_vaes(base: str | None = None) -> list[str]:
    root = (base or server_url()).rstrip("/")
    return _list_model_folder(root, "vae") if root else []


def _pick_qwen_stack(root: str) -> dict[str, str] | None:
    """Resolve Qwen-Image 2.1 UNET + T2I text encoder + VAE when present."""
    diffs = list_diffusion_models(root)
    texts = list_text_encoders(root)
    vaes = list_vaes(root)
    unet = next((n for n in diffs if "qwen_image" in n.lower() and "turbo" in n.lower()), None) or next(
        (n for n in diffs if "qwen_image" in n.lower()), None
    )
    clip = next((n for n in texts if "qwen_image" in n.lower() and "t2i" in n.lower()), None) or next(
        (n for n in texts if "qwen" in n.lower()), None
    )
    vae = next((n for n in vaes if "qwen_image" in n.lower()), None) or next(
        (n for n in vaes if n and n != "pixel_space"), None
    )
    if not (unet and clip and vae):
        return None
    return {"unet": unet, "clip": clip, "vae": vae}


_SIZES = {
    "16:9": (1280, 720),
    "9:16": (720, 1280),
    "4:3": (1024, 768),
    "3:4": (768, 1024),
    "1:1": (1024, 1024),
}


def _basic_checkpoint_workflow(
    *,
    prompt: str,
    negative: str,
    width: int,
    height: int,
    ckpt: str,
    seed: int,
    steps: int = 20,
    cfg: float = 7.0,
) -> dict[str, Any]:
    """API-format workflow that works on stock SD1.5 / SDXL ComfyUI installs."""
    return {
        "3": {
            "class_type": "KSampler",
            "inputs": {
                "seed": seed,
                "steps": steps,
                "cfg": cfg,
                "sampler_name": "euler",
                "scheduler": "normal",
                "denoise": 1,
                "model": ["4", 0],
                "positive": ["6", 0],
                "negative": ["7", 0],
                "latent_image": ["5", 0],
            },
        },
        "4": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": ckpt},
        },
        "5": {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": width, "height": height, "batch_size": 1},
        },
        "6": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": prompt, "clip": ["4", 1]},
        },
        "7": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": negative, "clip": ["4", 1]},
        },
        "8": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["3", 0], "vae": ["4", 2]},
        },
        "9": {
            "class_type": "SaveImage",
            "inputs": {"filename_prefix": "openmontage", "images": ["8", 0]},
        },
    }


def _qwen_image_workflow(
    *,
    prompt: str,
    negative: str,
    width: int,
    height: int,
    unet: str,
    clip: str,
    vae: str,
    seed: int,
    steps: int = 8,
    cfg: float = 2.5,
) -> dict[str, Any]:
    """API workflow for gpuhome ComfyUI: Qwen-Image-2.1 (UNET + TextEncodeQwenImage21)."""
    return {
        "10": {
            "class_type": "UNETLoader",
            "inputs": {"unet_name": unet, "weight_dtype": "default"},
        },
        "11": {
            "class_type": "ModelSamplingAuraFlow",
            "inputs": {"model": ["10", 0], "shift": 1.73},
        },
        "12": {
            "class_type": "CLIPLoader",
            "inputs": {"clip_name": clip, "type": "qwen_image"},
        },
        "13": {
            "class_type": "VAELoader",
            "inputs": {"vae_name": vae},
        },
        "14": {
            "class_type": "TextEncodeQwenImage21",
            "inputs": {
                "clip": ["12", 0],
                "prompt": prompt,
                "negative_prompt": negative,
                "resolution": 1024,
            },
        },
        "15": {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": width, "height": height, "batch_size": 1},
        },
        "16": {
            "class_type": "KSampler",
            "inputs": {
                "seed": seed,
                "steps": steps,
                "cfg": cfg,
                "sampler_name": "euler",
                "scheduler": "simple",
                "denoise": 1,
                "model": ["11", 0],
                "positive": ["14", 0],
                "negative": ["14", 1],
                "latent_image": ["15", 0],
            },
        },
        "17": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["16", 0], "vae": ["13", 0]},
        },
        "18": {
            "class_type": "SaveImage",
            "inputs": {"filename_prefix": "openmontage", "images": ["17", 0]},
        },
    }


def generate_image(
    *,
    prompt: str,
    ratio: str,
    out_path: Path,
    reference_path: Path | None = None,
    timeout: int = 600,
) -> Path:
    """Text-to-image via ComfyUI. reference_path is ignored for now (T2I only)."""
    del reference_path  # i2i needs LoadImage + different graph; Seedream still handles redraw.
    root = server_url(capability="image") or server_url()
    if not root:
        raise ComfyUIError("未配置 COMFYUI_SERVER_URL（智川云租 GPU 后填写 ComfyUI 公网地址）")

    width, height = _SIZES.get(ratio) or _SIZES["9:16"]
    # Keep dimensions multiples of 8
    width = max(512, (width // 8) * 8)
    height = max(512, (height // 8) * 8)
    seed = random.randint(0, 2**31 - 1)
    negative = (
        "lowres, bad anatomy, bad hands, text, error, missing fingers, "
        "extra digit, fewer digits, cropped, worst quality, low quality, "
        "jpeg artifacts, signature, watermark, username, blurry"
    )

    ckpts = list_checkpoints(root)
    qwen = None if ckpts else _pick_qwen_stack(root)
    model_label = ""
    if ckpts:
        preferred = _secret("COMFYUI_CHECKPOINT")
        ckpt = preferred if preferred in ckpts else ckpts[0]
        model_label = ckpt
        workflow = _basic_checkpoint_workflow(
            prompt=prompt,
            negative=negative,
            width=width,
            height=height,
            ckpt=ckpt,
            seed=seed,
        )
    elif qwen:
        model_label = qwen["unet"]
        workflow = _qwen_image_workflow(
            prompt=prompt,
            negative=negative,
            width=width,
            height=height,
            unet=qwen["unet"],
            clip=qwen["clip"],
            vae=qwen["vae"],
            seed=seed,
        )
    else:
        raise ComfyUIError(
            "ComfyUI 已连通，但未发现可用出图模型（带 CLIP 的 Checkpoint 或 Qwen-Image）。"
            "当前常见情况：镜像只有 MiniMax H3 视频模型，不能出角色/场景静帧。"
            "请安装 SDXL / Flux / Qwen-Image，或换用带出图权重的 ComfyUI 镜像。"
        )

    client_id = str(uuid.uuid4())
    t0 = time.time()
    try:
        submitted = _http_json(
            "POST",
            f"{root}/prompt",
            {"prompt": workflow, "client_id": client_id},
            timeout=60,
        )
    except ComfyUIError:
        raise
    if submitted.get("node_errors"):
        raise ComfyUIError(f"ComfyUI 节点错误: {json.dumps(submitted['node_errors'])[:400]}")
    if submitted.get("error"):
        raise ComfyUIError(f"ComfyUI 提交失败: {json.dumps(submitted['error'])[:400]}")
    prompt_id = submitted.get("prompt_id")
    if not prompt_id:
        raise ComfyUIError(f"ComfyUI 未返回 prompt_id: {submitted}")

    deadline = time.time() + timeout
    entry: dict[str, Any] | None = None
    while time.time() < deadline:
        hist = _http_json("GET", f"{root}/history/{prompt_id}", timeout=20)
        entry = hist.get(prompt_id) if isinstance(hist, dict) else None
        if entry is not None:
            status = entry.get("status") or {}
            if status.get("status_str") == "error":
                raise ComfyUIError(f"ComfyUI 执行失败: {status.get('messages')}")
            # Wait until outputs land (status may appear before images).
            outs = entry.get("outputs") or {}
            if any((node or {}).get("images") for node in outs.values()) or status.get("completed"):
                break
        time.sleep(2)
    else:
        raise ComfyUIError(f"ComfyUI 任务超时（>{timeout}s），prompt_id={prompt_id}")

    outputs = (entry or {}).get("outputs") or {}
    images: list[dict[str, Any]] = []
    for node_out in outputs.values():
        for img in node_out.get("images") or []:
            images.append(img)
    if not images:
        raise ComfyUIError("ComfyUI 完成但未产出图片")

    first = images[0]
    qs = urllib.parse.urlencode(
        {
            "filename": first.get("filename") or "",
            "subfolder": first.get("subfolder") or "",
            "type": first.get("type") or "output",
        }
    )
    blob = _http_bytes(f"{root}/view?{qs}", timeout=120)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(blob)

    try:
        from usage_store import record_usage

        record_usage(
            provider="comfyui",
            model=model_label,
            kind="image",
            ok=True,
            status=200,
            latency_ms=int((time.time() - t0) * 1000),
        )
    except Exception:
        pass
    return out_path


def list_loras(base: str | None = None) -> list[str]:
    root = (base or server_url()).rstrip("/")
    return _list_model_folder(root, "loras") if root else []


def _node_exists(root: str, class_type: str) -> bool:
    try:
        data = _http_json("GET", f"{root}/object_info/{class_type}", timeout=12)
        return isinstance(data, dict) and class_type in data
    except Exception:
        return False


def _pick_minimax_h3_stack(root: str) -> dict[str, str] | None:
    """Resolve MiniMax H3 FL2VA (I2V/T2V) weights when present on the server."""
    diffs = list_diffusion_models(root)
    texts = list_text_encoders(root)
    vaes = list_vaes(root)
    loras = list_loras(root)

    unet = next((n for n in diffs if "fl2va" in n.lower() and "minimax" in n.lower()), None) or next(
        (n for n in diffs if "fl2va" in n.lower()), None
    )
    clip = next((n for n in texts if "minimax" in n.lower() and "qwen" in n.lower()), None) or next(
        (n for n in texts if "qwen3vl" in n.lower() and "minimax" in n.lower()), None
    ) or next((n for n in texts if "qwen3vl" in n.lower()), None)
    video_vae = next((n for n in vaes if "minimax" in n.lower() and "video" in n.lower()), None) or next(
        (n for n in vaes if "minimax_h3_video" in n.lower()), None
    )
    audio_vae = next((n for n in vaes if "minimax" in n.lower() and "audio" in n.lower()), None)
    turbo = next((n for n in loras if "turbo" in n.lower() and "minimax" in n.lower()), None) or next(
        (n for n in loras if "h3_turbo" in n.lower() or "minimax_h3_turbo" in n.lower()), None
    )
    if not (unet and clip and video_vae and audio_vae):
        return None
    if not _node_exists(root, "MiniMaxH3ImageToVideo"):
        return None
    out = {"unet": unet, "clip": clip, "video_vae": video_vae, "audio_vae": audio_vae}
    if turbo:
        out["turbo"] = turbo
    return out


def _adapt_h3_canvas(width: int, height: int) -> tuple[int, int]:
    """Match ComfyUI MiniMax H3 adapt_canvas: 768 short-edge, 768*1344 cap, ×32."""
    import math

    ratio = width / max(height, 1)
    if ratio >= 1.0:
        nom_w, nom_h = 768 * ratio, 768.0
    else:
        nom_w, nom_h = 768.0, 768.0 / ratio
    max_pixels = 768 * 1344
    if nom_w * nom_h > max_pixels:
        s = math.sqrt(max_pixels / (nom_w * nom_h))
        nom_w, nom_h = nom_w * s, nom_h * s
    return (
        max(32, int(round(nom_w / 32) * 32)),
        max(32, int(round(nom_h / 32) * 32)),
    )


def _h3_frame_length(duration_s: float | int) -> int:
    """24fps frame count snapped to MiniMax H3's 17k+5 grid (124 ≈ 5s)."""
    n = max(5, int(round(float(duration_s) * 24)))
    while n % 17 != 5:
        n += 1
    return min(n, 362)


def _upload_image(root: str, path: Path) -> str:
    """POST multipart to ComfyUI /upload/image; returns server filename."""
    boundary = f"----OpenMontage{uuid.uuid4().hex}"
    filename = path.name or "ref.png"
    blob = path.read_bytes()
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="image"; filename="{filename}"\r\n'
        f"Content-Type: application/octet-stream\r\n\r\n"
    ).encode("utf-8") + blob + f"\r\n--{boundary}--\r\n".encode("utf-8")
    req = urllib.request.Request(
        f"{root}/upload/image",
        data=body,
        method="POST",
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:400]
        raise ComfyUIError(f"ComfyUI 上传参考图失败 ({exc.code}): {detail}") from exc
    except urllib.error.URLError as exc:
        raise ComfyUIError(f"ComfyUI 上传参考图失败: {exc.reason}") from exc
    name = data.get("name") or data.get("filename")
    if not name:
        raise ComfyUIError(f"ComfyUI 上传未返回文件名: {data}")
    return str(name)


def _minimax_h3_workflow(
    *,
    prompt: str,
    width: int,
    height: int,
    length: int,
    seed: int,
    stack: dict[str, str],
    image_name: str | None,
    use_low_vram: bool,
) -> tuple[dict[str, Any], str]:
    """Build MiniMax H3 FL2VA API graph. Returns (workflow, save_node_id)."""
    wf: dict[str, Any] = {
        "1": {
            "class_type": "UNETLoader",
            "inputs": {"unet_name": stack["unet"], "weight_dtype": "default"},
        },
        "10": {
            "class_type": "CLIPLoader",
            "inputs": {"clip_name": stack["clip"], "type": "minimax", "device": "default"},
        },
        "22": {
            "class_type": "VAELoader",
            "inputs": {"vae_name": stack["video_vae"]},
        },
        "23": {
            "class_type": "VAELoader",
            "inputs": {"vae_name": stack["audio_vae"]},
        },
        "13": {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}},
        "14": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler"}},
    }

    model_src = ["1", 0]
    if stack.get("turbo"):
        wf["32"] = {
            "class_type": "MiniMaxH3TurboLoRA",
            "inputs": {
                "lora_name": stack["turbo"],
                "strength": 1.0,
                "low_vram": True,
                "model": model_src,
            },
        }
        model_src = ["32", 0]
        steps = 4
    else:
        steps = 20

    wf["8"] = {
        "class_type": "MiniMaxH3SigmaShift",
        "inputs": {"shift_video": 12, "shift_audio": 3, "model": model_src},
    }
    model_src = ["8", 0]

    if use_low_vram:
        wf["26"] = {
            "class_type": "MiniMaxLowVRAMAttention",
            "inputs": {"head_chunks": 4, "model": model_src},
        }
        wf["28"] = {
            "class_type": "MiniMaxChunkFeedForward",
            "inputs": {"chunks": 2, "seq_threshold": 4096, "model": ["26", 0]},
        }
        sample_model = ["28", 0]
    else:
        sample_model = model_src

    i2v_inputs: dict[str, Any] = {
        "prompt": prompt,
        "width": width,
        "height": height,
        "length": length,
        "clip": ["10", 0],
        "vae": ["22", 0],
    }
    if image_name:
        wf["11"] = {"class_type": "LoadImage", "inputs": {"image": image_name}}
        i2v_inputs["first_frame"] = ["11", 0]

    wf["29"] = {"class_type": "MiniMaxH3ImageToVideo", "inputs": i2v_inputs}
    wf["15"] = {
        "class_type": "BasicScheduler",
        "inputs": {"scheduler": "simple", "steps": steps, "denoise": 1, "model": sample_model},
    }
    wf["16"] = {
        "class_type": "BasicGuider",
        "inputs": {"model": sample_model, "conditioning": ["29", 0]},
    }
    wf["17"] = {
        "class_type": "SamplerCustomAdvanced",
        "inputs": {
            "noise": ["13", 0],
            "guider": ["16", 0],
            "sampler": ["14", 0],
            "sigmas": ["15", 0],
            "latent_image": ["29", 1],
        },
    }
    wf["18"] = {"class_type": "VAEDecode", "inputs": {"samples": ["17", 0], "vae": ["22", 0]}}
    wf["19"] = {"class_type": "VAEDecodeAudio", "inputs": {"samples": ["17", 0], "vae": ["23", 0]}}
    wf["20"] = {
        "class_type": "CreateVideo",
        "inputs": {"fps": 24, "bit_depth": 8, "images": ["18", 0], "audio": ["19", 0]},
    }
    wf["21"] = {
        "class_type": "SaveVideo",
        "inputs": {
            "filename_prefix": "openmontage_h3",
            "format": "auto",
            "codec": "auto",
            "video": ["20", 0],
        },
    }
    return wf, "21"


def _submit_and_wait(
    root: str,
    workflow: dict[str, Any],
    *,
    timeout: int,
) -> dict[str, Any]:
    client_id = str(uuid.uuid4())
    submitted = _http_json(
        "POST",
        f"{root}/prompt",
        {"prompt": workflow, "client_id": client_id},
        timeout=60,
    )
    if submitted.get("node_errors"):
        raise ComfyUIError(f"ComfyUI 节点错误: {json.dumps(submitted['node_errors'])[:400]}")
    if submitted.get("error"):
        raise ComfyUIError(f"ComfyUI 提交失败: {json.dumps(submitted['error'])[:400]}")
    prompt_id = submitted.get("prompt_id")
    if not prompt_id:
        raise ComfyUIError(f"ComfyUI 未返回 prompt_id: {submitted}")

    deadline = time.time() + timeout
    entry: dict[str, Any] | None = None
    while time.time() < deadline:
        hist = _http_json("GET", f"{root}/history/{prompt_id}", timeout=20)
        entry = hist.get(prompt_id) if isinstance(hist, dict) else None
        if entry is not None:
            status = entry.get("status") or {}
            if status.get("status_str") == "error":
                raise ComfyUIError(f"ComfyUI 执行失败: {status.get('messages')}")
            outs = entry.get("outputs") or {}
            if outs or status.get("completed"):
                # Wait until media lands when status completes early.
                has_media = any(
                    (node or {}).get("images")
                    or (node or {}).get("gifs")
                    or (node or {}).get("videos")
                    or (node or {}).get("video")
                    for node in outs.values()
                )
                if has_media or status.get("completed"):
                    if has_media or status.get("completed"):
                        break
        time.sleep(2)
    else:
        raise ComfyUIError(f"ComfyUI 任务超时（>{timeout}s），prompt_id={prompt_id}")
    return entry or {}


def _first_media_item(outputs: dict[str, Any], preferred_node: str | None = None) -> dict[str, Any]:
    order = []
    if preferred_node and preferred_node in outputs:
        order.append(preferred_node)
    order.extend(k for k in outputs if k not in order)
    for nid in order:
        node = outputs.get(nid) or {}
        for key in ("gifs", "videos", "video", "images"):
            items = node.get(key) or []
            if items:
                return items[0]
    raise ComfyUIError("ComfyUI 完成但未产出视频文件")


def generate_video(
    *,
    prompt: str,
    ratio: str,
    duration: float | int,
    out_path: Path,
    reference_path: Path | None = None,
    resolution: str = "720p",
    timeout: int = 1200,
) -> Path:
    """Image/text-to-video via ComfyUI (MiniMax H3 FL2VA preferred)."""
    root = server_url(capability="video") or server_url()
    if not root:
        raise ComfyUIError("未配置 COMFYUI_SERVER_URL（智川云租 GPU 后填写 ComfyUI 公网地址）")

    base_w, base_h = _SIZES.get(ratio) or _SIZES["9:16"]
    # Resolution hint: bump long edge slightly for 1080p requests.
    if str(resolution).lower() in {"1080p", "1080", "2k"}:
        scale = 1.35
        base_w, base_h = int(base_w * scale), int(base_h * scale)
    width, height = _adapt_h3_canvas(base_w, base_h)
    length = _h3_frame_length(duration)
    seed = random.randint(0, 2**31 - 1)

    stack = _pick_minimax_h3_stack(root)
    if not stack:
        raise ComfyUIError(
            "ComfyUI 已连通，但未发现 MiniMax H3 出片模型（需 fl2va UNET + Qwen3-VL + video/audio VAE）。"
            "请使用 MiniMax-H3 / 含 H3 权重的 ComfyUI 镜像。"
        )

    image_name = None
    if reference_path and Path(reference_path).is_file():
        image_name = _upload_image(root, Path(reference_path))

    use_low_vram = _node_exists(root, "MiniMaxLowVRAMAttention") and _node_exists(
        root, "MiniMaxChunkFeedForward"
    )
    # Turbo LoRA node optional
    if stack.get("turbo") and not _node_exists(root, "MiniMaxH3TurboLoRA"):
        stack = {k: v for k, v in stack.items() if k != "turbo"}
    if not _node_exists(root, "MiniMaxH3SigmaShift"):
        raise ComfyUIError("ComfyUI 缺少 MiniMaxH3SigmaShift 节点，请升级含 MiniMax H3 的镜像。")

    workflow, save_node = _minimax_h3_workflow(
        prompt=prompt,
        width=width,
        height=height,
        length=length,
        seed=seed,
        stack=stack,
        image_name=image_name,
        use_low_vram=use_low_vram,
    )

    t0 = time.time()
    entry = _submit_and_wait(root, workflow, timeout=timeout)
    outputs = entry.get("outputs") or {}
    if not any(
        (n or {}).get("images") or (n or {}).get("gifs") or (n or {}).get("videos") or (n or {}).get("video")
        for n in outputs.values()
    ):
        # Some builds mark completed before SaveVideo flushes — one more poll already done.
        status = entry.get("status") or {}
        if status.get("status_str") == "error":
            raise ComfyUIError(f"ComfyUI 执行失败: {status.get('messages')}")
        raise ComfyUIError("ComfyUI 完成但未产出视频（请确认镜像含 MiniMax H3 与 SaveVideo）")

    first = _first_media_item(outputs, save_node)
    qs = urllib.parse.urlencode(
        {
            "filename": first.get("filename") or "",
            "subfolder": first.get("subfolder") or "",
            "type": first.get("type") or "output",
        }
    )
    blob = _http_bytes(f"{root}/view?{qs}", timeout=300)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(blob)

    try:
        from usage_store import record_usage

        record_usage(
            provider="comfyui",
            model=stack.get("unet") or "minimax-h3",
            kind="video",
            ok=True,
            status=200,
            latency_ms=int((time.time() - t0) * 1000),
        )
    except Exception:
        pass
    return out_path


def video_capable(*, probe: bool = False) -> bool:
    """True when a video URL is set; optionally verify H3 stack is installed."""
    root = server_url(capability="video") or server_url()
    if not root:
        return False
    if not probe:
        return True
    try:
        return _pick_minimax_h3_stack(root) is not None
    except Exception:
        return False


def public_status(*, probe: bool = False) -> dict[str, Any]:
    """Return ComfyUI config for the keys UI.

    *probe=False* (default) avoids blocking GET /api/settings/keys on a dead URL.
    Connectivity + checkpoint discovery runs when the user clicks「检测连通」.
    """
    url = server_url()
    image_url = server_url(capability="image") or url
    video_url = server_url(capability="video") or url
    reachable = False
    ping_info: dict[str, Any] = {}
    checkpoints: list[str] = []
    video_models: list[str] = []
    video_ready = False
    error = ""
    if url and probe:
        try:
            ping_info = ping(url)
            reachable = True
            checkpoints = list_checkpoints(url)[:20]
            if not checkpoints:
                qwen = _pick_qwen_stack(url)
                if qwen:
                    checkpoints = [qwen["unet"]]
            h3 = _pick_minimax_h3_stack(url)
            if h3:
                video_ready = True
                video_models = [h3["unet"]]
        except Exception as exc:  # noqa: BLE001
            error = str(exc)
    return {
        "configured": bool(url),
        "reachable": reachable,
        "serverUrl": url,
        "imageUrl": image_url if image_url != url else "",
        "videoUrl": video_url if video_url != url else "",
        "docs": "https://docs.gpuhome.cc/docs/env/comfyui.html",
        "portsDocs": "https://docs.gpuhome.cc/docs/instance/open-ports.html",
        "market": "https://gpuhome.cc/market",
        "checkpoints": checkpoints,
        "checkpoint": _secret("COMFYUI_CHECKPOINT") or (checkpoints[0] if checkpoints else ""),
        "videoModels": video_models,
        "videoReady": video_ready if probe else bool(video_url or url),
        "deviceName": ping_info.get("deviceName") or "",
        "error": error,
        "hint": (
            "在 gpuhome.cc/market 租 GPU → 选 ComfyUI（含 MiniMax H3）镜像 → 开放端口 → 填入地址。"
            "出片用 H3 即可；出图还需机内有 SDXL / Qwen-Image 等带 CLIP 的模型（仅 H3 不够）。"
        ),
        "imageReady": bool(checkpoints) if probe else bool(image_url or url),
    }
