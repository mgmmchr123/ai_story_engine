"""Deterministic canonical story extractor."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from .base_extractor import BaseStoryExtractor

_STYLE_VALUES = {"anime", "cartoon", "realistic"}
_DEFAULT_CAMERA = {"shot": "medium shot", "angle": "eye level"}
_DIALOGUE_RE = re.compile(r"^(?P<speaker>[A-Z][A-Za-z0-9_ ]{0,40}):\s*(?P<text>.+)$")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


@dataclass(slots=True)
class DeterministicStoryExtractor(BaseStoryExtractor):
    """Simple deterministic extractor that emits canonical story.json data."""

    default_style: str = "anime"

    def extract(self, text: str) -> dict[str, Any]:
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
                    "title": "Scene 1",
                    "location": default_location_id,
                    "mood": "mysterious",
                    "narration": "",
                    "duration_sec": 5,
                    "characters": [item["id"] for item in characters] or ["narrator"],
                    "camera": dict(_DEFAULT_CAMERA),
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
            if not match:
                continue
            candidate = match.group("speaker").strip()
            normalized = candidate.lower()
            if normalized in seen:
                continue
            names.append(candidate)
            seen.add(normalized)

        if not names:
            for candidate in re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\b", text):
                normalized = candidate.lower()
                if normalized in seen or normalized in {"scene", "chapter"}:
                    continue
                names.append(candidate)
                seen.add(normalized)
                if len(names) >= 4:
                    break

        if not names:
            names = ["Narrator"]

        characters: list[dict[str, str]] = []
        for index, name in enumerate(names, start=1):
            characters.append(
                {
                    "id": self._slugify(name, f"character_{index}"),
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
            actions = self.extract_actions(block, scene_character_ids, character_lookup)
            scenes.append(
                {
                    "scene_id": index,
                    "title": f"Scene {index}",
                    "location": self._match_location(block, locations, default_location),
                    "mood": self._infer_scene_mood(block),
                    "narration": block.strip(),
                    "duration_sec": max(3, min(12, len(block.split()) // 3 or 5)),
                    "characters": scene_character_ids,
                    "camera": self._build_camera(block),
                    "actions": actions,
                    "dialogue": dialogue,
                }
            )
        return scenes

    def extract_dialogue(self, block: str, character_lookup: dict[str, str]) -> list[dict[str, str]]:
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
        ).strip() or block.strip()
        action_type = "observe"
        lowered = plain_text.lower()
        for keyword in action_keywords:
            if keyword in lowered:
                action_type = keyword
                break

        character_id = scene_character_ids[0] if scene_character_ids else next(iter(character_lookup.values()), "narrator")
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

    def _match_location(self, block: str, locations: list[dict[str, str]], default_location: str) -> str:
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

    def _infer_scene_mood(self, text: str) -> str:
        lowered = text.lower()
        if any(word in lowered for word in ("battle", "charge", "triumph", "hero")):
            return "heroic"
        if any(word in lowered for word in ("laugh", "joke", "grin")):
            return "humorous"
        if any(word in lowered for word in ("fear", "shadow", "dark", "whisper", "mystery")):
            return "mysterious"
        if any(word in lowered for word in ("tense", "threat", "danger", "angry")):
            return "tense"
        return "mysterious"

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
