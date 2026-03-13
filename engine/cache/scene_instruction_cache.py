"""Persistence helpers for scene instruction artifacts."""

from __future__ import annotations

import json
from pathlib import Path


def save_scene_instruction(scene_instruction: dict, output_dir: Path) -> Path:
    """Save a single scene instruction as a readable JSON artifact."""

    scene_id = int(scene_instruction["scene_id"])
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"scene_{scene_id:03d}.json"
    path.write_text(json.dumps(scene_instruction, indent=2, ensure_ascii=True), encoding="utf-8")
    return path


def load_scene_instruction(path: Path) -> dict:
    """Load a scene instruction JSON artifact."""

    return json.loads(path.read_text(encoding="utf-8"))


def save_scene_instructions(scene_instructions: list[dict], output_dir: Path) -> list[Path]:
    """Save many scene instructions and return their artifact paths."""

    return [save_scene_instruction(scene_instruction, output_dir) for scene_instruction in scene_instructions]
