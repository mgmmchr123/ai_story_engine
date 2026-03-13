"""Stub Ollama-backed story extractor."""

from __future__ import annotations

from typing import Any

from .base_extractor import BaseStoryExtractor


class OllamaStoryExtractor(BaseStoryExtractor):
    """Placeholder extractor for future Ollama integration."""

    def __init__(self, model: str = "llama3"):
        self.model = model

    def extract(self, text: str) -> dict[str, Any]:
        _ = text
        raise NotImplementedError("OllamaStoryExtractor is not implemented yet")
