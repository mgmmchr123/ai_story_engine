"""Thin CLI for rerunning scenes from an existing run directory."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from config import ENGINE_SETTINGS
from engine.context import PipelineContext, RunPaths
from engine.manifest import build_manifest, load_manifest, save_manifest
from engine.parser.story_adapter import story_json_to_story_content
from engine.reporting.run_report import build_run_report
from engine.rerun import (
    bootstrap_rerun_context_from_run_dir,
    rerun_selected_scenes,
    resolve_rerun_scene_selection,
)
from pipeline.render_stage import SceneRenderStage
from providers.bgm_provider import build_bgm_provider
from providers.image_provider import build_image_provider
from providers.tts_provider import build_tts_provider


def _positive_scene_id(value: str) -> int:
    try:
        scene_id = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("scene ids must be integers") from exc
    if scene_id <= 0:
        raise argparse.ArgumentTypeError("scene ids must be positive integers")
    return scene_id


def _parse_scene_ids(value: str) -> set[int]:
    parts = [item.strip() for item in value.split(",")]
    if not parts or any(not item for item in parts):
        raise argparse.ArgumentTypeError("scene-ids must be a comma-separated list of positive integers")
    return { _positive_scene_id(item) for item in parts }


def build_scene_rerun_parser() -> argparse.ArgumentParser:
    """Build the scene rerun CLI parser."""

    parser = argparse.ArgumentParser(description="Rerun selected scenes from an existing run directory.")
    parser.add_argument("--run-dir", required=True, type=Path, help="Path to an existing run directory.")
    scene_group = parser.add_mutually_exclusive_group(required=True)
    scene_group.add_argument("--scene-id", type=_positive_scene_id, help="Rerun a single scene.")
    scene_group.add_argument(
        "--scene-ids",
        type=_parse_scene_ids,
        help="Comma-separated list of scene ids to rerun.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Show rerun plan without executing rendering.")
    return parser


def parse_scene_rerun_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments and normalize scene ids to a set[int]."""

    args = build_scene_rerun_parser().parse_args(argv)
    args.scene_ids = {args.scene_id} if args.scene_id is not None else set(args.scene_ids)
    return args


def _build_run_paths(run_dir: Path) -> RunPaths:
    output = ENGINE_SETTINGS.output
    return RunPaths(
        run_dir=run_dir,
        scenes_dir=run_dir / output.scenes_dirname,
        images_dir=run_dir / output.images_dirname,
        audio_dir=run_dir / output.audio_dirname,
        bgm_dir=run_dir / output.bgm_dirname,
        mixed_dir=run_dir / output.mixed_dirname,
        final_dir=run_dir / output.final_dirname,
        final_story_path=run_dir / output.final_dirname / output.final_story_filename,
        manifest_path=run_dir / output.manifest_filename,
    )


def _restore_story_from_manifest(context: PipelineContext, manifest: object) -> None:
    metadata = getattr(manifest, "metadata", None)
    story_json = metadata.get("story_json") if isinstance(metadata, dict) else None
    if isinstance(story_json, dict):
        context.story_json = dict(story_json)
        context.story = story_json_to_story_content(context.story_json, author=context.story_author)


def build_rerun_plan(context: PipelineContext, scene_ids: set[int]) -> dict:
    """Build a compact dry-run plan for a scene rerun request."""

    plan = {
        "mode": "dry-run",
        "run_id": context.run_id,
        "has_story": context.story is not None,
        "has_story_json": context.story_json is not None,
        "scene_instruction_count": len(context.scene_instructions),
    }
    plan.update(resolve_rerun_scene_selection(context, scene_ids))
    return plan


def _build_rerun_context(run_dir: Path) -> PipelineContext:
    paths = _build_run_paths(run_dir)
    manifest = load_manifest(paths.manifest_path)
    if manifest is None:
        raise ValueError(f"Manifest not found at {paths.manifest_path}")

    context = PipelineContext(
        run_id=run_dir.name,
        story_input="",
        story_title=manifest.story_title,
        story_author=manifest.story_author,
        config=ENGINE_SETTINGS,
        paths=paths,
    )
    _restore_story_from_manifest(context, manifest)
    bootstrap_rerun_context_from_run_dir(context)
    return context


def run_scene_rerun_cli(argv: list[str] | None = None) -> None:
    """Bootstrap an existing run and rerun the selected scenes."""

    args = parse_scene_rerun_args(argv)
    run_dir = args.run_dir.resolve()
    context = _build_rerun_context(run_dir)

    if args.dry_run:
        print(json.dumps(build_rerun_plan(context, args.scene_ids), indent=2))
        return

    selection = resolve_rerun_scene_selection(context, args.scene_ids)
    context.metadata["rerun_selection"] = selection
    valid_scene_ids = set(selection["will_rerun_scene_ids"])
    if not valid_scene_ids:
        raise ValueError("No requested scene ids are available for rerun")

    if context.story is None:
        raise ValueError("Manifest does not contain restorable story state for rerun CLI")

    render_stage = SceneRenderStage(
        image_provider=build_image_provider(context.config.providers),
        tts_provider=build_tts_provider(context.config.providers),
        bgm_provider=build_bgm_provider(context.config.providers),
    )
    rerun_selected_scenes(context, valid_scene_ids, render_stage, bootstrap=False)
    save_manifest(build_manifest(context), context.paths.manifest_path)

    print(json.dumps(build_run_report(context), indent=2))
