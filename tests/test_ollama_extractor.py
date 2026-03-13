"""Tests for OllamaStoryExtractor."""

import json
import unittest
from unittest.mock import patch
from urllib import error as urllib_error

from engine.parser.extractors.ollama_extractor import OllamaStoryExtractor


class _FakeResponse:
    def __init__(self, payload: dict):
        self._payload = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._payload

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


class OllamaStoryExtractorTests(unittest.TestCase):
    @patch("engine.parser.extractors.ollama_extractor.urllib_request.urlopen")
    def test_successful_json_response_returns_story_dict(self, mock_urlopen) -> None:
        mock_urlopen.return_value = _FakeResponse(
            {
                "response": json.dumps(
                    {
                        "story_id": "forest_story",
                        "title": "Forest Story",
                        "style": "anime",
                        "characters": [],
                        "locations": [],
                        "scenes": [],
                    }
                )
            }
        )
        extractor = OllamaStoryExtractor()

        result = extractor.extract("A ranger watches the trees sway.")

        self.assertEqual(result["story_id"], "forest_story")
        self.assertEqual(result["title"], "Forest Story")
        self.assertEqual(result["style"], "anime")
        self.assertIn("characters", result)
        self.assertIn("locations", result)
        self.assertIn("scenes", result)

    @patch("engine.parser.extractors.ollama_extractor.urllib_request.urlopen")
    def test_extractor_tolerates_wrapper_text_around_json_object(self, mock_urlopen) -> None:
        mock_urlopen.return_value = _FakeResponse(
            {
                "response": (
                    "Here is the canonical story_json:\n"
                    '{"story_id":"wrapped_story","title":"Wrapped","style":"anime","characters":[],"locations":[],"scenes":[]}\n'
                    "End."
                )
            }
        )
        extractor = OllamaStoryExtractor()

        result = extractor.extract("Wrapped output test")

        self.assertEqual(result["story_id"], "wrapped_story")
        self.assertEqual(result["title"], "Wrapped")

    @patch("engine.parser.extractors.ollama_extractor.urllib_request.urlopen")
    def test_invalid_non_json_content_raises_clear_value_error(self, mock_urlopen) -> None:
        mock_urlopen.return_value = _FakeResponse({"response": "not json at all"})
        extractor = OllamaStoryExtractor()

        with self.assertRaisesRegex(ValueError, "unusable non-JSON content"):
            extractor.extract("Bad response")

    @patch("engine.parser.extractors.ollama_extractor.urllib_request.urlopen")
    def test_http_failure_raises_clear_runtime_error(self, mock_urlopen) -> None:
        mock_urlopen.side_effect = urllib_error.URLError("connection refused")
        extractor = OllamaStoryExtractor()

        with self.assertRaisesRegex(RuntimeError, "Ollama request failed"):
            extractor.extract("Network failure")

    @patch("engine.parser.extractors.ollama_extractor.urllib_request.urlopen")
    def test_timeout_failure_raises_clear_timeout_error(self, mock_urlopen) -> None:
        mock_urlopen.side_effect = TimeoutError("timed out")
        extractor = OllamaStoryExtractor()

        with self.assertRaisesRegex(RuntimeError, "Ollama request timed out"):
            extractor.extract("Timeout failure")

    @patch("engine.parser.extractors.ollama_extractor.urllib_request.urlopen")
    def test_url_timeout_failure_raises_clear_timeout_error(self, mock_urlopen) -> None:
        mock_urlopen.side_effect = urllib_error.URLError(TimeoutError("timed out"))
        extractor = OllamaStoryExtractor()

        with self.assertRaisesRegex(RuntimeError, "Ollama request timed out"):
            extractor.extract("Timeout failure")

    @patch("engine.parser.extractors.ollama_extractor.urllib_request.urlopen")
    def test_invalid_json_envelope_raises_clear_value_error(self, mock_urlopen) -> None:
        mock_urlopen.return_value = _FakeResponse({"response": "{}"})
        mock_urlopen.return_value._payload = b"{not valid json"
        extractor = OllamaStoryExtractor()

        with self.assertRaisesRegex(ValueError, "invalid JSON envelope"):
            extractor.extract("Bad envelope")

    @patch("engine.parser.extractors.ollama_extractor.urllib_request.urlopen")
    def test_missing_message_content_raises_clear_value_error(self, mock_urlopen) -> None:
        mock_urlopen.return_value = _FakeResponse({"done": True})
        extractor = OllamaStoryExtractor()

        with self.assertRaisesRegex(ValueError, "missing message.content"):
            extractor.extract("Missing content")

    @patch("engine.parser.extractors.ollama_extractor.urllib_request.urlopen")
    def test_model_and_url_wiring_are_passed_to_request(self, mock_urlopen) -> None:
        mock_urlopen.return_value = _FakeResponse(
            {
                "response": json.dumps(
                    {
                        "story_id": "wired_story",
                        "title": "Wired",
                        "style": "anime",
                        "characters": [],
                        "locations": [],
                        "scenes": [],
                    }
                )
            }
        )
        extractor = OllamaStoryExtractor(
            model="llama3.1:8b",
            url="http://localhost:11434",
            timeout_seconds=17,
            temperature=0.25,
        )

        extractor.extract("Wiring test")

        request = mock_urlopen.call_args.args[0]
        timeout = mock_urlopen.call_args.kwargs["timeout"]
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(request.full_url, "http://localhost:11434/api/generate")
        self.assertEqual(timeout, 17)
        self.assertEqual(payload["model"], "llama3.1:8b")
        self.assertEqual(payload["options"]["temperature"], 0.25)
        self.assertFalse(payload["stream"])
        self.assertEqual(payload["format"], "json")
        self.assertIn("Return exactly one JSON object", payload["prompt"])
        self.assertIn("Do not use markdown fences", payload["prompt"])
        self.assertIn("story_id, title, style, characters, locations, scenes", payload["prompt"])
        self.assertIn("scene_id and duration_sec must be integers", payload["prompt"])


if __name__ == "__main__":
    unittest.main()
