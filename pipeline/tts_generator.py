"""Legacy TTS helpers kept for backward compatibility."""

import logging
from enum import Enum

from config import OUTPUT_DIR
from models.scene_schema import Mood, Scene, Setting
from providers.tts_provider import PlaceholderTTSProvider

logger = logging.getLogger(__name__)


class Voice(Enum):
    MALE_DEEP = "male_deep"
    MALE_NEUTRAL = "male_neutral"
    FEMALE_SOFT = "female_soft"
    FEMALE_STRONG = "female_strong"
    NARRATOR_EPIC = "narrator_epic"


def generate_narration(scene_id: int, text: str, voice: Voice = Voice.NARRATOR_EPIC, speed: float = 1.0) -> str:
    """Generate placeholder narration wav file and return path."""
    _ = voice, speed
    scene = Scene(
        scene_id=scene_id,
        title=f"Scene {scene_id}",
        description=text,
        characters=[],
        setting=Setting.FOREST,
        mood=Mood.CALM,
        narration_text=text,
    )
    audio_path = OUTPUT_DIR / "audio" / f"scene_{scene_id:03d}.wav"
    logger.info("[TTS] Generating narration for scene %s", scene_id)
    provider = PlaceholderTTSProvider()
    return str(provider.generate(scene, text, audio_path))


def adjust_audio_speed(audio_path: str, speed_factor: float = 1.0) -> str:
    _ = speed_factor
    return audio_path.replace(".wav", "_speed.wav")


def normalize_audio_levels(audio_path: str) -> str:
    return audio_path.replace(".wav", "_normalized.wav")


class VoiceProfile:
    def __init__(self, voice_name: str, gender: str = "neutral", age_range: str = "adult", accent: str = "neutral"):
        self.voice_name = voice_name
        self.gender = gender
        self.age_range = age_range
        self.accent = accent
        self.pitch = 1.0
        self.rate = 1.0
        self.volume = 1.0

    def to_dict(self) -> dict:
        return {
            "voice_name": self.voice_name,
            "gender": self.gender,
            "age_range": self.age_range,
            "accent": self.accent,
            "pitch": self.pitch,
            "rate": self.rate,
            "volume": self.volume,
        }


class NarrationSettings:
    def __init__(self, voice: Voice = Voice.NARRATOR_EPIC, speed: float = 1.0, emotion: str = "neutral"):
        self.voice = voice
        self.speed = max(0.5, min(2.0, speed))
        self.emotion = emotion
        self.add_pauses = True
        self.background_music_mixing = True
        self.compression = True

    def to_dict(self) -> dict:
        return {
            "voice": self.voice.value,
            "speed": self.speed,
            "emotion": self.emotion,
            "add_pauses": self.add_pauses,
            "background_music_mixing": self.background_music_mixing,
            "compression": self.compression,
        }
