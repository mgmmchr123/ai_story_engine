"""Video export helpers for story runs."""

from __future__ import annotations

import logging
from pathlib import Path
import shutil
import subprocess

from config import ENGINE_SETTINGS

logger = logging.getLogger(__name__)


def export_video(run_dir: Path) -> Path:
    """Export final MP4 by stitching per-scene image+audio segments."""
    images_dir = run_dir / "images"
    audio_dir = run_dir / "audio"
    bgm_dir = run_dir / "bgm"
    final_audio_path = run_dir / "final" / "story.mp3"
    output_dir = run_dir / "video"
    output_path = output_dir / "final_video.mp4"

    ffmpeg_bin = _resolve_binary(ENGINE_SETTINGS.providers.ffmpeg_binary_path, "ffmpeg")
    ffprobe_bin = _resolve_binary(ENGINE_SETTINGS.providers.ffprobe_binary_path, "ffprobe")

    scene_images = sorted(images_dir.glob("scene_*.png"))
    if not scene_images:
        raise FileNotFoundError(f"No scene images found in {images_dir}")
    if not audio_dir.exists():
        raise FileNotFoundError(f"Scene audio directory missing: {audio_dir}")
    if not final_audio_path.exists():
        raise FileNotFoundError(f"Final story audio missing: {final_audio_path}")

    final_audio_duration = get_media_duration(final_audio_path, ffprobe_bin=ffprobe_bin)
    if final_audio_duration <= 0:
        raise ValueError(f"Invalid final audio duration for {final_audio_path}: {final_audio_duration}")

    output_dir.mkdir(parents=True, exist_ok=True)
    segments_dir = output_dir / "segments"
    segments_dir.mkdir(parents=True, exist_ok=True)

    segment_paths: list[Path] = []
    for image_path in scene_images:
        scene_id = image_path.stem.split("_")[-1]
        audio_path = audio_dir / f"scene_{scene_id}.wav"
        bgm_path = bgm_dir / f"scene_{scene_id}.mp3"
        has_bgm = bgm_path.exists()
        if not audio_path.exists():
            raise FileNotFoundError(f"Scene audio missing for {image_path.name}: {audio_path}")

        logger.info(
            "Scene %s inputs: image=%s narration=%s bgm_found=%s bgm=%s",
            scene_id,
            image_path,
            audio_path,
            has_bgm,
            bgm_path if has_bgm else "N/A",
        )

        segment_path = segments_dir / f"scene_{scene_id}.mp4"
        segment_command: list[str] = [
            ffmpeg_bin,
            "-y",
            "-loop",
            "1",
            "-i",
            str(image_path),
            "-i",
            str(audio_path),
        ]
        if has_bgm:
            segment_command.extend(
                [
                    "-i",
                    str(bgm_path),
                    "-filter_complex",
                    "[2:a]volume=0.12[bgm];[1:a][bgm]amix=inputs=2:duration=first:dropout_transition=0[mix]",
                    "-map",
                    "0:v:0",
                    "-map",
                    "[mix]",
                ]
            )

        segment_command.extend(
            [
                "-r",
                "24",
                "-g",
                "24",
                "-keyint_min",
                "24",
                "-sc_threshold",
                "0",
                "-vf",
                "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2",
                "-c:v",
                "libx264",
                "-tune",
                "stillimage",
                "-c:a",
                "aac",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                "-shortest",
                str(segment_path),
            ]
        )
        logger.info("FFmpeg scene segment command: %s", _format_command(segment_command))
        segment_result = subprocess.run(segment_command, capture_output=True, text=True, check=False)
        if segment_result.returncode != 0:
            raise RuntimeError(
                f"ffmpeg scene segment export failed for {image_path.name}: {segment_result.stderr.strip()}"
            )
        if not segment_path.exists():
            raise FileNotFoundError(f"Segment export output missing: {segment_path}")
        segment_paths.append(segment_path)

    if not segment_paths:
        raise FileNotFoundError("No scene segments generated for final export")

    concat_list_path = segments_dir / "concat_list.txt"
    concat_lines = [f"file '{segment_path.resolve().as_posix()}'\n" for segment_path in segment_paths]
    concat_list_path.write_text("".join(concat_lines), encoding="utf-8")

    concat_command = [
        ffmpeg_bin,
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_list_path),
        "-t",
        f"{final_audio_duration:.6f}",
        "-c",
        "copy",
        "-movflags",
        "+faststart",
        str(output_path),
    ]
    logger.info("FFmpeg video concat command: %s", _format_command(concat_command))
    concat_result = subprocess.run(concat_command, capture_output=True, text=True, check=False)
    if concat_result.returncode != 0:
        raise RuntimeError(f"ffmpeg concat failed: {concat_result.stderr.strip()}")
    if not output_path.exists():
        raise FileNotFoundError(f"Video export output missing: {output_path}")

    video_duration = get_media_duration(output_path, ffprobe_bin=ffprobe_bin)
    duration_delta = video_duration - final_audio_duration
    logger.info(
        "Final duration check: video=%.6fs audio=%.6fs delta=%.6fs",
        video_duration,
        final_audio_duration,
        duration_delta,
    )

    if duration_delta > 0.05:
        trimmed_output_path = output_dir / "final_video_trimmed.mp4"
        trim_command = [
            ffmpeg_bin,
            "-y",
            "-i",
            str(output_path),
            "-t",
            f"{final_audio_duration:.6f}",
            "-c",
            "copy",
            "-movflags",
            "+faststart",
            str(trimmed_output_path),
        ]
        logger.info("FFmpeg trim command: %s", _format_command(trim_command))
        trim_result = subprocess.run(trim_command, capture_output=True, text=True, check=False)
        if trim_result.returncode != 0:
            raise RuntimeError(f"ffmpeg trim failed: {trim_result.stderr.strip()}")
        if not trimmed_output_path.exists():
            raise FileNotFoundError(f"Trimmed export output missing: {trimmed_output_path}")
        trimmed_output_path.replace(output_path)

    _log_streams_and_validate_audio(ffmpeg_bin=ffmpeg_bin, video_path=output_path)
    logger.info("Video exported to %s", output_path)
    return output_path


def get_media_duration(path: Path, ffprobe_bin: str | None = None) -> float:
    """Return media duration in seconds."""
    if not path.exists():
        raise FileNotFoundError(f"Media file missing: {path}")
    probe = ffprobe_bin or _resolve_binary(ENGINE_SETTINGS.providers.ffprobe_binary_path, "ffprobe")
    command = [
        probe,
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(path),
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed for {path}: {result.stderr.strip()}")
    return float(result.stdout.strip())


def build_scene_segment(*args, **kwargs):  # noqa: ANN002, ANN003
    """Compatibility shim retained for earlier tests/callers."""
    raise NotImplementedError("Scene-segment build is no longer used in the current exporter flow.")


def concat_segments(*args, **kwargs):  # noqa: ANN002, ANN003
    """Compatibility shim retained for earlier tests/callers."""
    raise NotImplementedError("Segment concatenation is no longer used in the current exporter flow.")


def probe_final_video_duration(video_path: Path, ffprobe_bin: str | None = None) -> float:
    """Probe final video duration using ffprobe."""
    return get_media_duration(video_path, ffprobe_bin=ffprobe_bin)


def _resolve_binary(configured_path: str, fallback_name: str) -> str:
    configured = Path(configured_path) if configured_path else None
    if configured and configured.exists():
        return str(configured)
    discovered = shutil.which(fallback_name)
    if discovered:
        return discovered
    raise FileNotFoundError(f"{fallback_name} binary not found: configured={configured_path}")


def _log_streams_and_validate_audio(ffmpeg_bin: str, video_path: Path) -> None:
    inspect_command = [ffmpeg_bin, "-i", str(video_path)]
    logger.info("FFmpeg stream probe command: %s", _format_command(inspect_command))
    inspect_result = subprocess.run(inspect_command, capture_output=True, text=True, check=False)
    stream_info = inspect_result.stderr.strip()
    logger.info("Final video stream info:\n%s", stream_info)
    if "Audio:" not in stream_info:
        raise RuntimeError(f"No audio stream detected in exported video: {video_path}")


def _format_command(command: list[str]) -> str:
    if hasattr(subprocess, "list2cmdline"):
        return subprocess.list2cmdline(command)
    return " ".join(command)
