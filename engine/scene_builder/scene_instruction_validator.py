"""Validation helpers for scene instruction payloads."""

from __future__ import annotations

from typing import Any

_DEFAULT_CAMERA = {"shot": "medium shot", "angle": "eye level"}


def validate_scene_instruction(instruction: dict[str, Any]) -> dict[str, Any]:
    """Validate a single scene instruction and return normalized data."""

    if not isinstance(instruction, dict):
        raise ValueError("scene instruction must be a dictionary")

    scene_id = instruction.get("scene_id")
    if scene_id is None:
        raise ValueError("scene instruction missing scene_id")

    image_prompt = str(instruction.get("image_prompt") or "").strip()
    if not image_prompt:
        raise ValueError(f"scene instruction {scene_id} has empty image_prompt")

    try:
        duration_sec = int(instruction.get("duration_sec"))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"scene instruction {scene_id} has invalid duration_sec") from exc
    if duration_sec <= 0:
        raise ValueError(f"scene instruction {scene_id} has invalid duration_sec")

    camera = instruction.get("camera")
    if not isinstance(camera, dict):
        raise ValueError(f"scene instruction {scene_id} has invalid camera")
    shot = str(camera.get("shot") or "").strip()
    angle = str(camera.get("angle") or "").strip()
    if not shot or not angle:
        raise ValueError(f"scene instruction {scene_id} has invalid camera")

    return {
        "scene_id": int(scene_id),
        "title": str(instruction.get("title") or f"Scene {int(scene_id)}").strip(),
        "mood": str(instruction.get("mood") or "mysterious").strip(),
        "narration": str(instruction.get("narration") or "").strip(),
        "image_prompt": image_prompt,
        "characters": [str(item) for item in instruction.get("characters", []) if str(item).strip()],
        "location": str(instruction.get("location") or ""),
        "camera": {"shot": shot or _DEFAULT_CAMERA["shot"], "angle": angle or _DEFAULT_CAMERA["angle"]},
        "duration_sec": duration_sec,
        "dialogue": [item for item in instruction.get("dialogue", []) if isinstance(item, dict)],
        "actions": [item for item in instruction.get("actions", []) if isinstance(item, dict)],
    }


def validate_scene_instructions(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Validate many scene instructions and ensure unique scene ids."""

    seen: set[int] = set()
    validated: list[dict[str, Any]] = []
    for item in items:
        normalized = validate_scene_instruction(item)
        scene_id = normalized["scene_id"]
        if scene_id in seen:
            raise ValueError(f"duplicate scene_id: {scene_id}")
        seen.add(scene_id)
        validated.append(normalized)
    return validated
