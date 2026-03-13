"""Adapters between canonical story.json and legacy StoryContent."""

from __future__ import annotations

import re
from typing import Any

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

_STYLE_VALUES = {"anime", "cartoon", "realistic"}


def story_json_to_story_content(story_json: dict[str, Any], *, author: str = "Anonymous") -> StoryContent:
    """Adapt canonical story.json payload into the legacy StoryContent model."""

    title = str(story_json.get("title") or "Untitled Story")
    style_name = str(story_json.get("style") or "anime")
    characters_json = _list_of_dicts(story_json.get("characters"))
    locations_json = _list_of_dicts(story_json.get("locations"))
    scenes_json = _list_of_dicts(story_json.get("scenes"))

    visual_bible = StoryVisualBible(
        title=title,
        style=StyleDefinition(art_style=style_name),
        characters=[
            CharacterDefinition(
                character_id=str(item.get("id") or f"character_{index}"),
                name=str(item.get("name") or f"Character {index}"),
                role="npc",
                appearance=str(item.get("appearance") or ""),
                personality_keywords=[str(item.get("voice") or "calm")],
            )
            for index, item in enumerate(characters_json, start=1)
        ],
        locations=[
            LocationDefinition(
                location_id=str(item.get("id") or f"location_{index}"),
                name=_location_name_from_id(str(item.get("id") or f"location_{index}")),
                appearance=str(item.get("description") or ""),
                environment_details=str(item.get("description") or ""),
                default_time_of_day=str(item.get("time_of_day") or ""),
            )
            for index, item in enumerate(locations_json, start=1)
        ],
    )

    character_map = visual_bible.character_map()
    scenes: list[Scene] = []
    for index, scene_json in enumerate(scenes_json, start=1):
        scene_id = int(scene_json.get("scene_id") or index)
        actions = _list_of_dicts(scene_json.get("actions"))
        dialogue = _list_of_dicts(scene_json.get("dialogue"))
        location_id = str(scene_json.get("location") or "unknown_location")
        description = _scene_description(actions, dialogue)
        active_character_ids = [str(item) for item in scene_json.get("characters", []) if str(item).strip()]
        characters = [
            CharacterData(
                name=character_map.get(character_id, CharacterDefinition(character_id, character_id, "npc")).name,
                type=Character.NPC,
                emotion=str(actions[0].get("emotion") or "neutral") if actions else "neutral",
                action=str(actions[0].get("type") or "present") if actions else "present",
            )
            for character_id in active_character_ids
        ] or [CharacterData(name="Narrator", type=Character.NPC, emotion="neutral", action="present")]

        scenes.append(
            Scene(
                scene_id=scene_id,
                title=f"Scene {scene_id}",
                description=description,
                characters=characters,
                setting=_setting_from_location(location_id),
                mood=_mood_from_scene(actions, dialogue),
                narration_text=_narration_from_scene(actions, dialogue, description),
                location_id=location_id,
                active_character_ids=active_character_ids,
                action_description=description,
                camera_description=_camera_description(scene_json.get("camera")),
            )
        )

    return StoryContent(
        title=title,
        author=author,
        description=f"{len(scenes)} scenes generated from story schema",
        scenes=scenes,
        visual_bible=visual_bible,
    )


def story_content_to_story_json(story: StoryContent) -> dict[str, Any]:
    """Adapt legacy StoryContent models into canonical story.json payload."""

    visual_bible = story.visual_bible
    characters: list[dict[str, str]] = []
    locations: list[dict[str, str]] = []
    style = "anime"
    if visual_bible:
        style = visual_bible.style.art_style if visual_bible.style.art_style in _STYLE_VALUES else "anime"
        characters = [
            {
                "id": character.character_id,
                "name": character.name,
                "appearance": character.appearance or character.outfit or "",
                "voice": character.personality_keywords[0] if character.personality_keywords else "calm",
            }
            for character in visual_bible.characters
        ]
        locations = [
            {
                "id": location.location_id,
                "description": location.appearance or location.environment_details or location.name,
                "time_of_day": location.default_time_of_day or "day",
            }
            for location in visual_bible.locations
        ]

    if not characters:
        seen_names: set[str] = set()
        for scene in story.scenes:
            for character in scene.characters:
                normalized = character.name.lower()
                if normalized in seen_names:
                    continue
                seen_names.add(normalized)
                characters.append(
                    {
                        "id": re.sub(r"[^a-z0-9]+", "_", normalized).strip("_") or "unknown_character",
                        "name": character.name,
                        "appearance": "",
                        "voice": character.emotion or "calm",
                    }
                )

    if not locations:
        location_ids: set[str] = set()
        for scene in story.scenes:
            location_id = scene.location_id or scene.setting.value
            if location_id in location_ids:
                continue
            location_ids.add(location_id)
            locations.append(
                {
                    "id": location_id,
                    "description": scene.setting.value.replace("_", " "),
                    "time_of_day": "day",
                }
            )

    scenes = []
    for scene in story.scenes:
        scene_character_ids = list(scene.active_character_ids) or [
            re.sub(r"[^a-z0-9]+", "_", character.name.lower()).strip("_") or "unknown_character"
            for character in scene.characters
        ]
        scenes.append(
            {
                "scene_id": scene.scene_id,
                "location": scene.location_id or scene.setting.value,
                "duration_sec": max(3, len(scene.narration_text.split()) // 3 or 5),
                "characters": scene_character_ids or ["narrator"],
                "camera": {
                    "shot": _camera_shot(scene.camera_description),
                    "angle": _camera_angle(scene.camera_description),
                },
                "actions": [
                    {
                        "character": scene_character_ids[0] if scene_character_ids else "narrator",
                        "type": scene.characters[0].action if scene.characters else "present",
                        "emotion": scene.characters[0].emotion if scene.characters else "neutral",
                        "description": scene.action_description or scene.description,
                    }
                ],
                "dialogue": [],
            }
        )

    return {
        "story_id": re.sub(r"[^a-z0-9]+", "_", story.title.lower()).strip("_") or "story",
        "title": story.title,
        "style": style if style in _STYLE_VALUES else "anime",
        "characters": characters,
        "locations": locations,
        "scenes": scenes,
    }


def _list_of_dicts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _setting_from_location(location_id: str) -> Setting:
    normalized = location_id.lower().replace(" ", "_")
    for item in Setting:
        if item.value in normalized:
            return item
    return Setting.FOREST


def _mood_from_scene(actions: list[dict[str, Any]], dialogue: list[dict[str, Any]]) -> Mood:
    probes = [str(item.get("emotion") or "") for item in actions + dialogue]
    normalized = " ".join(probes).lower()
    if "angry" in normalized or "tense" in normalized:
        return Mood.TENSE
    if "happy" in normalized:
        return Mood.CALM
    return Mood.MYSTERIOUS


def _scene_description(actions: list[dict[str, Any]], dialogue: list[dict[str, Any]]) -> str:
    if actions:
        return str(actions[0].get("description") or "")
    if dialogue:
        first = dialogue[0]
        return f'{first.get("speaker", "speaker")} says "{first.get("text", "")}"'
    return ""


def _narration_from_scene(actions: list[dict[str, Any]], dialogue: list[dict[str, Any]], description: str) -> str:
    if dialogue:
        return " ".join(f'{item.get("speaker", "speaker")}: {item.get("text", "")}' for item in dialogue)
    if actions:
        return str(actions[0].get("description") or description)
    return description


def _camera_description(camera: Any) -> str:
    if not isinstance(camera, dict):
        return ""
    shot = str(camera.get("shot") or "medium shot")
    angle = str(camera.get("angle") or "eye level")
    return f"{shot}, {angle}"


def _camera_shot(camera_description: str) -> str:
    lowered = camera_description.lower()
    if "close" in lowered:
        return "close-up"
    if "wide" in lowered:
        return "wide shot"
    return "medium shot"


def _camera_angle(camera_description: str) -> str:
    lowered = camera_description.lower()
    if "high" in lowered or "overhead" in lowered:
        return "high angle"
    if "low" in lowered:
        return "low angle"
    return "eye level"


def _location_name_from_id(location_id: str) -> str:
    return location_id.replace("_", " ").title()
