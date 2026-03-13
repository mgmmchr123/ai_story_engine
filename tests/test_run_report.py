"""Tests for run-level reporting."""

import tempfile
import unittest
from pathlib import Path

from config import ENGINE_SETTINGS
from engine.context import PipelineContext, RunPaths
from engine.reporting.run_report import build_run_report
from models.scene_schema import SceneAssets, SceneRenderResult, StoryContent


def _build_context(root: Path) -> PipelineContext:
    return PipelineContext(
        run_id="run_report",
        story_input="story",
        story_title="Fallback Title",
        story_author="Fallback Author",
        config=ENGINE_SETTINGS,
        paths=RunPaths(
            run_dir=root,
            scenes_dir=root / "scenes",
            images_dir=root / "images",
            audio_dir=root / "audio",
            bgm_dir=root / "bgm",
            mixed_dir=root / "mixed",
            final_dir=root / "final",
            final_story_path=root / "final" / "story.mp3",
            manifest_path=root / "manifest.json",
        ),
    )


class RunReportTests(unittest.TestCase):
    def test_build_run_report_returns_expected_populated_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            context = _build_context(Path(tmp))
            context.story = StoryContent(title="Story Title", author="Story Author", description="desc")
            context.story_json = {"title": "Story Title", "scenes": []}
            context.scene_instructions = [{"scene_id": 1}, {"scene_id": 2}]
            context.scene_results = {
                2: SceneRenderResult(scene_id=2, status="failed", assets=SceneAssets(), warnings=["missing"]),
                1: SceneRenderResult(
                    scene_id=1,
                    status="completed",
                    assets=SceneAssets(image_path="img.png", narration_path="audio.wav"),
                ),
            }
            context.metadata["scene_instruction_paths"] = ["scenes/scene_001.json", "scenes/scene_002.json"]
            context.metadata["rerun"] = {"is_rerun": True, "scene_ids": [1], "bootstrap": False}

            report = build_run_report(context)

            self.assertEqual(
                report,
                {
                    "run_id": "run_report",
                    "story_title": "Story Title",
                    "story_author": "Story Author",
                    "has_story_json": True,
                    "has_story": True,
                    "scene_instruction_count": 2,
                    "scene_instruction_paths": ["scenes/scene_001.json", "scenes/scene_002.json"],
                    "scene_summary": {
                        "total_scenes": 2,
                        "completed": 1,
                        "failed": 1,
                        "skipped": 0,
                        "scene_ids": [1, 2],
                        "scenes": [
                            {
                                "scene_id": 1,
                                "status": "completed",
                                "skipped": False,
                                "warning_count": 0,
                                "has_image": True,
                                "has_narration": True,
                                "has_bgm": False,
                                "scene_instruction_path": None,
                            },
                            {
                                "scene_id": 2,
                                "status": "failed",
                                "skipped": False,
                                "warning_count": 1,
                                "has_image": False,
                                "has_narration": False,
                                "has_bgm": False,
                                "scene_instruction_path": None,
                            },
                        ],
                        "rerun": {"is_rerun": True, "scene_ids": [1], "bootstrap": False},
                    },
                },
            )

    def test_build_run_report_returns_zero_for_empty_scene_instructions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            context = _build_context(Path(tmp))

            report = build_run_report(context)

            self.assertEqual(report["scene_instruction_count"], 0)

    def test_build_run_report_handles_missing_story_and_story_json_safely(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            context = _build_context(Path(tmp))

            report = build_run_report(context)

            self.assertEqual(report["story_title"], "Fallback Title")
            self.assertEqual(report["story_author"], "Fallback Author")
            self.assertFalse(report["has_story"])
            self.assertFalse(report["has_story_json"])

    def test_build_run_report_includes_scene_summary_with_expected_counts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            context = _build_context(Path(tmp))
            context.scene_results = {
                3: SceneRenderResult(scene_id=3, status="failed", assets=SceneAssets()),
                1: SceneRenderResult(scene_id=1, status="completed", assets=SceneAssets()),
                2: SceneRenderResult(scene_id=2, status="completed", skipped=True, assets=SceneAssets()),
            }

            report = build_run_report(context)

            self.assertEqual(report["scene_summary"]["total_scenes"], 3)
            self.assertEqual(report["scene_summary"]["completed"], 2)
            self.assertEqual(report["scene_summary"]["failed"], 1)
            self.assertEqual(report["scene_summary"]["skipped"], 1)
            self.assertEqual(report["scene_summary"]["scene_ids"], [1, 2, 3])

    def test_build_run_report_includes_scene_instruction_paths_only_for_list_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            context = _build_context(Path(tmp))
            context.metadata["scene_instruction_paths"] = "scenes/scene_001.json"

            report = build_run_report(context)

            self.assertNotIn("scene_instruction_paths", report)

            context.metadata["scene_instruction_paths"] = ["scenes/scene_001.json"]

            report = build_run_report(context)

            self.assertEqual(report["scene_instruction_paths"], ["scenes/scene_001.json"])

    def test_build_run_report_populates_core_fields_deterministically(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            context = _build_context(Path(tmp))
            context.story_json = {"title": "Fallback Title", "scenes": []}

            report = build_run_report(context)

            self.assertEqual(
                list(report.keys()),
                [
                    "run_id",
                    "story_title",
                    "story_author",
                    "has_story_json",
                    "has_story",
                    "scene_instruction_count",
                    "scene_summary",
                ],
            )


if __name__ == "__main__":
    unittest.main()
