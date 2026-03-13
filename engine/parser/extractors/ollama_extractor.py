"""Ollama-backed canonical story extractor."""

from __future__ import annotations

import json
import logging
from time import perf_counter
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request

from .base_extractor import BaseStoryExtractor

logger = logging.getLogger(__name__)

OLLAMA_STORY_JSON_PROMPT_TEMPLATE = """Convert the story text below into one canonical story_json object.

Output requirements:
- Return exactly one JSON object.
- Do not use markdown fences.
- Do not add prose before or after the JSON.
- Top-level fields must be: story_id, title, style, characters, locations, scenes.
- characters, locations, and scenes must be arrays even when empty.
- scene_id and duration_sec must be integers.
- style should be one of anime, cartoon, or realistic when possible.

Story text:
{story_text}
"""


class OllamaStoryExtractor(BaseStoryExtractor):
    """Minimal Ollama-backed extractor that returns canonical story.json payloads."""

    def __init__(
        self,
        model: str = "llama3.1:8b",
        url: str = "http://127.0.0.1:11434",
        timeout_seconds: int = 90,
        temperature: float = 0.0,
    ):
        self.model = model
        self.url = url
        self.timeout_seconds = timeout_seconds
        self.temperature = temperature

    def extract(self, text: str) -> dict[str, Any]:
        started = perf_counter()
        endpoint = f"{self.url.rstrip('/')}/api/generate"
        payload = {
            "model": self.model,
            "stream": False,
            "format": "json",
            "prompt": _build_user_prompt(text),
            "options": {"temperature": self.temperature},
        }
        request = urllib_request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={"Content-Type": "application/json"},
        )

        logger.info(
            "Invoking Ollama story extractor model=%s input_chars=%s",
            self.model,
            len(text),
        )
        raw = _read_ollama_response(request, timeout_seconds=self.timeout_seconds)

        try:
            response_data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("Ollama returned invalid JSON envelope") from exc

        content = response_data.get("response")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("Ollama response missing message.content")

        parsed = _extract_json_object(content)
        if not isinstance(parsed, dict):
            raise ValueError("Ollama returned unusable non-JSON content")

        logger.info(
            "Ollama story extractor completed model=%s elapsed=%.2fs",
            self.model,
            perf_counter() - started,
        )
        return parsed


def _read_ollama_response(request: urllib_request.Request, *, timeout_seconds: int) -> str:
    try:
        with urllib_request.urlopen(request, timeout=timeout_seconds) as response:
            return response.read().decode("utf-8")
    except TimeoutError as exc:
        raise RuntimeError("Ollama request timed out") from exc
    except urllib_error.HTTPError as exc:
        raise RuntimeError(f"Ollama request failed: HTTP {exc.code}") from exc
    except urllib_error.URLError as exc:
        if isinstance(exc.reason, TimeoutError):
            raise RuntimeError("Ollama request timed out") from exc
        raise RuntimeError(f"Ollama request failed: {exc.reason}") from exc
    except UnicodeDecodeError as exc:
        raise ValueError("Ollama returned invalid JSON envelope") from exc


def _build_system_prompt() -> str:
    return OLLAMA_STORY_JSON_PROMPT_TEMPLATE


def _build_user_prompt(text: str) -> str:
    return OLLAMA_STORY_JSON_PROMPT_TEMPLATE.format(story_text=text.strip() or "(empty story)")


def _extract_json_object(content: str) -> Any:
    stripped = content.strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass

    start = stripped.find("{")
    while start != -1:
        depth = 0
        in_string = False
        escape = False
        for index in range(start, len(stripped)):
            character = stripped[index]
            if in_string:
                if escape:
                    escape = False
                elif character == "\\":
                    escape = True
                elif character == '"':
                    in_string = False
                continue
            if character == '"':
                in_string = True
            elif character == "{":
                depth += 1
            elif character == "}":
                depth -= 1
                if depth == 0:
                    candidate = stripped[start : index + 1]
                    try:
                        return json.loads(candidate)
                    except json.JSONDecodeError:
                        break
        start = stripped.find("{", start + 1)

    raise ValueError("Ollama returned unusable non-JSON content")
