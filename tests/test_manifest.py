"""Unit tests for manifest persistence."""

import tempfile
import unittest
from pathlib import Path

from config import ENGINE_SETTINGS
from engine.context import PipelineContext, RunPaths, StageExecutionState
from engine.manifest import build_manifest, load_manifest, save_manifest


class ManifestTests(unittest.TestCase):
    def test_manifest_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = RunPaths(
                run_dir=root,
                scenes_dir=root / "scenes",
                images_dir=root / "images",
                audio_dir=root / "audio",
                bgm_dir=root / "bgm",
                mixed_dir=root / "mixed",
                final_dir=root / "final",
                final_story_path=root / "final" / "story.mp3",
                manifest_path=root / "manifest.json",
            )
            context = PipelineContext(
                run_id="run_123",
                story_input="line one",
                story_title="Title",
                story_author="Author",
                config=ENGINE_SETTINGS,
                paths=paths,
            )
            context.status = "completed"
            context.completed_at = context.started_at
            context.metadata["scene_state_summary"] = [
                {
                    "scene_id": 1,
                    "title": "Scene 1",
                    "location_id": "forest_001",
                    "location_name": "Forest",
                    "active_character_ids": ["hero_001"],
                    "active_character_names": ["Aria"],
                }
            ]
            context.stage_state["parse_story"] = StageExecutionState(
                status="completed",
                attempts=1,
                started_at=context.started_at,
                completed_at=context.completed_at,
                duration_seconds=0.01,
            )

            manifest = build_manifest(context)
            save_manifest(manifest, paths.manifest_path)
            loaded = load_manifest(paths.manifest_path)

            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual(loaded.run_id, "run_123")
            self.assertEqual(loaded.status, "completed")
            self.assertIn("parse_story", loaded.stage_status)
            self.assertIn("scene_state_summary", loaded.metadata)
            self.assertEqual(loaded.metadata["scene_state_summary"][0]["location_name"], "Forest")


if __name__ == "__main__":
    unittest.main()
