"""Lookup helpers for scene instruction artifacts."""

from __future__ import annotations

from pathlib import Path


def scene_instruction_filename(scene_id: int) -> str:
    """Return the canonical artifact filename for a scene instruction."""

    return f"scene_{int(scene_id):03d}.json"


def scene_instruction_path_for_scene(scene_id: int, scenes_dir: Path) -> Path:
    """Return the canonical artifact path for a scene instruction."""

    return scenes_dir / scene_instruction_filename(scene_id)


def build_scene_instruction_path_index(paths: list[str]) -> dict[int, str]:
    """Build a scene_id -> artifact path index from metadata path strings."""

    index: dict[int, str] = {}
    for path_text in paths:
        path_str = str(path_text or "").strip()
        if not path_str:
            continue
        artifact_path = Path(path_str)
        stem = artifact_path.stem
        if not stem.startswith("scene_"):
            continue
        suffix = stem.removeprefix("scene_")
        try:
            scene_id = int(suffix)
        except ValueError:
            continue
        index[scene_id] = path_str
    return index


def resolve_scene_instruction_path(
    scene_id: int,
    scenes_dir: Path,
    metadata_paths: list[str] | None = None,
) -> Path | None:
    """Resolve a scene instruction artifact path by scene id."""

    if metadata_paths:
        indexed_paths = build_scene_instruction_path_index(metadata_paths)
        path_text = indexed_paths.get(int(scene_id))
        if path_text:
            return Path(path_text)

    deterministic_path = scene_instruction_path_for_scene(scene_id, scenes_dir)
    if deterministic_path.exists():
        return deterministic_path
    return None
