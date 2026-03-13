"""Parse stage implementation."""

from time import perf_counter

from engine.parser.extractor_factory import build_story_extractor
from engine.parser.extractors import OllamaStoryExtractor
from engine.parser.story_adapter import story_content_to_story_json, story_json_to_story_content
from engine.parser.story_parser import StoryParser
from engine.parser.story_validator import validate_story_json
from engine.world_state import resolve_scene_characters, resolve_scene_location
from engine.context import PipelineContext
from engine.logging_utils import compact_json, get_stage_logger
from engine.stage import PipelineStage
from providers.story_parser_provider import PlaceholderStoryParserProvider, StoryParserProvider


class StoryParseStage(PipelineStage):
    """Parses raw story text into structured scene domain objects."""

    def __init__(
        self,
        parser_provider: StoryParserProvider,
        extractor_kind: str = "ollama",
        extractor_kwargs: dict | None = None,
    ):
        # Retained for constructor compatibility and future provider-based fallback expansion.
        self.parser_provider = parser_provider
        extractor = build_story_extractor(
            extractor_kind,
            **self._resolve_extractor_kwargs(extractor_kind, extractor_kwargs or {}),
        )
        self.canonical_parser = StoryParser(extractor=extractor)
        self.fallback_provider = PlaceholderStoryParserProvider()

    @property
    def name(self) -> str:
        return "parse_story"

    def should_skip(self, context: PipelineContext) -> bool:
        return context.story_json is not None

    def run(self, context: PipelineContext) -> None:
        logger = get_stage_logger(__name__, context.run_id, self.name)
        try:
            story_json = self._parse_canonical(context, logger)
            context.story_json = story_json
            context.story = story_json_to_story_content(story_json, author=context.story_author)
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

    def _parse_canonical(self, context: PipelineContext, logger) -> dict:  # noqa: ANN001
        started = perf_counter()
        extractor = self.canonical_parser.extractor
        if isinstance(extractor, OllamaStoryExtractor):
            logger.info(
                "parse_story invoking Ollama model=%s input_chars=%s",
                extractor.model,
                len(context.story_input),
            )
        story_json = self.canonical_parser.parse(context.story_input)
        self._log_story_snapshot(logger, "extractor_output", story_json)
        story_json["title"] = context.story_title or story_json.get("title", "Untitled Story")
        validated = validate_story_json(story_json)
        self._log_story_snapshot(logger, "validated_story_json", validated)
        if isinstance(extractor, OllamaStoryExtractor):
            logger.info(
                "parse_story Ollama completed model=%s input_chars=%s scene_count=%s character_count=%s elapsed=%.2fs",
                extractor.model,
                len(context.story_input),
                len(validated.get("scenes", [])),
                len(validated.get("characters", [])),
                perf_counter() - started,
            )
        return validated

    def _resolve_extractor_kwargs(self, extractor_kind: str, extractor_kwargs: dict) -> dict:
        if extractor_kind != "ollama":
            return dict(extractor_kwargs)

        resolved = {
            "model": getattr(getattr(self.parser_provider, "settings", None), "ollama_model", "qwen2.5:7b"),
            "url": getattr(getattr(self.parser_provider, "settings", None), "ollama_url", "http://127.0.0.1:11434"),
            "timeout_seconds": getattr(
                getattr(self.parser_provider, "settings", None),
                "ollama_timeout_seconds",
                90,
            ),
            "temperature": getattr(
                getattr(self.parser_provider, "settings", None),
                "ollama_temperature",
                0.0,
            ),
        }
        resolved.update(extractor_kwargs)
        return resolved

    def _apply_fallback(self, context: PipelineContext, reason: str, logger) -> None:  # noqa: ANN001
        logger.warning("Primary parser degraded; entering placeholder parser fallback: %s", reason)
        context.record_warning(f"Parser degraded; fallback used: {reason}")
        context.metadata["parser_quality"] = "degraded"
        context.metadata.setdefault("parser_degradation_reasons", []).append(reason)
        fallback_story = self.fallback_provider.parse(
            story_text=context.story_input,
            title=context.story_title,
            author=context.story_author,
        )
        context.story_json = validate_story_json(story_content_to_story_json(fallback_story))
        context.story_json["title"] = context.story_title or context.story_json.get("title", "Untitled Story")
        self._log_story_snapshot(logger, "fallback_story_json", context.story_json)
        context.story = story_json_to_story_content(context.story_json, author=context.story_author)
        self._update_story_metadata(context)

    def _update_story_metadata(self, context: PipelineContext) -> None:
        if context.story_json:
            context.metadata["story_json"] = context.story_json
            context.metadata["story_schema_version"] = "1.0"
        if context.story is not None and context.story.visual_bible:
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

    def _log_story_snapshot(self, logger, label: str, story_json: dict) -> None:  # noqa: ANN001
        if not isinstance(story_json, dict):
            logger.info("parse_story snapshot=%s non_dict=%s", label, type(story_json).__name__)
            return
        scenes = story_json.get("scenes") if isinstance(story_json.get("scenes"), list) else []
        characters = story_json.get("characters") if isinstance(story_json.get("characters"), list) else []
        logger.info(
            "parse_story snapshot=%s keys=%s title=%s style=%s character_count=%s scene_count=%s",
            label,
            sorted(story_json.keys()),
            story_json.get("title"),
            story_json.get("style"),
            len(characters),
            len(scenes),
        )
        if scenes:
            logger.info(
                "parse_story snapshot=%s first_scene=%s",
                label,
                compact_json(scenes[0], max_len=2000),
            )
