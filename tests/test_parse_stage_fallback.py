"""Tests for parse-stage fallback behavior."""

import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from config import ENGINE_SETTINGS, ParserSettings
from engine.context import PipelineContext, RunPaths
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
    @patch("providers.story_parser_provider.urllib_request.urlopen")
    def test_parse_stage_falls_back_to_placeholder_on_invalid_ollama_output(self, mock_urlopen) -> None:
        mock_urlopen.return_value = _InvalidJSONResponse()
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

    def test_parse_stage_falls_back_on_primary_timeout(self) -> None:
        class _TimeoutParser:
            def parse(self, story_text: str, title: str, author: str):  # noqa: ANN001
                raise TimeoutError("primary parser timed out")

        stage = StoryParseStage(parser_provider=_TimeoutParser())  # type: ignore[arg-type]

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
