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
    *,
    trailing_padding_ms: int = 500,
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
        target_duration_ms = _resolve_target_duration_ms(
            narration_segment=narration_segment,
            bgm_segment=bgm_segment,
            trailing_padding_ms=trailing_padding_ms,
        )

        if narration_segment and bgm_segment:
            lowered_bgm = _fit_bgm_to_duration(
                segment=bgm_segment - abs(float(bgm_reduction_db)),
                target_duration_ms=target_duration_ms,
            )
            mixed = lowered_bgm.overlay(_pad_narration(narration_segment, target_duration_ms))
            return _export_audiosegment(mixed, output_path)

        if narration_segment:
            return _export_audiosegment(_pad_narration(narration_segment, target_duration_ms), output_path)
        if bgm_segment:
            return _export_audiosegment(
                _fit_bgm_to_duration(segment=bgm_segment, target_duration_ms=target_duration_ms),
                output_path,
            )
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


def _resolve_target_duration_ms(narration_segment, bgm_segment, trailing_padding_ms: int) -> int:  # noqa: ANN001
    if narration_segment is not None:
        return len(narration_segment) + max(0, int(trailing_padding_ms))
    if bgm_segment is not None:
        return len(bgm_segment)
    return 0


def _fit_bgm_to_duration(segment, target_duration_ms: int):  # noqa: ANN001
    if target_duration_ms <= 0:
        return segment
    if len(segment) < target_duration_ms:
        loops = ceil(target_duration_ms / max(len(segment), 1))
        segment = segment * loops
    return segment[:target_duration_ms]


def _pad_narration(segment, target_duration_ms: int):  # noqa: ANN001
    if target_duration_ms <= len(segment):
        return segment[:target_duration_ms]
    return segment + AudioSegment.silent(duration=target_duration_ms - len(segment))
