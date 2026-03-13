"""Validation helpers for canonical story.json payloads."""

from __future__ import annotations

import logging
import re
from copy import deepcopy
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_CAMERA = {"shot": "medium shot", "angle": "eye level"}
_DEFAULT_MOOD = "mysterious"
_CHARACTER_STOPWORDS = {"the", "in", "with", "a", "an", "and", "of", "to", "for", "on", "at", "from"}
_SCENE_FALLBACK_FIELDS = {
    "scene_id": 1,
    "title": "Scene 1",
    "location": "unknown_location",
    "mood": _DEFAULT_MOOD,
    "characters": ["narrator"],
    "narration": "",
    "duration_sec": 5,
    "camera": _DEFAULT_CAMERA,
    "dialogue": [],
    "actions": [],
    "image_prompt": "",
}


def validate_story_json(story_json: dict) -> dict:
    """Normalize canonical story payloads and enforce required fields."""

    if not isinstance(story_json, dict):
        raise ValueError("story_json must be a dictionary")

    normalized = dict(story_json)
    if not normalized.get("story_id"):
        logger.info("validate_story_json applied default story_id=story")
    if not normalized.get("title"):
        logger.info("validate_story_json applied default title=Untitled Story")
    if not normalized.get("style"):
        logger.info("validate_story_json applied default style=anime")

    normalized["story_id"] = str(normalized.get("story_id") or "story")
    normalized["title"] = str(normalized.get("title") or "Untitled Story")
    normalized["style"] = str(normalized.get("style") or "anime")
    normalized["characters"] = _normalize_characters(normalized.get("characters"))
    normalized["locations"] = _normalize_locations(normalized.get("locations"))
    normalized["scenes"] = normalize_scenes(normalized.get("scenes"), top_level_characters=normalized["characters"])
    return normalized


def normalize_story_json(story_json: dict[str, Any]) -> dict[str, Any]:
    """Public alias for canonical story normalization."""

    return validate_story_json(story_json)


def normalize_scenes(value: Any, *, top_level_characters: list[dict[str, str]]) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        logger.warning("validate_story_json scenes missing or invalid; using placeholder default scene")
        return [deepcopy(_SCENE_FALLBACK_FIELDS)]

    scenes: list[dict[str, Any]] = []
    for index, item in enumerate(value, start=1):
        if not isinstance(item, dict):
            continue
        scene = normalize_scene(
            item,
            index=index,
            top_level_characters=top_level_characters,
        )
        scenes.append(scene)

    if not scenes:
        logger.warning("validate_story_json scenes list empty after normalization; using placeholder default scene")
        return [deepcopy(_SCENE_FALLBACK_FIELDS)]
    return scenes


def normalize_scene(
    scene: dict[str, Any],
    *,
    index: int,
    top_level_characters: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Normalize a model scene into the canonical downstream schema."""

    scene_id = _coerce_scene_id(scene.get("scene_id"), fallback=index)
    title = resolve_title(scene, scene_id=scene_id)
    mood = resolve_mood(scene, scene_id=scene_id)
    narration = resolve_narration(scene, scene_id=scene_id)
    location = resolve_location(scene, scene_id=scene_id)
    camera = _normalize_camera(scene.get("camera"), scene_id=scene_id)
    duration_sec = _normalize_duration(scene.get("duration_sec"), scene_id=scene_id)
    characters = coerce_characters(
        scene.get("characters") or scene.get("cast") or scene.get("entities"),
        top_level_characters=top_level_characters or [],
        scene=scene,
        scene_id=scene_id,
    )
    image_prompt = resolve_image_prompt(scene)
    actions = _normalize_dict_list(scene.get("actions"))
    dialogue = _normalize_dict_list(scene.get("dialogue"))

    normalized = {
        "scene_id": scene_id,
        "title": title,
        "location": location,
        "mood": mood,
        "characters": characters,
        "narration": narration,
        "duration_sec": duration_sec,
        "camera": camera,
        "dialogue": dialogue,
        "actions": actions,
        "image_prompt": image_prompt,
    }
    if image_prompt:
        normalized["visual_prompt"] = image_prompt
    return normalized


def _normalize_characters(value: Any) -> list[dict[str, str]]:
    raw_items: list[Any]
    if isinstance(value, list):
        raw_items = value
    elif value is None:
        raw_items = []
    else:
        raw_items = [value]

    items: list[dict[str, str]] = []
    for index, item in enumerate(raw_items, start=1):
        normalized = _normalize_character_definition(item, index=index)
        if normalized is not None:
            items.append(normalized)
    return items


def _normalize_character_definition(value: Any, *, index: int) -> dict[str, str] | None:
    if isinstance(value, dict):
        name = str(
            value.get("name")
            or value.get("character")
            or value.get("character_id")
            or value.get("id")
            or f"Character {index}"
        ).strip()
        if not _is_meaningful_character_name(name):
            return None
        return {
            "id": str(value.get("id") or _slugify(name, fallback=f"character_{index}")),
            "name": name,
            "appearance": str(value.get("appearance") or value.get("description") or ""),
            "voice": str(value.get("voice") or value.get("personality") or "calm"),
        }
    if isinstance(value, str):
        name = value.strip()
        if not _is_meaningful_character_name(name):
            return None
        return {
            "id": _slugify(name, fallback=f"character_{index}"),
            "name": name,
            "appearance": "",
            "voice": "calm",
        }
    return None


def _normalize_locations(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    items: list[dict[str, str]] = []
    for index, item in enumerate(value, start=1):
        if not isinstance(item, dict):
            continue
        location_id = str(item.get("id") or item.get("location_id") or f"location_{index}")
        items.append(
            {
                "id": location_id,
                "description": str(item.get("description") or item.get("appearance") or item.get("name") or ""),
                "time_of_day": str(item.get("time_of_day") or "day"),
            }
        )
    return items


def coerce_characters(
    value: Any,
    *,
    top_level_characters: list[dict[str, str]],
    scene: dict[str, Any],
    scene_id: int,
) -> list[str]:
    """Normalize scene character references into a list of ids/names."""

    candidates = _normalize_scene_character_candidates(value)
    if not candidates:
        inferred = _infer_scene_characters_from_scene(scene, top_level_characters)
        if inferred:
            logger.info("validate_story_json scene_id=%s inferred characters=%s", scene_id, inferred)
            return inferred
        logger.info("validate_story_json scene_id=%s applied default characters=['narrator']", scene_id)
        return ["narrator"]
    return candidates


def resolve_narration(scene: dict[str, Any], *, scene_id: int) -> str:
    narration = str(
        scene.get("narration")
        or scene.get("description")
        or scene.get("summary")
        or scene.get("text")
        or ""
    ).strip()
    if not narration:
        logger.warning("validate_story_json scene_id=%s missing narration after normalization", scene_id)
    return narration


def resolve_location(scene: dict[str, Any], *, scene_id: int) -> str:
    location = str(
        scene.get("location")
        or scene.get("setting_name")
        or scene.get("place")
        or ""
    ).strip()
    if not location:
        logger.info("validate_story_json scene_id=%s applied default location=unknown_location", scene_id)
        return "unknown_location"
    return _slugify_location(location)


def resolve_mood(scene: dict[str, Any], *, scene_id: int) -> str:
    mood = str(scene.get("mood") or scene.get("tone") or scene.get("atmosphere") or "").strip()
    if not mood:
        logger.info("validate_story_json scene_id=%s applied default mood=%s", scene_id, _DEFAULT_MOOD)
        return _DEFAULT_MOOD
    return mood.lower().replace(" ", "_")


def resolve_title(scene: dict[str, Any], *, scene_id: int) -> str:
    title = str(scene.get("title") or scene.get("scene_title") or "").strip()
    if not title:
        title = f"Scene {scene_id}"
        logger.info("validate_story_json scene_id=%s applied default title=%s", scene_id, title)
    return title


def resolve_image_prompt(scene: dict[str, Any]) -> str:
    return str(scene.get("image_prompt") or scene.get("visual_prompt") or "").strip()


def _normalize_scene_character_candidates(value: Any) -> list[str]:
    if isinstance(value, str):
        items = [value]
    elif isinstance(value, list):
        items = value
    else:
        return []

    result: list[str] = []
    for item in items:
        if isinstance(item, dict):
            candidate = str(item.get("id") or item.get("character_id") or item.get("name") or "").strip()
        else:
            candidate = str(item).strip()
        if candidate:
            result.append(_slugify(candidate, fallback=candidate))
    return _unique_preserving_order(result)


def _infer_scene_characters_from_scene(scene: dict[str, Any], top_level_characters: list[dict[str, str]]) -> list[str]:
    inferred: list[str] = []
    dialogue = scene.get("dialogue")
    if isinstance(dialogue, list):
        for item in dialogue:
            if not isinstance(item, dict):
                continue
            speaker = str(item.get("speaker") or item.get("character") or "").strip()
            if speaker:
                inferred.append(_slugify(speaker, fallback=speaker))

    narration_sources = [
        scene.get("narration"),
        scene.get("description"),
        scene.get("summary"),
        scene.get("text"),
        scene.get("title"),
        scene.get("scene_title"),
    ]
    narrative_text = " ".join(str(item or "") for item in narration_sources)
    lowered = narrative_text.lower()
    for character in top_level_characters:
        character_id = str(character.get("id") or "").strip()
        character_name = str(character.get("name") or "").strip().lower()
        if character_name and character_name in lowered:
            inferred.append(character_id or _slugify(character_name, fallback=character_name))
            continue
        normalized_id = character_id.replace("_", " ").lower()
        if normalized_id and normalized_id in lowered:
            inferred.append(character_id)
    return _unique_preserving_order(inferred)


def _coerce_scene_id(value: Any, *, fallback: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _normalize_camera(value: Any, *, scene_id: int) -> dict[str, str]:
    if not isinstance(value, dict):
        logger.info(
            "validate_story_json scene_id=%s applied default camera shot=%s angle=%s",
            scene_id,
            _DEFAULT_CAMERA["shot"],
            _DEFAULT_CAMERA["angle"],
        )
        return dict(_DEFAULT_CAMERA)
    shot = str(value.get("shot") or _DEFAULT_CAMERA["shot"])
    angle = str(value.get("angle") or _DEFAULT_CAMERA["angle"])
    if not value.get("shot") or not value.get("angle"):
        logger.info(
            "validate_story_json scene_id=%s applied default camera shot=%s angle=%s",
            scene_id,
            shot,
            angle,
        )
    return {"shot": shot, "angle": angle}


def _normalize_duration(value: Any, *, scene_id: int) -> int:
    try:
        duration = int(value)
    except (TypeError, ValueError):
        logger.info("validate_story_json scene_id=%s applied default duration_sec=5", scene_id)
        return 5
    if duration <= 0:
        logger.info("validate_story_json scene_id=%s applied default duration_sec=5", scene_id)
        return 5
    return duration


def _normalize_dict_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


def _slugify(value: str, fallback: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")
    return slug or fallback


def _slugify_location(value: str) -> str:
    return _slugify(value, fallback="unknown_location")


def _unique_preserving_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if not item or item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def _is_meaningful_character_name(name: str) -> bool:
    stripped = name.strip()
    if not stripped:
        return False
    lowered = stripped.lower()
    if lowered in _CHARACTER_STOPWORDS:
        return False
    if len(stripped) == 1 and lowered.isalpha():
        return False
    return any(character.isalpha() for character in stripped)
