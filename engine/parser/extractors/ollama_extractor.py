"""Ollama-backed canonical story extractor."""

from __future__ import annotations

import json
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request

from .base_extractor import BaseStoryExtractor


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
        payload = {
            "model": self.model,
            "stream": False,
            "format": "json",
            "options": {"temperature": self.temperature},
            "messages": [
                {"role": "system", "content": _build_system_prompt()},
                {"role": "user", "content": _build_user_prompt(text)},
            ],
        }
        endpoint = f"{self.url.rstrip('/')}/api/chat"
        request = urllib_request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={"Content-Type": "application/json"},
        )

        try:
            with urllib_request.urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
        except urllib_error.URLError as exc:
            raise RuntimeError(f"Ollama request failed: {exc}") from exc

        try:
            response_data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("Ollama returned invalid JSON envelope") from exc

        content = response_data.get("message", {}).get("content")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("Ollama response missing message.content")

        parsed = _extract_json_object(content)
        if not isinstance(parsed, dict):
            raise ValueError("Ollama content must decode to a JSON object")
        return parsed


def _build_system_prompt() -> str:
    return (
        "You are a strict JSON service. Return only one JSON object and no extra text. "
        'The object must follow canonical story_json shape: '
        '{"story_id":"string","title":"string","style":"anime|cartoon|realistic",'
        '"characters":[{"id":"string","name":"string","appearance":"string","voice":"string"}],'
        '"locations":[{"id":"string","description":"string","time_of_day":"string"}],'
        '"scenes":[{"scene_id":"number","location":"string","duration_sec":"number",'
        '"characters":["string"],"camera":{"shot":"string","angle":"string"},'
        '"actions":[{"character":"string","type":"string","emotion":"string","description":"string"}],'
        '"dialogue":[{"speaker":"string","text":"string","emotion":"string"}]}]}.'
    )


def _build_user_prompt(text: str) -> str:
    return "Convert the following story text into canonical story_json only.\nStory:\n" + text


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
