"""TTS provider interfaces and implementations."""

from abc import ABC, abstractmethod
import logging
from pathlib import Path
import shutil
import struct
import subprocess
import time
import wave

from config import ProviderSettings
from engine.logging_utils import preview_text
from models.scene_schema import Scene

logger = logging.getLogger(__name__)


class TTSProvider(ABC):
    """Generates narration audio artifacts."""

    @abstractmethod
    def generate(self, scene: Scene, narration_text: str, output_path: Path) -> Path:
        """Generate narration file and return path."""


class PlaceholderTTSProvider(TTSProvider):
    """Creates deterministic tone audio for local testing."""

    def generate(self, scene: Scene, narration_text: str, output_path: Path) -> Path:
        _log_tts_input(scene=scene, narration_text=narration_text, provider="placeholder")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        sample_rate = 16000
        duration_seconds = 1
        amplitude = 0.2

        with wave.open(str(output_path), "w") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            for _ in range(sample_rate * duration_seconds):
                value = int(32767 * amplitude)
                wav_file.writeframesraw(struct.pack("<h", value))
        return output_path


class PiperTTSProvider(TTSProvider):
    """Local Piper CLI provider with fallback to placeholder."""

    def __init__(self, settings: ProviderSettings, fallback_provider: TTSProvider | None = None):
        self.settings = settings
        self.fallback_provider = fallback_provider or PlaceholderTTSProvider()

    def generate(self, scene: Scene, narration_text: str, output_path: Path) -> Path:
        started = time.monotonic()
        _log_tts_input(scene=scene, narration_text=narration_text, provider="piper")
        logger.info(
            "[TTS] provider=piper scene_id=%s output=%s model=%s language=%s voice=%s",
            scene.scene_id,
            output_path,
            self.settings.piper_model_path,
            self.settings.tts_language,
            self.settings.tts_voice_name,
        )
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            binary = self._resolve_binary()
            model_path = self._resolve_model()
            command = self._build_command(binary=binary, model_path=model_path, output_path=output_path)
            subprocess.run(
                command,
                input=narration_text,
                text=True,
                capture_output=True,
                timeout=self.settings.piper_timeout_seconds,
                check=True,
            )
            self._validate_output(output_path)
            duration = time.monotonic() - started
            logger.info(
                "[TTS] provider=piper scene_id=%s output=%s duration=%.2fs",
                scene.scene_id,
                output_path,
                duration,
            )
            return output_path
        except Exception as exc:  # noqa: BLE001
            output_path.unlink(missing_ok=True)
            duration = time.monotonic() - started
            logger.warning(
                "[TTS] provider=piper scene_id=%s output=%s fallback=placeholder reason=%s duration=%.2fs",
                scene.scene_id,
                output_path,
                exc,
                duration,
            )
            return self.fallback_provider.generate(scene, narration_text, output_path)

    def _resolve_binary(self) -> str:
        if self.settings.piper_binary_path:
            binary = Path(self.settings.piper_binary_path)
            if not binary.exists():
                raise FileNotFoundError(f"Piper binary not found: {binary}")
            return str(binary)

        for candidate in ("piper-tts", "piper"):
            resolved = shutil.which(candidate)
            if resolved:
                return resolved
        raise FileNotFoundError("Piper executable not found on PATH (tried: piper-tts, piper)")

    def _resolve_model(self) -> Path:
        if not self.settings.piper_model_path:
            raise ValueError("Piper model path is not configured")
        model_path = Path(self.settings.piper_model_path)
        if not model_path.exists():
            raise FileNotFoundError(f"Piper model not found: {model_path}")
        return model_path

    def _build_command(self, binary: str, model_path: Path, output_path: Path) -> list[str]:
        command = [
            binary,
            "--model",
            str(model_path),
            "--output_file",
            str(output_path),
            "--length_scale",
            str(self.settings.piper_length_scale),
            "--noise_scale",
            str(self.settings.piper_noise_scale),
            "--noise_w",
            str(self.settings.piper_noise_w),
        ]
        if self.settings.piper_config_path:
            command.extend(["--config", str(self.settings.piper_config_path)])
        if self.settings.tts_speaker_id is not None:
            command.extend(["--speaker", str(self.settings.tts_speaker_id)])
        return command

    def _validate_output(self, output_path: Path) -> None:
        if not output_path.exists():
            raise FileNotFoundError(f"Piper did not produce output file: {output_path}")
        size = output_path.stat().st_size
        if size <= int(self.settings.piper_min_audio_bytes):
            raise ValueError(
                f"Piper output too small ({size} bytes), expected > {self.settings.piper_min_audio_bytes}"
            )


def build_tts_provider(settings: ProviderSettings) -> TTSProvider:
    """Resolve provider from settings."""
    if settings.tts_provider == "placeholder":
        return PlaceholderTTSProvider()
    if settings.tts_provider == "piper":
        return PiperTTSProvider(settings=settings, fallback_provider=PlaceholderTTSProvider())
    raise ValueError(f"Unsupported TTS provider: {settings.tts_provider}")


def _log_tts_input(scene: Scene, narration_text: str, provider: str) -> None:
    narration_length = len(narration_text or "")
    logger.info(
        "[TTS] provider=%s scene_id=%s narration_chars=%s preview=%s",
        provider,
        scene.scene_id,
        narration_length,
        preview_text(narration_text, max_len=120),
    )
    if not (narration_text or "").strip():
        logger.warning("[TTS] provider=%s scene_id=%s narration_text is empty", provider, scene.scene_id)
