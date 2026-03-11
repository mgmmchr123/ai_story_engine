"""Unit tests for prompt builder functions."""

import unittest

from models.scene_schema import (
    Character,
    CharacterData,
    CharacterDefinition,
    LocationDefinition,
    Mood,
    Scene,
    Setting,
    StoryVisualBible,
    StyleDefinition,
)
from pipeline.prompt_builder import build_bgm_prompt, build_image_prompt, build_narration_prompt


class PromptBuilderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.scene = Scene(
            scene_id=1,
            title="Arrival",
            description="The hero arrives at the old castle.",
            characters=[
                CharacterData(name="Aria", type=Character.HERO, emotion="focused", action="walking"),
            ],
            setting=Setting.CASTLE,
            mood=Mood.HEROIC,
            narration_text="Aria pushed open the castle gates.",
            location_id="castle_001",
            active_character_ids=["hero_001"],
            action_description="Aria enters the castle courtyard with urgency.",
            camera_description="wide shot",
        )
        self.visual_bible = StoryVisualBible(
            title="Integration Story",
            style=StyleDefinition(
                art_style="stylized fantasy realism",
                lighting_style="moody rim lighting",
                rendering_style="high-detail painterly",
                mood_baseline="adventurous and tense",
                consistency_instructions="Keep Aria's face, armor, and cloak consistent.",
            ),
            characters=[
                CharacterDefinition(
                    character_id="hero_001",
                    name="Aria",
                    role="hero",
                    appearance="young knight with short black hair",
                    outfit="silver armor and blue cloak",
                    props=["long sword"],
                    personality_keywords=["determined", "brave"],
                )
            ],
            locations=[
                LocationDefinition(
                    location_id="castle_001",
                    name="Ironkeep Castle",
                    appearance="massive stone fortress with high battlements",
                    environment_details="rain-soaked courtyard and torch-lit walls",
                    color_palette="cold gray stone with warm orange torches",
                    default_time_of_day="night",
                )
            ],
        )

    def test_build_image_prompt_contains_expected_elements(self) -> None:
        prompt = build_image_prompt(self.scene)
        self.assertIn("Aria", prompt)
        self.assertIn("castle", prompt)
        self.assertIn("heroic", prompt)

    def test_build_image_prompt_uses_visual_bible_and_scene_state(self) -> None:
        prompt = build_image_prompt(self.scene, self.visual_bible)
        self.assertIn("stylized fantasy realism", prompt)
        self.assertIn("Ironkeep Castle", prompt)
        self.assertIn("silver armor and blue cloak", prompt)
        self.assertIn("Aria enters the castle courtyard", prompt)

    def test_build_image_prompt_gracefully_handles_missing_references(self) -> None:
        scene = Scene(
            scene_id=2,
            title="Unknown Scene",
            description="No known IDs.",
            characters=[CharacterData(name="Unknown", type=Character.NPC, emotion="neutral", action="standing")],
            setting=Setting.FOREST,
            mood=Mood.MYSTERIOUS,
            location_id="missing_loc",
            active_character_ids=["missing_char"],
            action_description="A shadow moves.",
        )
        prompt = build_image_prompt(scene, self.visual_bible)
        self.assertIn("missing_loc", prompt)
        self.assertIn("A shadow moves.", prompt)

    def test_build_narration_prompt_prefixes_title(self) -> None:
        narration = build_narration_prompt(self.scene)
        self.assertTrue(narration.startswith("Arrival."))

    def test_build_bgm_prompt_contains_intensity_and_tempo(self) -> None:
        bgm = build_bgm_prompt(self.scene)
        self.assertEqual(bgm["mood"], "heroic")
        self.assertIn("intensity", bgm)
        self.assertIn("tempo", bgm)

    def test_build_bgm_prompt_prefers_scene_state_location_over_stale_setting(self) -> None:
        scene = Scene(
            scene_id=2,
            title="Throne Return",
            description="The hero enters the throne room.",
            characters=self.scene.characters,
            setting=Setting.FOREST,  # intentionally stale legacy value
            mood=Mood.CALM,
            narration_text="The hero enters the throne room.",
            location_id="throne_room_001",
            active_character_ids=["hero_001"],
            action_description="The hero presents the artifact.",
        )
        visual_bible = StoryVisualBible(
            title="Story",
            style=self.visual_bible.style,
            characters=self.visual_bible.characters,
            locations=[
                LocationDefinition(
                    location_id="throne_room_001",
                    name="Throne Room",
                    appearance="grand royal chamber",
                    environment_details="gold pillars and crimson drapes",
                    color_palette="gold and red",
                    default_time_of_day="day",
                )
            ],
        )
        bgm = build_bgm_prompt(scene, visual_bible)
        self.assertEqual(bgm["setting"], "throne_room")
        self.assertEqual(bgm["genre"], "epic_orchestral")


if __name__ == "__main__":
    unittest.main()
