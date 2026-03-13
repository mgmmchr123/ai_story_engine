"""Factory helpers for parser extractor selection."""

from __future__ import annotations

from .extractors import (
    BaseStoryExtractor,
    DeterministicStoryExtractor,
    GPTStoryExtractor,
    OllamaStoryExtractor,
)


def build_story_extractor(kind: str = "deterministic", **kwargs) -> BaseStoryExtractor:
    """Build a story extractor by kind."""

    if kind == "deterministic":
        return DeterministicStoryExtractor(**kwargs)
    if kind == "ollama":
        return OllamaStoryExtractor(**kwargs)
    if kind == "gpt":
        return GPTStoryExtractor(**kwargs)
    raise ValueError(f"Unsupported story extractor: {kind}")
