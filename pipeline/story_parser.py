"""
Story Parser Module - Converts raw story text into structured scenes.
"""

import logging
from typing import List
from models.scene_schema import (
    StoryContent, 
    Scene, 
    Character_Data, 
    Character, 
    Setting, 
    Mood
)

logger = logging.getLogger(__name__)


def parse_story(story_text: str, title: str, author: str) -> StoryContent:

    logger.info(f"[PARSER] Parsing story: {title}")

    lines = story_text.strip().split("\n")

    scenes = []
    scene_id = 1

    for line in lines:
        line = line.strip()
        if not line:
            continue

        characters = extract_characters_nlp(line)
        setting = detect_setting_nlp(line)
        mood = detect_mood_nlp(line)

        scene = Scene(
            scene_id=scene_id,
            title=f"Scene {scene_id}",
            description=line,
            characters=characters or [
                Character_Data(
                    name="Unknown",
                    type=Character.NPC,
                    emotion="neutral",
                    action="standing"
                )
            ],
            setting=setting,
            mood=mood,
            narration_text=line
        )

        scenes.append(scene)
        scene_id += 1

    story = StoryContent(
        title=title,
        author=author,
        description=f"{len(scenes)} scenes generated",
        scenes=scenes
    )

    logger.info(f"[PARSER] Generated {len(scenes)} scenes")

    return story

# Placeholder for advanced parsing with NLP
def extract_characters_nlp(text: str) -> List[Character_Data]:
    """
    Extract characters using NLP (placeholder).
    
    Future implementation:
    - Use spaCy/NLTK for named entity recognition
    - Match entities to character archetypes
    - Extract emotion/action descriptors
    """
    logger.debug("[PARSER] Extracting characters (NLP placeholder)")
    return []


def detect_setting_nlp(text: str) -> Setting:
    """
    Detect scene setting using NLP (placeholder).
    
    Future implementation:
    - Use semantic similarity to known settings
    - Extract location descriptors
    """
    logger.debug("[PARSER] Detecting setting (NLP placeholder)")
    return Setting.FOREST


def detect_mood_nlp(text: str) -> Mood:
    """
    Detect scene mood using sentiment analysis (placeholder).
    
    Future implementation:
    - Use sentiment analysis models
    - Analyze vocabulary for tone
    - Cross-reference with scene context
    """
    logger.debug("[PARSER] Detecting mood (NLP placeholder)")
    return Mood.MYSTERIOUS
