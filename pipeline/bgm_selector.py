"""Legacy BGM selector kept for backward compatibility."""

import logging

from config import OUTPUT_DIR
from models.scene_schema import Mood, Scene, Setting
from providers.bgm_provider import RuleBasedBGMProvider

logger = logging.getLogger(__name__)


def select_bgm(mood: str, setting: str, intensity: str = "medium", tempo: str = "moderate") -> str:
    """Select placeholder BGM and return path."""
    scene = Scene(
        scene_id=0,
        title="Legacy BGM Selection",
        description="",
        characters=[],
        setting=Setting(setting),
        mood=Mood(mood),
        narration_text="",
    )
    path = OUTPUT_DIR / "bgm" / "legacy_bgm.txt"
    provider = RuleBasedBGMProvider()
    return str(provider.select(scene, {"intensity": intensity, "tempo": tempo}, path))
