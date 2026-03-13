"""Story Player UI module for playing generated story output."""

import logging
from dataclasses import dataclass
from typing import Optional

from engine.world_state import resolve_scene_characters, resolve_scene_location
from models.scene_schema import PipelineOutput, Scene, SceneAssets, display_value, scene_mood_value

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
        self.output = pipeline_output
        self.story = pipeline_output.story
        self._assets_by_scene = {result.scene_id: result.assets for result in pipeline_output.scene_results}
        total_duration = pipeline_output.total_duration_seconds or sum(
            result.media_duration_seconds for result in pipeline_output.scene_results if result.media_duration_seconds > 0
        )
        self.state = PlaybackState(total_duration=total_duration)

        logger.info("[PLAYER] Initialized player for '%s'", self.story.title)
        logger.info("[PLAYER] Total scenes: %s", len(self.story.scenes))
        logger.info("[PLAYER] Total duration: %.1fs", self.state.total_duration)

    def get_scene_assets(self, scene_id: int) -> Optional[SceneAssets]:
        """Return generated assets for a scene."""
        return self._assets_by_scene.get(scene_id)

    def play(self) -> None:
        if not self.story.scenes:
            logger.warning("[PLAYER] No scenes available to play")
            return

        logger.info("[PLAYER] Starting playback")
        self.state.is_playing = True
        self._play_current_scene()

    def pause(self) -> None:
        logger.info("[PLAYER] Pausing playback")
        self.state.is_playing = False

    def resume(self) -> None:
        logger.info("[PLAYER] Resuming playback")
        self.state.is_playing = True

    def stop(self) -> None:
        logger.info("[PLAYER] Stopping playback")
        self.state.is_playing = False
        self.state.current_scene_index = 0
        self.state.current_time = 0.0

    def next_scene(self) -> None:
        if self.state.current_scene_index < len(self.story.scenes) - 1:
            self.state.current_scene_index += 1
            logger.info("[PLAYER] Advancing to scene %s", self.state.current_scene_index + 1)
            self._play_current_scene()
        else:
            logger.info("[PLAYER] Reached end of story")

    def previous_scene(self) -> None:
        if self.state.current_scene_index > 0:
            self.state.current_scene_index -= 1
            logger.info("[PLAYER] Rewinding to scene %s", self.state.current_scene_index + 1)
            self._play_current_scene()

    def goto_scene(self, scene_index: int) -> None:
        if 0 <= scene_index < len(self.story.scenes):
            self.state.current_scene_index = scene_index
            logger.info("[PLAYER] Jumping to scene %s", scene_index + 1)
            self._play_current_scene()
        else:
            logger.warning("[PLAYER] Invalid scene index: %s", scene_index)

    def set_volume(self, volume: float) -> None:
        self.state.volume = max(0.0, min(1.0, volume))
        logger.debug("[PLAYER] Volume set to %.1f%%", self.state.volume * 100)

    def _play_current_scene(self) -> None:
        scene = self.story.scenes[self.state.current_scene_index]
        logger.info("[PLAYER] Playing scene %s: %s", self.state.current_scene_index + 1, scene.title)
        self._display_scene(scene)

    def _display_scene(self, scene: Scene) -> None:
        location = resolve_scene_location(scene, self.story.visual_bible)
        characters = resolve_scene_characters(scene, self.story.visual_bible)
        logger.info("  Scene ID: %s", scene.scene_id)
        logger.info("  Title: %s", scene.title)
        logger.info("  Setting: %s", display_value(location["bgm_setting"]))
        logger.info("  Location: %s", display_value(location["location_name"]))
        logger.info("  Mood: %s", scene_mood_value(scene.mood))
        logger.info("  Characters: %s", ", ".join([item["name"] for item in characters]))

        assets = self.get_scene_assets(scene.scene_id)
        if assets and assets.image_path:
            logger.info("  Image: %s", assets.image_path)
        if assets and assets.narration_path:
            logger.info("  Narration: %s", assets.narration_path)
        if assets and assets.bgm_path:
            logger.info("  BGM: %s", assets.bgm_path)

    def get_current_scene(self) -> Optional[Scene]:
        if 0 <= self.state.current_scene_index < len(self.story.scenes):
            return self.story.scenes[self.state.current_scene_index]
        return None

    def get_scene_list(self) -> list:
        scene_list = []
        for idx, scene in enumerate(self.story.scenes, 1):
            location = resolve_scene_location(scene, self.story.visual_bible)
            characters = resolve_scene_characters(scene, self.story.visual_bible)
            scene_list.append(
                {
                    "index": idx - 1,
                    "title": scene.title,
                    "setting": location["bgm_setting"],
                    "location_name": location["location_name"],
                    "mood": scene_mood_value(scene.mood),
                    "characters": [item["name"] for item in characters],
                }
            )
        return scene_list

    def display_story_info(self) -> None:
        logger.info("\n" + "=" * 60)
        logger.info("STORY: %s", self.story.title)
        logger.info("AUTHOR: %s", self.story.author)
        logger.info("DESCRIPTION: %s", self.story.description)
        logger.info("SCENES: %s", len(self.story.scenes))
        logger.info("STATUS: %s", self.output.status)
        logger.info("RUN ID: %s", self.output.run_id)
        logger.info("=" * 60 + "\n")


class PlaybackController:
    """Controller for playback operations."""

    def __init__(self, player: StoryPlayer):
        self.player = player
        self.is_fullscreen = False
        self.subtitles_enabled = True
        self.skip_intro = False

    def toggle_fullscreen(self) -> None:
        self.is_fullscreen = not self.is_fullscreen

    def toggle_subtitles(self) -> None:
        self.subtitles_enabled = not self.subtitles_enabled

    def quick_skip_ahead(self, seconds: float = 30) -> None:
        _ = seconds

    def get_playback_info(self) -> dict:
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
            "total_duration": self.player.state.total_duration,
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
        "quit": "Q",
    }

    @staticmethod
    def get_hotkey(action: str) -> str:
        return HotkeyBindings.HOTKEYS.get(action, "")

    @staticmethod
    def list_hotkeys() -> dict:
        return HotkeyBindings.HOTKEYS.copy()
