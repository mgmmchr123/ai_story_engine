"""Build scene generation instructions from canonical story.json scenes."""

from __future__ import annotations

from typing import Any


def build_scene(scene_json: dict[str, Any]) -> dict[str, Any]:
    """Convert schema scene data into provider-friendly generation instructions."""

    location = str(scene_json.get("location") or "unknown location").replace("_", " ")
    camera = scene_json.get("camera") if isinstance(scene_json.get("camera"), dict) else {}
    shot = str(camera.get("shot") or "medium shot")
    angle = str(camera.get("angle") or "eye level")
    actions = scene_json.get("actions") if isinstance(scene_json.get("actions"), list) else []
    action_description = ""
    if actions and isinstance(actions[0], dict):
        action_description = str(actions[0].get("description") or "")

    style = str(scene_json.get("style") or "anime")
    prompt_parts = [location]
    if action_description:
        prompt_parts.append(action_description)
    prompt_parts.append(f"{style} style")
    prompt_parts.append(f"{shot}, {angle}")

    return {
        "scene_id": int(scene_json.get("scene_id") or 0),
        "image_prompt": ", ".join(prompt_parts),
        "characters": [str(item) for item in scene_json.get("characters", []) if str(item).strip()],
        "camera": shot,
        "duration": int(scene_json.get("duration_sec") or 5),
        "location": str(scene_json.get("location") or ""),
        "dialogue": scene_json.get("dialogue", []),
        "actions": actions,
    }


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
        instructions.append(build_scene(enriched_scene))
    return instructions
