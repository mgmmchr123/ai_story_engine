"""Unit tests for story parser."""

import unittest

from pipeline.story_parser import parse_story


class StoryParserTests(unittest.TestCase):
    def test_parse_story_creates_scene_per_non_empty_line(self) -> None:
        story = parse_story(
            story_text="First line\n\nSecond line\nThird line",
            title="Test Story",
            author="Tester",
        )
        self.assertEqual(story.title, "Test Story")
        self.assertEqual(story.author, "Tester")
        self.assertEqual(len(story.scenes), 3)
        self.assertEqual(story.scenes[0].scene_id, 1)
        self.assertEqual(story.scenes[2].scene_id, 3)
        self.assertEqual(story.scenes[1].narration_text, "Second line")


if __name__ == "__main__":
    unittest.main()
