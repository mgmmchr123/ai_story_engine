"""Tests for scene render result summaries."""

import tempfile
import unittest
from pathlib import Path

from config import ENGINE_SETTINGS
from engine.context import PipelineContext, RunPaths
from engine.reporting.scene_render_summary import summarize_scene_result, summarize_scene_results
from models.scene_schema import SceneAssets, SceneRenderResult


def _build_context(root: Path) -> PipelineContext:
    return PipelineContext(
        run_id="run_scene_summary",
        story_input="story",
        story_title="Title",
        story_author="Author",
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


class SceneRenderSummaryTests(unittest.TestCase):
    def test_summarize_scene_result_computes_asset_flags_and_warning_count(self) -> None:
        scene_result = SceneRenderResult(
            scene_id=2,
            scene_instruction_path="output/scenes/scene_002.json",
            status="completed",
            assets=SceneAssets(
                image_path="output/images/scene_002.png",
                narration_path="output/audio/scene_002.wav",
                bgm_path=None,
            ),
            warnings=["bgm missing"],
        )

        summary = summarize_scene_result(scene_result)

        self.assertEqual(summary["scene_id"], 2)
        self.assertEqual(summary["warning_count"], 1)
        self.assertTrue(summary["has_image"])
        self.assertTrue(summary["has_narration"])
        self.assertFalse(summary["has_bgm"])
        self.assertEqual(summary["scene_instruction_path"], "output/scenes/scene_002.json")

    def test_summarize_scene_results_handles_mixed_statuses_and_sorted_scene_ids(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            context = _build_context(Path(tmp))
            context.scene_results = {
                3: SceneRenderResult(scene_id=3, status="failed", assets=SceneAssets(), warnings=["error"]),
                1: SceneRenderResult(
                    scene_id=1,
                    status="completed",
                    assets=SceneAssets(image_path="img.png", narration_path="audio.wav", bgm_path="bgm.mp3"),
                ),
                2: SceneRenderResult(scene_id=2, status="skipped", skipped=True, assets=SceneAssets()),
            }

            summary = summarize_scene_results(context)

            self.assertEqual(summary["total_scenes"], 3)
            self.assertEqual(summary["completed"], 1)
            self.assertEqual(summary["failed"], 1)
            self.assertEqual(summary["skipped"], 1)
            self.assertEqual(summary["scene_ids"], [1, 2, 3])
            self.assertEqual([item["scene_id"] for item in summary["scenes"]], [1, 2, 3])

    def test_summarize_scene_results_includes_rerun_metadata_when_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            context = _build_context(Path(tmp))
            context.scene_results = {1: SceneRenderResult(scene_id=1, status="completed")}
            context.metadata["rerun"] = {"is_rerun": True, "scene_ids": [1], "bootstrap": False}

            summary = summarize_scene_results(context)

            self.assertEqual(summary["rerun"], {"is_rerun": True, "scene_ids": [1], "bootstrap": False})

    def test_summarize_scene_results_returns_valid_empty_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            context = _build_context(Path(tmp))

            summary = summarize_scene_results(context)

            self.assertEqual(
                summary,
                {
                    "total_scenes": 0,
                    "completed": 0,
                    "failed": 0,
                    "skipped": 0,
                    "scene_ids": [],
                    "scenes": [],
                },
            )


if __name__ == "__main__":
    unittest.main()
