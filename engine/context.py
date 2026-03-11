"""Run-scoped pipeline context."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from config import EngineSettings
from models.scene_schema import SceneRenderResult, StoryContent


def utc_now_iso() -> str:
    """Return a stable UTC timestamp string."""
    return datetime.now(UTC).isoformat()


@dataclass(slots=True)
class RunPaths:
    """Filesystem paths for a run."""

    run_dir: Path
    images_dir: Path
    audio_dir: Path
    bgm_dir: Path
    mixed_dir: Path
    final_dir: Path
    final_story_path: Path
    manifest_path: Path


@dataclass(slots=True)
class StageExecutionState:
    """Execution metadata for a stage."""

    status: str = "pending"
    attempts: int = 0
    started_at: str = ""
    completed_at: str = ""
    duration_seconds: float = 0.0
    error: str | None = None


@dataclass(slots=True)
class PipelineContext:
    """Mutable execution context shared across stages."""

    run_id: str
    story_input: str
    story_title: str
    story_author: str
    config: EngineSettings
    paths: RunPaths
    resume: bool = False
    story: StoryContent | None = None
    scene_results: dict[int, SceneRenderResult] = field(default_factory=dict)
    stage_state: dict[str, StageExecutionState] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    started_at: str = field(default_factory=utc_now_iso)
    completed_at: str = ""
    status: str = "pending"

    def record_warning(self, message: str) -> None:
        self.warnings.append(message)

    def record_error(self, message: str) -> None:
        self.errors.append(message)
