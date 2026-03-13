"""Compatibility parser API backed by canonical story.json parsing."""

import logging

from engine.parser.story_adapter import story_json_to_story_content
from engine.parser.story_parser import StoryParser
from engine.parser.story_validator import validate_story_json
from models.scene_schema import CharacterData, Mood, Setting, StoryContent

logger = logging.getLogger(__name__)


def parse_story(story_text: str, title: str, author: str) -> StoryContent:
    """Legacy parse function retained for compatibility and tests."""
    logger.info("[PARSER] Parsing story: %s", title)
    parser = StoryParser()
    story_json = validate_story_json(parser.parse(story_text))
    story_json["title"] = title or story_json.get("title", "Untitled Story")
    story = story_json_to_story_content(story_json, author=author)
    logger.info("[PARSER] Generated %s scenes", len(story.scenes))
    return story


def extract_characters_nlp(text: str) -> list[CharacterData]:
    _ = text
    return []


def detect_setting_nlp(text: str) -> Setting:
    _ = text
    return Setting.FOREST


def detect_mood_nlp(text: str) -> Mood:
    _ = text
    return Mood.MYSTERIOUS
