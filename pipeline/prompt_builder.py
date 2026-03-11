"""Prompt builders for image, narration, and BGM providers."""

import logging
from engine.world_state import resolve_scene_location
from models.scene_schema import Scene, StoryVisualBible

logger = logging.getLogger(__name__)


def build_image_prompt(scene: Scene, visual_bible: StoryVisualBible | None = None) -> str:
    """Build a scene prompt using inherited story-level visual definitions."""

    if not visual_bible:
        characters = ", ".join([c.name for c in scene.characters]) or "characters"
        scene_action = scene.action_description or scene.description
        return (
            f"{characters} in a {scene.setting.value}, "
            f"{scene.mood.value} atmosphere, "
            f"{scene_action}, "
            "cinematic lighting, dramatic composition, high quality illustration"
        )

    character_map = visual_bible.character_map()
    location_map = visual_bible.location_map()

    resolved_character_ids = scene.active_character_ids or [
        _find_character_id_by_name(character_map, character.name) for character in scene.characters
    ]
    character_fragments = [
        _character_fragment(character_map.get(character_id))
        for character_id in resolved_character_ids
        if character_id
    ]
    if not character_fragments:
        character_fragments = [", ".join([c.name for c in scene.characters]) or "no named character focus"]

    location = location_map.get(scene.location_id) if scene.location_id else None
    if location:
        location_fragment = _location_fragment(location)
    elif scene.location_id:
        location_fragment = f"{scene.location_id} (unresolved), fallback setting: {scene.setting.value}"
    else:
        location_fragment = scene.setting.value

    style = visual_bible.style
    action = scene.action_description or scene.description
    camera = scene.camera_description or "medium cinematic framing"

    prompt_parts = [
        f"story style: {style.art_style}",
        f"lighting: {style.lighting_style}",
        f"rendering: {style.rendering_style}",
        f"baseline mood: {style.mood_baseline}",
        f"consistency: {style.consistency_instructions}",
        f"location: {location_fragment}",
        f"characters: {'; '.join(character_fragments)}",
        f"current action: {action}",
        f"scene mood: {scene.mood.value}",
        f"camera: {camera}",
    ]

    if scene.state_delta:
        prompt_parts.append(f"state delta: {scene.state_delta}")

    return ", ".join(prompt_parts)


def _find_character_id_by_name(character_map: dict[str, object], name: str) -> str | None:
    normalized = (name or "").strip().lower()
    if not normalized:
        return None
    for character_id, character in character_map.items():
        character_name = getattr(character, "name", "")
        if character_name.strip().lower() == normalized:
            return character_id
    return None


def _character_fragment(character) -> str:  # noqa: ANN001
    if not character:
        return ""
    props = ", ".join(character.props) if character.props else "no specific props"
    personality = ", ".join(character.personality_keywords) if character.personality_keywords else "neutral"
    return (
        f"{character.name} ({character.role}), appearance: {character.appearance}, "
        f"outfit: {character.outfit}, props: {props}, personality: {personality}"
    )


def _location_fragment(location) -> str:  # noqa: ANN001
    if not location:
        return "unspecified location"
    return (
        f"{location.name}, appearance: {location.appearance}, environment: {location.environment_details}, "
        f"palette: {location.color_palette}, time: {location.default_time_of_day}"
    )

def build_bgm_prompt(scene: Scene, visual_bible: StoryVisualBible | None = None) -> dict:
    """
    Build parameters for background music selection.
    
    Args:
        scene: Scene object
        
    Returns:
        Dictionary of parameters for BGM selector
    """
    logger.debug(f"[PROMPT_BUILDER] Building BGM prompt for scene {scene.scene_id}")
    
    location = resolve_scene_location(scene, visual_bible)
    setting_value = location["bgm_setting"]

    bgm_params = {
        "mood": scene.mood.value,
        "setting": setting_value,
        "intensity": _calculate_intensity(scene),
        "tempo": _calculate_tempo(scene),
        "duration_seconds": 180,
        "genre": _determine_genre(setting_value),
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

def build_narration_prompt(scene: Scene) -> str:
    """Build narration text for TTS."""
    return f"{scene.title}. {scene.narration_text}"

def _determine_genre(setting: str) -> str:
    """Determine appropriate music genre for setting."""
    genre_map = {
        "forest": "orchestral",
        "castle": "orchestral",
        "village": "folk",
        "dungeon": "dark_orchestral",
        "throne_room": "epic_orchestral",
        "tavern": "folk"
    }
    return genre_map.get(setting, "orchestral")


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
