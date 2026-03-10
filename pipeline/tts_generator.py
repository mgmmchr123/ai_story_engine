"""
Text-to-Speech (TTS) Generator Module - Generates narration audio from text.
"""
import wave
import struct

import logging
from pathlib import Path
from enum import Enum
from config import OUTPUT_AUDIO_DIR

logger = logging.getLogger(__name__)


class Voice(Enum):
    """Available voice options."""
    MALE_DEEP = "male_deep"
    MALE_NEUTRAL = "male_neutral"
    FEMALE_SOFT = "female_soft"
    FEMALE_STRONG = "female_strong"
    NARRATOR_EPIC = "narrator_epic"


class TTSProvider(Enum):
    """Text-to-speech providers."""
    OPENAI = "openai"
    ELEVENLABS = "elevenlabs"
    GOOGLE_CLOUD = "google_cloud"
    AZURE = "azure"
    LOCAL = "local"  # Local TTS engine


def generate_narration(scene_id: int, text: str, voice: Voice = Voice.NARRATOR_EPIC,
                      speed: float = 1.0) -> str:

    logger.info(f"[TTS] Generating narration for scene {scene_id}")

    audio_filename = f"scene_{scene_id:03d}.wav"
    audio_path = OUTPUT_AUDIO_DIR / audio_filename

    # 生成1秒简单音频
    sample_rate = 44100
    duration = 1
    frequency = 440

    with wave.open(str(audio_path), 'w') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)

        for i in range(sample_rate * duration):
            value = int(32767 * 0.3)
            data = struct.pack('<h', value)
            wav_file.writeframesraw(data)

    logger.info(f"[TTS] Placeholder narration created: {audio_path}")

    return str(audio_path)

def adjust_audio_speed(audio_path: str, speed_factor: float = 1.0) -> str:
    """
    Adjust playback speed of audio file.
    
    Args:
        audio_path: Path to audio file
        speed_factor: Speed multiplier (0.5-2.0)
        
    Returns:
        Path to speed-adjusted audio
    """
    logger.debug(f"[TTS] Adjusting audio speed: {speed_factor}x")
    
    # TODO: Implement with librosa or pydub
    # from pydub import AudioSegment
    # sound = AudioSegment.from_mp3(audio_path)
    # sped_up = sound.speedup(playback_speed=speed_factor)
    # sped_up.export(output_path, format="mp3")
    
    output_path = audio_path.replace(".mp3", f"_speed{speed_factor:.1f}.mp3")
    logger.debug(f"[TTS] Audio speed adjusted: {output_path}")
    
    return output_path


def normalize_audio_levels(audio_path: str) -> str:
    """
    Normalize audio levels for consistent playback.
    
    Args:
        audio_path: Path to audio file
        
    Returns:
        Path to normalized audio
    """
    logger.debug(f"[TTS] Normalizing audio levels: {audio_path}")
    
    # TODO: Implement with librosa or pydub
    # from pydub import AudioSegment
    # sound = AudioSegment.from_mp3(audio_path)
    # normalized = sound.normalize()
    # normalized.export(output_path, format="mp3")
    
    output_path = audio_path.replace(".mp3", "_normalized.mp3")
    logger.debug(f"[TTS] Audio normalized: {output_path}")
    
    return output_path


class VoiceProfile:
    """Voice configuration and characteristics."""
    
    def __init__(self, voice_name: str, gender: str = "neutral", 
                 age_range: str = "adult", accent: str = "neutral"):
        """
        Initialize voice profile.
        
        Args:
            voice_name: Name of the voice
            gender: Voice gender
            age_range: Age range the voice represents
            accent: Accent/language variant
        """
        self.voice_name = voice_name
        self.gender = gender
        self.age_range = age_range
        self.accent = accent
        self.pitch = 1.0
        self.rate = 1.0
        self.volume = 1.0
        
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "voice_name": self.voice_name,
            "gender": self.gender,
            "age_range": self.age_range,
            "accent": self.accent,
            "pitch": self.pitch,
            "rate": self.rate,
            "volume": self.volume
        }


class NarrationSettings:
    """Settings for narration generation."""
    
    def __init__(self, voice: Voice = Voice.NARRATOR_EPIC, 
                 speed: float = 1.0, emotion: str = "neutral"):
        """
        Initialize narration settings.
        
        Args:
            voice: Voice to use
            speed: Speech speed (0.5-2.0)
            emotion: Emotion style (neutral, happy, sad, dramatic, etc.)
        """
        self.voice = voice
        self.speed = max(0.5, min(2.0, speed))  # Clamp between 0.5 and 2.0
        self.emotion = emotion
        self.add_pauses = True
        self.background_music_mixing = True
        self.compression = True  # Dynamic range compression
        
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "voice": self.voice.value,
            "speed": self.speed,
            "emotion": self.emotion,
            "add_pauses": self.add_pauses,
            "background_music_mixing": self.background_music_mixing,
            "compression": self.compression
        }
