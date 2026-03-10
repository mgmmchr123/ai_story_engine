"""
Prompt Builder Module - Creates prompts for AI models from scene data.
"""

import logging
from models.scene_schema import Scene, Character_Data

logger = logging.getLogger(__name__)


def build_image_prompt(scene: Scene) -> str:

    characters = ", ".join([c.name for c in scene.characters])

    prompt = (
        f"{characters} in a {scene.setting.value}, "
        f"{scene.mood.value} atmosphere, "
        f"{scene.description}, "
        "cinematic lighting, dramatic composition, "
        "high quality illustration"
    )

    return prompt

def build_narration_text(scene: Scene) -> str:

    narration = f"{scene.title}. {scene.narration_text}"

    return narration

def build_bgm_prompt(scene: Scene) -> dict:
    """
    Build parameters for background music selection.
    
    Args:
        scene: Scene object
        
    Returns:
        Dictionary of parameters for BGM selector
    """
    logger.debug(f"[PROMPT_BUILDER] Building BGM prompt for scene {scene.scene_id}")
    
    bgm_params = {
        "mood": scene.mood.value,
        "setting": scene.setting.value,
        "intensity": _calculate_intensity(scene),
        "tempo": _calculate_tempo(scene),
        "duration_seconds": 180,
        "genre": _determine_genre(scene.setting)
    }
    
    logger.debug(f"[PROMPT_BUILDER] BGM parameters: {bgm_params}")
    return bgm_params


def _calculate_intensity(scene: Scene) -> str:
    """Determine scene intensity level."""
    mood_intensity_map = {
        "heroic": "high",
        "epic": "high",
        "tense": "medium",
        "mysterious": "medium",
        "calm": "low",
        "humorous": "low"
    }
    return mood_intensity_map.get(scene.mood.value, "medium")


def _calculate_tempo(scene: Scene) -> str:
    """Determine BGM tempo based on mood."""
    mood_tempo_map = {
        "heroic": "fast",
        "epic": "moderate",
        "tense": "fast",
        "mysterious": "slow",
        "calm": "slow",
        "humorous": "moderate"
    }
    return mood_tempo_map.get(scene.mood.value, "moderate")

def build_narration_prompt(scene):
    """
    Build narration text for TTS.
    """

    narration = f"{scene.title}. {scene.narration_text}"

    return narration

def _determine_genre(setting) -> str:
    """Determine appropriate music genre for setting."""
    genre_map = {
        "forest": "orchestral",
        "castle": "orchestral",
        "village": "folk",
        "dungeon": "dark_orchestral",
        "throne_room": "epic_orchestral",
        "tavern": "folk"
    }
    return genre_map.get(setting.value, "orchestral")


class PromptTemplate:
    """Template system for standardized prompts."""
    
    SYSTEM_PROMPT = """You are a creative AI assistant helping to generate 
    immersive story content. Your outputs should be detailed, vivid, and 
    cinematically appropriate."""
    
    SCENE_CONTEXT_TEMPLATE = """
    Story: {title}
    Author: {author}
    Current Scene: {scene_number}/{total_scenes}
    Previous Context: {previous_context}
    """
    
    @staticmethod
    def format_system_prompt() -> str:
        """Return the system prompt."""
        return PromptTemplate.SYSTEM_PROMPT
    
    @staticmethod
    def format_context(title: str, author: str, scene_num: int, 
                      total_scenes: int, previous_context: str = "") -> str:
        """Format context information for the prompt."""
        return PromptTemplate.SCENE_CONTEXT_TEMPLATE.format(
            title=title,
            author=author,
            scene_number=scene_num,
            total_scenes=total_scenes,
            previous_context=previous_context or "None"
        )
