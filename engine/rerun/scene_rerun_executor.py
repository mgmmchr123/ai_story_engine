"""Executor helpers for scene-level reruns."""

from __future__ import annotations

from engine.context import PipelineContext
from engine.rerun.scene_rerun import prepare_scene_rerun, prepare_single_scene_rerun
from engine.rerun.scene_rerun_bootstrap import bootstrap_scene_rerun_context
from pipeline.render_stage import SceneRenderStage


def rerun_single_scene(
    context: PipelineContext,
    scene_id: int,
    render_stage: SceneRenderStage,
    *,
    bootstrap: bool = True,
) -> PipelineContext:
    """Bootstrap and rerun a single scene using the existing render stage."""

    return rerun_selected_scenes(context, {scene_id}, render_stage, bootstrap=bootstrap)


def rerun_selected_scenes(
    context: PipelineContext,
    scene_ids: set[int],
    render_stage: SceneRenderStage,
    *,
    bootstrap: bool = True,
) -> PipelineContext:
    """Bootstrap and rerun the selected scenes using the existing render stage."""

    if context.story is None:
        raise ValueError("context.story must be available for scene rerun")

    if bootstrap:
        bootstrap_scene_rerun_context(context)

    prepare_scene_rerun(context, scene_ids)
    render_stage.run(context)
    return context
