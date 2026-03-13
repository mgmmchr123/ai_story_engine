"""Tests for rerun CLI argument parsing."""

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from config import ENGINE_SETTINGS
from engine.cache.scene_instruction_cache import save_scene_instruction
from engine.cli.rerun_cli import build_rerun_plan, parse_scene_rerun_args, run_scene_rerun_cli
from engine.context import PipelineContext, RunPaths
from engine.manifest import StoryRunManifest, save_manifest
from models.scene_schema import StoryContent


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


def _run_paths(root: Path) -> RunPaths:
    return RunPaths(
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


class RerunCliParsingTests(unittest.TestCase):
    def test_scene_id_parsing(self) -> None:
        args = parse_scene_rerun_args(["--run-dir", "output/runs/run_123", "--scene-id", "7"])

        self.assertEqual(args.run_dir.parts[-3:], ("output", "runs", "run_123"))
        self.assertEqual(args.scene_id, 7)
        self.assertEqual(args.scene_ids, {7})

    def test_scene_ids_parsing(self) -> None:
        args = parse_scene_rerun_args(["--run-dir", "output/runs/run_123", "--scene-ids", "1,2,3"])

        self.assertIsNone(args.scene_id)
        self.assertEqual(args.scene_ids, {1, 2, 3})

    def test_scene_ids_parsing_deduplicates_to_int_set(self) -> None:
        args = parse_scene_rerun_args(["--run-dir", "output/runs/run_123", "--scene-ids", "3,1,3,2"])

        self.assertEqual(args.scene_ids, {1, 2, 3})

    def test_dry_run_flag_parses_correctly(self) -> None:
        args = parse_scene_rerun_args(["--run-dir", "output/runs/run_123", "--scene-id", "7", "--dry-run"])

        self.assertTrue(args.dry_run)
        self.assertEqual(args.scene_ids, {7})

    def test_invalid_combinations_require_scene_selection(self) -> None:
        with self.assertRaises(SystemExit):
            parse_scene_rerun_args(["--run-dir", "output/runs/run_123"])

    def test_invalid_combinations_reject_both_scene_flags(self) -> None:
        with self.assertRaises(SystemExit):
            parse_scene_rerun_args(
                ["--run-dir", "output/runs/run_123", "--scene-id", "1", "--scene-ids", "2,3"]
            )

    def test_invalid_scene_ids_reject_non_positive_values(self) -> None:
        with self.assertRaises(SystemExit):
            parse_scene_rerun_args(["--run-dir", "output/runs/run_123", "--scene-ids", "0,2"])

    def test_dry_run_plan_for_one_scene(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            save_scene_instruction(_instruction(1), root / "scenes")
            save_scene_instruction(_instruction(2), root / "scenes")
            manifest = StoryRunManifest(
                run_id=root.name,
                status="completed",
                story_title="Title",
                story_author="Author",
                scene_count=0,
                started_at="2026-03-13T00:00:00+00:00",
                completed_at="2026-03-13T00:00:00+00:00",
                total_duration_seconds=0.0,
                metadata={
                    "story_json": {
                        "story_id": "story",
                        "title": "Title",
                        "style": "anime",
                        "characters": [],
                        "locations": [],
                        "scenes": [],
                    }
                },
            )
            save_manifest(manifest, root / "manifest.json")

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                run_scene_rerun_cli(["--run-dir", str(root), "--scene-id", "1", "--dry-run"])

            plan = json.loads(stdout.getvalue())
            self.assertEqual(plan["mode"], "dry-run")
            self.assertEqual(plan["requested_scene_ids"], [1])
            self.assertEqual(plan["available_scene_instruction_ids"], [1, 2])
            self.assertEqual(plan["missing_scene_ids"], [])
            self.assertEqual(plan["will_rerun_scene_ids"], [1])
            self.assertTrue(plan["has_story"])
            self.assertTrue(plan["has_story_json"])
            self.assertEqual(plan["scene_instruction_count"], 2)

    def test_dry_run_plan_for_multiple_scenes_with_one_missing_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            context = PipelineContext(
                run_id=root.name,
                story_input="",
                story_title="Title",
                story_author="Author",
                config=ENGINE_SETTINGS,
                paths=_run_paths(root),
            )
            context.story = StoryContent(title="Title", author="Author", description="desc")
            context.story_json = {"story_id": "story", "title": "Title", "style": "anime", "characters": [], "locations": [], "scenes": []}
            context.scene_instructions = [_instruction(1), _instruction(2), _instruction(3)]

            plan = build_rerun_plan(context, {1, 4})

            self.assertEqual(plan["requested_scene_ids"], [1, 4])
            self.assertEqual(plan["available_scene_instruction_ids"], [1, 2, 3])
            self.assertEqual(plan["missing_scene_ids"], [4])
            self.assertEqual(plan["will_rerun_scene_ids"], [1])
            self.assertEqual(plan["scene_instruction_count"], 3)

    def test_dry_run_does_not_require_render_execution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            save_scene_instruction(_instruction(1), root / "scenes")
            manifest = StoryRunManifest(
                run_id=root.name,
                status="completed",
                story_title="Title",
                story_author="Author",
                scene_count=0,
                started_at="2026-03-13T00:00:00+00:00",
                completed_at="2026-03-13T00:00:00+00:00",
                total_duration_seconds=0.0,
            )
            save_manifest(manifest, root / "manifest.json")

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                run_scene_rerun_cli(["--run-dir", str(root), "--scene-id", "1", "--dry-run"])

            plan = json.loads(stdout.getvalue())
            self.assertFalse(plan["has_story"])
            self.assertFalse(plan["has_story_json"])
            self.assertEqual(plan["will_rerun_scene_ids"], [1])


if __name__ == "__main__":
    unittest.main()
