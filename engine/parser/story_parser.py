"""Schema-driven story parser and adapters."""

from __future__ import annotations

from dataclasses import dataclass
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
_DIALOGUE_RE = re.compile(r"^(?P<speaker>[A-Z][A-Za-z0-9_ ]{0,40}):\s*(?P<text>.+)$")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


@dataclass(slots=True)
class StoryParser:
    """Simple deterministic parser that emits canonical story.json data."""

    default_style: str = "anime"

    def parse(self, text: str) -> dict[str, Any]:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        title = lines[0][:80] if lines else "Untitled Story"
        style = self._detect_style(text)
        characters = self.extract_characters(text)
        locations = self.extract_locations(text)
        scenes = self.extract_scenes(text, characters, locations)
        if not scenes:
            default_location_id = locations[0]["id"] if locations else "unknown_location"
            scenes = [
                {
                    "scene_id": 1,
                    "location": default_location_id,
                    "duration_sec": 5,
                    "characters": [item["id"] for item in characters] or ["unknown_character"],
                    "camera": {"shot": "medium shot", "angle": "eye level"},
                    "actions": [],
                    "dialogue": [],
                }
            ]

        return {
            "story_id": self._slugify(title, "story"),
            "title": title,
            "style": style,
            "characters": characters,
            "locations": locations,
            "scenes": scenes,
        }

    def extract_characters(self, text: str) -> list[dict[str, str]]:
        names: list[str] = []
        seen: set[str] = set()
        for line in text.splitlines():
            match = _DIALOGUE_RE.match(line.strip())
            if match:
                candidate = match.group("speaker").strip()
                normalized = candidate.lower()
                if normalized not in seen:
                    names.append(candidate)
                    seen.add(normalized)

        if not names:
            for candidate in re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\b", text):
                normalized = candidate.lower()
                if normalized in seen or candidate.lower() in {"scene", "chapter"}:
                    continue
                names.append(candidate)
                seen.add(normalized)
                if len(names) >= 4:
                    break

        if not names:
            names = ["Narrator"]

        characters: list[dict[str, str]] = []
        for index, name in enumerate(names, start=1):
            character_id = self._slugify(name, f"character_{index}")
            characters.append(
                {
                    "id": character_id,
                    "name": name,
                    "appearance": f"{name} with a distinctive silhouette",
                    "voice": "calm",
                }
            )
        return characters

    def extract_locations(self, text: str) -> list[dict[str, str]]:
        known_locations = {
            "forest": ("forest", "a dense forest", "day"),
            "castle": ("castle", "a weathered stone castle", "night"),
            "village": ("village", "a quiet village square", "day"),
            "dungeon": ("dungeon", "a torch-lit dungeon corridor", "night"),
            "throne room": ("throne_room", "an ornate throne room", "day"),
            "tavern": ("tavern", "a busy tavern interior", "night"),
            "inn": ("tavern", "a busy tavern interior", "night"),
        }
        lowered = text.lower()
        locations: list[dict[str, str]] = []
        seen: set[str] = set()
        for keyword, (location_id, description, time_of_day) in known_locations.items():
            if keyword not in lowered or location_id in seen:
                continue
            seen.add(location_id)
            locations.append(
                {
                    "id": location_id,
                    "description": description,
                    "time_of_day": time_of_day,
                }
            )

        if not locations:
            locations.append(
                {
                    "id": "unknown_location",
                    "description": "an unspecified story location",
                    "time_of_day": "day",
                }
            )
        return locations

    def extract_scenes(
        self,
        text: str,
        characters: list[dict[str, str]],
        locations: list[dict[str, str]],
    ) -> list[dict[str, Any]]:
        character_lookup = {item["name"].lower(): item["id"] for item in characters}
        default_location = locations[0]["id"] if locations else "unknown_location"
        raw_lines = [line.strip() for line in text.splitlines() if line.strip()]
        if len(raw_lines) > 1:
            raw_scenes = raw_lines
        else:
            raw_scenes = [block.strip() for block in re.split(r"\n\s*\n+", text) if block.strip()]
            if len(raw_scenes) == 1:
                raw_scenes = [item.strip() for item in _SENTENCE_SPLIT_RE.split(raw_scenes[0]) if item.strip()]

        scenes: list[dict[str, Any]] = []
        for index, block in enumerate(raw_scenes, start=1):
            dialogue = self.extract_dialogue(block, character_lookup)
            scene_character_ids = self._collect_scene_character_ids(block, dialogue, character_lookup, characters)
            scene_location = self._match_location(block, locations, default_location)
            actions = self.extract_actions(block, scene_character_ids, character_lookup)
            scenes.append(
                {
                    "scene_id": index,
                    "location": scene_location,
                    "duration_sec": max(3, min(12, len(block.split()) // 3 or 5)),
                    "characters": scene_character_ids,
                    "camera": self._build_camera(block),
                    "actions": actions,
                    "dialogue": dialogue,
                }
            )
        return scenes

    def extract_dialogue(
        self,
        block: str,
        character_lookup: dict[str, str],
    ) -> list[dict[str, str]]:
        dialogue: list[dict[str, str]] = []
        for line in block.splitlines():
            match = _DIALOGUE_RE.match(line.strip())
            if not match:
                continue
            speaker_name = match.group("speaker").strip()
            speaker_id = character_lookup.get(speaker_name.lower(), self._slugify(speaker_name, "speaker"))
            text = match.group("text").strip()
            dialogue.append(
                {
                    "speaker": speaker_id,
                    "text": text,
                    "emotion": self._infer_emotion(text),
                }
            )
        return dialogue

    def extract_actions(
        self,
        block: str,
        scene_character_ids: list[str],
        character_lookup: dict[str, str],
    ) -> list[dict[str, str]]:
        action_keywords = ("walk", "run", "look", "turn", "reach", "draw", "open", "whisper", "smile", "stare")
        plain_text = " ".join(
            line for line in block.splitlines() if not _DIALOGUE_RE.match(line.strip())
        ).strip()
        if not plain_text:
            plain_text = block.strip()
        action_type = "observe"
        lowered = plain_text.lower()
        for keyword in action_keywords:
            if keyword in lowered:
                action_type = keyword
                break

        character_id = scene_character_ids[0] if scene_character_ids else next(iter(character_lookup.values()), "unknown_character")
        return [
            {
                "character": character_id,
                "type": action_type,
                "emotion": self._infer_emotion(plain_text),
                "description": plain_text or "The scene holds on a quiet beat.",
            }
        ]

    def _collect_scene_character_ids(
        self,
        block: str,
        dialogue: list[dict[str, str]],
        character_lookup: dict[str, str],
        characters: list[dict[str, str]],
    ) -> list[str]:
        ids = [item["speaker"] for item in dialogue]
        lowered = block.lower()
        for name, character_id in character_lookup.items():
            if name in lowered:
                ids.append(character_id)
        if not ids and characters:
            ids.append(characters[0]["id"])
        return self._unique(ids)

    def _match_location(
        self,
        block: str,
        locations: list[dict[str, str]],
        default_location: str,
    ) -> str:
        lowered = block.lower()
        for location in locations:
            if location["id"].replace("_", " ") in lowered:
                return location["id"]
        return default_location

    def _build_camera(self, block: str) -> dict[str, str]:
        lowered = block.lower()
        shot = "medium shot"
        angle = "eye level"
        if "close" in lowered:
            shot = "close-up"
        elif "wide" in lowered or "panorama" in lowered:
            shot = "wide shot"
        if "above" in lowered or "overhead" in lowered:
            angle = "high angle"
        elif "below" in lowered or "low angle" in lowered:
            angle = "low angle"
        return {"shot": shot, "angle": angle}

    def _infer_emotion(self, text: str) -> str:
        lowered = text.lower()
        if any(word in lowered for word in ("shout", "angry", "furious", "slam")):
            return "angry"
        if any(word in lowered for word in ("smile", "laugh", "warm", "joy")):
            return "happy"
        if any(word in lowered for word in ("fear", "tremble", "dark", "whisper")):
            return "tense"
        return "neutral"

    def _detect_style(self, text: str) -> str:
        lowered = text.lower()
        for style in _STYLE_VALUES:
            if style in lowered:
                return style
        return self.default_style

    def _slugify(self, value: str, fallback: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")
        return slug or fallback

    def _unique(self, items: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for item in items:
            if not item or item in seen:
                continue
            seen.add(item)
            result.append(item)
        return result


def story_json_to_story_content(
    story_json: dict[str, Any],
    *,
    author: str = "Anonymous",
) -> StoryContent:
    """Adapt canonical story.json payload into the legacy StoryContent model."""

    title = str(story_json.get("title") or "Untitled Story")
    style_name = str(story_json.get("style") or "anime")
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
            for index, item in enumerate(_list_of_dicts(story_json.get("characters")), start=1)
        ],
        locations=[
            LocationDefinition(
                location_id=str(item.get("id") or f"location_{index}"),
                name=_location_name_from_id(str(item.get("id") or f"location_{index}")),
                appearance=str(item.get("description") or ""),
                environment_details=str(item.get("description") or ""),
                default_time_of_day=str(item.get("time_of_day") or ""),
            )
            for index, item in enumerate(_list_of_dicts(story_json.get("locations")), start=1)
        ],
    )

    character_map = visual_bible.character_map()
    scenes: list[Scene] = []
    for index, scene_json in enumerate(_list_of_dicts(story_json.get("scenes")), start=1):
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
    characters = []
    locations = []
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
        scenes.append(
            {
                "scene_id": scene.scene_id,
                "location": scene.location_id or scene.setting.value,
                "duration_sec": max(3, len(scene.narration_text.split()) // 3 or 5),
                "characters": list(scene.active_character_ids)
                or [re.sub(r"[^a-z0-9]+", "_", character.name.lower()).strip("_") for character in scene.characters],
                "camera": {
                    "shot": _camera_shot(scene.camera_description),
                    "angle": _camera_angle(scene.camera_description),
                },
                "actions": [
                    {
                        "character": (scene.active_character_ids[0] if scene.active_character_ids else "unknown_character"),
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
