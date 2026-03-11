"""Helpers for resolving scene state against the visual bible."""

from models.scene_schema import Scene, StoryVisualBible

_BGM_SETTINGS = {"forest", "castle", "village", "dungeon", "throne_room", "tavern"}


def resolve_scene_location(scene: Scene, visual_bible: StoryVisualBible | None) -> dict[str, str]:
    """Resolve scene location info with compatibility fallback."""
    location_id = scene.location_id or ""
    location_name = scene.setting.value.replace("_", " ").title()
    if visual_bible and location_id:
        location = visual_bible.location_map().get(location_id)
        if location:
            location_name = location.name
    bgm_setting = normalize_location_for_bgm(location_id, location_name, scene.setting.value)
    return {
        "location_id": location_id,
        "location_name": location_name,
        "bgm_setting": bgm_setting,
    }


def resolve_scene_characters(scene: Scene, visual_bible: StoryVisualBible | None) -> list[dict[str, str]]:
    """Resolve active characters with compatibility fallback."""
    if visual_bible and scene.active_character_ids:
        character_map = visual_bible.character_map()
        resolved: list[dict[str, str]] = []
        for character_id in scene.active_character_ids:
            character = character_map.get(character_id)
            if character:
                resolved.append({"character_id": character_id, "name": character.name})
        if resolved:
            return resolved

    return [
        {"character_id": f"legacy_{index + 1:03d}", "name": character.name}
        for index, character in enumerate(scene.characters)
    ]


def normalize_location_for_bgm(location_id: str, location_name: str, fallback_setting: str) -> str:
    """Map rich location IDs/names into supported BGM setting categories."""
    probes = [location_id, location_name, fallback_setting]
    normalized = " ".join(value.lower().replace("-", "_") for value in probes if value).strip()

    keyword_map = {
        "throne": "throne_room",
        "royal": "throne_room",
        "forest": "forest",
        "woods": "forest",
        "castle": "castle",
        "keep": "castle",
        "village": "village",
        "town": "village",
        "dungeon": "dungeon",
        "crypt": "dungeon",
        "tavern": "tavern",
        "inn": "tavern",
    }
    for keyword, mapped in keyword_map.items():
        if keyword in normalized:
            return mapped

    fallback = fallback_setting.lower().strip()
    if fallback in _BGM_SETTINGS:
        return fallback
    return "forest"
