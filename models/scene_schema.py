"""Domain and artifact models for the AI Storytelling Engine."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class Character(Enum):
    """Available character types."""

    HERO = "hero"
    VILLAIN = "villain"
    SIDEKICK = "sidekick"
    NPC = "npc"


class Setting(Enum):
    """Available scene settings."""

    FOREST = "forest"
    CASTLE = "castle"
    VILLAGE = "village"
    DUNGEON = "dungeon"
    THRONE_ROOM = "throne_room"
    TAVERN = "tavern"


class Mood(Enum):
    """Scene mood/atmosphere."""

    HEROIC = "heroic"
    MYSTERIOUS = "mysterious"
    TENSE = "tense"
    CALM = "calm"
    EPIC = "epic"
    HUMOROUS = "humorous"


SceneMood = Mood | str


def display_value(value: Any) -> str:
    """Return a stable display string for enums, plain strings, and other values."""

    raw = getattr(value, "value", value)
    text = str(raw or "").strip()
    return text


def scene_mood_value(mood: SceneMood) -> str:
    """Return a stable string value for enum-backed or raw scene moods."""

    text = display_value(mood)
    return text or Mood.MYSTERIOUS.value


@dataclass(slots=True)
class CharacterData:
    """Character information in a scene."""

    name: str
    type: Character
    emotion: str
    action: str


@dataclass(slots=True)
class CharacterDefinition:
    """Stable character definition shared across scenes."""

    character_id: str
    name: str
    role: str
    appearance: str = ""
    outfit: str = ""
    props: list[str] = field(default_factory=list)
    personality_keywords: list[str] = field(default_factory=list)
    reference_image_path: str | None = None


@dataclass(slots=True)
class LocationDefinition:
    """Stable location definition shared across scenes."""

    location_id: str
    name: str
    appearance: str = ""
    environment_details: str = ""
    color_palette: str = ""
    default_time_of_day: str = ""


@dataclass(slots=True)
class StyleDefinition:
    """Stable style definition shared across all scene prompts."""

    art_style: str = "cinematic illustration"
    lighting_style: str = "dramatic lighting"
    rendering_style: str = "high detail"
    mood_baseline: str = "immersive fantasy"
    consistency_instructions: str = (
        "Maintain consistent character identity, proportions, costume, and location layout across scenes."
    )


@dataclass(slots=True)
class StoryVisualBible:
    """Story-level visual definitions for consistency."""

    title: str
    style: StyleDefinition = field(default_factory=StyleDefinition)
    characters: list[CharacterDefinition] = field(default_factory=list)
    locations: list[LocationDefinition] = field(default_factory=list)
    props: list[str] = field(default_factory=list)

    def character_map(self) -> dict[str, CharacterDefinition]:
        return {character.character_id: character for character in self.characters}

    def location_map(self) -> dict[str, LocationDefinition]:
        return {location.location_id: location for location in self.locations}


@dataclass(slots=True)
class Scene:
    """Domain scene model (no generated asset fields)."""

    scene_id: int
    title: str
    description: str
    characters: list[CharacterData]
    setting: Setting
    mood: SceneMood
    narration_text: str = ""
    location_id: str | None = None
    active_character_ids: list[str] = field(default_factory=list)
    action_description: str = ""
    camera_description: str = ""
    state_delta: str = ""


@dataclass(slots=True)
class StoryContent:
    """Complete story structure."""

    title: str
    author: str
    description: str
    scenes: list[Scene] = field(default_factory=list)
    visual_bible: StoryVisualBible | None = None


@dataclass(slots=True)
class SceneAssets:
    """Generated files for a scene."""

    image_path: Optional[str] = None
    narration_path: Optional[str] = None
    bgm_path: Optional[str] = None
    mixed_audio_path: Optional[str] = None


@dataclass(slots=True)
class SceneRenderResult:
    """Render result and metadata for a scene."""

    scene_id: int
    scene_instruction_path: Optional[str] = None
    status: str = "pending"
    assets: SceneAssets = field(default_factory=SceneAssets)
    image_prompt: str = ""
    narration_prompt: str = ""
    bgm_parameters: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    error: Optional[str] = None
    duration_seconds: float = 0.0
    media_duration_seconds: float = 0.0
    skipped: bool = False
    attempts: int = 0
    started_at: str = ""
    completed_at: str = ""


@dataclass(slots=True)
class PipelineOutput:
    """Final output from a pipeline run."""

    run_id: str
    story: StoryContent
    scene_results: list[SceneRenderResult] = field(default_factory=list)
    status: str = "pending"
    total_duration_seconds: float = 0.0
    manifest_path: str = ""
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def generated_assets(self) -> list[SceneAssets]:
        """Compatibility helper for older callers."""
        return [result.assets for result in self.scene_results]


# Backward-compatible alias used by legacy modules.
Character_Data = CharacterData
