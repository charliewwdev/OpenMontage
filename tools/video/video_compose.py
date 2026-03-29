"""Video composition tool — FFmpeg + Remotion.

Final composition path that takes edit decisions, assets, and audio
and renders the complete output video. Supports subtitle burn-in,
overlay compositing, and platform-specific encoding profiles.

For compositions with still images, animated scenes, or component types
(text cards, stat cards, etc.), the render operation auto-routes to
Remotion for frame-accurate spring animations and React-based rendering.
For pure video cuts (talking-head, etc.), FFmpeg handles trimming and concat.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Optional

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    RetryPolicy,
    ResumeSupport,
    ToolResult,
    ToolStability,
    ToolTier,
)


class VideoCompose(BaseTool):
    name = "video_compose"
    version = "0.1.0"
    tier = ToolTier.CORE
    capability = "video_post"
    provider = "ffmpeg"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC

    dependencies = ["cmd:ffmpeg"]
    install_instructions = "Install FFmpeg: https://ffmpeg.org/download.html"
    agent_skills = ["remotion-best-practices", "remotion", "ffmpeg"]

    capabilities = [
        "compose_cuts",
        "burn_subtitles",
        "overlay_assets",
        "encode_profile",
        "remotion_render",
    ]

    input_schema = {
        "type": "object",
        "required": ["operation"],
        "properties": {
            "operation": {
                "type": "string",
                "enum": ["compose", "render", "remotion_render", "burn_subtitles", "overlay", "encode"],
                "description": (
                    "compose: low-level concat cuts + audio + subtitles. "
                    "render: high-level — resolves asset IDs, auto-routes to Remotion "
                    "for images/animations or FFmpeg for video-only. Preferred for compose-director. "
                    "remotion_render: render via Remotion (Node.js). "
                    "burn_subtitles: burn subtitle file into existing video. "
                    "overlay: composite overlays onto base video. "
                    "encode: re-encode to a target profile/codec."
                ),
            },
            "input_path": {"type": "string"},
            "output_path": {"type": "string"},
            "edit_decisions": {
                "type": "object",
                "description": "Full edit_decisions artifact (required for compose/render)",
            },
            "asset_manifest": {
                "type": "object",
                "description": (
                    "Full asset_manifest artifact (required for render). "
                    "Used to resolve asset IDs in cuts[].source to file paths."
                ),
            },
            "subtitle_path": {"type": "string"},
            "subtitle_style": {
                "type": "object",
                "description": "ASS subtitle styling. Also extracted from edit_decisions.subtitles if not provided.",
                "properties": {
                    "font": {"type": "string", "default": "Arial"},
                    "font_size": {"type": "integer", "default": 24},
                    "primary_color": {"type": "string", "default": "&HFFFFFF"},
                    "outline_color": {"type": "string", "default": "&H000000"},
                    "outline_width": {"type": "number", "default": 2},
                    "margin_v": {"type": "integer", "default": 40},
                    "alignment": {"type": "integer", "default": 2},
                },
            },
            "overlays": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "asset_path": {"type": "string"},
                        "x": {"type": "number"},
                        "y": {"type": "number"},
                        "width": {"type": "number"},
                        "height": {"type": "number"},
                        "start_seconds": {"type": "number"},
                        "end_seconds": {"type": "number"},
                        "opacity": {"type": "number", "minimum": 0, "maximum": 1},
                    },
                },
            },
            "audio_path": {"type": "string", "description": "Mixed audio to mux into output"},
            "profile": {
                "type": "string",
                "description": (
                    "Media profile name from media_profiles.py "
                    "(e.g. youtube_landscape, tiktok, instagram_reels). "
                    "Applied in render and encode operations."
                ),
            },
            "options": {
                "type": "object",
                "description": "Render options (used by the render operation)",
                "properties": {
                    "subtitle_burn": {"type": "boolean", "default": True},
                    "two_pass_encode": {"type": "boolean", "default": False},
                },
            },
            "codec": {"type": "string", "default": "libx264"},
            "crf": {"type": "integer", "default": 23},
            "preset": {"type": "string", "default": "medium"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=4, ram_mb=2048, vram_mb=0, disk_mb=5000, network_required=False
    )

    # Remotion scene types that trigger React-based rendering
    _REMOTION_COMPONENTS = [
        "text_card", "stat_card", "callout", "comparison",
        "progress", "chart", "bar_chart", "line_chart", "pie_chart", "kpi_grid",
    ]

    best_for = [
        "Final render for explainer and animation pipelines",
        "Image-to-video with spring animations (Remotion)",
        "Animated text cards, stat cards, charts (Remotion)",
        "Complex transitions between scenes (Remotion)",
        "Pure video concat and trim (FFmpeg)",
    ]
    retry_policy = RetryPolicy(max_retries=1, retryable_errors=["Conversion failed"])
    resume_support = ResumeSupport.FROM_START
    idempotency_key_fields = ["operation", "input_path", "edit_decisions"]
    side_effects = ["writes video file to output_path"]
    user_visible_verification = [
        "Play the composed output and verify cuts, subtitles, and overlays",
    ]

    def _remotion_available(self) -> bool:
        """Check if Remotion rendering is available (requires npx + composer project + node_modules)."""
        import shutil as _shutil

        if not _shutil.which("npx"):
            return False
        composer_dir = Path(__file__).resolve().parent.parent.parent / "remotion-composer"
        if not composer_dir.exists() or not (composer_dir / "package.json").exists():
            return False
        # Check that node_modules are actually installed — without this,
        # npx remotion render will fail even though the project exists.
        if not (composer_dir / "node_modules").exists():
            return False
        return True

    def get_info(self) -> dict[str, Any]:
        """Extend base get_info to surface Remotion sub-capability.

        This lets preflight report 'video_compose: AVAILABLE (FFmpeg + Remotion)'
        so the agent knows Remotion is usable for motion graphics, animated text
        cards, stat cards, charts, and image-to-video rendering — rather than
        falling back to Ken Burns pan-and-zoom over still images.
        """
        info = super().get_info()
        remotion_ok = self._remotion_available()
        info["render_engines"] = {
            "ffmpeg": True,
            "remotion": remotion_ok,
        }
        if remotion_ok:
            info["remotion_components"] = self._REMOTION_COMPONENTS
            info["remotion_note"] = (
                "Remotion is available for React-based rendering. Use it for "
                "image-to-video with spring animations, animated text/stat cards, "
                "charts, callouts, comparisons, and complex transitions. "
                "Prefer Remotion over Ken Burns pan-and-zoom for explainer "
                "and motion-graphics pipelines."
            )
        else:
            composer_dir = Path(__file__).resolve().parent.parent.parent / "remotion-composer"
            if composer_dir.exists() and (composer_dir / "package.json").exists() and not (composer_dir / "node_modules").exists():
                info["remotion_note"] = (
                    "Remotion project exists but node_modules are NOT installed. "
                    "Run 'cd remotion-composer && npm install' to enable Remotion rendering. "
                    "Falling back to FFmpeg Ken Burns for image-based compositions."
                )
            else:
                info["remotion_note"] = (
                    "Remotion is NOT available (needs Node.js/npx + remotion-composer). "
                    "Falling back to FFmpeg Ken Burns for image-based compositions."
                )
        return info

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        operation = inputs["operation"]
        start = time.time()

        try:
            if operation == "compose":
                result = self._compose(inputs)
            elif operation == "render":
                result = self._render(inputs)
            elif operation == "remotion_render":
                result = self._remotion_render(inputs)
            elif operation == "burn_subtitles":
                result = self._burn_subtitles(inputs)
            elif operation == "overlay":
                result = self._overlay(inputs)
            elif operation == "encode":
                result = self._encode(inputs)
            else:
                return ToolResult(success=False, error=f"Unknown operation: {operation}")
        except Exception as e:
            return ToolResult(success=False, error=str(e))

        result.duration_seconds = round(time.time() - start, 2)
        return result

    _IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp"}

    @staticmethod
    def _is_image(path: Path) -> bool:
        """Check if a file is a still image (routes to Remotion, not FFmpeg)."""
        return path.suffix.lower() in VideoCompose._IMAGE_EXTENSIONS

    def _compose(self, inputs: dict[str, Any]) -> ToolResult:
        """FFmpeg composition: concat video cuts, add audio, burn subtitles.

        Handles video sources only. Still images and animated scene types
        are routed to Remotion via the render operation — call compose
        directly only for pure video pipelines (e.g. talking-head).
        """
        edit_decisions = inputs.get("edit_decisions")
        if not edit_decisions:
            return ToolResult(success=False, error="edit_decisions required for compose")

        output_path = Path(inputs.get("output_path", "composed_output.mp4"))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        audio_path = inputs.get("audio_path")
        subtitle_path = inputs.get("subtitle_path")
        codec = inputs.get("codec", "libx264")
        crf = inputs.get("crf", 23)
        preset = inputs.get("preset", "medium")
        profile_name = inputs.get("profile")

        # Resolve target resolution from profile or default
        resolution = "1920x1080"
        if profile_name:
            try:
                from lib.media_profiles import get_profile
                p = get_profile(profile_name)
                resolution = f"{p.width}x{p.height}"
            except (ImportError, ValueError):
                pass

        cuts = edit_decisions.get("cuts", [])
        if not cuts:
            return ToolResult(success=False, error="No cuts in edit_decisions")

        # Extract subtitle style from edit_decisions if not provided directly
        if not inputs.get("subtitle_style"):
            ed_subs = edit_decisions.get("subtitles", {})
            if ed_subs:
                inputs = dict(inputs)
                inputs["subtitle_style"] = {
                    k: v for k, v in ed_subs.items()
                    if k in ("font", "font_size", "color", "outline_color", "background")
                }
                if ed_subs.get("source") and not subtitle_path:
                    subtitle_path = ed_subs["source"]

        temp_dir = output_path.parent / ".compose_tmp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        temp_segments: list[Path] = []

        try:
            for i, cut in enumerate(cuts):
                source = Path(cut["source"])
                if not source.exists():
                    return ToolResult(success=False, error=f"Cut source not found: {source}")

                seg_path = temp_dir / f"seg_{i:04d}.mp4"
                in_s = cut["in_seconds"]
                out_s = cut["out_seconds"]
                duration = out_s - in_s
                speed = cut.get("speed", 1.0)

                if self._is_image(source):
                    return ToolResult(
                        success=False,
                        error=(
                            f"Still image '{source.name}' in cuts. "
                            "Use operation='render' (auto-routes to Remotion) "
                            "or operation='remotion_render' for compositions "
                            "with images, animations, or component scenes."
                        ),
                    )
                else:
                    # Video source: trim to segment
                    cmd = [
                        "ffmpeg", "-y",
                        "-i", str(source),
                        "-ss", str(in_s),
                        "-to", str(out_s),
                    ]

                    if speed != 1.0:
                        vf = f"setpts={1.0/speed}*PTS"
                        af = self._build_atempo(speed)
                        cmd.extend(["-filter:v", vf, "-filter:a", af])
                        cmd.extend(["-c:v", codec, "-crf", str(crf), "-c:a", "aac"])
                    else:
                        cmd.extend(["-c", "copy"])

                    cmd.append(str(seg_path))
                    self.run_command(cmd)

                temp_segments.append(seg_path)

            # Step 2: Concat segments
            concat_path = temp_dir / "concat_list.txt"
            with open(concat_path, "w", encoding="utf-8") as f:
                for seg in temp_segments:
                    safe = str(seg.resolve()).replace("\\", "/")
                    f.write(f"file '{safe}'\n")

            concat_out = temp_dir / "concat.mp4"
            cmd = [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0",
                "-i", str(concat_path),
                "-c", "copy",
                str(concat_out),
            ]
            self.run_command(cmd)

            # Step 3: Apply subtitles and/or replace audio
            final_input = concat_out
            vfilters = []

            if subtitle_path and Path(subtitle_path).exists():
                style = inputs.get("subtitle_style", {})
                ass_style = self._build_subtitle_style(style)
                sub_escaped = str(Path(subtitle_path).resolve()).replace("\\", "/").replace(":", "\\:")
                vfilters.append(f"subtitles='{sub_escaped}':force_style='{ass_style}'")

            cmd = ["ffmpeg", "-y", "-i", str(final_input)]

            if audio_path and Path(audio_path).exists():
                cmd.extend(["-i", audio_path])

            if vfilters:
                cmd.extend(["-vf", ",".join(vfilters)])
                cmd.extend(["-c:v", codec, "-crf", str(crf), "-preset", preset])
            else:
                cmd.extend(["-c:v", "copy"])

            if audio_path and Path(audio_path).exists():
                cmd.extend(["-map", "0:v:0", "-map", "1:a:0", "-c:a", "aac", "-shortest"])
            else:
                cmd.extend(["-c:a", "copy"])

            # Apply profile resolution/fps at final output
            if profile_name:
                try:
                    from lib.media_profiles import get_profile
                    p = get_profile(profile_name)
                    cmd.extend(["-s", f"{p.width}x{p.height}", "-r", str(p.fps)])
                except (ImportError, ValueError):
                    pass

            cmd.append(str(output_path))
            self.run_command(cmd)

            return ToolResult(
                success=True,
                data={
                    "operation": "compose",
                    "cut_count": len(cuts),
                    "has_subtitles": subtitle_path is not None,
                    "has_mixed_audio": audio_path is not None,
                    "profile": profile_name,
                    "output": str(output_path),
                },
                artifacts=[str(output_path)],
            )
        finally:
            # Cleanup temp files
            for f in temp_segments:
                if f.exists():
                    f.unlink()
            for f in [concat_path, concat_out]:
                if f.exists():
                    f.unlink()
            if temp_dir.exists():
                try:
                    temp_dir.rmdir()
                except OSError:
                    pass

    _REMOTION_SCENE_TYPES = {
        "text_card", "stat_card", "callout", "comparison", "progress", "chart",
    }

    def _needs_remotion(self, cuts: list[dict]) -> bool:
        """Determine if the composition requires Remotion.

        Returns True when any cut contains still images, animated scene types,
        component types (text_card, stat_card, etc.), or transitions — all of
        which benefit from Remotion's React-based rendering over FFmpeg.
        """
        for cut in cuts:
            source = cut.get("source", "")
            if source and Path(source).suffix.lower() in self._IMAGE_EXTENSIONS:
                return True
            if cut.get("type") in self._REMOTION_SCENE_TYPES:
                return True
            if cut.get("animation") or cut.get("transition_in") or cut.get("transition_out"):
                return True
            transform = cut.get("transform", {})
            if transform and transform.get("animation"):
                return True
        return False

    def _render(self, inputs: dict[str, Any]) -> ToolResult:
        """High-level render: assemble edit decisions + asset manifest into final video.

        This is the primary entry point for the compose-director skill.
        It resolves asset IDs, then auto-routes to Remotion (for images,
        animations, component scenes) or FFmpeg (for pure video cuts).

        The agent should pass edit_decisions, asset_manifest, and optionally
        profile, subtitle_path, audio_path, and options.
        """
        edit_decisions = inputs.get("edit_decisions")
        asset_manifest = inputs.get("asset_manifest")
        if not edit_decisions:
            return ToolResult(success=False, error="edit_decisions required for render")
        if not asset_manifest:
            return ToolResult(success=False, error="asset_manifest required for render")

        output_path = Path(inputs.get("output_path", "renders/output.mp4"))
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Build asset lookup: id -> asset info
        asset_lookup = {a["id"]: a for a in asset_manifest.get("assets", [])}

        cuts = edit_decisions.get("cuts", [])
        if not cuts:
            return ToolResult(success=False, error="No cuts in edit_decisions")

        # Resolve asset IDs in cuts to file paths
        resolved_cuts = []
        for cut in cuts:
            source_id = cut.get("source", "")
            resolved_cut = dict(cut)
            if source_id in asset_lookup:
                resolved_cut["source"] = asset_lookup[source_id]["path"]
            resolved_cuts.append(resolved_cut)

        # Also accept profile as "output_profile" (skill convention) or "profile"
        profile = inputs.get("profile") or inputs.get("output_profile")

        # --- Route: Remotion for rich content, FFmpeg for pure video ---
        if self._needs_remotion(resolved_cuts):
            remotion_inputs: dict[str, Any] = {
                "edit_decisions": dict(edit_decisions, cuts=resolved_cuts),
                "output_path": str(output_path),
            }
            if profile:
                remotion_inputs["profile"] = profile
            return self._remotion_render(remotion_inputs)

        # --- FFmpeg path: pure video cuts (talking-head, etc.) ---
        # Handle options
        options = inputs.get("options", {})
        subtitle_burn = options.get("subtitle_burn", True)

        # Resolve subtitle_path from edit_decisions if not provided
        subtitle_path = inputs.get("subtitle_path")
        if subtitle_burn and not subtitle_path:
            ed_subs = edit_decisions.get("subtitles", {})
            if ed_subs.get("enabled") and ed_subs.get("source"):
                subtitle_path = ed_subs["source"]

        # Build compose inputs
        compose_inputs = dict(inputs)
        compose_inputs["edit_decisions"] = dict(edit_decisions, cuts=resolved_cuts)
        compose_inputs["output_path"] = str(output_path)
        if subtitle_path:
            compose_inputs["subtitle_path"] = subtitle_path
        if profile:
            compose_inputs["profile"] = profile

        return self._compose(compose_inputs)

    def _remotion_render(self, inputs: dict[str, Any]) -> ToolResult:
        """Render via Remotion (requires Node.js + npx).

        Handles compositions with still images, animated scenes, component
        types, and transitions using React-based frame-accurate rendering.
        Accepts edit_decisions (with resolved file paths) or raw composition_data.
        """
        import shutil

        if not shutil.which("npx"):
            return ToolResult(
                success=False,
                error="npx not found. Install Node.js to use Remotion rendering.",
            )

        composition_data = inputs.get("edit_decisions") or inputs.get("composition_data")
        if not composition_data:
            return ToolResult(
                success=False,
                error="edit_decisions or composition_data required for remotion_render",
            )

        output_path = Path(inputs.get("output_path", "renders/remotion_output.mp4"))
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Deep-copy props so we don't mutate the original
        props = json.loads(json.dumps(composition_data))

        # Convert absolute file paths to file:// URIs for Remotion's
        # Img and OffthreadVideo components
        for cut in props.get("cuts", []):
            source = cut.get("source", "")
            if source and not source.startswith(("http://", "https://", "file://")):
                resolved = Path(source).resolve()
                if resolved.exists():
                    posix = resolved.as_posix()
                    cut["source"] = f"file:///{posix}" if not posix.startswith("/") else f"file://{posix}"

        # Write props to temp file for Remotion CLI
        props_path = output_path.parent / ".remotion_props.json"
        with open(props_path, "w", encoding="utf-8") as f:
            json.dump(props, f)

        # remotion-composer lives at project root
        composer_dir = Path(__file__).resolve().parent.parent.parent / "remotion-composer"
        if not composer_dir.exists():
            return ToolResult(
                success=False,
                error=f"Remotion composer project not found at {composer_dir}",
            )

        cmd = [
            "npx", "remotion", "render",
            str(composer_dir / "src" / "index.tsx"),
            "Explainer",
            str(output_path),
            "--props", str(props_path),
        ]

        # Apply media profile dimensions
        profile_name = inputs.get("profile")
        if profile_name:
            try:
                from lib.media_profiles import get_profile
                p = get_profile(profile_name)
                cmd.extend(["--width", str(p.width), "--height", str(p.height)])
            except (ImportError, ValueError):
                pass

        try:
            self.run_command(cmd, timeout=600)
        except Exception as e:
            return ToolResult(success=False, error=f"Remotion render failed: {e}")
        finally:
            if props_path.exists():
                props_path.unlink()

        if not output_path.exists():
            return ToolResult(
                success=False,
                error=f"Remotion render completed but output file missing: {output_path}",
            )

        return ToolResult(
            success=True,
            data={
                "operation": "remotion_render",
                "output": str(output_path),
                "profile": profile_name,
            },
            artifacts=[str(output_path)],
        )

    def _burn_subtitles(self, inputs: dict[str, Any]) -> ToolResult:
        """Burn subtitle file into video."""
        input_path = Path(inputs["input_path"])
        subtitle_path = Path(inputs["subtitle_path"])
        output_path = Path(inputs.get("output_path", str(input_path.with_stem(f"{input_path.stem}_subtitled"))))

        if not input_path.exists():
            return ToolResult(success=False, error=f"Input not found: {input_path}")
        if not subtitle_path.exists():
            return ToolResult(success=False, error=f"Subtitle file not found: {subtitle_path}")

        style = inputs.get("subtitle_style", {})
        ass_style = self._build_subtitle_style(style)
        sub_escaped = str(subtitle_path.resolve()).replace("\\", "/").replace(":", "\\:")
        codec = inputs.get("codec", "libx264")
        crf = inputs.get("crf", 23)

        cmd = [
            "ffmpeg", "-y",
            "-i", str(input_path),
            "-vf", f"subtitles='{sub_escaped}':force_style='{ass_style}'",
            "-c:v", codec, "-crf", str(crf),
            "-c:a", "copy",
            str(output_path),
        ]

        self.run_command(cmd)

        return ToolResult(
            success=True,
            data={
                "operation": "burn_subtitles",
                "output": str(output_path),
            },
            artifacts=[str(output_path)],
        )

    def _overlay(self, inputs: dict[str, Any]) -> ToolResult:
        """Composite overlay images/videos on top of base video."""
        input_path = Path(inputs["input_path"])
        overlays = inputs.get("overlays", [])
        output_path = Path(inputs.get("output_path", str(input_path.with_stem(f"{input_path.stem}_overlay"))))
        codec = inputs.get("codec", "libx264")
        crf = inputs.get("crf", 23)

        if not input_path.exists():
            return ToolResult(success=False, error=f"Input not found: {input_path}")
        if not overlays:
            return ToolResult(success=False, error="No overlays provided")

        # Build complex filter for each overlay
        input_args = ["-i", str(input_path)]
        filter_parts = []
        prev_label = "0:v"

        for i, ov in enumerate(overlays):
            asset_path = Path(ov["asset_path"])
            if not asset_path.exists():
                return ToolResult(success=False, error=f"Overlay asset not found: {asset_path}")

            input_args.extend(["-i", str(asset_path)])

            x = int(ov.get("x", 0))
            y = int(ov.get("y", 0))
            start = ov.get("start_seconds", 0)
            end = ov.get("end_seconds")
            opacity = ov.get("opacity", 1.0)

            overlay_input = f"{i + 1}:v"

            # Scale overlay if dimensions specified
            if "width" in ov and "height" in ov:
                w = int(ov["width"])
                h = int(ov["height"])
                filter_parts.append(f"[{overlay_input}]scale={w}:{h}[ov_scaled_{i}]")
                overlay_input = f"ov_scaled_{i}"

            # Build enable expression for timed overlays
            enable = f"between(t,{start},{end})" if end else f"gte(t,{start})"
            out_label = f"v{i}"

            filter_parts.append(
                f"[{prev_label}][{overlay_input}]overlay={x}:{y}:enable='{enable}'[{out_label}]"
            )
            prev_label = out_label

        filter_complex = ";".join(filter_parts)

        cmd = ["ffmpeg", "-y"]
        cmd.extend(input_args)
        cmd.extend(["-filter_complex", filter_complex])
        cmd.extend(["-map", f"[{prev_label}]", "-map", "0:a?"])
        cmd.extend(["-c:v", codec, "-crf", str(crf), "-c:a", "copy"])
        cmd.append(str(output_path))

        self.run_command(cmd)

        return ToolResult(
            success=True,
            data={
                "operation": "overlay",
                "overlay_count": len(overlays),
                "output": str(output_path),
            },
            artifacts=[str(output_path)],
        )

    def _encode(self, inputs: dict[str, Any]) -> ToolResult:
        """Re-encode video with a specific profile/codec settings."""
        input_path = Path(inputs["input_path"])
        output_path = Path(inputs.get("output_path", str(input_path.with_stem(f"{input_path.stem}_encoded"))))
        codec = inputs.get("codec", "libx264")
        crf = inputs.get("crf", 23)
        preset = inputs.get("preset", "medium")
        profile_name = inputs.get("profile")

        if not input_path.exists():
            return ToolResult(success=False, error=f"Input not found: {input_path}")

        cmd = [
            "ffmpeg", "-y",
            "-i", str(input_path),
            "-c:v", codec, "-crf", str(crf), "-preset", preset,
            "-c:a", "aac", "-b:a", "192k",
        ]

        # Apply media profile if specified
        if profile_name:
            try:
                from lib.media_profiles import get_profile, ffmpeg_output_args
                profile = get_profile(profile_name)
                cmd.extend(["-s", f"{profile.width}x{profile.height}"])
                cmd.extend(["-r", str(profile.fps)])
            except (ImportError, ValueError):
                pass  # proceed without profile

        cmd.append(str(output_path))
        self.run_command(cmd)

        return ToolResult(
            success=True,
            data={
                "operation": "encode",
                "codec": codec,
                "crf": crf,
                "profile": profile_name,
                "output": str(output_path),
            },
            artifacts=[str(output_path)],
        )

    @staticmethod
    def _build_subtitle_style(style: dict) -> str:
        """Build ASS force_style string from style dict.

        Produces modern social-media-style captions by default:
        bold, outlined, positioned in the lower portion of the frame.
        """
        parts = []
        parts.append(f"FontName={style.get('font', 'Arial')}")
        parts.append(f"FontSize={style.get('font_size', 16)}")
        parts.append(f"Bold={1 if style.get('bold', True) else 0}")
        if style.get("primary_color"):
            parts.append(f"PrimaryColour={style['primary_color']}")
        if style.get("outline_color"):
            parts.append(f"OutlineColour={style['outline_color']}")
        if style.get("back_color"):
            parts.append(f"BackColour={style['back_color']}")
        # BorderStyle: 1=outline+shadow (default), 4=opaque box
        border_style = style.get("border_style", 1)
        parts.append(f"BorderStyle={border_style}")
        parts.append(f"Outline={style.get('outline_width', 3)}")
        parts.append(f"Shadow={style.get('shadow', 1)}")
        parts.append(f"MarginV={style.get('margin_v', 40)}")
        parts.append(f"Alignment={style.get('alignment', 2)}")
        return ",".join(parts)

    @staticmethod
    def _build_atempo(factor: float) -> str:
        """Build atempo filter chain for audio speed adjustment."""
        filters = []
        remaining = factor
        while remaining > 100.0:
            filters.append("atempo=100.0")
            remaining /= 100.0
        while remaining < 0.5:
            filters.append("atempo=0.5")
            remaining /= 0.5
        filters.append(f"atempo={remaining:.4f}")
        return ",".join(filters)
