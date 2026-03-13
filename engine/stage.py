"""Stage contract abstractions."""

from abc import ABC, abstractmethod

from .context import PipelineContext


class PipelineStage(ABC):
    """Pipeline stage interface."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique stage name."""

    def should_skip(self, context: PipelineContext) -> bool:
        """Allow a stage to skip based on context."""
        return False

    def timeout_seconds(self, context: PipelineContext) -> int | None:
        """Allow stages to override the runner-level timeout."""
        _ = context
        return None

    @abstractmethod
    def run(self, context: PipelineContext) -> None:
        """Execute stage and update context."""
