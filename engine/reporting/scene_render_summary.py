"""Helpers for summarizing scene render outcomes."""

from __future__ import annotations

from engine.context import PipelineContext
from models.scene_schema import SceneRenderResult


def summarize_scene_result(scene_result: SceneRenderResult) -> dict:
    """Summarize a single scene render result into a compact structure."""

    return {
        "scene_id": scene_result.scene_id,
        "status": scene_result.status,
        "skipped": scene_result.skipped,
        "warning_count": len(scene_result.warnings),
        "has_image": bool(scene_result.assets.image_path),
        "has_narration": bool(scene_result.assets.narration_path),
        "has_bgm": bool(scene_result.assets.bgm_path),
        "scene_instruction_path": scene_result.scene_instruction_path,
    }


def summarize_scene_results(context: PipelineContext) -> dict:
    """Summarize all scene render results in a pipeline context."""

    ordered_results = sorted(context.scene_results.values(), key=lambda item: item.scene_id)
    scenes = [summarize_scene_result(scene_result) for scene_result in ordered_results]

    summary = {
        "total_scenes": len(scenes),
        "completed": sum(1 for item in scenes if item["status"] == "completed"),
        "failed": sum(1 for item in scenes if item["status"] == "failed"),
        "skipped": sum(1 for item in scenes if item["status"] == "skipped"),
        "scene_ids": [item["scene_id"] for item in scenes],
        "scenes": scenes,
    }

    rerun_metadata = context.metadata.get("rerun")
    if isinstance(rerun_metadata, dict):
        summary["rerun"] = dict(rerun_metadata)

    return summary
