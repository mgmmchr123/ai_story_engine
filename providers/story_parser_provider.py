"""Story parser provider interfaces and implementations."""

from abc import ABC, abstractmethod
import json
import logging
import re
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request

from config import ParserSettings
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

logger = logging.getLogger(__name__)


class StoryParserProvider(ABC):
    """Provider abstraction for story parsing."""

    @abstractmethod
    def parse(self, story_text: str, title: str, author: str) -> StoryContent:
        """Parse raw text into structured story content."""


class PlaceholderStoryParserProvider(StoryParserProvider):
    """Deterministic line-based parser used as baseline and fallback."""

    def parse(self, story_text: str, title: str, author: str) -> StoryContent:
        lines = [line.strip() for line in story_text.strip().splitlines() if line.strip()]
        visual_bible = StoryVisualBible(
            title=title,
            style=StyleDefinition(),
            characters=[
                CharacterDefinition(
                    character_id="unknown_001",
                    name="Unknown",
                    role="npc",
                    appearance="unidentified traveler",
                    outfit="simple clothing",
                )
            ],
            locations=[
                LocationDefinition(
                    location_id="forest_001",
                    name="Forest",
                    appearance="dense old-growth forest",
                    environment_details="misty atmosphere and layered tree depth",
                    color_palette="deep greens and cool blues",
                    default_time_of_day="dusk",
                )
            ],
        )
        scenes: list[Scene] = []

        for index, line in enumerate(lines, start=1):
            scenes.append(
                Scene(
                    scene_id=index,
                    title=f"Scene {index}",
                    description=line,
                    characters=[
                        CharacterData(
                            name="Unknown",
                            type=Character.NPC,
                            emotion="neutral",
                            action="standing",
                        )
                    ],
                    setting=Setting.FOREST,
                    mood=Mood.MYSTERIOUS,
                    narration_text=line,
                    location_id="forest_001",
                    active_character_ids=["unknown_001"],
                    action_description=line,
                )
            )

        return StoryContent(
            title=title,
            author=author,
            description=f"{len(scenes)} scenes generated",
            scenes=scenes,
            visual_bible=visual_bible,
        )


class OllamaStoryParserProvider(StoryParserProvider):
    """Parser provider backed by local Ollama structured JSON output."""

    def __init__(self, settings: ParserSettings):
        self.settings = settings

    def parse(self, story_text: str, title: str, author: str) -> StoryContent:
        visual_bible_payload = self._extract_visual_bible(story_text=story_text, title=title, author=author)
        scene_state_payload = self._extract_scene_states(
            story_text=story_text,
            title=title,
            author=author,
            visual_bible_payload=visual_bible_payload,
        )
        structured = {
            "story_description": scene_state_payload.get("story_description")
            or visual_bible_payload.get("story_description")
            or visual_bible_payload.get("description")
            or scene_state_payload.get("description")
            or "",
            "visual_bible": visual_bible_payload.get("visual_bible", {}),
            "scene_states": scene_state_payload.get("scene_states", []),
        }
        return self._structured_to_story(structured, title=title, author=author)

    def _extract_visual_bible(self, story_text: str, title: str, author: str) -> dict[str, Any]:
        system_prompt = (
            "You are a strict JSON service. Output only valid JSON with schema: "
            '{"story_description":"string","visual_bible":{"style":{"art_style":"string","lighting_style":"string",'
            '"rendering_style":"string","mood_baseline":"string","consistency_instructions":"string"},'
            '"characters":[{"character_id":"string","name":"string","role":"hero|villain|sidekick|npc","appearance":"string","outfit":"string",'
            '"props":["string"],"personality_keywords":["string"],"reference_image_path":"string|null"}],'
            '"locations":[{"location_id":"string","name":"string","appearance":"string","environment_details":"string","color_palette":"string","default_time_of_day":"string"}],'
            '"props":["string"]}}.'
        )
        user_prompt = (
            f"Title: {title}\nAuthor: {author}\n"
            "Extract stable recurring visual entities from this story. Keep IDs deterministic and concise.\n"
            f"Story:\n{story_text}"
        )
        return self._call_ollama_json(system_prompt=system_prompt, user_prompt=user_prompt)

    def _extract_scene_states(
        self,
        story_text: str,
        title: str,
        author: str,
        visual_bible_payload: dict[str, Any],
    ) -> dict[str, Any]:
        visual_bible_json = json.dumps(visual_bible_payload.get("visual_bible", {}), ensure_ascii=True)
        system_prompt = (
            "You are a strict JSON service. Output only valid JSON with schema: "
            '{"story_description":"string","scene_states":[{"scene_id":"number","title":"string","location_id":"string","active_character_ids":["string"],'
            '"action_description":"string","description":"string","mood":"heroic|mysterious|tense|calm|epic|humorous","camera_description":"string","state_delta":"string","narration_text":"string"}]}.'
        )
        user_prompt = (
            f"Title: {title}\nAuthor: {author}\n"
            "Using this visual_bible, create scene states that reference existing IDs.\n"
            f"visual_bible:\n{visual_bible_json}\n"
            f"Story:\n{story_text}"
        )
        return self._call_ollama_json(system_prompt=system_prompt, user_prompt=user_prompt)

    def _call_ollama_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        payload = {
            "model": self.settings.ollama_model,
            "stream": False,
            "format": "json",
            "options": {"temperature": self.settings.ollama_temperature},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        endpoint = f"{self.settings.ollama_url.rstrip('/')}/api/chat"
        body = json.dumps(payload).encode("utf-8")
        req = urllib_request.Request(
            endpoint,
            data=body,
            method="POST",
            headers={"Content-Type": "application/json"},
        )

        try:
            with urllib_request.urlopen(req, timeout=self.settings.ollama_timeout_seconds) as response:
                raw = response.read().decode("utf-8")
        except urllib_error.URLError as exc:
            raise TimeoutError(f"Ollama request failed/timed out: {exc}") from exc

        data = json.loads(raw)
        content = data.get("message", {}).get("content", "")
        if not content:
            raise ValueError("Ollama response missing message.content")
        parsed = json.loads(content)
        if not isinstance(parsed, dict):
            raise ValueError("Ollama response content must decode to object JSON")
        return parsed

    def _structured_to_story(self, structured: dict[str, Any], title: str, author: str) -> StoryContent:
        if not isinstance(structured, dict):
            raise ValueError("Structured output must be a JSON object")

        visual_bible = _normalize_visual_bible(structured, title)
        character_map = visual_bible.character_map()
        location_map = visual_bible.location_map()

        raw_scene_states = structured.get("scene_states")
        if not isinstance(raw_scene_states, list):
            raw_scene_states = structured.get("scenes")
        if not isinstance(raw_scene_states, list):
            raise ValueError("Structured output must contain 'scene_states' or 'scenes' list")

        scenes: list[Scene] = []
        for index, raw_scene in enumerate(raw_scene_states, start=1):
            if not isinstance(raw_scene, dict):
                continue
            scene = _normalize_scene_state(
                raw_scene=raw_scene,
                index=index,
                visual_bible=visual_bible,
                character_map=character_map,
                location_map=location_map,
            )
            scenes.append(scene)

        if not scenes:
            raise ValueError("Structured output did not include valid scenes")

        description = str(
            structured.get("story_description")
            or structured.get("description")
            or f"{len(scenes)} scenes generated"
        )
        return StoryContent(
            title=title,
            author=author,
            description=description,
            scenes=scenes,
            visual_bible=visual_bible,
        )


def _normalize_visual_bible(structured: dict[str, Any], title: str) -> StoryVisualBible:
    raw_visual_bible = structured.get("visual_bible")
    raw_visual_bible = raw_visual_bible if isinstance(raw_visual_bible, dict) else {}

    raw_style = raw_visual_bible.get("style")
    raw_style = raw_style if isinstance(raw_style, dict) else {}
    style = StyleDefinition(
        art_style=str(raw_style.get("art_style") or "cinematic illustration"),
        lighting_style=str(raw_style.get("lighting_style") or "dramatic lighting"),
        rendering_style=str(raw_style.get("rendering_style") or "high detail"),
        mood_baseline=str(raw_style.get("mood_baseline") or "immersive fantasy"),
        consistency_instructions=str(
            raw_style.get("consistency_instructions")
            or "Maintain consistent character identity, proportions, and location continuity."
        ),
    )

    characters = _normalize_character_definitions(raw_visual_bible.get("characters"))
    if not characters:
        characters.append(
            CharacterDefinition(
                character_id="unknown_001",
                name="Unknown",
                role="npc",
                appearance="undefined silhouette",
                outfit="simple clothing",
            )
        )

    locations = _normalize_location_definitions(raw_visual_bible.get("locations"))
    if not locations:
        locations.append(
            LocationDefinition(
                location_id="forest_001",
                name="Forest",
                appearance="old forest clearing",
                environment_details="fog and dense trees",
                color_palette="green and blue",
                default_time_of_day="dusk",
            )
        )

    return StoryVisualBible(
        title=title,
        style=style,
        characters=characters,
        locations=locations,
        props=_normalize_string_list(raw_visual_bible.get("props")),
    )


def _normalize_character_definitions(value: Any) -> list[CharacterDefinition]:
    if not isinstance(value, list):
        return []
    result: list[CharacterDefinition] = []
    for index, raw_character in enumerate(value, start=1):
        if not isinstance(raw_character, dict):
            continue
        name = str(raw_character.get("name") or f"Character {index}")
        role = _normalize_character_type(raw_character.get("role") or raw_character.get("type")).value
        raw_character_id = str(raw_character.get("character_id") or "").strip()
        character_id = _semantic_character_id(raw_character_id, name, role, index)
        result.append(
            CharacterDefinition(
                character_id=character_id,
                name=name,
                role=role,
                appearance=str(raw_character.get("appearance") or ""),
                outfit=str(raw_character.get("outfit") or ""),
                props=_normalize_string_list(raw_character.get("props")),
                personality_keywords=_normalize_string_list(raw_character.get("personality_keywords")),
                reference_image_path=_normalize_optional_string(raw_character.get("reference_image_path")),
            )
        )
    return result


def _normalize_location_definitions(value: Any) -> list[LocationDefinition]:
    if not isinstance(value, list):
        return []
    result: list[LocationDefinition] = []
    for index, raw_location in enumerate(value, start=1):
        if not isinstance(raw_location, dict):
            continue
        name = str(raw_location.get("name") or f"Location {index}")
        raw_location_id = str(raw_location.get("location_id") or "").strip()
        location_id = _semantic_location_id(raw_location_id, name, index)
        result.append(
            LocationDefinition(
                location_id=location_id,
                name=name,
                appearance=str(raw_location.get("appearance") or ""),
                environment_details=str(raw_location.get("environment_details") or ""),
                color_palette=str(raw_location.get("color_palette") or ""),
                default_time_of_day=str(raw_location.get("default_time_of_day") or ""),
            )
        )
    return result


def _normalize_scene_state(
    raw_scene: dict[str, Any],
    index: int,
    visual_bible: StoryVisualBible,
    character_map: dict[str, CharacterDefinition],
    location_map: dict[str, LocationDefinition],
) -> Scene:
    scene_id = int(raw_scene.get("scene_id") or index)
    title = str(raw_scene.get("title") or f"Scene {scene_id}")
    description = str(raw_scene.get("description") or raw_scene.get("action_description") or "")
    action_description = str(raw_scene.get("action_description") or description)
    narration_text = str(raw_scene.get("narration_text") or description or action_description)
    mood = _normalize_mood(raw_scene.get("mood"))

    location_id = str(raw_scene.get("location_id") or "").strip()
    if not location_id:
        location_id = _guess_location_id_from_scene(raw_scene, location_map)
    else:
        location_id = _coerce_known_location_id(location_id, location_map)
    if location_id not in location_map:
        fallback_location = LocationDefinition(
            location_id=location_id or f"location_{scene_id:03d}",
            name=str(raw_scene.get("location_name") or "Unknown Location"),
            appearance=str(raw_scene.get("location_appearance") or ""),
            environment_details="",
            color_palette="",
            default_time_of_day="",
        )
        visual_bible.locations.append(fallback_location)
        location_map[fallback_location.location_id] = fallback_location
        location_id = fallback_location.location_id

    setting = _normalize_setting(raw_scene.get("setting"))

    raw_character_ids = raw_scene.get("active_character_ids")
    active_character_ids: list[str] = []
    if isinstance(raw_character_ids, list):
        for raw_id in raw_character_ids:
            character_id = str(raw_id or "").strip()
            if character_id:
                active_character_ids.append(_coerce_known_character_id(character_id, character_map))

    raw_characters = raw_scene.get("characters")
    if isinstance(raw_characters, list):
        for raw_character in raw_characters:
            if not isinstance(raw_character, dict):
                continue
            character_id = str(raw_character.get("character_id") or "").strip()
            name = str(raw_character.get("name") or "").strip()
            if not character_id and name:
                character_id = _find_character_id_by_name(character_map, name) or _slugify(
                    name,
                    fallback=f"character_{scene_id:03d}_{len(active_character_ids) + 1}",
                )
            if character_id and character_id not in character_map:
                generated = CharacterDefinition(
                    character_id=character_id,
                    name=name or character_id,
                    role=_normalize_character_type(raw_character.get("role") or raw_character.get("type")).value,
                    appearance=str(raw_character.get("appearance") or ""),
                    outfit=str(raw_character.get("outfit") or ""),
                    props=_normalize_string_list(raw_character.get("props")),
                    personality_keywords=_normalize_string_list(raw_character.get("personality_keywords")),
                )
                visual_bible.characters.append(generated)
                character_map[generated.character_id] = generated
            if character_id:
                active_character_ids.append(_coerce_known_character_id(character_id, character_map))

    active_character_ids = _unique_list(active_character_ids)
    if not active_character_ids:
        active_character_ids = [visual_bible.characters[0].character_id]

    character_states = _build_scene_character_states(raw_scene)
    characters: list[CharacterData] = []
    for character_id in active_character_ids:
        definition = character_map.get(character_id)
        if not definition:
            continue
        state = character_states.get(character_id, {})
        characters.append(
            CharacterData(
                name=definition.name,
                type=_normalize_character_type(definition.role),
                emotion=str(state.get("emotion") or "neutral"),
                action=str(state.get("action") or action_description or "present"),
            )
        )
    if not characters:
        characters = [CharacterData(name="Unknown", type=Character.NPC, emotion="neutral", action="present")]

    camera_description = str(raw_scene.get("camera_description") or raw_scene.get("camera") or "")
    state_delta = str(raw_scene.get("state_delta") or "")

    return Scene(
        scene_id=scene_id,
        title=title,
        description=description or action_description,
        characters=characters,
        setting=setting,
        mood=mood,
        narration_text=narration_text,
        location_id=location_id,
        active_character_ids=active_character_ids,
        action_description=action_description or description,
        camera_description=camera_description,
        state_delta=state_delta,
    )


def _build_scene_character_states(raw_scene: dict[str, Any]) -> dict[str, dict[str, str]]:
    states: dict[str, dict[str, str]] = {}
    raw_characters = raw_scene.get("characters")
    if not isinstance(raw_characters, list):
        return states
    for raw_character in raw_characters:
        if not isinstance(raw_character, dict):
            continue
        character_id = str(raw_character.get("character_id") or "").strip()
        if not character_id:
            continue
        states[character_id] = {
            "emotion": str(raw_character.get("emotion") or "neutral"),
            "action": str(raw_character.get("action") or ""),
        }
    return states


def _guess_location_id_from_scene(raw_scene: dict[str, Any], location_map: dict[str, LocationDefinition]) -> str:
    location_name = str(raw_scene.get("location_name") or "").strip().lower()
    if location_name:
        for location_id, location in location_map.items():
            if location.name.strip().lower() == location_name:
                return location_id

    setting = _normalize_setting(raw_scene.get("setting"))
    for location_id in location_map:
        if setting.value in location_id:
            return location_id
    return next(iter(location_map), "forest_001")


def _find_character_id_by_name(character_map: dict[str, CharacterDefinition], name: str) -> str | None:
    normalized = name.strip().lower()
    if not normalized:
        return None
    for character_id, definition in character_map.items():
        if definition.name.strip().lower() == normalized:
            return character_id
    return None


def _coerce_known_character_id(candidate: str, character_map: dict[str, CharacterDefinition]) -> str:
    if candidate in character_map:
        return candidate
    if candidate.isdigit():
        suffix = f"_{int(candidate):03d}"
        for character_id in character_map:
            if character_id.endswith(suffix):
                return character_id
    return candidate


def _coerce_known_location_id(candidate: str, location_map: dict[str, LocationDefinition]) -> str:
    if candidate in location_map:
        return candidate
    if candidate.isdigit():
        suffix = f"_{int(candidate):03d}"
        for location_id in location_map:
            if location_id.endswith(suffix):
                return location_id
    return candidate


def _normalize_setting(value: Any) -> Setting:
    normalized = str(value or "").strip().lower().replace(" ", "_")
    for enum_item in Setting:
        if enum_item.value == normalized:
            return enum_item
    return Setting.FOREST


def _normalize_mood(value: Any) -> Mood:
    normalized = str(value or "").strip().lower().replace(" ", "_")
    for enum_item in Mood:
        if enum_item.value == normalized:
            return enum_item
    return Mood.MYSTERIOUS


def _normalize_character_type(value: Any) -> Character:
    normalized = str(value or "").strip().lower().replace(" ", "_")
    for enum_item in Character:
        if enum_item.value == normalized:
            return enum_item
    return Character.NPC


def _normalize_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        text = str(item or "").strip()
        if text:
            result.append(text)
    return result


def _normalize_optional_string(value: Any) -> str | None:
    text = str(value or "").strip()
    return text if text else None


def _slugify(value: str, fallback: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.strip().lower())
    slug = slug.strip("_")
    return slug or fallback


def _semantic_character_id(raw_id: str, name: str, role: str, index: int) -> str:
    candidate = raw_id or _slugify(name, fallback=f"{role}_{index:03d}")
    if candidate.isdigit():
        return f"{role}_{int(candidate):03d}"
    if candidate.startswith("_"):
        return f"{role}{candidate}"
    return candidate


def _semantic_location_id(raw_id: str, name: str, index: int) -> str:
    candidate = raw_id or _slugify(name, fallback=f"location_{index:03d}")
    if candidate.isdigit():
        return f"{_slugify(name, fallback='location')}_{int(candidate):03d}"
    return candidate


def _unique_list(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def build_story_parser_provider(settings: ParserSettings) -> StoryParserProvider:
    """Factory for parser provider."""
    if settings.provider == "placeholder":
        return PlaceholderStoryParserProvider()
    if settings.provider == "ollama":
        return OllamaStoryParserProvider(settings)
    raise ValueError(f"Unsupported story parser provider: {settings.provider}")
