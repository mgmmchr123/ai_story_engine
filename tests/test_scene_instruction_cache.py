"""Tests for scene instruction cache persistence."""

import tempfile
import unittest
from pathlib import Path

from config import ENGINE_SETTINGS
from engine.cache.scene_instruction_cache import (
    load_scene_instruction,
    save_scene_instruction,
    save_scene_instructions,
)
from engine.cache.scene_instruction_index import (
    build_scene_instruction_path_index,
    resolve_scene_instruction_path,
    scene_instruction_filename,
    scene_instruction_path_for_scene,
)
from engine.context import PipelineContext, RunPaths
from pipeline.scene_builder_stage import SceneBuilderStage


def _example_instruction(scene_id: int = 1) -> dict:
    return {
        "scene_id": scene_id,
        "image_prompt": "ancient tavern interior at night, anime style",
        "characters": ["zhangsan"],
        "location": "ancient_tavern",
        "camera": {"shot": "medium shot", "angle": "eye level"},
        "duration_sec": 5,
        "dialogue": [{"speaker": "zhangsan", "text": "We are too late.", "emotion": "tense"}],
        "actions": [
            {
                "character": "zhangsan",
                "type": "enter",
                "emotion": "tense",
                "description": "Zhangsan pushes open the tavern door.",
            }
        ],
    }


class SceneInstructionCacheTests(unittest.TestCase):
    def test_scene_instruction_filename_uses_zero_padded_format(self) -> None:
        self.assertEqual(scene_instruction_filename(1), "scene_001.json")

    def test_scene_instruction_path_for_scene_returns_expected_path(self) -> None:
        path = scene_instruction_path_for_scene(7, Path("output/scenes"))

        self.assertTrue(str(path).endswith("scene_007.json"))

    def test_build_scene_instruction_path_index_parses_valid_scene_paths(self) -> None:
        index = build_scene_instruction_path_index(
            [
                "C:/runs/example/scenes/scene_001.json",
                "C:/runs/example/scenes/scene_002.json",
            ]
        )

        self.assertEqual(index[1], "C:/runs/example/scenes/scene_001.json")
        self.assertEqual(index[2], "C:/runs/example/scenes/scene_002.json")

    def test_build_scene_instruction_path_index_ignores_malformed_entries(self) -> None:
        index = build_scene_instruction_path_index(
            [
                "",
                "C:/runs/example/scenes/not_a_scene.json",
                "C:/runs/example/scenes/scene_xyz.json",
                "C:/runs/example/scenes/scene_003.json",
            ]
        )

        self.assertEqual(index, {3: "C:/runs/example/scenes/scene_003.json"})

    def test_resolve_scene_instruction_path_prefers_metadata_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            scenes_dir = Path(tmp)
            metadata_path = scenes_dir / "scene_001.json"
            metadata_path.write_text("{}", encoding="utf-8")
            alternate = scenes_dir / "scene_001.json"

            resolved = resolve_scene_instruction_path(1, alternate.parent, metadata_paths=[str(metadata_path)])

            self.assertEqual(resolved, metadata_path)

    def test_resolve_scene_instruction_path_falls_back_to_deterministic_scene_dir_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            scenes_dir = Path(tmp)
            expected = scenes_dir / "scene_004.json"
            expected.write_text("{}", encoding="utf-8")

            resolved = resolve_scene_instruction_path(4, scenes_dir, metadata_paths=None)

            self.assertEqual(resolved, expected)

    def test_resolve_scene_instruction_path_returns_none_when_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            scenes_dir = Path(tmp)

            resolved = resolve_scene_instruction_path(9, scenes_dir, metadata_paths=None)

            self.assertIsNone(resolved)

    def test_save_scene_instruction_uses_zero_padded_file_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            path = save_scene_instruction(_example_instruction(1), output_dir)

            self.assertEqual(path.name, "scene_001.json")
            self.assertTrue(path.exists())

    def test_saved_scene_instruction_can_be_loaded_back(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            save_scene_instruction(_example_instruction(2), output_dir)

            loaded = load_scene_instruction(output_dir / "scene_002.json")

            self.assertEqual(loaded["scene_id"], 2)
            self.assertEqual(loaded["location"], "ancient_tavern")
            self.assertEqual(loaded["camera"]["shot"], "medium shot")

    def test_save_scene_instructions_writes_deterministic_zero_padded_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            paths = save_scene_instructions([_example_instruction(2), _example_instruction(10)], output_dir)

            self.assertEqual([path.name for path in paths], ["scene_002.json", "scene_010.json"])

    def test_scene_builder_stage_persists_scene_instruction_artifacts_and_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            context = PipelineContext(
                run_id="run_scene_cache",
                story_input="line",
                story_title="Story",
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
            context.story_json = {
                "story_id": "story",
                "title": "Story",
                "style": "anime",
                "characters": [{"id": "zhangsan", "name": "Zhangsan", "appearance": "", "voice": "steady"}],
                "locations": [{"id": "ancient_tavern", "description": "tavern", "time_of_day": "night"}],
                "scenes": [
                    {
                        "scene_id": 1,
                        "location": "ancient_tavern",
                        "duration_sec": 5,
                        "characters": ["zhangsan"],
                        "camera": {"shot": "medium shot", "angle": "eye level"},
                        "actions": [
                            {
                                "character": "zhangsan",
                                "type": "enter",
                                "emotion": "tense",
                                "description": "Zhangsan pushes open the tavern door.",
                            }
                        ],
                        "dialogue": [],
                    }
                ],
            }

            stage = SceneBuilderStage()
            stage.run(context)

            self.assertEqual(context.metadata["scene_instruction_count"], 1)
            self.assertEqual(len(context.metadata["scene_instruction_paths"]), 1)
            saved_path = Path(context.metadata["scene_instruction_paths"][0])
            self.assertEqual(saved_path.name, "scene_001.json")
            self.assertTrue(saved_path.exists())
            self.assertEqual(load_scene_instruction(saved_path)["scene_id"], 1)


if __name__ == "__main__":
    unittest.main()
