"""Tests for scene-level rerun preparation helpers."""

import tempfile
import unittest
from pathlib import Path

from config import ENGINE_SETTINGS
from engine.context import PipelineContext, RunPaths
from engine.rerun.scene_rerun import prepare_scene_rerun, prepare_single_scene_rerun
from models.scene_schema import SceneRenderResult, StoryContent


def _build_context(root: Path) -> PipelineContext:
    context = PipelineContext(
        run_id="run_rerun_test",
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
    context.story = StoryContent(title="Title", author="Author", description="desc", scenes=[])
    context.story_json = {"story_id": "story", "title": "Title", "style": "anime", "characters": [], "locations": [], "scenes": []}
    context.scene_instructions = [
        {"scene_id": 1, "image_prompt": "one", "characters": [], "location": "forest", "camera": {"shot": "medium shot", "angle": "eye level"}, "duration_sec": 5, "dialogue": [], "actions": []},
        {"scene_id": 2, "image_prompt": "two", "characters": [], "location": "forest", "camera": {"shot": "medium shot", "angle": "eye level"}, "duration_sec": 5, "dialogue": [], "actions": []},
        {"scene_id": 3, "image_prompt": "three", "characters": [], "location": "forest", "camera": {"shot": "medium shot", "angle": "eye level"}, "duration_sec": 5, "dialogue": [], "actions": []},
    ]
    context.scene_results = {
        1: SceneRenderResult(scene_id=1, status="completed"),
        2: SceneRenderResult(scene_id=2, status="failed"),
        3: SceneRenderResult(scene_id=3, status="completed"),
    }
    return context


class SceneRerunPreparationTests(unittest.TestCase):
    def test_prepare_single_scene_rerun_sets_selected_scene_ids(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            context = _build_context(Path(tmp))

            prepared = prepare_single_scene_rerun(context, 2)

            self.assertIs(prepared, context)
            self.assertEqual(prepared.selected_scene_ids, {2})

    def test_prepare_scene_rerun_sets_selected_scene_ids(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            context = _build_context(Path(tmp))

            prepared = prepare_scene_rerun(context, {1, 3})

            self.assertEqual(prepared.selected_scene_ids, {1, 3})

    def test_prepare_scene_rerun_rejects_invalid_scene_ids(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            context = _build_context(Path(tmp))

            with self.assertRaisesRegex(ValueError, "positive integers"):
                prepare_scene_rerun(context, {0})
            with self.assertRaisesRegex(ValueError, "positive integers"):
                prepare_scene_rerun(context, {-1})
            with self.assertRaisesRegex(ValueError, "positive integers"):
                prepare_scene_rerun(context, {True})  # type: ignore[arg-type]

    def test_prepare_scene_rerun_preserves_non_selected_scene_results(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            context = _build_context(Path(tmp))

            prepare_scene_rerun(context, {2})

            self.assertIn(1, context.scene_results)
            self.assertIn(3, context.scene_results)
            self.assertNotIn(2, context.scene_results)

    def test_prepare_scene_rerun_preserves_story_and_scene_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            context = _build_context(Path(tmp))
            story = context.story
            story_json = context.story_json
            scene_instructions = list(context.scene_instructions)

            prepare_scene_rerun(context, {1, 3})

            self.assertIs(context.story, story)
            self.assertIs(context.story_json, story_json)
            self.assertEqual(context.scene_instructions, scene_instructions)


if __name__ == "__main__":
    unittest.main()
