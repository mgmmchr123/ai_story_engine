"""Final story-level audio export stage."""

from pathlib import Path

from engine.context import PipelineContext
from engine.logging_utils import get_stage_logger
from engine.stage import PipelineStage
from pipeline.audio_mixer import export_story_audio


class FinalStoryAudioStage(PipelineStage):
    """Concatenate scene audio into a final story output artifact."""

    @property
    def name(self) -> str:
        return "final_story_audio"

    def run(self, context: PipelineContext) -> None:
        logger = get_stage_logger(__name__, context.run_id, self.name)
        ordered_scene_results = sorted(context.scene_results.values(), key=lambda item: item.scene_id)

        scene_audio_paths = []
        for result in ordered_scene_results:
            candidate = result.assets.mixed_audio_path or result.assets.narration_path
            if candidate:
                scene_audio_paths.append(candidate)

        resolved_paths = [Path(candidate) for candidate in scene_audio_paths]

        final_audio = export_story_audio(resolved_paths, context.paths.final_story_path)
        if final_audio:
            context.metadata["final_story_audio_path"] = str(final_audio)
            logger.info("Final story audio exported: %s", final_audio)
            return

        context.record_warning("Final story audio export skipped: no scene audio available")
        logger.warning("Final story audio export skipped")
