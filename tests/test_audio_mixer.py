"""Tests for scene-level and final audio export helpers."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pipeline.audio_mixer import export_story_audio, mix_scene_audio


class _FakeSegment:
    exported = []
    loaded = []

    def __init__(self, duration=1000, sources=None):
        self.duration = duration
        self.sources = sources or []

    def __len__(self):
        return self.duration

    def __sub__(self, other):  # noqa: ANN001
        return self

    def __mul__(self, loops):  # noqa: ANN001
        return _FakeSegment(duration=self.duration * loops, sources=self.sources)

    def __getitem__(self, item):  # noqa: ANN001
        if isinstance(item, slice):
            stop = item.stop if item.stop is not None else self.duration
            return _FakeSegment(duration=int(stop), sources=self.sources)
        return self

    def overlay(self, other):  # noqa: ANN001
        return _FakeSegment(duration=max(self.duration, len(other)), sources=self.sources + other.sources)

    def __add__(self, other):  # noqa: ANN001
        return _FakeSegment(duration=self.duration + other.duration, sources=self.sources + other.sources)

    def export(self, output_path, format):  # noqa: ANN001
        _FakeSegment.exported.append((str(output_path), format, list(self.sources)))
        Path(output_path).write_bytes(b"x" * 2048)


class _FakeAudioSegmentModule:
    @staticmethod
    def from_file(path):  # noqa: ANN001
        _FakeSegment.loaded.append(str(path))
        return _FakeSegment(duration=1000, sources=[str(path)])

    @staticmethod
    def empty():
        return _FakeSegment(duration=0, sources=[])


class _BrokenAudioSegmentModule:
    @staticmethod
    def from_file(path):  # noqa: ANN001
        raise FileNotFoundError("ffmpeg missing")

    @staticmethod
    def empty():
        return _FakeSegment(duration=0, sources=[])


class AudioMixerTests(unittest.TestCase):
    def test_narration_only_mix_when_bgm_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            narration = root / "scene_001.wav"
            narration.write_bytes(b"narration")
            output = root / "mixed" / "scene_001.mp3"

            with patch("pipeline.audio_mixer.AudioSegment", None):
                mixed = mix_scene_audio(narration, None, output, bgm_reduction_db=14.0)

            assert mixed is not None
            self.assertTrue(mixed.exists())
            self.assertEqual(mixed.suffix, ".wav")

    def test_bgm_only_mix_when_narration_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bgm = root / "scene_001.mp3"
            bgm.write_bytes(b"bgm")
            output = root / "mixed" / "scene_001.mp3"

            with patch("pipeline.audio_mixer.AudioSegment", None):
                mixed = mix_scene_audio(None, bgm, output, bgm_reduction_db=14.0)

            assert mixed is not None
            self.assertTrue(mixed.exists())

    def test_final_story_export_concatenates_in_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = root / "scene_001.mp3"
            second = root / "scene_002.mp3"
            first.write_bytes(b"a")
            second.write_bytes(b"b")
            out = root / "final" / "story.mp3"

            _FakeSegment.exported = []
            _FakeSegment.loaded = []
            with patch("pipeline.audio_mixer.AudioSegment", _FakeAudioSegmentModule):
                final = export_story_audio([first, second], out)

            assert final is not None
            self.assertTrue(final.exists())
            self.assertEqual(_FakeSegment.loaded, [str(first), str(second)])

    def test_mix_degrades_to_copy_when_pydub_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            narration = root / "scene_001.wav"
            narration.write_bytes(b"narration")
            output = root / "mixed" / "scene_001.mp3"

            with patch("pipeline.audio_mixer.AudioSegment", _BrokenAudioSegmentModule):
                mixed = mix_scene_audio(narration, None, output, bgm_reduction_db=14.0)

            assert mixed is not None
            self.assertTrue(mixed.exists())
            self.assertEqual(mixed.suffix, ".wav")


if __name__ == "__main__":
    unittest.main()
