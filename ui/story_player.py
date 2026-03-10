"""
Story Player UI Module - Interface for playing generated story content.
"""

import logging
from dataclasses import dataclass
from typing import Optional
from models.scene_schema import PipelineOutput, Scene

logger = logging.getLogger(__name__)


@dataclass
class PlaybackState:
    """Current playback state."""
    current_scene_index: int = 0
    is_playing: bool = False
    current_time: float = 0.0
    total_duration: float = 0.0
    volume: float = 0.8
    autoplay: bool = True


class StoryPlayer:
    """Main story player interface."""
    
    def __init__(self, pipeline_output: PipelineOutput):
        """
        Initialize story player.
        
        Args:
            pipeline_output: Complete output from the pipeline
        """
        self.output = pipeline_output
        self.story = pipeline_output.story
        self.state = PlaybackState(total_duration=pipeline_output.total_duration_seconds)
        
        logger.info(f"[PLAYER] Initialized player for '{self.story.title}'")
        logger.info(f"[PLAYER] Total scenes: {len(self.story.scenes)}")
        logger.info(f"[PLAYER] Total duration: {self.state.total_duration:.1f}s")
    
    def play(self) -> None:
        """Start playback."""
        if not self.story.scenes:
            logger.warning("[PLAYER] No scenes available to play")
            return
            
        logger.info("[PLAYER] Starting playback")
        self.state.is_playing = True
        self._play_current_scene()
    
    def pause(self) -> None:
        """Pause playback."""
        logger.info("[PLAYER] Pausing playback")
        self.state.is_playing = False
    
    def resume(self) -> None:
        """Resume playback."""
        logger.info("[PLAYER] Resuming playback")
        self.state.is_playing = True
    
    def stop(self) -> None:
        """Stop playback and reset."""
        logger.info("[PLAYER] Stopping playback")
        self.state.is_playing = False
        self.state.current_scene_index = 0
        self.state.current_time = 0.0
    
    def next_scene(self) -> None:
        """Go to next scene."""
        if self.state.current_scene_index < len(self.story.scenes) - 1:
            self.state.current_scene_index += 1
            logger.info(f"[PLAYER] Advancing to scene {self.state.current_scene_index + 1}")
            self._play_current_scene()
        else:
            logger.info("[PLAYER] Reached end of story")
    
    def previous_scene(self) -> None:
        """Go to previous scene."""
        if self.state.current_scene_index > 0:
            self.state.current_scene_index -= 1
            logger.info(f"[PLAYER] Rewinding to scene {self.state.current_scene_index + 1}")
            self._play_current_scene()
    
    def goto_scene(self, scene_index: int) -> None:
        """Jump to specific scene."""
        if 0 <= scene_index < len(self.story.scenes):
            self.state.current_scene_index = scene_index
            logger.info(f"[PLAYER] Jumping to scene {scene_index + 1}")
            self._play_current_scene()
        else:
            logger.warning(f"[PLAYER] Invalid scene index: {scene_index}")
    
    def set_volume(self, volume: float) -> None:
        """Set playback volume (0.0-1.0)."""
        self.state.volume = max(0.0, min(1.0, volume))
        logger.debug(f"[PLAYER] Volume set to {self.state.volume:.1%}")
    
    def _play_current_scene(self) -> None:
        """Play the current scene."""
        scene = self.story.scenes[self.state.current_scene_index]
        logger.info(f"[PLAYER] Playing scene {self.state.current_scene_index + 1}: {scene.title}")
        self._display_scene(scene)
        # TODO: Play audio files (narration + BGM)
    
    def _display_scene(self, scene: Scene) -> None:
        """Display scene information."""
        logger.info(f"  Scene ID: {scene.scene_id}")
        logger.info(f"  Title: {scene.title}")
        logger.info(f"  Setting: {scene.setting.value}")
        logger.info(f"  Mood: {scene.mood.value}")
        logger.info(f"  Characters: {', '.join([c.name for c in scene.characters])}")
        
        if scene.image_path:
            logger.info(f"  Image: {scene.image_path}")
        if scene.audio_path:
            logger.info(f"  Narration: {scene.audio_path}")
        if scene.bgm_path:
            logger.info(f"  BGM: {scene.bgm_path}")
    
    def get_current_scene(self) -> Optional[Scene]:
        """Get current scene being played."""
        if 0 <= self.state.current_scene_index < len(self.story.scenes):
            return self.story.scenes[self.state.current_scene_index]
        return None
    
    def get_scene_list(self) -> list:
        """Get list of all scenes with summaries."""
        scene_list = []
        for idx, scene in enumerate(self.story.scenes, 1):
            scene_list.append({
                "index": idx - 1,
                "title": scene.title,
                "setting": scene.setting.value,
                "mood": scene.mood.value,
                "characters": [c.name for c in scene.characters]
            })
        return scene_list
    
    def display_story_info(self) -> None:
        """Display story information."""
        logger.info("\n" + "="*60)
        logger.info(f"STORY: {self.story.title}")
        logger.info(f"AUTHOR: {self.story.author}")
        logger.info(f"DESCRIPTION: {self.story.description}")
        logger.info(f"SCENES: {len(self.story.scenes)}")
        logger.info(f"STATUS: {self.output.status}")
        logger.info("="*60 + "\n")


class PlaybackController:
    """Controller for managing playback operations."""
    
    def __init__(self, player: StoryPlayer):
        """
        Initialize playback controller.
        
        Args:
            player: StoryPlayer instance
        """
        self.player = player
        self.is_fullscreen = False
        self.subtitles_enabled = True
        self.skip_intro = False
        
        logger.debug("[PLAYBACK] Playback controller initialized")
    
    def toggle_fullscreen(self) -> None:
        """Toggle fullscreen mode."""
        self.is_fullscreen = not self.is_fullscreen
        logger.debug(f"[PLAYBACK] Fullscreen: {self.is_fullscreen}")
    
    def toggle_subtitles(self) -> None:
        """Toggle subtitle display."""
        self.subtitles_enabled = not self.subtitles_enabled
        logger.debug(f"[PLAYBACK] Subtitles: {self.subtitles_enabled}")
    
    def quick_skip_ahead(self, seconds: float = 30) -> None:
        """Skip ahead by specified seconds."""
        logger.debug(f"[PLAYBACK] Skipping ahead {seconds}s")
        # TODO: Implement actual time-based seeking
    
    def get_playback_info(self) -> dict:
        """Get current playback information."""
        scene = self.player.get_current_scene()
        return {
            "story": self.player.story.title,
            "current_scene": self.player.state.current_scene_index + 1,
            "total_scenes": len(self.player.story.scenes),
            "scene_title": scene.title if scene else "N/A",
            "is_playing": self.player.state.is_playing,
            "volume": self.player.state.volume,
            "fullscreen": self.is_fullscreen,
            "subtitles": self.subtitles_enabled,
            "total_duration": self.player.state.total_duration
        }


class HotkeyBindings:
    """Keyboard shortcuts for player control."""
    
    HOTKEYS = {
        "play_pause": "SPACE",
        "next_scene": "RIGHT_ARROW",
        "previous_scene": "LEFT_ARROW",
        "increase_volume": "UP_ARROW",
        "decrease_volume": "DOWN_ARROW",
        "toggle_fullscreen": "F",
        "toggle_subtitles": "S",
        "quit": "Q"
    }
    
    @staticmethod
    def get_hotkey(action: str) -> str:
        """Get hotkey for action."""
        return HotkeyBindings.HOTKEYS.get(action, "")
    
    @staticmethod
    def list_hotkeys() -> dict:
        """List all available hotkeys."""
        return HotkeyBindings.HOTKEYS.copy()
