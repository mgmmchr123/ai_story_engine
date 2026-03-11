"""Tests for story parser providers."""

import json
import unittest
from unittest.mock import patch

from config import ParserSettings
from models.scene_schema import Mood, Setting
from providers.story_parser_provider import OllamaStoryParserProvider


class _FakeHTTPResponse:
    def __init__(self, payload: dict):
        self._raw = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._raw

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class StoryParserProviderTests(unittest.TestCase):
    @patch("providers.story_parser_provider.urllib_request.urlopen")
    def test_ollama_provider_parses_structured_json(self, mock_urlopen) -> None:
        visual_bible_content = {
            "story_description": "Adventure journey.",
            "visual_bible": {
                "style": {
                    "art_style": "cinematic fantasy",
                    "lighting_style": "moonlit dramatic lighting",
                    "rendering_style": "detailed digital painting",
                    "mood_baseline": "mysterious heroism",
                    "consistency_instructions": "Keep Aria's look consistent.",
                },
                "characters": [
                    {
                        "character_id": "hero_001",
                        "name": "Aria",
                        "role": "hero",
                        "appearance": "young knight with short black hair",
                        "outfit": "silver armor and blue cloak",
                        "props": ["long sword"],
                        "personality_keywords": ["determined", "brave"],
                    }
                ],
                "locations": [
                    {
                        "location_id": "forest_001",
                        "name": "Whispering Forest",
                        "appearance": "ancient dark forest with twisted trees",
                        "environment_details": "blue mist and deep shadows",
                        "color_palette": "cool blue and deep green",
                        "default_time_of_day": "night",
                    }
                ],
            },
        }
        scene_state_content = {
            "story_description": "Adventure journey.",
            "scene_states": [
                {
                    "scene_id": 1,
                    "title": "Forest Arrival",
                    "location_id": "forest_001",
                    "active_character_ids": ["hero_001"],
                    "action_description": "Aria enters the forest with caution.",
                    "description": "Hero enters forest.",
                    "mood": "heroic",
                    "camera_description": "wide shot",
                    "narration_text": "Aria stepped into the forest.",
                }
            ],
        }
        mock_urlopen.side_effect = [
            _FakeHTTPResponse({"message": {"content": json.dumps(visual_bible_content)}}),
            _FakeHTTPResponse({"message": {"content": json.dumps(scene_state_content)}}),
        ]

        provider = OllamaStoryParserProvider(ParserSettings())
        story = provider.parse("Some story text", title="My Story", author="Me")

        self.assertEqual(story.title, "My Story")
        self.assertEqual(len(story.scenes), 1)
        self.assertEqual(story.scenes[0].title, "Forest Arrival")
        self.assertEqual(story.scenes[0].setting, Setting.FOREST)
        self.assertEqual(story.scenes[0].mood, Mood.HEROIC)
        self.assertEqual(story.scenes[0].active_character_ids, ["hero_001"])
        self.assertEqual(story.scenes[0].location_id, "forest_001")
        self.assertEqual(story.scenes[0].characters[0].name, "Aria")
        self.assertIsNotNone(story.visual_bible)
        assert story.visual_bible is not None
        self.assertEqual(story.visual_bible.characters[0].character_id, "hero_001")
        self.assertEqual(story.visual_bible.locations[0].location_id, "forest_001")
        character_ids = {item.character_id for item in story.visual_bible.characters}
        location_ids = {item.location_id for item in story.visual_bible.locations}
        self.assertIn(story.scenes[0].location_id, location_ids)
        self.assertTrue(all(char_id in character_ids for char_id in story.scenes[0].active_character_ids))
        self.assertEqual(mock_urlopen.call_count, 2)

    @patch("providers.story_parser_provider.urllib_request.urlopen")
    def test_ollama_provider_normalizes_unknown_values(self, mock_urlopen) -> None:
        visual_bible_content = {
            "description": "Unknown fields test.",
            "visual_bible": {
                "characters": [{"character_id": "x_001", "name": "X", "role": "alien"}],
                "locations": [{"location_id": "base_001", "name": "Unknown Base"}],
            },
        }
        scene_state_content = {
            "description": "Unknown fields test.",
            "scene_states": [
                {
                    "title": "Odd Scene",
                    "description": "Unknown setting and mood.",
                    "location_id": "base_001",
                    "active_character_ids": ["x_001"],
                    "setting": "space_station",
                    "mood": "melancholic",
                    "narration_text": "Odd narration.",
                }
            ],
        }
        mock_urlopen.side_effect = [
            _FakeHTTPResponse({"message": {"content": json.dumps(visual_bible_content)}}),
            _FakeHTTPResponse({"message": {"content": json.dumps(scene_state_content)}}),
        ]

        provider = OllamaStoryParserProvider(ParserSettings())
        story = provider.parse("Some story text", title="My Story", author="Me")

        self.assertEqual(story.scenes[0].setting, Setting.FOREST)
        self.assertEqual(story.scenes[0].mood, Mood.MYSTERIOUS)
        self.assertEqual(story.scenes[0].characters[0].type.value, "npc")
        self.assertEqual(story.scenes[0].active_character_ids, ["x_001"])
        self.assertEqual(story.scenes[0].location_id, "base_001")
        self.assertEqual(mock_urlopen.call_count, 2)

    @patch("providers.story_parser_provider.urllib_request.urlopen")
    def test_ollama_provider_upgrades_opaque_ids_to_semantic_ids(self, mock_urlopen) -> None:
        visual_bible_content = {
            "story_description": "Opaque IDs test.",
            "visual_bible": {
                "characters": [{"character_id": "001", "name": "Aria", "role": "hero"}],
                "locations": [{"location_id": "002", "name": "Throne Room"}],
            },
        }
        scene_state_content = {
            "scene_states": [
                {
                    "scene_id": 1,
                    "title": "Finale",
                    "location_id": "002",
                    "active_character_ids": ["001"],
                    "description": "Aria returns.",
                    "mood": "calm",
                    "narration_text": "Aria returns.",
                }
            ]
        }
        mock_urlopen.side_effect = [
            _FakeHTTPResponse({"message": {"content": json.dumps(visual_bible_content)}}),
            _FakeHTTPResponse({"message": {"content": json.dumps(scene_state_content)}}),
        ]

        provider = OllamaStoryParserProvider(ParserSettings())
        story = provider.parse("Some story text", title="My Story", author="Me")
        assert story.visual_bible is not None
        self.assertEqual(story.visual_bible.characters[0].character_id, "hero_001")
        self.assertEqual(story.visual_bible.locations[0].location_id, "throne_room_002")
        self.assertEqual(story.scenes[0].active_character_ids, ["hero_001"])
        self.assertEqual(story.scenes[0].location_id, "throne_room_002")


if __name__ == "__main__":
    unittest.main()
