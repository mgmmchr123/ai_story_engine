"""Helpers for preparing scene-level reruns."""

from __future__ import annotations

from engine.context import PipelineContext


def prepare_single_scene_rerun(context: PipelineContext, scene_id: int) -> PipelineContext:
    """Prepare a context to rerun a single scene."""

    return prepare_scene_rerun(context, {scene_id})


def prepare_scene_rerun(context: PipelineContext, scene_ids: set[int]) -> PipelineContext:
    """Prepare a context to rerun only the selected scenes."""

    normalized_scene_ids = _normalize_scene_ids(scene_ids)
    context.selected_scene_ids = normalized_scene_ids

    for scene_id in normalized_scene_ids:
        context.scene_results.pop(scene_id, None)

    return context


def _normalize_scene_ids(scene_ids: set[int]) -> set[int]:
    if not isinstance(scene_ids, set):
        raise ValueError("scene_ids must be a set of positive integers")

    normalized: set[int] = set()
    for scene_id in scene_ids:
        if isinstance(scene_id, bool) or not isinstance(scene_id, int) or scene_id <= 0:
            raise ValueError("scene_ids must contain only positive integers")
        normalized.add(scene_id)

    if not normalized:
        raise ValueError("scene_ids must not be empty")

    return normalized
