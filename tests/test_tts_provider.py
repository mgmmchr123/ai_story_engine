"""Tests for TTS provider selection and Piper fallback behavior."""

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from config import ProviderSettings
from models.scene_schema import Mood, Scene, Setting
from providers.tts_provider import PiperTTSProvider, PlaceholderTTSProvider, build_tts_provider


def _sample_scene() -> Scene:
    return Scene(
        scene_id=1,
        title="Scene 1",
        description="A hero speaks.",
        characters=[],
        setting=Setting.FOREST,
        mood=Mood.HEROIC,
        narration_text="A hero speaks.",
    )


class TTSProviderTests(unittest.TestCase):
    def test_build_tts_provider_selects_piper(self) -> None:
        provider = build_tts_provider(ProviderSettings(tts_provider="piper"))
        self.assertIsInstance(provider, PiperTTSProvider)

    @patch("providers.tts_provider.subprocess.run")
    @patch("providers.tts_provider.shutil.which")
    def test_piper_success_path_returns_generated_wav(self, mock_which, mock_run) -> None:
        mock_which.return_value = "piper-tts"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            model = root / "model.onnx"
            model.write_bytes(b"model")
            output = root / "scene_001.wav"
            settings = ProviderSettings(
                tts_provider="piper",
                piper_model_path=str(model),
                piper_min_audio_bytes=1024,
            )
            provider = PiperTTSProvider(settings=settings)

            def _run_side_effect(command, **kwargs):  # noqa: ANN001
                out_path = Path(command[command.index("--output_file") + 1])
                out_path.write_bytes(b"x" * 2048)
                return subprocess.CompletedProcess(command, returncode=0)

            mock_run.side_effect = _run_side_effect
            result = provider.generate(_sample_scene(), "Hello world", output)

            self.assertEqual(result, output)
            self.assertTrue(output.exists())
            self.assertGreater(output.stat().st_size, 1024)

    @patch("providers.tts_provider.subprocess.run")
    @patch("providers.tts_provider.shutil.which")
    def test_piper_subprocess_failure_triggers_fallback(self, mock_which, mock_run) -> None:
        mock_which.return_value = "piper-tts"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            model = root / "model.onnx"
            model.write_bytes(b"model")
            output = root / "scene_001.wav"
            settings = ProviderSettings(
                tts_provider="piper",
                piper_model_path=str(model),
            )
            provider = PiperTTSProvider(settings=settings, fallback_provider=PlaceholderTTSProvider())
            mock_run.side_effect = subprocess.CalledProcessError(returncode=1, cmd="piper")

            result = provider.generate(_sample_scene(), "Hello world", output)

            self.assertEqual(result, output)
            self.assertTrue(output.exists())
            self.assertGreater(output.stat().st_size, 1024)

    def test_missing_piper_binary_triggers_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            model = root / "model.onnx"
            model.write_bytes(b"model")
            output = root / "scene_001.wav"
            settings = ProviderSettings(
                tts_provider="piper",
                piper_binary_path=str(root / "missing_piper.exe"),
                piper_model_path=str(model),
            )
            provider = PiperTTSProvider(settings=settings, fallback_provider=PlaceholderTTSProvider())

            result = provider.generate(_sample_scene(), "Hello world", output)

            self.assertEqual(result, output)
            self.assertTrue(output.exists())
            self.assertGreater(output.stat().st_size, 1024)

    @patch("providers.tts_provider.shutil.which")
    def test_missing_model_triggers_fallback(self, mock_which) -> None:
        mock_which.return_value = "piper-tts"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / "scene_001.wav"
            settings = ProviderSettings(
                tts_provider="piper",
                piper_model_path=str(root / "missing_model.onnx"),
            )
            provider = PiperTTSProvider(settings=settings, fallback_provider=PlaceholderTTSProvider())

            result = provider.generate(_sample_scene(), "Hello world", output)

            self.assertEqual(result, output)
            self.assertTrue(output.exists())
            self.assertGreater(output.stat().st_size, 1024)

    @patch("providers.tts_provider.subprocess.run")
    @patch("providers.tts_provider.shutil.which")
    def test_tiny_wav_triggers_fallback(self, mock_which, mock_run) -> None:
        mock_which.return_value = "piper-tts"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            model = root / "model.onnx"
            model.write_bytes(b"model")
            output = root / "scene_001.wav"
            settings = ProviderSettings(
                tts_provider="piper",
                piper_model_path=str(model),
                piper_min_audio_bytes=1024,
            )
            provider = PiperTTSProvider(settings=settings, fallback_provider=PlaceholderTTSProvider())

            def _run_side_effect(command, **kwargs):  # noqa: ANN001
                out_path = Path(command[command.index("--output_file") + 1])
                out_path.write_bytes(b"x" * 256)
                return subprocess.CompletedProcess(command, returncode=0)

            mock_run.side_effect = _run_side_effect
            result = provider.generate(_sample_scene(), "Hello world", output)

            self.assertEqual(result, output)
            self.assertTrue(output.exists())
            self.assertGreater(output.stat().st_size, 1024)


if __name__ == "__main__":
    unittest.main()
