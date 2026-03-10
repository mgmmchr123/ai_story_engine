"""
Data models for the AI Storytelling Engine.
"""

from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum


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


@dataclass
class Character_Data:
    """Character information in a scene."""
    name: str
    type: Character
    emotion: str
    action: str


@dataclass
class Scene:
    """Single scene in the story."""
    scene_id: int
    title: str
    description: str
    characters: List[Character_Data]
    setting: Setting
    mood: Mood
    narration_text: str = ""
    image_path: Optional[str] = None
    audio_path: Optional[str] = None
    bgm_path: Optional[str] = None


@dataclass
class StoryContent:
    """Complete story structure."""
    title: str
    author: str
    description: str
    scenes: List[Scene] = field(default_factory=list)


@dataclass
class GeneratedAssets:
    """Assets generated from the pipeline."""
    scene_id: int
    image_path: Optional[str] = None
    narration_path: Optional[str] = None
    bgm_path: Optional[str] = None
    generation_timestamp: str = ""


@dataclass
class PipelineOutput:
    """Final output from the complete pipeline."""
    story: StoryContent
    generated_assets: List[GeneratedAssets] = field(default_factory=list)
    status: str = "pending"
    total_duration_seconds: float = 0.0
