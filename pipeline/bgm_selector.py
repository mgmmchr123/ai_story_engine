"""
Background Music (BGM) Selector Module - Selects appropriate BGM for scenes.
"""

import logging
from enum import Enum
from pathlib import Path
from config import BGM_DIR

logger = logging.getLogger(__name__)


class MusicGenre(Enum):
    """Music genre categories."""
    ORCHESTRAL = "orchestral"
    FOLK = "folk"
    EPIC = "epic"
    DARK = "dark"
    AMBIENT = "ambient"
    DRAMATIC = "dramatic"
    COMEDIC = "comedic"


class MusicIntensity(Enum):
    """Music intensity levels."""
    CALM = "calm"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    INTENSE = "intense"


class MusicTempo(Enum):
    """Music tempo classifications."""
    SLOW = "slow"  # <100 BPM
    MODERATE = "moderate"  # 100-140 BPM
    FAST = "fast"  # >140 BPM


def select_bgm(mood: str, setting: str, intensity: str = "medium",
               tempo: str = "moderate") -> str:

    track_name = _rule_based_selection(mood, setting, intensity, tempo)

    bgm_path = BGM_DIR / f"{track_name}.mp3"

    if not bgm_path.exists():
        logger.warning(f"[BGM] Track not found: {bgm_path}, using default")
        bgm_path = BGM_DIR / "default.mp3"

    return str(bgm_path)

def _rule_based_selection(mood: str, setting: str, 
                         intensity: str, tempo: str) -> str:
    """
    Rule-based music selection logic.
    
    Args:
        mood: Scene mood
        setting: Scene setting
        intensity: Music intensity
        tempo: Desired tempo
        
    Returns:
        Music file identifier
    """
    # Mood-based primary selection
    mood_music_map = {
        "heroic": "orchestral_heroic",
        "epic": "epic_adventure",
        "tense": "dark_suspense",
        "mysterious": "ambient_mysterious",
        "calm": "peaceful_ambient",
        "humorous": "comedic_whimsy"
    }
    
    # Setting-based secondary adjustment
    setting_adjustment = {
        "forest": "_nature",
        "castle": "_medieval",
        "village": "_folk",
        "dungeon": "_dark",
        "throne_room": "_ceremonial",
        "tavern": "_tavern"
    }
    
    base_track = mood_music_map.get(mood, "orchestral_neutral")
    setting_suffix = setting_adjustment.get(setting, "")
    
    track_name = f"{base_track}{setting_suffix}_{intensity}_{tempo}"
    
    logger.debug(f"[BGM] Rule-based selection: {track_name}")
    return track_name


class MusicLibrary:
    """In-memory music library catalog."""
    
    def __init__(self):
        """Initialize music library."""
        self.tracks = self._load_track_metadata()
        logger.debug(f"[BGM] Loaded {len(self.tracks)} tracks from library")
        
    def _load_track_metadata(self) -> dict:
        """
        Load music track metadata.
        
        TODO: Load actual metadata from disk/database
        - Track names
        - Duration
        - Genre
        - Mood
        - Tempo
        - Intensity
        """
        # Placeholder metadata
        return {
            "orchestral_heroic_medium_moderate": {
                "duration": 180,
                "genre": "orchestral",
                "mood": "heroic",
                "intensity": "medium",
                "tempo": "moderate",
                "bpm": 120
            },
            "epic_adventure_high_fast": {
                "duration": 240,
                "genre": "epic",
                "mood": "epic",
                "intensity": "high",
                "tempo": "fast",
                "bpm": 160
            },
            "dark_suspense_medium_slow": {
                "duration": 200,
                "genre": "dark",
                "mood": "tense",
                "intensity": "medium",
                "tempo": "slow",
                "bpm": 80
            },
            "ambient_mysterious_low_slow": {
                "duration": 300,
                "genre": "ambient",
                "mood": "mysterious",
                "intensity": "low",
                "tempo": "slow",
                "bpm": 60
            }
        }
    
    def get_track_info(self, track_id: str) -> dict:
        """Get track metadata."""
        return self.tracks.get(track_id, {})
    
    def list_tracks_by_mood(self, mood: str) -> list:
        """List all tracks matching a mood."""
        return [
            track_id for track_id, info in self.tracks.items()
            if info.get("mood") == mood
        ]


class DynamicMusicComposer:
    """Placeholder for dynamic music composition."""
    
    @staticmethod
    def compose_music(mood: str, duration: int = 180,
                     parameters: dict = None) -> str:
        """
        Compose music dynamically based on parameters.
        
        Future implementations:
        - MuseGAN for music generation
        - Procedural composition algorithms
        - Real-time synthesis
        
        Args:
            mood: Desired mood
            duration: Duration in seconds
            parameters: Additional composition parameters
            
        Returns:
            Path to generated music file
        """
        logger.debug(f"[BGM] Composing dynamic music: {mood}, {duration}s")
        
        # TODO: Implement music generation
        # - Use generative models
        # - Parameter-driven synthesis
        # - Real-time orchestration
        
        composed_path = f"bgm/composed_{mood}_{duration}s.mp3"
        logger.info(f"[BGM] Composed music: {composed_path}")
        
        return composed_path
