"""Pipeline stage that converts story.json scenes into render instructions."""

from engine.context import PipelineContext
from engine.logging_utils import get_stage_logger
from engine.stage import PipelineStage
from engine.scene_builder.scene_builder import build_scenes


class SceneBuilderStage(PipelineStage):
    """Build scene-level generation instructions from canonical story schema."""

    @property
    def name(self) -> str:
        return "scene_builder"

    def should_skip(self, context: PipelineContext) -> bool:
        return bool(context.scene_instructions)

    def run(self, context: PipelineContext) -> None:
        logger = get_stage_logger(__name__, context.run_id, self.name)
        if not context.story_json:
            raise ValueError("story.json must be available before scene_builder stage.")

        context.scene_instructions = build_scenes(context.story_json)
        context.metadata["scene_instruction_count"] = len(context.scene_instructions)
        logger.info("Built %s scene instructions", len(context.scene_instructions))
