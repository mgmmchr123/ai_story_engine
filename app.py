"""Application entrypoint using the refactored pipeline runner."""

from datetime import datetime
import logging
import os
from pathlib import Path

from config import CONFIG_SAMPLE_STORY, ENGINE_SETTINGS, PROJECT_ROOT, SAMPLE_STORY_PATH
from engine.world_state import resolve_scene_characters, resolve_scene_location
from models.scene_schema import PipelineOutput, display_value, scene_mood_value
from ui.story_player import PlaybackController, StoryPlayer

os.environ["FFMPEG_BINARY"] = ENGINE_SETTINGS.providers.ffmpeg_binary_path
os.environ["FFPROBE_BINARY"] = ENGINE_SETTINGS.providers.ffprobe_binary_path
ffmpeg_dir = str(Path(ENGINE_SETTINGS.providers.ffmpeg_binary_path).parent)
if ffmpeg_dir:
    os.environ["PATH"] = f"{ffmpeg_dir};{os.environ.get('PATH', '')}"

try:
    from pydub import AudioSegment

    AudioSegment.converter = ENGINE_SETTINGS.providers.ffmpeg_binary_path
    AudioSegment.ffmpeg = ENGINE_SETTINGS.providers.ffmpeg_binary_path
    AudioSegment.ffprobe = ENGINE_SETTINGS.providers.ffprobe_binary_path
except Exception:  # noqa: BLE001
    pass

from engine.runner import PipelineRunner

logger = logging.getLogger(__name__)
runner = PipelineRunner()


def load_story(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def run_pipeline(
    story_text: str,
    story_title: str = "Default Story",
    story_author: str = "Anonymous",
    resume: bool = False,
    run_id: str | None = None,
) -> PipelineOutput:
    """Run the complete storytelling pipeline through engine runner."""
    return runner.run(
        story_text=story_text,
        story_title=story_title,
        story_author=story_author,
        resume=resume,
        run_id=run_id,
    )


def play_story(pipeline_output: PipelineOutput) -> None:
    """Play generated story with the UI module."""
    logger.info("=" * 70)
    logger.info("LAUNCHING STORY PLAYER")
    logger.info("=" * 70)

    player = StoryPlayer(pipeline_output)
    controller = PlaybackController(player)
    player.display_story_info()
    player.play()

    for idx, scene in enumerate(player.story.scenes):
        player.goto_scene(idx)
        location = resolve_scene_location(scene, player.story.visual_bible)
        characters = resolve_scene_characters(scene, player.story.visual_bible)
        logger.info("[SCENE %s] %s", idx + 1, scene.title)
        logger.info(
            "Setting=%s Location=%s Mood=%s",
            display_value(location["bgm_setting"]),
            display_value(location["location_name"]),
            scene_mood_value(scene.mood),
        )
        logger.info("Characters=%s", ", ".join([item["name"] for item in characters]))
        logger.info("Narration=%s", scene.narration_text[:120])
        assets = player.get_scene_assets(scene.scene_id)
        if assets and assets.image_path:
            logger.info("Image=%s", assets.image_path)
        if assets and assets.narration_path:
            logger.info("Narration Audio=%s", assets.narration_path)
        if assets and assets.bgm_path:
            logger.info("BGM=%s", assets.bgm_path)

    playback_info = controller.get_playback_info()
    logger.info("PLAYBACK COMPLETE: %s", playback_info)


def main() -> None:
    """Main executable entrypoint."""
    logger.info("AI Storytelling Engine started at %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    logger.info("Project root: %s", PROJECT_ROOT)

    if not CONFIG_SAMPLE_STORY:
        logger.info("Sample story disabled in configuration.")
        return

    output = run_pipeline(
        story_text=load_story(SAMPLE_STORY_PATH),
        story_title="The Quest for the Lost Artifact",
        story_author="AI Storyteller",
    )
    play_story(output)
    logger.info("Manifest: %s", output.manifest_path)
    logger.info("Application finished at %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


if __name__ == "__main__":
    main()
