"""Bootstrap helpers for scene-level reruns from persisted artifacts."""

from __future__ import annotations

from pathlib import Path

from engine.cache.scene_instruction_cache import load_scene_instruction
from engine.scene_builder.scene_instruction_validator import validate_scene_instructions
from engine.context import PipelineContext


def load_scene_instructions_from_dir(scenes_dir: Path) -> list[dict]:
    """Load and validate scene instruction artifacts from a scenes directory."""

    scene_paths = sorted(scenes_dir.glob("scene_*.json"))
    loaded = [load_scene_instruction(path) for path in scene_paths]
    return validate_scene_instructions(loaded) if loaded else []


def bootstrap_scene_rerun_context(context: PipelineContext) -> PipelineContext:
    """Populate rerun-relevant scene instruction state from persisted artifacts."""

    scene_paths = sorted(context.paths.scenes_dir.glob("scene_*.json"))
    context.scene_instructions = load_scene_instructions_from_dir(context.paths.scenes_dir)
    context.metadata["scene_instruction_paths"] = [str(path) for path in scene_paths]
    return context
