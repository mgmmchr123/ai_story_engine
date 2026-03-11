"""Helpers for scene-level and story-level audio assembly."""

import logging
from math import ceil
import os
from pathlib import Path
import shutil
from typing import Iterable

from config import ENGINE_SETTINGS

logger = logging.getLogger(__name__)

os.environ["FFMPEG_BINARY"] = ENGINE_SETTINGS.providers.ffmpeg_binary_path
os.environ["FFPROBE_BINARY"] = ENGINE_SETTINGS.providers.ffprobe_binary_path
ffmpeg_dir = str(Path(ENGINE_SETTINGS.providers.ffmpeg_binary_path).parent)
if ffmpeg_dir:
    os.environ["PATH"] = f"{ffmpeg_dir};{os.environ.get('PATH', '')}"

try:
    from pydub import AudioSegment
except Exception:  # noqa: BLE001
    AudioSegment = None  # type: ignore[assignment]

if AudioSegment is not None:
    AudioSegment.converter = ENGINE_SETTINGS.providers.ffmpeg_binary_path
    AudioSegment.ffmpeg = ENGINE_SETTINGS.providers.ffmpeg_binary_path
    AudioSegment.ffprobe = ENGINE_SETTINGS.providers.ffprobe_binary_path


def mix_scene_audio(
    narration_path: Path | None,
    bgm_path: Path | None,
    output_path: Path,
    bgm_reduction_db: float,
) -> Path | None:
    """Mix narration and BGM, with graceful degradation for missing assets/tools."""
    narration_exists = bool(narration_path and narration_path.exists())
    bgm_exists = bool(bgm_path and bgm_path.exists())

    if not narration_exists and not bgm_exists:
        logger.warning("[AUDIO] scene mix skipped: no narration or bgm source available")
        return None

    output_path.parent.mkdir(parents=True, exist_ok=True)

    if AudioSegment is None:
        logger.warning("[AUDIO] pydub unavailable; using file-copy fallback for scene mix")
        if narration_exists:
            fallback = output_path.with_suffix(".wav")
            shutil.copy2(narration_path, fallback)  # type: ignore[arg-type]
            return fallback
        fallback = output_path.with_suffix(bgm_path.suffix if bgm_path else ".wav")
        if bgm_path:
            shutil.copy2(bgm_path, fallback)
            return fallback
        return None

    try:
        narration_segment = AudioSegment.from_file(narration_path) if narration_exists else None  # type: ignore[arg-type]
        bgm_segment = AudioSegment.from_file(bgm_path) if bgm_exists else None  # type: ignore[arg-type]

        if narration_segment and bgm_segment:
            lowered_bgm = bgm_segment - abs(float(bgm_reduction_db))
            if len(lowered_bgm) < len(narration_segment):
                loops = ceil(len(narration_segment) / max(len(lowered_bgm), 1))
                lowered_bgm = lowered_bgm * loops
            lowered_bgm = lowered_bgm[: len(narration_segment)]
            mixed = lowered_bgm.overlay(narration_segment)
            return _export_audiosegment(mixed, output_path)

        if narration_segment:
            return _export_audiosegment(narration_segment, output_path)
        if bgm_segment:
            return _export_audiosegment(bgm_segment, output_path)
        return None
    except Exception as exc:  # noqa: BLE001
        logger.warning("[AUDIO] pydub mix failed (%s); using file-copy fallback", exc)
        return _copy_fallback(
            narration_path=narration_path if narration_exists else None,
            bgm_path=bgm_path if bgm_exists else None,
            output_path=output_path,
        )


def export_story_audio(scene_audio_paths: Iterable[Path], output_path: Path) -> Path | None:
    """Concatenate scene-level audio files in order."""
    valid_paths = [path for path in scene_audio_paths if path and path.exists()]
    if not valid_paths:
        logger.warning("[AUDIO] final story export skipped: no scene audio files found")
        return None

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if AudioSegment is None:
        logger.warning("[AUDIO] pydub unavailable; final export fallback copies first scene audio")
        fallback = output_path.with_suffix(valid_paths[0].suffix)
        shutil.copy2(valid_paths[0], fallback)
        return fallback

    try:
        combined = AudioSegment.empty()
        for scene_path in valid_paths:
            combined += AudioSegment.from_file(scene_path)
        return _export_audiosegment(combined, output_path)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[AUDIO] final concatenation failed (%s); copying first available audio", exc)
        fallback = output_path.with_suffix(valid_paths[0].suffix)
        shutil.copy2(valid_paths[0], fallback)
        return fallback


def _export_audiosegment(segment, output_path: Path) -> Path:  # noqa: ANN001
    try:
        segment.export(output_path, format="mp3")
        return output_path
    except Exception as exc:  # noqa: BLE001
        fallback = output_path.with_suffix(".wav")
        logger.warning("[AUDIO] mp3 export failed (%s); falling back to wav export: %s", exc, fallback)
        segment.export(fallback, format="wav")
        return fallback


def _copy_fallback(narration_path: Path | None, bgm_path: Path | None, output_path: Path) -> Path | None:
    if narration_path and narration_path.exists():
        fallback = output_path.with_suffix(".wav")
        shutil.copy2(narration_path, fallback)
        return fallback
    if bgm_path and bgm_path.exists():
        fallback = output_path.with_suffix(bgm_path.suffix)
        shutil.copy2(bgm_path, fallback)
        return fallback
    return None
