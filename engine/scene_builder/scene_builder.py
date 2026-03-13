"""Build scene generation instructions from canonical story.json scenes."""

from __future__ import annotations

import logging
import re
from typing import Any

from engine.logging_utils import compact_json

_DEFAULT_CAMERA = {"shot": "medium shot", "angle": "eye level"}
logger = logging.getLogger(__name__)


def build_scene(scene_json: dict[str, Any]) -> dict[str, Any]:
    """Convert schema scene data into provider-friendly generation instructions."""
    raw_keys = sorted(scene_json.keys())
    logger.info("build_scene incoming scene_id=%s raw_keys=%s", scene_json.get("scene_id"), raw_keys)
    logger.info(
        "build_scene scene_id=%s field_presence narration=%s title=%s mood=%s location=%s characters=%s",
        scene_json.get("scene_id"),
        bool(str(scene_json.get("narration") or scene_json.get("narration_text") or "").strip()),
        bool(str(scene_json.get("title") or "").strip()),
        bool(str(scene_json.get("mood") or "").strip()),
        bool(str(scene_json.get("location") or "").strip()),
        bool(scene_json.get("characters")),
    )
    location = str(scene_json.get("location") or "unknown location").replace("_", " ")
    camera = scene_json.get("camera") if isinstance(scene_json.get("camera"), dict) else {}
    shot = str(camera.get("shot") or _DEFAULT_CAMERA["shot"])
    angle = str(camera.get("angle") or _DEFAULT_CAMERA["angle"])
    actions = scene_json.get("actions") if isinstance(scene_json.get("actions"), list) else []
    narration = str(scene_json.get("narration") or scene_json.get("narration_text") or "").strip()
    title = str(scene_json.get("title") or f"Scene {int(scene_json.get('scene_id') or 0)}").strip()
    mood = str(scene_json.get("mood") or "mysterious").strip()
    style = str(scene_json.get("style") or "anime")
    image_prompt = str(scene_json.get("image_prompt") or scene_json.get("visual_prompt") or "").strip()
    prompt_source = "provided"
    if not image_prompt:
        image_prompt = _build_visual_image_prompt(
            title=title,
            location=location,
            mood=mood,
            characters=scene_json.get("characters"),
            actions=actions,
            camera_shot=shot,
            camera_angle=angle,
            style=style,
        )
        prompt_source = "constructed"

    built = {
        "scene_id": int(scene_json.get("scene_id") or 0),
        "title": title,
        "mood": mood,
        "narration": narration,
        "image_prompt": image_prompt,
        "characters": [str(item) for item in scene_json.get("characters", []) if str(item).strip()],
        "location": str(scene_json.get("location") or "unknown_location"),
        "camera": {"shot": shot, "angle": angle},
        "duration_sec": int(scene_json.get("duration_sec") or 5),
        "dialogue": [item for item in scene_json.get("dialogue", []) if isinstance(item, dict)],
        "actions": actions,
    }
    logger.info(
        "build_scene outgoing scene_id=%s built_keys=%s image_prompt_source=%s",
        built["scene_id"],
        sorted(built.keys()),
        prompt_source,
    )
    return built


def build_scenes(story_json: dict[str, Any]) -> list[dict[str, Any]]:
    """Build instructions for each scene in a canonical story payload."""

    style = str(story_json.get("style") or "anime")
    scenes = story_json.get("scenes") if isinstance(story_json.get("scenes"), list) else []
    instructions: list[dict[str, Any]] = []
    for scene in scenes:
        if not isinstance(scene, dict):
            continue
        enriched_scene = dict(scene)
        enriched_scene.setdefault("style", style)
        built = build_scene(enriched_scene)
        if not instructions:
            logger.info("build_scenes first built instruction=%s", compact_json(built, max_len=2000))
        instructions.append(built)
    return instructions


def _build_visual_image_prompt(
    *,
    title: str,
    location: str,
    mood: str,
    characters: Any,
    actions: list[Any],
    camera_shot: str,
    camera_angle: str,
    style: str,
) -> str:
    prompt_parts = [
        f"scene: {_humanize_text(title)}",
        f"location: {_humanize_text(location)}",
        f"mood: {_humanize_text(mood)}",
        f"style: {_humanize_text(style)}",
    ]
    visible_characters = _visible_characters_fragment(characters)
    if visible_characters:
        prompt_parts.append(f"visible characters: {visible_characters}")
    action_summary = _action_summary(actions)
    if action_summary:
        prompt_parts.append(f"visual action: {action_summary}")
    prompt_parts.append(f"camera: {_humanize_text(camera_shot)}, {_humanize_text(camera_angle)}")
    prompt_parts.append("focus on concrete visual details, cinematic composition, no text overlay")
    return ", ".join(prompt_parts)


def _visible_characters_fragment(characters: Any) -> str:
    if not isinstance(characters, list):
        return ""
    items = [_humanize_text(str(item)) for item in characters if str(item).strip()]
    return ", ".join(items)


def _action_summary(actions: list[Any]) -> str:
    for action in actions:
        if not isinstance(action, dict):
            continue
        description = str(action.get("description") or "").strip()
        if description:
            return description
        subject = _humanize_text(str(action.get("character") or ""))
        verb = _humanize_text(str(action.get("type") or ""))
        emotion = _humanize_text(str(action.get("emotion") or ""))
        fragments = [item for item in [subject, verb, emotion] if item]
        if fragments:
            return " ".join(fragments)
    return "establishing shot"


def _humanize_text(value: str) -> str:
    text = str(value or "").strip().replace("_", " ")
    text = re.sub(r"\s+", " ", text)
    return text
