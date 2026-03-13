"""Tests for scene rerun bootstrap helpers."""

import tempfile
import unittest
from pathlib import Path

from config import ENGINE_SETTINGS
from engine.cache.scene_instruction_cache import save_scene_instruction
from engine.context import PipelineContext, RunPaths
from engine.manifest import StoryRunManifest, save_manifest
from engine.rerun.manifest_rerun_bootstrap import (
    bootstrap_rerun_context_from_manifest,
    bootstrap_rerun_context_from_run_dir,
)
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

    def test_bootstrap_rerun_context_from_manifest_restores_paths_and_scene_instructions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            context = _build_context(root)
            save_scene_instruction(_instruction(2), context.paths.scenes_dir)
            save_scene_instruction(_instruction(1), context.paths.scenes_dir)
            manifest = StoryRunManifest(
                run_id=context.run_id,
                status="completed",
                story_title=context.story_title,
                story_author=context.story_author,
                scene_count=0,
                started_at=context.started_at,
                completed_at=context.started_at,
                total_duration_seconds=0.0,
                metadata={"scene_instruction_paths": ["from_manifest/scene_001.json", "from_manifest/scene_002.json"]},
            )
            save_manifest(manifest, context.paths.manifest_path)

            bootstrapped = bootstrap_rerun_context_from_manifest(context.paths.manifest_path, context)

            self.assertIs(bootstrapped, context)
            self.assertEqual([item["scene_id"] for item in context.scene_instructions], [1, 2])
            self.assertEqual(
                [Path(path).name for path in context.metadata["scene_instruction_paths"]],
                ["scene_001.json", "scene_002.json"],
            )

    def test_bootstrap_rerun_context_from_run_dir_uses_context_manifest_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            context = _build_context(root)
            save_scene_instruction(_instruction(1), context.paths.scenes_dir)
            manifest = StoryRunManifest(
                run_id=context.run_id,
                status="completed",
                story_title=context.story_title,
                story_author=context.story_author,
                scene_count=0,
                started_at=context.started_at,
                completed_at=context.started_at,
                total_duration_seconds=0.0,
                run_report={"scene_instruction_paths": ["from_run_report/scene_001.json"]},
            )
            save_manifest(manifest, context.paths.manifest_path)

            bootstrap_rerun_context_from_run_dir(context)

            self.assertEqual([item["scene_id"] for item in context.scene_instructions], [1])
            self.assertEqual([Path(path).name for path in context.metadata["scene_instruction_paths"]], ["scene_001.json"])

    def test_bootstrap_rerun_context_from_manifest_raises_for_missing_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            context = _build_context(root)

            with self.assertRaisesRegex(ValueError, "Manifest not found"):
                bootstrap_rerun_context_from_manifest(context.paths.manifest_path, context)

    def test_bootstrap_rerun_context_from_manifest_raises_for_invalid_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            context = _build_context(root)
            context.paths.manifest_path.write_text("{invalid json", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "Invalid manifest"):
                bootstrap_rerun_context_from_manifest(context.paths.manifest_path, context)

    def test_bootstrap_rerun_context_from_manifest_preserves_story_and_story_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            context = _build_context(root)
            original_story = context.story
            original_story_json = context.story_json
            save_scene_instruction(_instruction(1), context.paths.scenes_dir)
            manifest = StoryRunManifest(
                run_id=context.run_id,
                status="completed",
                story_title=context.story_title,
                story_author=context.story_author,
                scene_count=0,
                started_at=context.started_at,
                completed_at=context.started_at,
                total_duration_seconds=0.0,
                metadata={"scene_instruction_paths": ["from_manifest/scene_001.json"]},
            )
            save_manifest(manifest, context.paths.manifest_path)

            bootstrap_rerun_context_from_manifest(context.paths.manifest_path, context)

            self.assertIs(context.story, original_story)
            self.assertIs(context.story_json, original_story_json)

    def test_bootstrap_rerun_context_from_manifest_allows_empty_scenes_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            context = _build_context(root)
            manifest = StoryRunManifest(
                run_id=context.run_id,
                status="completed",
                story_title=context.story_title,
                story_author=context.story_author,
                scene_count=0,
                started_at=context.started_at,
                completed_at=context.started_at,
                total_duration_seconds=0.0,
                metadata={"scene_instruction_paths": ["from_manifest/scene_001.json"]},
            )
            save_manifest(manifest, context.paths.manifest_path)

            bootstrap_rerun_context_from_manifest(context.paths.manifest_path, context)

            self.assertEqual(context.scene_instructions, [])
            self.assertEqual(context.metadata["scene_instruction_paths"], [])


if __name__ == "__main__":
    unittest.main()
