"""Tests for scene rerun bootstrap helpers."""

import tempfile
import unittest
from pathlib import Path

from config import ENGINE_SETTINGS
from engine.cache.scene_instruction_cache import save_scene_instruction
from engine.context import PipelineContext, RunPaths
from engine.rerun.scene_rerun_bootstrap import (
    bootstrap_scene_rerun_context,
    load_scene_instructions_from_dir,
)
from models.scene_schema import StoryContent


def _build_context(root: Path) -> PipelineContext:
    context = PipelineContext(
        run_id="run_rerun_bootstrap",
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
    return context


def _instruction(scene_id: int) -> dict:
    return {
        "scene_id": scene_id,
        "image_prompt": f"prompt {scene_id}",
        "characters": ["zhangsan"],
        "location": "ancient_tavern",
        "camera": {"shot": "medium shot", "angle": "eye level"},
        "duration_sec": 5,
        "dialogue": [],
        "actions": [],
    }


class SceneRerunBootstrapTests(unittest.TestCase):
    def test_load_scene_instructions_from_dir_reads_stable_zero_padded_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            scenes_dir = Path(tmp)
            save_scene_instruction(_instruction(2), scenes_dir)
            save_scene_instruction(_instruction(1), scenes_dir)

            items = load_scene_instructions_from_dir(scenes_dir)

            self.assertEqual([item["scene_id"] for item in items], [1, 2])

    def test_load_scene_instructions_from_dir_fails_on_invalid_scene_instruction(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            scenes_dir = Path(tmp)
            save_scene_instruction(_instruction(1), scenes_dir)
            (scenes_dir / "scene_002.json").write_text('{"scene_id": 2, "image_prompt": ""}', encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "empty image_prompt"):
                load_scene_instructions_from_dir(scenes_dir)

    def test_bootstrap_scene_rerun_context_populates_scene_instructions_and_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            context = _build_context(root)
            save_scene_instruction(_instruction(2), context.paths.scenes_dir)
            save_scene_instruction(_instruction(1), context.paths.scenes_dir)

            bootstrapped = bootstrap_scene_rerun_context(context)

            self.assertIs(bootstrapped, context)
            self.assertEqual([item["scene_id"] for item in context.scene_instructions], [1, 2])
            self.assertEqual(
                [Path(path).name for path in context.metadata["scene_instruction_paths"]],
                ["scene_001.json", "scene_002.json"],
            )

    def test_bootstrap_scene_rerun_context_preserves_story_and_story_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            context = _build_context(root)
            original_story = context.story
            original_story_json = context.story_json
            save_scene_instruction(_instruction(1), context.paths.scenes_dir)

            bootstrap_scene_rerun_context(context)

            self.assertIs(context.story, original_story)
            self.assertIs(context.story_json, original_story_json)

    def test_bootstrap_scene_rerun_context_allows_empty_scenes_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            context = _build_context(root)

            bootstrap_scene_rerun_context(context)

            self.assertEqual(context.scene_instructions, [])
            self.assertEqual(context.metadata["scene_instruction_paths"], [])


if __name__ == "__main__":
    unittest.main()
