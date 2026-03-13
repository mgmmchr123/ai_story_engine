"""Tests for FFmpeg-based video exporter."""

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from engine.video_exporter import (
    export_video,
    get_media_duration,
    probe_final_video_duration,
)


class VideoExporterTests(unittest.TestCase):
    @patch("engine.video_exporter.subprocess.run")
    @patch("engine.video_exporter._resolve_binary")
    def test_export_video_builds_mp4(self, mock_resolve_binary, mock_run) -> None:
        mock_resolve_binary.side_effect = ["ffmpeg", "ffprobe"]
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            images_dir = run_dir / "images"
            audio_dir = run_dir / "audio"
            images_dir.mkdir(parents=True, exist_ok=True)
            audio_dir.mkdir(parents=True, exist_ok=True)
            for idx in range(1, 3):
                (images_dir / f"scene_{idx:03d}.png").write_bytes(b"png")
                (audio_dir / f"scene_{idx:03d}.wav").write_bytes(b"wav")
            final_dir = run_dir / "final"
            final_dir.mkdir(parents=True, exist_ok=True)
            (final_dir / "story.mp3").write_bytes(b"mp3")

            def _run_side_effect(command, **kwargs):  # noqa: ANN001
                if "ffprobe" in command[0]:
                    target = str(command[-1])
                    if target.endswith("story.mp3"):
                        return subprocess.CompletedProcess(command, returncode=0, stdout="3.0\n", stderr="")
                    if target.endswith("combined_segments.mp4"):
                        return subprocess.CompletedProcess(command, returncode=0, stdout="2.0\n", stderr="")
                    if target.endswith("combined_segments_padded.mp4"):
                        return subprocess.CompletedProcess(command, returncode=0, stdout="3.0\n", stderr="")
                    if target.endswith("final_video.mp4"):
                        return subprocess.CompletedProcess(command, returncode=0, stdout="3.0\n", stderr="")
                    return subprocess.CompletedProcess(command, returncode=0, stdout="1.0\n", stderr="")
                if len(command) == 3 and command[1] == "-i" and command[2] == str(run_dir / "video" / "final_video.mp4"):
                    return subprocess.CompletedProcess(
                        command,
                        returncode=0,
                        stdout="",
                        stderr="Stream #0:0: Video: h264\nStream #0:1: Audio: aac\n",
                    )
                output = Path(command[-1])
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_bytes(b"video")
                return subprocess.CompletedProcess(command, returncode=0, stdout="", stderr="")

            mock_run.side_effect = _run_side_effect
            exported = export_video(run_dir)

            self.assertTrue(exported.exists())
            self.assertEqual(exported.suffix, ".mp4")

    @patch("engine.video_exporter.subprocess.run")
    @patch("engine.video_exporter._resolve_binary")
    def test_export_video_applies_guard_frame_when_mux_is_still_short(self, mock_resolve_binary, mock_run) -> None:
        mock_resolve_binary.side_effect = ["ffmpeg", "ffprobe"]
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            images_dir = run_dir / "images"
            audio_dir = run_dir / "audio"
            images_dir.mkdir(parents=True, exist_ok=True)
            audio_dir.mkdir(parents=True, exist_ok=True)
            (images_dir / "scene_001.png").write_bytes(b"png")
            (audio_dir / "scene_001.wav").write_bytes(b"wav")
            final_dir = run_dir / "final"
            final_dir.mkdir(parents=True, exist_ok=True)
            (final_dir / "story.mp3").write_bytes(b"mp3")

            final_video_probe_count = {"count": 0}

            def _run_side_effect(command, **kwargs):  # noqa: ANN001
                if "ffprobe" in command[0]:
                    target = str(command[-1])
                    if target.endswith("story.mp3"):
                        return subprocess.CompletedProcess(command, returncode=0, stdout="3.000\n", stderr="")
                    if target.endswith("combined_segments.mp4"):
                        return subprocess.CompletedProcess(command, returncode=0, stdout="2.900\n", stderr="")
                    if target.endswith("combined_segments_padded.mp4"):
                        return subprocess.CompletedProcess(command, returncode=0, stdout="3.000\n", stderr="")
                    if target.endswith("combined_segments_guarded.mp4"):
                        return subprocess.CompletedProcess(command, returncode=0, stdout="3.083333\n", stderr="")
                    if target.endswith("final_video.mp4"):
                        final_video_probe_count["count"] += 1
                        stdout = "2.900\n" if final_video_probe_count["count"] == 1 else "3.000\n"
                        return subprocess.CompletedProcess(command, returncode=0, stdout=stdout, stderr="")
                    return subprocess.CompletedProcess(command, returncode=0, stdout="1.000\n", stderr="")
                if len(command) == 3 and command[1] == "-i" and command[2] == str(run_dir / "video" / "final_video.mp4"):
                    return subprocess.CompletedProcess(
                        command,
                        returncode=0,
                        stdout="",
                        stderr="Stream #0:0: Video: h264\nStream #0:1: Audio: aac\n",
                    )
                output = Path(command[-1])
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_bytes(b"video")
                return subprocess.CompletedProcess(command, returncode=0, stdout="", stderr="")

            mock_run.side_effect = _run_side_effect
            exported = export_video(run_dir)

            self.assertTrue(exported.exists())
            self.assertGreaterEqual(final_video_probe_count["count"], 2)

    @patch("engine.video_exporter._resolve_binary")
    def test_export_video_raises_on_missing_images(self, mock_resolve_binary) -> None:
        mock_resolve_binary.side_effect = ["ffmpeg", "ffprobe"]
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            final_dir = run_dir / "final"
            final_dir.mkdir(parents=True, exist_ok=True)
            (final_dir / "story.mp3").write_bytes(b"mp3")
            with self.assertRaises(FileNotFoundError):
                export_video(run_dir)

    @patch("engine.video_exporter._resolve_binary")
    def test_export_video_raises_on_missing_audio(self, mock_resolve_binary) -> None:
        mock_resolve_binary.side_effect = ["ffmpeg", "ffprobe"]
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            images_dir = run_dir / "images"
            images_dir.mkdir(parents=True, exist_ok=True)
            (images_dir / "scene_001.png").write_bytes(b"png")
            with self.assertRaises(FileNotFoundError):
                export_video(run_dir)

    @patch("engine.video_exporter.subprocess.run")
    @patch("engine.video_exporter._resolve_binary")
    def test_export_video_raises_if_audio_stream_missing(self, mock_resolve_binary, mock_run) -> None:
        mock_resolve_binary.side_effect = ["ffmpeg", "ffprobe"]
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            images_dir = run_dir / "images"
            audio_dir = run_dir / "audio"
            images_dir.mkdir(parents=True, exist_ok=True)
            audio_dir.mkdir(parents=True, exist_ok=True)
            (images_dir / "scene_001.png").write_bytes(b"png")
            (audio_dir / "scene_001.wav").write_bytes(b"wav")
            final_dir = run_dir / "final"
            final_dir.mkdir(parents=True, exist_ok=True)
            (final_dir / "story.mp3").write_bytes(b"mp3")

            def _run_side_effect(command, **kwargs):  # noqa: ANN001
                if "ffprobe" in command[0]:
                    target = str(command[-1])
                    if target.endswith("story.mp3"):
                        return subprocess.CompletedProcess(command, returncode=0, stdout="2.0\n", stderr="")
                    return subprocess.CompletedProcess(command, returncode=0, stdout="2.0\n", stderr="")
                if len(command) == 3 and command[1] == "-i" and command[2] == str(run_dir / "video" / "final_video.mp4"):
                    return subprocess.CompletedProcess(
                        command,
                        returncode=0,
                        stdout="",
                        stderr="Stream #0:0: Video: h264\n",
                    )
                output = Path(command[-1])
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_bytes(b"video")
                return subprocess.CompletedProcess(command, returncode=0, stdout="", stderr="")

            mock_run.side_effect = _run_side_effect
            with self.assertRaises(RuntimeError):
                export_video(run_dir)

    @patch("engine.video_exporter.subprocess.run")
    def test_get_media_duration_uses_ffprobe(self, mock_run) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            audio = Path(tmp) / "scene_001.wav"
            audio.write_bytes(b"wav")
            mock_run.return_value = subprocess.CompletedProcess(["ffprobe"], returncode=0, stdout="1.234\n", stderr="")
            duration = get_media_duration(audio, ffprobe_bin="ffprobe")
            self.assertAlmostEqual(duration, 1.234, places=3)

    @patch("engine.video_exporter.subprocess.run")
    def test_probe_final_video_duration(self, mock_run) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            video = Path(tmp) / "final_video.mp4"
            video.write_bytes(b"video")
            mock_run.return_value = subprocess.CompletedProcess(["ffprobe"], returncode=0, stdout="9.876\n", stderr="")
            duration = probe_final_video_duration(video, ffprobe_bin="ffprobe")
            self.assertAlmostEqual(duration, 9.876, places=3)


if __name__ == "__main__":
    unittest.main()
