"""Helpers for building run-level reports."""

from __future__ import annotations

from engine.context import PipelineContext
from engine.reporting.scene_render_summary import summarize_scene_results


def build_run_report(context: PipelineContext) -> dict:
    """Build a compact run-level report from pipeline context state."""

    report = {
        "run_id": context.run_id,
        "story_title": context.story.title if context.story is not None else context.story_title,
        "story_author": context.story.author if context.story is not None else context.story_author,
        "has_story_json": context.story_json is not None,
        "has_story": context.story is not None,
        "scene_instruction_count": len(context.scene_instructions),
    }

    scene_instruction_paths = context.metadata.get("scene_instruction_paths")
    if isinstance(scene_instruction_paths, list):
        report["scene_instruction_paths"] = list(scene_instruction_paths)

    report["scene_summary"] = summarize_scene_results(context)
    return report
