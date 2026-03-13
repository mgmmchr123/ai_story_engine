"""Tests for rerun CLI argument parsing."""

import unittest

from engine.cli.rerun_cli import parse_scene_rerun_args


class RerunCliParsingTests(unittest.TestCase):
    def test_scene_id_parsing(self) -> None:
        args = parse_scene_rerun_args(["--run-dir", "output/runs/run_123", "--scene-id", "7"])

        self.assertEqual(str(args.run_dir), "output\\runs\\run_123")
        self.assertEqual(args.scene_id, 7)
        self.assertEqual(args.scene_ids, {7})

    def test_scene_ids_parsing(self) -> None:
        args = parse_scene_rerun_args(["--run-dir", "output/runs/run_123", "--scene-ids", "1,2,3"])

        self.assertIsNone(args.scene_id)
        self.assertEqual(args.scene_ids, {1, 2, 3})

    def test_scene_ids_parsing_deduplicates_to_int_set(self) -> None:
        args = parse_scene_rerun_args(["--run-dir", "output/runs/run_123", "--scene-ids", "3,1,3,2"])

        self.assertEqual(args.scene_ids, {1, 2, 3})

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


if __name__ == "__main__":
    unittest.main()
