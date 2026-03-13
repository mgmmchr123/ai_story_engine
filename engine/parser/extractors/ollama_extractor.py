"""Ollama-backed canonical story extractor."""

from __future__ import annotations

import json
import logging
import re
from time import perf_counter
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request

from engine.logging_utils import compact_json

from .base_extractor import BaseStoryExtractor

logger = logging.getLogger(__name__)

OLLAMA_STORY_JSON_PROMPT_TEMPLATE = """Convert the story text below into one canonical story_json object.

Output requirements:
- Return exactly one JSON object.
- Do not use markdown fences.
- Do not add prose before or after the JSON.
- Return valid JSON only.
- Top-level fields must be: story_id, title, style, characters, locations, scenes.
- characters, locations, and scenes must be arrays even when empty.
- scene_id and duration_sec must be integers.
- style should be one of anime, cartoon, or realistic when possible.
- Each scene must include: scene_id, title, location, mood, characters, narration, duration_sec.
- Scene characters must be an array of strings.
- Use narration for scene narration text. Do not use description instead of narration.
- Do not leave characters empty if a real character exists in the scene.
- Match the number of scenes to the number of narrative beats provided in the story text.
- Keep one scene per beat, preserve chronological order, and do not merge adjacent beats unless the input explicitly says they are one scene.
- camera, dialogue, actions, and image_prompt are optional but should be included when known.

Story text:
{story_text}
"""


class OllamaStoryExtractor(BaseStoryExtractor):
    """Minimal Ollama-backed extractor that returns canonical story.json payloads."""

    def __init__(
        self,
        model: str = "qwen2.5:7b",
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
        expected_scene_count = _estimate_narrative_beats(text)
        payload = {
            "model": self.model,
            "stream": False,
            "format": "json",
            "prompt": _build_user_prompt(text, expected_scene_count=expected_scene_count),
            "options": {"temperature": self.temperature},
        }
        request = urllib_request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={"Content-Type": "application/json"},
        )

        logger.info(
            "Invoking Ollama story extractor endpoint=%s model=%s input_chars=%s expected_scene_count=%s",
            endpoint,
            self.model,
            len(text),
            expected_scene_count,
        )
        raw = _read_ollama_response(request, timeout_seconds=self.timeout_seconds)

        try:
            response_data = json.loads(raw)
        except json.JSONDecodeError as exc:
            logger.error("Ollama returned invalid JSON envelope raw=%s", compact_json(raw))
            raise ValueError("Ollama returned invalid JSON envelope") from exc

        content = response_data.get("response")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("Ollama response missing message.content")

        try:
            parsed = _extract_json_object(content)
        except ValueError:
            logger.error("Ollama content parse failed raw_response=%s", compact_json(content, max_len=2000))
            raise
        if not isinstance(parsed, dict):
            raise ValueError("Ollama returned unusable non-JSON content")

        scenes = parsed.get("scenes") if isinstance(parsed.get("scenes"), list) else []
        characters = parsed.get("characters") if isinstance(parsed.get("characters"), list) else []
        logger.info("Ollama parsed top-level keys=%s", sorted(parsed.keys()))
        logger.info("Ollama parsed character_count=%s scene_count=%s", len(characters), len(scenes))
        if scenes:
            logger.info("Ollama first raw scene=%s", compact_json(scenes[0], max_len=2000))
        if len(scenes) != expected_scene_count:
            raise ValueError(
                f"Ollama returned {len(scenes)} scenes but expected {expected_scene_count} narrative beats"
            )

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


def _build_user_prompt(text: str, *, expected_scene_count: int) -> str:
    story_text = text.strip() or "(empty story)"
    beat_instruction = (
        f"\nNarrative beat requirements:\n"
        f"- The input contains {expected_scene_count} narrative beats.\n"
        f"- Return exactly {expected_scene_count} scenes.\n"
        f"- Keep scene_id values sequential from 1 to {expected_scene_count}.\n"
        f"- Preserve chronological order.\n"
    )
    return OLLAMA_STORY_JSON_PROMPT_TEMPLATE.format(story_text=f"{beat_instruction}\n{story_text}")


def _estimate_narrative_beats(text: str) -> int:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) > 1:
        return len(lines)
    blocks = [block.strip() for block in re.split(r"\n\s*\n+", text) if block.strip()]
    if len(blocks) > 1:
        return len(blocks)
    sentences = [item.strip() for item in re.split(r"(?<=[.!?])\s+", text.strip()) if item.strip()]
    if sentences:
        return len(sentences)
    return 1


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
