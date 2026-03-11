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

    @abstractmethod
    def run(self, context: PipelineContext) -> None:
        """Execute stage and update context."""
