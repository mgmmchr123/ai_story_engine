"""Unit tests for manifest persistence."""

import tempfile
import unittest
from pathlib import Path

from config import ENGINE_SETTINGS
from engine.context import PipelineContext, RunPaths, StageExecutionState
from engine.reporting.run_report import build_run_report
from engine.manifest import build_manifest, load_manifest, save_manifest
from models.scene_schema import SceneAssets, SceneRenderResult


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
            context.scene_instructions = [{"scene_id": 1}]
            context.metadata["scene_instruction_paths"] = ["scenes/scene_001.json"]
            context.scene_results = {
                1: SceneRenderResult(
                    scene_id=1,
                    status="completed",
                    assets=SceneAssets(image_path="image.png"),
                )
            }

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
            self.assertEqual(loaded.run_report, build_run_report(context))

    def test_build_manifest_includes_run_report_matching_context_snapshot(self) -> None:
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
                run_id="run_report_manifest",
                story_input="line one",
                story_title="Title",
                story_author="Author",
                config=ENGINE_SETTINGS,
                paths=paths,
            )
            context.scene_results = {
                2: SceneRenderResult(scene_id=2, status="failed", assets=SceneAssets()),
                1: SceneRenderResult(scene_id=1, status="completed", skipped=True, assets=SceneAssets()),
            }

            manifest = build_manifest(context)

            self.assertEqual(manifest.run_report, build_run_report(context))
            self.assertEqual(manifest.run_report["scene_summary"]["scene_ids"], [1, 2])
            self.assertEqual(manifest.run_report["scene_summary"]["skipped"], 1)

    def test_build_manifest_preserves_legacy_fields_while_adding_run_report(self) -> None:
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
                run_id="legacy_fields",
                story_input="line one",
                story_title="Title",
                story_author="Author",
                config=ENGINE_SETTINGS,
                paths=paths,
            )
            context.status = "completed"
            context.completed_at = context.started_at
            context.warnings.append("warning")
            context.errors.append("error")
            context.metadata["key"] = "value"

            manifest = build_manifest(context)

            self.assertEqual(manifest.run_id, "legacy_fields")
            self.assertEqual(manifest.status, "completed")
            self.assertEqual(manifest.story_title, "Title")
            self.assertEqual(manifest.story_author, "Author")
            self.assertEqual(manifest.scene_count, 0)
            self.assertEqual(manifest.warnings, ["warning"])
            self.assertEqual(manifest.errors, ["error"])
            self.assertEqual(manifest.metadata, {"key": "value"})
            self.assertEqual(manifest.run_report["run_id"], "legacy_fields")

    def test_build_manifest_with_minimal_context_includes_valid_run_report(self) -> None:
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
                run_id="minimal",
                story_input="",
                story_title="Untitled",
                story_author="Anonymous",
                config=ENGINE_SETTINGS,
                paths=paths,
            )

            manifest = build_manifest(context)

            self.assertEqual(manifest.run_id, "minimal")
            self.assertEqual(
                manifest.run_report,
                {
                    "run_id": "minimal",
                    "story_title": "Untitled",
                    "story_author": "Anonymous",
                    "has_story_json": False,
                    "has_story": False,
                    "scene_instruction_count": 0,
                    "scene_summary": {
                        "total_scenes": 0,
                        "completed": 0,
                        "failed": 0,
                        "skipped": 0,
                        "scene_ids": [],
                        "scenes": [],
                    },
                },
            )


if __name__ == "__main__":
    unittest.main()
