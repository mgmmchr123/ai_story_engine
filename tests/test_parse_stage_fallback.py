"""Tests for parse-stage fallback behavior."""

import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from config import ENGINE_SETTINGS, ParserSettings
from engine.context import PipelineContext, RunPaths
from engine.parser.extractors import DeterministicStoryExtractor, GPTStoryExtractor, OllamaStoryExtractor
from pipeline.parse_stage import StoryParseStage
from providers.story_parser_provider import OllamaStoryParserProvider


class _InvalidJSONResponse:
    def read(self) -> bytes:
        return b'{"message":{"content":"not valid json"}}'

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class ParseStageFallbackTests(unittest.TestCase):
    def test_parse_stage_defaults_to_deterministic_extractor(self) -> None:
        stage = StoryParseStage(parser_provider=OllamaStoryParserProvider(ParserSettings()))

        self.assertIsInstance(stage.canonical_parser.extractor, DeterministicStoryExtractor)

    def test_parse_stage_accepts_explicit_deterministic_extractor_kind(self) -> None:
        stage = StoryParseStage(
            parser_provider=OllamaStoryParserProvider(ParserSettings()),
            extractor_kind="deterministic",
        )

        self.assertIsInstance(stage.canonical_parser.extractor, DeterministicStoryExtractor)

    def test_parse_stage_wires_ollama_extractor(self) -> None:
        stage = StoryParseStage(
            parser_provider=OllamaStoryParserProvider(ParserSettings()),
            extractor_kind="ollama",
        )

        self.assertIsInstance(stage.canonical_parser.extractor, OllamaStoryExtractor)

    def test_parse_stage_wires_gpt_extractor(self) -> None:
        stage = StoryParseStage(
            parser_provider=OllamaStoryParserProvider(ParserSettings()),
            extractor_kind="gpt",
        )

        self.assertIsInstance(stage.canonical_parser.extractor, GPTStoryExtractor)

    def test_parse_stage_raises_on_invalid_extractor_kind(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unsupported story extractor: invalid"):
            StoryParseStage(
                parser_provider=OllamaStoryParserProvider(ParserSettings()),
                extractor_kind="invalid",
            )

    def test_parse_stage_primary_path_sets_canonical_and_preserves_generated_title_when_input_title_empty(self) -> None:
        stage = StoryParseStage(parser_provider=OllamaStoryParserProvider(ParserSettings()))

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            context = PipelineContext(
                run_id="run_parse_primary",
                story_input="Lanterns sway above the tavern door.",
                story_title="",
                story_author="Tester",
                config=ENGINE_SETTINGS,
                paths=RunPaths(
                    run_dir=root,
                    images_dir=root / "images",
                    audio_dir=root / "audio",
                    bgm_dir=root / "bgm",
                    mixed_dir=root / "mixed",
                    final_dir=root / "final",
                    final_story_path=root / "final" / "story.mp3",
                    manifest_path=root / "manifest.json",
                ),
            )

            stage.run(context)

        self.assertIsNotNone(context.story_json)
        self.assertIsNotNone(context.story)
        assert context.story_json is not None
        assert context.story is not None
        self.assertEqual(context.metadata.get("story_schema_version"), "1.0")
        self.assertEqual(context.story_json["title"], "Lanterns sway above the tavern door.")
        self.assertEqual(context.story.title, "Lanterns sway above the tavern door.")

    @patch("pipeline.parse_stage.StoryParser.parse")
    def test_parse_stage_falls_back_to_placeholder_when_canonical_parse_fails(self, mock_parse) -> None:
        mock_parse.side_effect = ValueError("canonical parser failed")
        parser_provider = OllamaStoryParserProvider(ParserSettings())
        stage = StoryParseStage(parser_provider=parser_provider)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            context = PipelineContext(
                run_id="run_parse_fallback",
                story_input="Line one.\nLine two.",
                story_title="Fallback Story",
                story_author="Tester",
                config=ENGINE_SETTINGS,
                paths=RunPaths(
                    run_dir=root,
                    images_dir=root / "images",
                    audio_dir=root / "audio",
                    bgm_dir=root / "bgm",
                    mixed_dir=root / "mixed",
                    final_dir=root / "final",
                    final_story_path=root / "final" / "story.mp3",
                    manifest_path=root / "manifest.json",
                ),
            )

            stage.run(context)

        self.assertIsNotNone(context.story)
        assert context.story is not None
        self.assertEqual(len(context.story.scenes), 2)
        self.assertEqual(context.story.scenes[0].title, "Scene 1")
        self.assertTrue(context.warnings)
        self.assertEqual(context.metadata.get("parser_quality"), "degraded")
        self.assertTrue(context.metadata.get("parser_degradation_reasons"))
        summary = context.metadata.get("scene_state_summary", [])
        self.assertTrue(summary)
        self.assertIn("location_name", summary[0])
        self.assertIn("active_character_names", summary[0])

    @patch("pipeline.parse_stage.StoryParser.parse")
    def test_parse_stage_falls_back_on_canonical_timeout(self, mock_parse) -> None:
        mock_parse.side_effect = TimeoutError("primary parser timed out")
        stage = StoryParseStage(parser_provider=OllamaStoryParserProvider(ParserSettings()))

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            context = PipelineContext(
                run_id="run_parse_timeout",
                story_input="Line one.\nLine two.",
                story_title="Timeout Story",
                story_author="Tester",
                config=ENGINE_SETTINGS,
                paths=RunPaths(
                    run_dir=root,
                    images_dir=root / "images",
                    audio_dir=root / "audio",
                    bgm_dir=root / "bgm",
                    mixed_dir=root / "mixed",
                    final_dir=root / "final",
                    final_story_path=root / "final" / "story.mp3",
                    manifest_path=root / "manifest.json",
                ),
            )

            stage.run(context)

        self.assertIsNotNone(context.story)
        assert context.story is not None
        self.assertEqual(len(context.story.scenes), 2)
        self.assertEqual(context.metadata.get("parser_quality"), "degraded")
        self.assertTrue(any("primary_parser_failed" in warning for warning in context.warnings))


if __name__ == "__main__":
    unittest.main()
