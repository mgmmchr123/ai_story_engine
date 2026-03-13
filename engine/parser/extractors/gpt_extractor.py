"""Stub GPT-backed story extractor."""

from __future__ import annotations

from typing import Any

from .base_extractor import BaseStoryExtractor


class GPTStoryExtractor(BaseStoryExtractor):
    """Placeholder extractor for future GPT integration."""

    def __init__(self, model: str = "gpt-4.1-mini"):
        self.model = model

    def extract(self, text: str) -> dict[str, Any]:
        _ = text
        raise NotImplementedError("GPTStoryExtractor is not implemented yet")
