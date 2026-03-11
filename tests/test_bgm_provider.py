"""Tests for local-asset BGM provider selection."""

import tempfile
import unittest
from pathlib import Path

from config import ProviderSettings
from models.scene_schema import Mood, Scene, Setting
from providers.bgm_provider import RuleBasedBGMProvider


def _scene(mood: Mood = Mood.MYSTERIOUS) -> Scene:
    return Scene(
        scene_id=1,
        title="Scene",
        description="desc",
        characters=[],
        setting=Setting.FOREST,
        mood=mood,
    )


class BGMProviderTests(unittest.TestCase):
    def test_selects_exact_mood_setting_track(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            assets = Path(tmp) / "assets"
            assets.mkdir(parents=True, exist_ok=True)
            exact = assets / "forest_mysterious.mp3"
            exact.write_bytes(b"music")

            provider = RuleBasedBGMProvider(
                ProviderSettings(bgm_assets_dir=assets)
            )
            output = Path(tmp) / "run" / "bgm" / "scene_001.mp3"
            selected = provider.select(_scene(Mood.MYSTERIOUS), {"setting": "forest"}, output)

            self.assertTrue(selected.exists())
            self.assertEqual(selected.name, "scene_001.mp3")
            self.assertEqual(selected.read_bytes(), b"music")

    def test_falls_back_to_available_track_when_exact_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            assets = Path(tmp) / "assets"
            assets.mkdir(parents=True, exist_ok=True)
            fallback = assets / "default_ambient.mp3"
            fallback.write_bytes(b"default")

            provider = RuleBasedBGMProvider(
                ProviderSettings(bgm_assets_dir=assets)
            )
            output = Path(tmp) / "run" / "bgm" / "scene_001.mp3"
            selected = provider.select(_scene(Mood.TENSE), {"setting": "forest"}, output)

            self.assertTrue(selected.exists())
            self.assertEqual(selected.read_bytes(), b"default")


if __name__ == "__main__":
    unittest.main()
