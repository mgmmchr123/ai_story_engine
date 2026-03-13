"""Tests for runner wiring of parser extractor configuration."""

from dataclasses import replace
import unittest
from unittest.mock import patch

from config import ENGINE_SETTINGS, ParserSettings
import engine.runner as runner_module
from engine.runner import PipelineRunner
from engine.parser.extractors import DeterministicStoryExtractor, GPTStoryExtractor, OllamaStoryExtractor
from pipeline.parse_stage import StoryParseStage


class RunnerParserExtractorConfigTests(unittest.TestCase):
    def test_runner_defaults_to_ollama_extractor(self) -> None:
        config = replace(ENGINE_SETTINGS, parser=ParserSettings())

        with patch.object(runner_module, "ENGINE_SETTINGS", config):
            runner = PipelineRunner()

        parse_stage = runner._stages[0]
        self.assertIsInstance(parse_stage, StoryParseStage)
        self.assertIsInstance(parse_stage.canonical_parser.extractor, OllamaStoryExtractor)

    def test_runner_uses_configured_ollama_extractor(self) -> None:
        config = replace(
            ENGINE_SETTINGS,
            parser=ParserSettings(
                extractor_kind="ollama",
                ollama_model="llama3.1:8b",
                ollama_url="http://localhost:11434",
            ),
        )

        with patch.object(runner_module, "ENGINE_SETTINGS", config):
            runner = PipelineRunner()

        parse_stage = runner._stages[0]
        self.assertIsInstance(parse_stage.canonical_parser.extractor, OllamaStoryExtractor)
        self.assertEqual(parse_stage.canonical_parser.extractor.model, "llama3.1:8b")
        self.assertEqual(parse_stage.canonical_parser.extractor.url, "http://localhost:11434")

    def test_runner_uses_configured_gpt_extractor(self) -> None:
        config = replace(
            ENGINE_SETTINGS,
            parser=ParserSettings(extractor_kind="gpt"),
        )

        with patch.object(runner_module, "ENGINE_SETTINGS", config):
            runner = PipelineRunner()

        parse_stage = runner._stages[0]
        self.assertIsInstance(parse_stage.canonical_parser.extractor, GPTStoryExtractor)

    def test_runner_fails_fast_on_invalid_extractor_kind(self) -> None:
        config = replace(
            ENGINE_SETTINGS,
            parser=ParserSettings(extractor_kind="invalid"),
        )

        with patch.object(runner_module, "ENGINE_SETTINGS", config):
            with self.assertRaisesRegex(ValueError, "Unsupported story extractor: invalid"):
                PipelineRunner()


if __name__ == "__main__":
    unittest.main()
