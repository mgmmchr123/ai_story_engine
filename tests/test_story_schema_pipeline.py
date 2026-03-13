"""Tests for schema-driven parse and scene-builder flow."""

import unittest

from engine.parser.story_parser import StoryParser, story_json_to_story_content
from engine.scene_builder.scene_builder import build_scene


class StorySchemaPipelineTests(unittest.TestCase):
    def test_story_parser_emits_story_json_and_scene_builder_instruction(self) -> None:
        parser = StoryParser()
        story_json = parser.parse(
            "Mira enters the tavern.\n"
            "MIRA: We are too late.\n\n"
            "The lanterns sway above the bar."
        )

        self.assertIn("story_id", story_json)
        self.assertEqual(story_json["style"], "anime")
        self.assertTrue(story_json["characters"])
        self.assertTrue(story_json["locations"])
        self.assertGreaterEqual(len(story_json["scenes"]), 1)

        instruction = build_scene({**story_json["scenes"][0], "style": story_json["style"]})
        self.assertIn("image_prompt", instruction)
        self.assertIn("characters", instruction)
        self.assertIn("duration", instruction)

        story = story_json_to_story_content(story_json, author="Tester")
        self.assertEqual(story.author, "Tester")
        self.assertEqual(len(story.scenes), len(story_json["scenes"]))


if __name__ == "__main__":
    unittest.main()
