"""Parse stage implementation."""

from engine.parser.story_adapter import story_content_to_story_json, story_json_to_story_content
from engine.parser.story_validator import validate_story_json
from engine.world_state import resolve_scene_characters, resolve_scene_location
from engine.context import PipelineContext
from engine.logging_utils import get_stage_logger
from engine.stage import PipelineStage
from providers.story_parser_provider import PlaceholderStoryParserProvider, StoryParserProvider


class StoryParseStage(PipelineStage):
    """Parses raw story text into structured scene domain objects."""

    def __init__(self, parser_provider: StoryParserProvider):
        self.parser_provider = parser_provider
        self.fallback_provider = PlaceholderStoryParserProvider()

    @property
    def name(self) -> str:
        return "parse_story"

    def should_skip(self, context: PipelineContext) -> bool:
        return context.story_json is not None or context.story is not None

    def run(self, context: PipelineContext) -> None:
        logger = get_stage_logger(__name__, context.run_id, self.name)
        try:
            parsed_story = self.parser_provider.parse(
                story_text=context.story_input,
                title=context.story_title,
                author=context.story_author,
            )
            context.story_json = validate_story_json(story_content_to_story_json(parsed_story))
            context.story_json["title"] = context.story_title
            context.story = story_json_to_story_content(context.story_json, author=context.story_author)
            self._update_story_metadata(context)
        except Exception as exc:  # noqa: BLE001
            self._apply_fallback(
                context=context,
                reason=f"primary_parser_failed: {exc}",
                logger=logger,
            )

    def recover_from_timeout(self, context: PipelineContext, reason: str) -> bool:
        logger = get_stage_logger(__name__, context.run_id, self.name)
        self._apply_fallback(
            context=context,
            reason=f"primary_parser_timeout: {reason}",
            logger=logger,
        )
        return True

    def _apply_fallback(self, context: PipelineContext, reason: str, logger) -> None:  # noqa: ANN001
        logger.warning("Primary parser degraded; falling back to placeholder parser: %s", reason)
        context.record_warning(f"Parser degraded; fallback used: {reason}")
        context.metadata["parser_quality"] = "degraded"
        context.metadata.setdefault("parser_degradation_reasons", []).append(reason)
        fallback_story = self.fallback_provider.parse(
            story_text=context.story_input,
            title=context.story_title,
            author=context.story_author,
        )
        context.story_json = validate_story_json(story_content_to_story_json(fallback_story))
        context.story_json["title"] = context.story_title
        context.story = story_json_to_story_content(context.story_json, author=context.story_author)
        self._update_story_metadata(context)

    def _update_story_metadata(self, context: PipelineContext) -> None:
        if context.story_json:
            context.metadata["story_json"] = context.story_json
            context.metadata["story_schema_version"] = "1.0"
        if context.story.visual_bible:
            context.metadata["visual_bible_summary"] = {
                "character_count": len(context.story.visual_bible.characters),
                "location_count": len(context.story.visual_bible.locations),
                "style": context.story.visual_bible.style.art_style,
            }
        context.metadata["scene_state_summary"] = [
            {
                "scene_id": scene.scene_id,
                "title": scene.title,
                "location_id": scene_location["location_id"],
                "location_name": scene_location["location_name"],
                "active_character_ids": [item["character_id"] for item in resolved_characters],
                "active_character_names": [item["name"] for item in resolved_characters],
            }
            for scene in context.story.scenes
            for scene_location in [resolve_scene_location(scene, context.story.visual_bible)]
            for resolved_characters in [resolve_scene_characters(scene, context.story.visual_bible)]
        ]
