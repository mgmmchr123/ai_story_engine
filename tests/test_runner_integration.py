"""Integration-style test for end-to-end pipeline runner."""

import shutil
import unittest
from pathlib import Path

from app import run_pipeline
from config import ENGINE_SETTINGS


class RunnerIntegrationTests(unittest.TestCase):
    def test_runner_generates_manifest_and_scene_artifacts(self) -> None:
        output = run_pipeline(
            story_text="A hero enters the forest.\nA storm rises over the castle.",
            story_title="Integration Story",
            story_author="Test Runner",
        )

        self.assertIn(output.status, {"completed", "completed_with_warnings"})
        self.assertEqual(len(output.story.scenes), 2)
        self.assertEqual(len(output.scene_results), 2)

        for result in output.scene_results:
            if result.status == "completed":
                self.assertTrue(result.assets.image_path)
                self.assertTrue(result.assets.narration_path)
                assert result.assets.narration_path is not None
                self.assertTrue(result.assets.narration_path.endswith(".wav"))
                self.assertTrue(result.assets.mixed_audio_path)

        self.assertTrue(output.manifest_path)

        import json

        manifest = json.loads(Path(output.manifest_path).read_text(encoding="utf-8"))
        self.assertIn("final_story_audio_path", manifest.get("metadata", {}))

        # Cleanup generated run folder to keep test idempotent.
        run_dir = ENGINE_SETTINGS.output.base_output_dir / output.run_id
        shutil.rmtree(run_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
