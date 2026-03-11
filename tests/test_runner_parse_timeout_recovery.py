"""Tests for parser-timeout recovery semantics in runner."""

import shutil
import unittest

from config import ENGINE_SETTINGS
from engine.errors import StageTimeoutError
from engine.runner import ManifestPersistStage, PipelineRunner
from pipeline.parse_stage import StoryParseStage
from providers.story_parser_provider import PlaceholderStoryParserProvider


class RunnerParseTimeoutRecoveryTests(unittest.TestCase):
    def test_runner_marks_parse_stage_completed_with_warnings_on_timeout_recovery(self) -> None:
        parse_stage = StoryParseStage(parser_provider=PlaceholderStoryParserProvider())
        runner = PipelineRunner(stages=[parse_stage, ManifestPersistStage()])

        original_run_with_timeout = runner._run_with_timeout

        def _run_with_timeout_override(stage, context):  # noqa: ANN001
            if stage.name == "parse_story":
                raise StageTimeoutError("Stage 'parse_story' timed out after 1 seconds")
            return original_run_with_timeout(stage, context)

        runner._run_with_timeout = _run_with_timeout_override  # type: ignore[assignment]

        run_id = "run_parse_timeout_recovery"
        run_dir = ENGINE_SETTINGS.output.base_output_dir / run_id
        output = runner.run(
            story_text="Line one.\nLine two.",
            story_title="Recovery Story",
            story_author="Tester",
            run_id=run_id,
        )

        self.assertIn(output.status, {"completed", "completed_with_warnings"})
        self.assertTrue(output.warnings)

        manifest_path = run_dir / ENGINE_SETTINGS.output.manifest_filename
        self.assertTrue(manifest_path.exists())

        import json

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        parse_stage_status = manifest["stage_status"]["parse_story"]["status"]
        self.assertEqual(parse_stage_status, "completed_with_warnings")
        self.assertEqual(manifest.get("metadata", {}).get("parser_quality"), "degraded")

        shutil.rmtree(run_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
