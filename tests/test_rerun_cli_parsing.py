"""Tests for rerun CLI argument parsing."""

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from config import ENGINE_SETTINGS
from engine.cache.scene_instruction_cache import save_scene_instruction
from engine.cli.rerun_cli import build_rerun_plan, parse_scene_rerun_args, run_scene_rerun_cli
from engine.context import PipelineContext, RunPaths
from engine.manifest import StoryRunManifest, load_manifest, save_manifest
from engine.rerun.scene_selection import resolve_rerun_scene_selection
from models.scene_schema import SceneAssets, SceneRenderResult, StoryContent


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


def _manifest_with_story(root: Path) -> StoryRunManifest:
    return StoryRunManifest(
        run_id=root.name,
        status="completed",
        story_title="Title",
        story_author="Author",
        scene_count=1,
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
                "scenes": [
                    {
                        "scene_id": 1,
                        "title": "Scene 1",
                        "location": "ancient_tavern",
                        "camera": {"shot": "medium shot", "angle": "eye level"},
                    }
                ],
            }
        },
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

    def test_selection_helper_returns_full_hit_structure(self) -> None:
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
            context.scene_instructions = [_instruction(1), _instruction(2), _instruction(3)]

            selection = resolve_rerun_scene_selection(context, {1, 3})

            self.assertEqual(
                selection,
                {
                    "requested_scene_ids": [1, 3],
                    "available_scene_instruction_ids": [1, 2, 3],
                    "missing_scene_ids": [],
                    "will_rerun_scene_ids": [1, 3],
                },
            )

    def test_selection_helper_returns_partial_miss_structure(self) -> None:
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
            context.scene_instructions = [_instruction(1), _instruction(2), _instruction(3)]

            selection = resolve_rerun_scene_selection(context, {1, 4})

            self.assertEqual(
                selection,
                {
                    "requested_scene_ids": [1, 4],
                    "available_scene_instruction_ids": [1, 2, 3],
                    "missing_scene_ids": [4],
                    "will_rerun_scene_ids": [1],
                },
            )

    def test_selection_helper_returns_full_miss_structure(self) -> None:
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
            context.scene_instructions = [_instruction(1), _instruction(2), _instruction(3)]

            selection = resolve_rerun_scene_selection(context, {4, 5})

            self.assertEqual(
                selection,
                {
                    "requested_scene_ids": [4, 5],
                    "available_scene_instruction_ids": [1, 2, 3],
                    "missing_scene_ids": [4, 5],
                    "will_rerun_scene_ids": [],
                },
            )

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
            manifest = _manifest_with_story(root)
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

    def test_dry_run_uses_shared_selection_logic(self) -> None:
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
            context.scene_instructions = [_instruction(1), _instruction(2), _instruction(3)]

            plan = build_rerun_plan(context, {1, 4})
            selection = resolve_rerun_scene_selection(context, {1, 4})

            self.assertEqual(plan["requested_scene_ids"], selection["requested_scene_ids"])
            self.assertEqual(plan["available_scene_instruction_ids"], selection["available_scene_instruction_ids"])
            self.assertEqual(plan["missing_scene_ids"], selection["missing_scene_ids"])
            self.assertEqual(plan["will_rerun_scene_ids"], selection["will_rerun_scene_ids"])

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

    def test_normal_rerun_writes_updated_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            save_scene_instruction(_instruction(1), root / "scenes")
            save_manifest(_manifest_with_story(root), root / "manifest.json")

            def _fake_rerun(context: PipelineContext, scene_ids: set[int], render_stage: object, *, bootstrap: bool) -> PipelineContext:
                context.scene_results[1] = SceneRenderResult(
                    scene_id=1,
                    status="completed",
                    assets=SceneAssets(image_path="images/scene_001.png", narration_path="audio/scene_001.wav"),
                )
                context.metadata["rerun"] = {"is_rerun": True, "scene_ids": sorted(scene_ids), "bootstrap": bootstrap}
                return context

            stdout = io.StringIO()
            with (
                patch("engine.cli.rerun_cli.build_image_provider", return_value=object()),
                patch("engine.cli.rerun_cli.build_tts_provider", return_value=object()),
                patch("engine.cli.rerun_cli.build_bgm_provider", return_value=object()),
                patch("engine.cli.rerun_cli.SceneRenderStage", return_value=object()),
                patch("engine.cli.rerun_cli.rerun_selected_scenes", side_effect=_fake_rerun),
                redirect_stdout(stdout),
            ):
                run_scene_rerun_cli(["--run-dir", str(root), "--scene-id", "1"])

            written = load_manifest(root / "manifest.json")
            assert written is not None
            self.assertEqual(written.run_report["run_id"], root.name)
            self.assertEqual(written.run_report["scene_summary"]["completed"], 1)
            self.assertEqual(written.run_report["scene_summary"]["scene_ids"], [1])
            output = json.loads(stdout.getvalue())
            self.assertEqual(output["scene_summary"]["completed"], 1)
            self.assertEqual(output["scene_summary"]["scene_ids"], [1])

    def test_real_execution_reruns_only_valid_scene_ids_for_mixed_request(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            save_scene_instruction(_instruction(1), root / "scenes")
            save_scene_instruction(_instruction(2), root / "scenes")
            save_manifest(_manifest_with_story(root), root / "manifest.json")

            def _fake_rerun(context: PipelineContext, scene_ids: set[int], render_stage: object, *, bootstrap: bool) -> PipelineContext:
                self.assertEqual(scene_ids, {1})
                context.scene_results[1] = SceneRenderResult(scene_id=1, status="completed", assets=SceneAssets())
                context.metadata["rerun"] = {"is_rerun": True, "scene_ids": sorted(scene_ids), "bootstrap": bootstrap}
                return context

            with (
                patch("engine.cli.rerun_cli.build_image_provider", return_value=object()),
                patch("engine.cli.rerun_cli.build_tts_provider", return_value=object()),
                patch("engine.cli.rerun_cli.build_bgm_provider", return_value=object()),
                patch("engine.cli.rerun_cli.SceneRenderStage", return_value=object()),
                patch("engine.cli.rerun_cli.rerun_selected_scenes", side_effect=_fake_rerun),
            ):
                run_scene_rerun_cli(["--run-dir", str(root), "--scene-ids", "1,4"])

    def test_real_execution_raises_when_all_requested_ids_are_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            save_scene_instruction(_instruction(1), root / "scenes")
            save_manifest(_manifest_with_story(root), root / "manifest.json")

            with self.assertRaisesRegex(ValueError, "No requested scene ids are available for rerun"):
                run_scene_rerun_cli(["--run-dir", str(root), "--scene-id", "4"])

    def test_dry_run_does_not_rewrite_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            save_scene_instruction(_instruction(1), root / "scenes")
            save_manifest(_manifest_with_story(root), root / "manifest.json")
            before = (root / "manifest.json").read_text(encoding="utf-8")

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                run_scene_rerun_cli(["--run-dir", str(root), "--scene-id", "1", "--dry-run"])

            after = (root / "manifest.json").read_text(encoding="utf-8")
            self.assertEqual(after, before)

    def test_manifest_is_unchanged_when_story_restore_fails_before_rerun(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            save_scene_instruction(_instruction(1), root / "scenes")
            save_manifest(_manifest_with_story(root), root / "manifest.json")
            before = (root / "manifest.json").read_text(encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "Manifest does not contain restorable story state"):
                with patch("engine.cli.rerun_cli._restore_story_from_manifest", autospec=True) as restore_story:
                    restore_story.side_effect = lambda context, manifest: None
                    run_scene_rerun_cli(["--run-dir", str(root), "--scene-id", "1"])

            after = (root / "manifest.json").read_text(encoding="utf-8")
            self.assertEqual(after, before)


if __name__ == "__main__":
    unittest.main()
