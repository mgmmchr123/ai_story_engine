"""Compatibility parser API that delegates to placeholder parser provider."""

import logging

from models.scene_schema import CharacterData, Mood, Setting, StoryContent
from providers.story_parser_provider import PlaceholderStoryParserProvider

logger = logging.getLogger(__name__)


def parse_story(story_text: str, title: str, author: str) -> StoryContent:
    """Legacy parse function retained for compatibility and tests."""
    logger.info("[PARSER] Parsing story: %s", title)
    provider = PlaceholderStoryParserProvider()
    story = provider.parse(story_text=story_text, title=title, author=author)
    logger.info("[PARSER] Generated %s scenes", len(story.scenes))
    return story


# Placeholder hooks retained for compatibility.
def extract_characters_nlp(text: str) -> list[CharacterData]:
    _ = text
    return []


def detect_setting_nlp(text: str) -> Setting:
    _ = text
    return Setting.FOREST


def detect_mood_nlp(text: str) -> Mood:
    _ = text
    return Mood.MYSTERIOUS
