"""
Configuration settings for the AI Storytelling Engine.
"""

from pathlib import Path

# Project root directory
PROJECT_ROOT = Path(__file__).parent.resolve()

# Asset directories
ASSETS_DIR = PROJECT_ROOT / "assets"
CHARACTERS_DIR = ASSETS_DIR / "characters"
SCENES_DIR = ASSETS_DIR / "scenes"
EFFECTS_DIR = ASSETS_DIR / "effects"
BGM_DIR = ASSETS_DIR / "bgm"

# Output directories
OUTPUT_DIR = PROJECT_ROOT / "output"
OUTPUT_IMAGES_DIR = OUTPUT_DIR / "images"
OUTPUT_AUDIO_DIR = OUTPUT_DIR / "audio"

# AI Model Configuration (placeholders for future integration)
ILLUSTRATION_MODEL = "openai"  # "openai", "stable_diffusion", "custom", etc.
TTS_MODEL = "openai"  # "openai", "elevenlabs", "gcloud", etc.
BGM_MODEL = "rule_based"  # "rule_based", "custom_ai", etc.

# Generation parameters
IMAGE_RESOLUTION = (1920, 1080)
AUDIO_FORMAT = "mp3"
BGM_VOLUME = 0.3
NARRATION_VOLUME = 0.8
VOICE_SPEED = 1.0

# Logging
LOG_LEVEL = "INFO"
ENABLE_CONSOLE_LOGGING = True

# Processing
MAX_SCENES = 100
SCENE_GENERATION_TIMEOUT = 60  # seconds
RETRY_ATTEMPTS = 3

# Sample story configuration
CONFIG_SAMPLE_STORY = True
