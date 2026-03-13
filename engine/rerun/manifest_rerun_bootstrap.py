"""Manifest-aware bootstrap helpers for scene-level reruns."""

from __future__ import annotations

from pathlib import Path

from engine.context import PipelineContext
from engine.manifest import load_manifest
from engine.rerun.scene_rerun_bootstrap import bootstrap_scene_rerun_context


def _scene_instruction_paths_from_manifest(manifest: object) -> list[str] | None:
    metadata = getattr(manifest, "metadata", None)
    if isinstance(metadata, dict):
        scene_instruction_paths = metadata.get("scene_instruction_paths")
        if isinstance(scene_instruction_paths, list):
            return list(scene_instruction_paths)

    run_report = getattr(manifest, "run_report", None)
    if isinstance(run_report, dict):
        scene_instruction_paths = run_report.get("scene_instruction_paths")
        if isinstance(scene_instruction_paths, list):
            return list(scene_instruction_paths)

    return None


def bootstrap_rerun_context_from_manifest(manifest_path: Path, context: PipelineContext) -> PipelineContext:
    """Seed rerun metadata from a manifest, then load scene instructions from disk."""

    try:
        manifest = load_manifest(manifest_path)
    except Exception as exc:  # pragma: no cover - defensive wrapper around manifest parsing
        raise ValueError(f"Invalid manifest at {manifest_path}") from exc

    if manifest is None:
        raise ValueError(f"Manifest not found at {manifest_path}")

    scene_instruction_paths = _scene_instruction_paths_from_manifest(manifest)
    if scene_instruction_paths is not None:
        context.metadata["scene_instruction_paths"] = scene_instruction_paths

    return bootstrap_scene_rerun_context(context)


def bootstrap_rerun_context_from_run_dir(context: PipelineContext) -> PipelineContext:
    """Bootstrap rerun context using the manifest path already attached to the run context."""

    return bootstrap_rerun_context_from_manifest(context.paths.manifest_path, context)
