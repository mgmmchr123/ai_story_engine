"""Canonical story parser orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .extractors import BaseStoryExtractor, DeterministicStoryExtractor


@dataclass(slots=True)
class StoryParser:
    """Parser facade that delegates extraction to a pluggable extractor."""

    extractor: BaseStoryExtractor | None = None
    default_style: str = "anime"

    def __post_init__(self) -> None:
        if self.extractor is None:
            self.extractor = DeterministicStoryExtractor(default_style=self.default_style)

    def parse(self, text: str) -> dict[str, Any]:
        return self.extractor.extract(text)
