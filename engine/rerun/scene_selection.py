"""Helpers for resolving rerun scene selection against loaded instructions."""

from __future__ import annotations

from engine.context import PipelineContext


def resolve_rerun_scene_selection(context: PipelineContext, requested_scene_ids: set[int]) -> dict:
    """Resolve requested rerun ids against scene instructions already loaded in context."""

    requested_ids = sorted(requested_scene_ids)
    available_ids = sorted({
        int(item["scene_id"])
        for item in context.scene_instructions
        if isinstance(item, dict) and isinstance(item.get("scene_id"), int)
    })
    available_id_set = set(available_ids)

    return {
        "requested_scene_ids": requested_ids,
        "available_scene_instruction_ids": available_ids,
        "missing_scene_ids": [scene_id for scene_id in requested_ids if scene_id not in available_id_set],
        "will_rerun_scene_ids": [scene_id for scene_id in requested_ids if scene_id in available_id_set],
    }
