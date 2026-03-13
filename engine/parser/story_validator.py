"""Validation helpers for canonical story.json payloads."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

_DEFAULT_CAMERA = {"shot": "medium shot", "angle": "eye level"}
_CHARACTER_STOPWORDS = {"the", "in", "with", "a", "an", "and", "of", "to", "for", "on", "at", "from"}
_DEFAULT_SCENE = {
    "scene_id": 1,
    "location": "unknown_location",
    "duration_sec": 5,
    "characters": ["narrator"],
    "camera": _DEFAULT_CAMERA,
    "actions": [],
    "dialogue": [],
}


def validate_story_json(story_json: dict) -> dict:
    """Normalize canonical story payloads and enforce required fields."""

    if not isinstance(story_json, dict):
        raise ValueError("story_json must be a dictionary")

    normalized = dict(story_json)
    normalized["story_id"] = str(normalized.get("story_id") or "story")
    normalized["title"] = str(normalized.get("title") or "Untitled Story")
    normalized["style"] = str(normalized.get("style") or "anime")
    normalized["characters"] = _normalize_characters(normalized.get("characters"))
    normalized["locations"] = _normalize_locations(normalized.get("locations"))
    normalized["scenes"] = _normalize_scenes(normalized.get("scenes"))
    return normalized


def _normalize_characters(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    items: list[dict[str, str]] = []
    for index, item in enumerate(value, start=1):
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or f"Character {index}").strip()
        if not _is_meaningful_character_name(name):
            continue
        items.append(
            {
                "id": str(item.get("id") or f"character_{index}"),
                "name": name,
                "appearance": str(item.get("appearance") or ""),
                "voice": str(item.get("voice") or "calm"),
            }
        )
    return items


def _normalize_locations(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    items: list[dict[str, str]] = []
    for index, item in enumerate(value, start=1):
        if not isinstance(item, dict):
            continue
        items.append(
            {
                "id": str(item.get("id") or f"location_{index}"),
                "description": str(item.get("description") or ""),
                "time_of_day": str(item.get("time_of_day") or "day"),
            }
        )
    return items


def _normalize_scenes(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return [deepcopy(_DEFAULT_SCENE)]

    scenes: list[dict[str, Any]] = []
    for index, item in enumerate(value, start=1):
        if not isinstance(item, dict):
            continue
        camera = _normalize_camera(item.get("camera"))
        characters = [str(character) for character in item.get("characters", []) if str(character).strip()]
        scenes.append(
            {
                "scene_id": int(item.get("scene_id") or index),
                "location": str(item.get("location") or "unknown_location"),
                "duration_sec": _normalize_duration(item.get("duration_sec")),
                "characters": characters or ["narrator"],
                "camera": camera,
                "actions": _normalize_dict_list(item.get("actions")),
                "dialogue": _normalize_dict_list(item.get("dialogue")),
            }
        )

    return scenes or [deepcopy(_DEFAULT_SCENE)]


def _normalize_camera(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return dict(_DEFAULT_CAMERA)
    shot = str(value.get("shot") or _DEFAULT_CAMERA["shot"])
    angle = str(value.get("angle") or _DEFAULT_CAMERA["angle"])
    return {"shot": shot, "angle": angle}


def _normalize_duration(value: Any) -> int:
    try:
        duration = int(value)
    except (TypeError, ValueError):
        return 5
    return duration if duration > 0 else 5


def _normalize_dict_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


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
