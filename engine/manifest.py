"""Manifest model and persistence helpers."""

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from engine.context import PipelineContext
from engine.reporting.run_report import build_run_report
from models.scene_schema import PipelineOutput, SceneAssets, SceneRenderResult, StoryContent


@dataclass(slots=True)
class StageManifestEntry:
    """Persisted execution details for a single stage."""

    status: str
    attempts: int
    started_at: str
    completed_at: str
    duration_seconds: float
    error: str | None = None


@dataclass(slots=True)
class StoryRunManifest:
    """Persisted run metadata."""

    run_id: str
    status: str
    story_title: str
    story_author: str
    scene_count: int
    started_at: str
    completed_at: str
    total_duration_seconds: float
    stage_status: dict[str, StageManifestEntry] = field(default_factory=dict)
    scene_results: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    run_report: dict[str, Any] = field(default_factory=dict)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def build_manifest(context: PipelineContext) -> StoryRunManifest:
    """Build a manifest snapshot from pipeline context."""

    story = context.story or StoryContent(
        title=context.story_title,
        author=context.story_author,
        description="",
        scenes=[],
    )

    stage_status = {
        stage_name: StageManifestEntry(
            status=state.status,
            attempts=state.attempts,
            started_at=state.started_at,
            completed_at=state.completed_at,
            duration_seconds=state.duration_seconds,
            error=state.error,
        )
        for stage_name, state in context.stage_state.items()
    }

    total_duration = _resolve_total_duration_seconds(context)

    return StoryRunManifest(
        run_id=context.run_id,
        status=context.status,
        story_title=story.title,
        story_author=story.author,
        scene_count=len(story.scenes),
        started_at=context.started_at,
        completed_at=context.completed_at or _utc_now(),
        total_duration_seconds=total_duration,
        stage_status=stage_status,
        scene_results=[asdict(result) for result in context.scene_results.values()],
        warnings=list(context.warnings),
        errors=list(context.errors),
        metadata=dict(context.metadata),
        run_report=build_run_report(context),
    )


def save_manifest(manifest: StoryRunManifest, path: Path) -> None:
    """Persist manifest JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(asdict(manifest), file, indent=2)


def load_manifest(path: Path) -> StoryRunManifest | None:
    """Load existing manifest."""
    if not path.exists():
        return None

    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    stage_status = {
        name: StageManifestEntry(**entry) for name, entry in data.get("stage_status", {}).items()
    }
    return StoryRunManifest(
        run_id=data["run_id"],
        status=data.get("status", "pending"),
        story_title=data.get("story_title", ""),
        story_author=data.get("story_author", ""),
        scene_count=data.get("scene_count", 0),
        started_at=data.get("started_at", ""),
        completed_at=data.get("completed_at", ""),
        total_duration_seconds=data.get("total_duration_seconds", 0.0),
        stage_status=stage_status,
        scene_results=data.get("scene_results", []),
        warnings=data.get("warnings", []),
        errors=data.get("errors", []),
        metadata=data.get("metadata", {}),
        run_report=data.get("run_report", {}),
    )


def pipeline_output_from_context(context: PipelineContext) -> PipelineOutput:
    """Convert context to app-facing output model."""

    story = context.story or StoryContent(
        title=context.story_title,
        author=context.story_author,
        description="",
        scenes=[],
    )

    scene_results = sorted(context.scene_results.values(), key=lambda item: item.scene_id)
    total_duration = _resolve_total_duration_seconds(context)

    return PipelineOutput(
        run_id=context.run_id,
        story=story,
        scene_results=scene_results,
        status=context.status,
        total_duration_seconds=total_duration,
        manifest_path=str(context.paths.manifest_path),
        warnings=list(context.warnings),
        errors=list(context.errors),
    )


def scene_result_from_manifest(data: dict[str, Any]) -> SceneRenderResult:
    """Hydrate scene result from manifest dictionary."""

    assets_data = data.get("assets", {})
    assets = SceneAssets(
        image_path=assets_data.get("image_path"),
        narration_path=assets_data.get("narration_path"),
        bgm_path=assets_data.get("bgm_path"),
        mixed_audio_path=assets_data.get("mixed_audio_path"),
    )
    return SceneRenderResult(
        scene_id=data["scene_id"],
        scene_instruction_path=data.get("scene_instruction_path"),
        status=data.get("status", "pending"),
        assets=assets,
        image_prompt=data.get("image_prompt", ""),
        narration_prompt=data.get("narration_prompt", ""),
        bgm_parameters=data.get("bgm_parameters", {}),
        warnings=data.get("warnings", []),
        error=data.get("error"),
        duration_seconds=data.get("duration_seconds", 0.0),
        media_duration_seconds=data.get("media_duration_seconds", 0.0),
        skipped=data.get("skipped", False),
        attempts=data.get("attempts", 0),
        started_at=data.get("started_at", ""),
        completed_at=data.get("completed_at", ""),
    )


def _resolve_total_duration_seconds(context: PipelineContext) -> float:
    total_duration = float(context.metadata.get("final_video_duration_seconds") or 0.0)
    if total_duration > 0:
        return total_duration

    scene_media_total = sum(
        result.media_duration_seconds
        for result in context.scene_results.values()
        if result.media_duration_seconds > 0
    )
    if scene_media_total > 0:
        return float(scene_media_total)

    if context.completed_at:
        start = datetime.fromisoformat(context.started_at)
        end = datetime.fromisoformat(context.completed_at)
        return (end - start).total_seconds()
    return 0.0
