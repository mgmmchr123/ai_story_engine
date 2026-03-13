"""Extractor interface for canonical story.json generation."""

from abc import ABC, abstractmethod


class BaseStoryExtractor(ABC):
    """Convert raw story text into canonical partial/full story.json."""

    @abstractmethod
    def extract(self, text: str) -> dict:
        """Extract canonical story data from raw text."""
