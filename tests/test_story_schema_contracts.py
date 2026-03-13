"""Contract-focused tests for canonical story schema flow."""

import unittest

from engine.parser.extractor_factory import build_story_extractor
from engine.parser.extractors import (
    BaseStoryExtractor,
    DeterministicStoryExtractor,
    GPTStoryExtractor,
    OllamaStoryExtractor,
)
from engine.parser.story_adapter import story_content_to_story_json, story_json_to_story_content
from engine.parser.story_parser import StoryParser
from engine.parser.story_validator import validate_story_json
from engine.scene_builder.scene_builder import build_scene
from engine.scene_builder.scene_instruction_validator import (
    validate_scene_instruction,
    validate_scene_instructions,
)
from models.scene_schema import (
    Character,
    CharacterData,
    CharacterDefinition,
    LocationDefinition,
    Mood,
    Scene,
    Setting,
    StoryContent,
    StoryVisualBible,
    StyleDefinition,
)


class FakeExtractor(BaseStoryExtractor):
    def extract(self, text: str) -> dict:
        _ = text
        return {
            "story_id": "fake_story",
            "title": "Fake",
            "style": "anime",
            "characters": [],
            "locations": [],
            "scenes": [],
        }


class StoryParserDefaultingTests(unittest.TestCase):
    def test_story_parser_uses_default_deterministic_extractor(self) -> None:
        parser = StoryParser()

        story_json = parser.parse("Narrator watches the rain.")

        self.assertEqual(story_json["style"], "anime")
        self.assertTrue(story_json["scenes"])

    def test_story_parser_accepts_custom_extractor_dependency(self) -> None:
        parser = StoryParser(extractor=FakeExtractor())

        story_json = parser.parse("ignored")

        self.assertEqual(story_json["story_id"], "fake_story")
        self.assertEqual(story_json["title"], "Fake")
        self.assertEqual(story_json["scenes"], [])

    def test_deterministic_extractor_emits_expected_canonical_shape(self) -> None:
        extractor = DeterministicStoryExtractor()

        story_json = extractor.extract("MIRA: We are too late.\nThe tavern door swings open.")

        self.assertIn("story_id", story_json)
        self.assertIn("title", story_json)
        self.assertIn("style", story_json)
        self.assertIn("characters", story_json)
        self.assertIn("locations", story_json)
        self.assertIn("scenes", story_json)
        self.assertIsInstance(story_json["scenes"], list)
        self.assertIn("scene_id", story_json["scenes"][0])
        self.assertIn("camera", story_json["scenes"][0])

    def test_missing_location_defaults_to_unknown_location(self) -> None:
        parser = StoryParser()
        story_json = parser.parse("Narrator watches the rain.")

        self.assertEqual(story_json["locations"][0]["id"], "unknown_location")
        self.assertEqual(story_json["scenes"][0]["location"], "unknown_location")

    def test_missing_characters_falls_back_to_narrator(self) -> None:
        parser = StoryParser()
        story_json = parser.parse("")

        self.assertEqual(story_json["characters"][0]["id"], "narrator")
        self.assertEqual(story_json["characters"][0]["name"], "Narrator")

    def test_missing_scenes_gets_default_scene_after_validation(self) -> None:
        story_json = validate_story_json(
            {
                "story_id": "story",
                "title": "No Scenes",
                "style": "anime",
                "characters": [],
                "locations": [],
                "scenes": [],
            }
        )

        self.assertEqual(len(story_json["scenes"]), 1)
        self.assertEqual(story_json["scenes"][0]["scene_id"], 1)
        self.assertEqual(story_json["scenes"][0]["location"], "unknown_location")


class StoryValidatorTests(unittest.TestCase):
    def test_validator_normalizes_malformed_camera_and_missing_duration(self) -> None:
        normalized = validate_story_json(
            {
                "story_id": "story",
                "title": "Camera Test",
                "style": "anime",
                "scenes": [
                    {
                        "scene_id": 7,
                        "location": "forest",
                        "characters": [],
                        "camera": "bad",
                        "actions": [],
                        "dialogue": [],
                    }
                ],
            }
        )

        scene = normalized["scenes"][0]
        self.assertEqual(scene["camera"], {"shot": "medium shot", "angle": "eye level"})
        self.assertEqual(scene["duration_sec"], 5)
        self.assertEqual(scene["characters"], ["narrator"])

    def test_validator_inserts_missing_top_level_arrays(self) -> None:
        normalized = validate_story_json({"story_id": "story", "title": "Top Level", "style": "anime"})

        self.assertEqual(normalized["characters"], [])
        self.assertEqual(normalized["locations"], [])
        self.assertEqual(len(normalized["scenes"]), 1)


class StoryExtractorFactoryTests(unittest.TestCase):
    def test_build_story_extractor_returns_deterministic_extractor(self) -> None:
        extractor = build_story_extractor("deterministic")

        self.assertIsInstance(extractor, DeterministicStoryExtractor)

    def test_build_story_extractor_returns_ollama_extractor(self) -> None:
        extractor = build_story_extractor("ollama")

        self.assertIsInstance(extractor, OllamaStoryExtractor)

    def test_build_story_extractor_returns_gpt_extractor(self) -> None:
        extractor = build_story_extractor("gpt")

        self.assertIsInstance(extractor, GPTStoryExtractor)

    def test_build_story_extractor_raises_for_unknown_kind(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unsupported story extractor: unknown"):
            build_story_extractor("unknown")

    def test_ollama_extractor_stub_raises_not_implemented(self) -> None:
        extractor = OllamaStoryExtractor()

        with self.assertRaisesRegex(NotImplementedError, "OllamaStoryExtractor is not implemented yet"):
            extractor.extract("story")

    def test_gpt_extractor_stub_raises_not_implemented(self) -> None:
        extractor = GPTStoryExtractor()

        with self.assertRaisesRegex(NotImplementedError, "GPTStoryExtractor is not implemented yet"):
            extractor.extract("story")


class SceneBuilderContractTests(unittest.TestCase):
    def test_scene_builder_emits_stable_instruction_schema(self) -> None:
        instruction = build_scene(
            {
                "scene_id": 1,
                "location": "ancient_tavern",
                "duration_sec": 5,
                "characters": ["zhangsan"],
                "camera": {"shot": "medium shot", "angle": "eye level"},
                "actions": [
                    {
                        "character": "zhangsan",
                        "type": "enter",
                        "emotion": "neutral",
                        "description": "Zhangsan enters the tavern.",
                    }
                ],
                "dialogue": [{"speaker": "zhangsan", "text": "Hello.", "emotion": "neutral"}],
                "style": "anime",
            }
        )

        self.assertEqual(instruction["scene_id"], 1)
        self.assertTrue(instruction["image_prompt"])
        self.assertEqual(instruction["characters"], ["zhangsan"])
        self.assertEqual(instruction["location"], "ancient_tavern")
        self.assertEqual(instruction["camera"]["shot"], "medium shot")
        self.assertEqual(instruction["camera"]["angle"], "eye level")
        self.assertEqual(instruction["duration_sec"], 5)
        self.assertEqual(len(instruction["dialogue"]), 1)
        self.assertEqual(len(instruction["actions"]), 1)


class SceneInstructionValidatorTests(unittest.TestCase):
    def test_duplicate_scene_id_fails(self) -> None:
        with self.assertRaisesRegex(ValueError, "duplicate scene_id"):
            validate_scene_instructions(
                [
                    {
                        "scene_id": 1,
                        "image_prompt": "scene one",
                        "characters": [],
                        "location": "forest",
                        "camera": {"shot": "medium shot", "angle": "eye level"},
                        "duration_sec": 5,
                        "dialogue": [],
                        "actions": [],
                    },
                    {
                        "scene_id": 1,
                        "image_prompt": "scene two",
                        "characters": [],
                        "location": "forest",
                        "camera": {"shot": "medium shot", "angle": "eye level"},
                        "duration_sec": 5,
                        "dialogue": [],
                        "actions": [],
                    },
                ]
            )

    def test_empty_image_prompt_fails(self) -> None:
        with self.assertRaisesRegex(ValueError, "empty image_prompt"):
            validate_scene_instruction(
                {
                    "scene_id": 1,
                    "image_prompt": "",
                    "characters": [],
                    "location": "forest",
                    "camera": {"shot": "medium shot", "angle": "eye level"},
                    "duration_sec": 5,
                    "dialogue": [],
                    "actions": [],
                }
            )

    def test_invalid_duration_sec_fails(self) -> None:
        with self.assertRaisesRegex(ValueError, "invalid duration_sec"):
            validate_scene_instruction(
                {
                    "scene_id": 1,
                    "image_prompt": "scene",
                    "characters": [],
                    "location": "forest",
                    "camera": {"shot": "medium shot", "angle": "eye level"},
                    "duration_sec": 0,
                    "dialogue": [],
                    "actions": [],
                }
            )


class StoryAdapterRoundTripTests(unittest.TestCase):
    def test_round_trip_preserves_key_identity_fields(self) -> None:
        story = StoryContent(
            title="Round Trip",
            author="Tester",
            description="story",
            scenes=[
                Scene(
                    scene_id=1,
                    title="Scene 1",
                    description="Hero enters the tavern.",
                    characters=[CharacterData(name="Hero", type=Character.HERO, emotion="neutral", action="enter")],
                    setting=Setting.TAVERN,
                    mood=Mood.CALM,
                    narration_text="Hero enters the tavern.",
                    location_id="ancient_tavern",
                    active_character_ids=["hero_001"],
                    action_description="Hero enters the tavern.",
                    camera_description="medium shot, eye level",
                )
            ],
            visual_bible=StoryVisualBible(
                title="Round Trip",
                style=StyleDefinition(art_style="anime"),
                characters=[],
                locations=[LocationDefinition(location_id="ancient_tavern", name="Ancient Tavern")],
            ),
        )
        story.visual_bible.characters.append(
            CharacterDefinition(
                character_id="hero_001",
                name="Hero",
                role="hero",
                appearance="blue coat",
            )
        )

        story_json = validate_story_json(story_content_to_story_json(story))
        round_tripped = validate_story_json(
            story_content_to_story_json(story_json_to_story_content(story_json, author="Tester"))
        )

        self.assertEqual(round_tripped["title"], "Round Trip")
        self.assertEqual(round_tripped["style"], "anime")
        self.assertEqual(len(round_tripped["scenes"]), 1)
        self.assertEqual(round_tripped["characters"][0]["id"], "hero_001")
        self.assertEqual(round_tripped["locations"][0]["id"], "ancient_tavern")


if __name__ == "__main__":
    unittest.main()
