"""Custom exceptions for pipeline execution."""


class PipelineError(Exception):
    """Base class for pipeline-related errors."""


class StageExecutionError(PipelineError):
    """Raised when a stage fails."""


class StageTimeoutError(StageExecutionError):
    """Raised when a stage exceeds timeout."""


class ProviderError(PipelineError):
    """Raised when a provider fails to generate an artifact."""
