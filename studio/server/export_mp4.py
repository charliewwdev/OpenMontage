"""Export episode MP4 from shot clips / keyframe boards via FFmpeg."""

from __future__ import annotations

import shutil
import struct
import subprocess
import tempfile
import time
import zlib
from pathlib import Path
from typing import Any


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def _run_ffmpeg(args: list[str], timeout: int = 600) -> None:
    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "ffmpeg failed")


def _aspect_size(aspect: str) -> tuple[int, int]:
    if aspect == "16:9":
        return 1280, 720
    if aspect == "1:1":
        return 1080, 1080
    return 720, 1280


def _png_chunk(tag: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)


def write_board_png(path: Path, width: int, height: int, *, top_rgb=(11, 28, 36), bottom_rgb=(196, 92, 38)) -> Path:
    """Write a gradient board PNG without external deps (no drawtext needed)."""
    rows = []
    for y in range(height):
        t = y / max(height - 1, 1)
        r = int(top_rgb[0] * (1 - t) + bottom_rgb[0] * t)
        g = int(top_rgb[1] * (1 - t) + bottom_rgb[1] * t)
        b = int(top_rgb[2] * (1 - t) + bottom_rgb[2] * t)
        # frame inset
        row = bytearray()
        row.append(0)  # filter none
        for x in range(width):
            edge = x < 36 or y < 36 or x >= width - 36 or y >= height - 36
            if edge:
                row.extend((max(0, r - 20), max(0, g - 10), min(255, b + 20)))
            else:
                row.extend((r, g, b))
        rows.append(bytes(row))
    raw = b"".join(rows)
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n" + _png_chunk(b"IHDR", ihdr) + _png_chunk(b"IDAT", zlib.compress(raw, 6)) + _png_chunk(b"IEND", b"")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png)
    return path


def render_clip_from_board(
    project: Path,
    shot: dict[str, Any],
    *,
    aspect: str,
    out_path: Path | None = None,
) -> Path:
    """Make a short MP4 from a generated PNG board (portable, no drawtext)."""
    if not ffmpeg_available():
        raise RuntimeError("未检测到 FFmpeg，请安装并加入 PATH")

    w, h = _aspect_size(aspect)
    dur = max(1.0, float(shot.get("duration_sec") or 3))
    out_dir = project / "renders" / "clips"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_path or (out_dir / f"{shot['id']}.mp4")

    with tempfile.TemporaryDirectory(prefix="om-clip-") as tmp:
        png = Path(tmp) / "board.png"
        write_board_png(png, w, h)
        _run_ffmpeg(
            [
                "-y",
                "-loop",
                "1",
                "-i",
                str(png),
                "-f",
                "lavfi",
                "-i",
                f"anullsrc=channel_layout=stereo:sample_rate=44100",
                "-t",
                str(dur),
                "-c:v",
                "libx264",
                "-tune",
                "stillimage",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-shortest",
                "-movflags",
                "+faststart",
                str(out_path),
            ]
        )
    return out_path


def export_episode_mp4(
    project: Path,
    storyboard: dict[str, Any],
    ledger: dict[str, Any] | None,
    *,
    shot_ids: list[str] | None = None,
) -> dict[str, Any]:
    if not ffmpeg_available():
        raise RuntimeError("未检测到 FFmpeg，无法导出成片")

    aspect = storyboard.get("aspect_ratio") or "9:16"
    w, h = _aspect_size(aspect)
    jobs = {j.get("shot_id"): j for j in (ledger or {}).get("jobs") or []}
    shots = list(storyboard.get("shots") or [])
    if shot_ids:
        order = {sid: i for i, sid in enumerate(shot_ids)}
        shots = sorted(shots, key=lambda s: order.get(s["id"], 10_000))
        shots = [s for s in shots if s["id"] in order]

    if not shots:
        raise RuntimeError("没有可导出的镜头")

    export_dir = project / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    episode_id = storyboard.get("episode_id") or "ep01"
    out_rel = f"exports/{episode_id}-{stamp}.mp4"
    out_path = project / out_rel

    with tempfile.TemporaryDirectory(prefix="om-export-") as tmp:
        tmp_path = Path(tmp)
        normalized: list[Path] = []
        used: list[dict[str, Any]] = []

        for i, shot in enumerate(shots):
            job = jobs.get(shot["id"]) or {}
            clip_rel = job.get("clip_path") or shot.get("clip_path")
            src: Path | None = None
            if clip_rel:
                candidate = project / clip_rel
                if candidate.is_file() and candidate.stat().st_size > 0:
                    src = candidate
            if src is None:
                synth = tmp_path / f"synth_{i:03d}.mp4"
                render_clip_from_board(project, shot, aspect=aspect, out_path=synth)
                src = synth

            norm = tmp_path / f"{i:03d}.mp4"
            _run_ffmpeg(
                [
                    "-y",
                    "-i",
                    str(src),
                    "-vf",
                    f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
                    f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "veryfast",
                    "-crf",
                    "20",
                    "-pix_fmt",
                    "yuv420p",
                    "-c:a",
                    "aac",
                    "-b:a",
                    "128k",
                    "-movflags",
                    "+faststart",
                    str(norm),
                ]
            )
            normalized.append(norm)
            used.append(
                {
                    "shot_id": shot["id"],
                    "source": str(src.relative_to(project))
                    if str(src).startswith(str(project))
                    else "synthetic",
                }
            )

        list_file = tmp_path / "files.txt"
        list_file.write_text(
            "\n".join(f"file '{p.as_posix()}'" for p in normalized) + "\n",
            encoding="utf-8",
        )
        _run_ffmpeg(
            [
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(list_file),
                "-c",
                "copy",
                "-movflags",
                "+faststart",
                str(out_path),
            ]
        )

    return {
        "ok": True,
        "path": out_rel,
        "url": f"/api/media/{project.name}/{out_rel}",
        "episode_id": episode_id,
        "clips": len(used),
        "used": used,
        "bytes": out_path.stat().st_size if out_path.is_file() else 0,
    }
