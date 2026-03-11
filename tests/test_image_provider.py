"""Tests for image providers, including ComfyUI real image handling."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib import error as urllib_error
from urllib import request as urllib_request

from config import ProviderSettings
from models.scene_schema import Mood, Scene, Setting
from providers.image_provider import ComfyUIImageProvider


class _FakeHTTPResponse:
    def __init__(self, payload: dict):
        self._raw = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._raw

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def _sample_scene() -> Scene:
    return Scene(
        scene_id=1,
        title="Scene 1",
        description="A hero enters the forest.",
        characters=[],
        setting=Setting.FOREST,
        mood=Mood.HEROIC,
        narration_text="A hero enters the forest.",
    )


def _workflow_template() -> dict:
    return {
        "3": {"inputs": {"seed": 1, "steps": 20, "cfg": 8}},
        "5": {"inputs": {"width": 512, "height": 512, "batch_size": 1}},
        "6": {"inputs": {"text": "old-positive"}},
        "7": {"inputs": {"text": "old-negative"}},
        "9": {"inputs": {"filename_prefix": "ComfyUI"}},
    }


class ComfyUIImageProviderTests(unittest.TestCase):
    def test_loads_workflow_json_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflow_path = root / "workflow.json"
            workflow_path.write_text(json.dumps(_workflow_template()), encoding="utf-8")

            provider = ComfyUIImageProvider(
                ProviderSettings(
                    comfyui_workflow_path=str(workflow_path),
                    comfyui_output_dir=str(root / "output"),
                )
            )
            workflow = provider._load_workflow()

        self.assertIn("6", workflow)
        self.assertIn("7", workflow)

    def test_injects_positive_prompt_into_node_6(self) -> None:
        provider = ComfyUIImageProvider(ProviderSettings())
        injected = provider._inject_workflow(
            workflow=_workflow_template(),
            prompt="a cinematic scene",
            scene=_sample_scene(),
            output_path=Path("output/runs/test_run/images/scene_001.png"),
        )
        self.assertEqual(injected["6"]["inputs"]["text"], "a cinematic scene")

    def test_injects_negative_prompt_into_node_7(self) -> None:
        settings = ProviderSettings(comfyui_negative_prompt="no text, no watermark")
        provider = ComfyUIImageProvider(settings)
        injected = provider._inject_workflow(
            workflow=_workflow_template(),
            prompt="unused positive",
            scene=_sample_scene(),
            output_path=Path("output/runs/test_run/images/scene_001.png"),
        )
        self.assertEqual(injected["7"]["inputs"]["text"], "no text, no watermark")

    def test_extract_image_metadata_from_history_returns_filename_subfolder_type(self) -> None:
        provider = ComfyUIImageProvider(ProviderSettings())
        history_entry = {
            "outputs": {
                "9": {
                    "images": [
                        {
                            "filename": "ComfyUI_00001_.png",
                            "subfolder": "story",
                            "type": "output",
                        }
                    ]
                }
            }
        }
        metadata = provider.extract_image_metadata_from_history(history_entry)
        self.assertEqual(metadata["filename"], "ComfyUI_00001_.png")
        self.assertEqual(metadata["subfolder"], "story")
        self.assertEqual(metadata["type"], "output")

    def test_resolve_comfyui_output_file_uses_output_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            comfy_output = root / "output"
            nested = comfy_output / "story"
            nested.mkdir(parents=True, exist_ok=True)
            source_image = nested / "ComfyUI_00001_.png"
            source_image.write_bytes(b"x" * 12000)
            provider = ComfyUIImageProvider(
                ProviderSettings(comfyui_output_dir=str(comfy_output))
            )
            resolved = provider.resolve_comfyui_output_file(
                filename="ComfyUI_00001_.png",
                subfolder="story",
                output_type="output",
            )
        self.assertEqual(resolved, source_image)

    def test_copy_real_image_to_run_output_copies_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "src.png"
            source.write_bytes(b"x" * 12000)
            destination = root / "run" / "images" / "scene_001.png"
            provider = ComfyUIImageProvider(ProviderSettings())
            copied = provider.copy_real_image_to_run_output(source, destination)
            self.assertEqual(copied, destination)
            self.assertTrue(destination.exists())
            self.assertGreater(destination.stat().st_size, 10240)

    @patch("providers.image_provider.urllib_request.urlopen")
    def test_generate_uses_prompt_and_history_and_returns_png_path(self, mock_urlopen) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            comfy_output = root / "output"
            comfy_output.mkdir(parents=True, exist_ok=True)
            source_image = comfy_output / "image_00001_.png"
            source_image.write_bytes(b"x" * 12000)

            workflow_path = root / "workflow.json"
            workflow_path.write_text(json.dumps(_workflow_template()), encoding="utf-8")
            settings = ProviderSettings(
                comfyui_workflow_path=str(workflow_path),
                comfyui_output_dir=str(comfy_output),
                comfyui_timeout_seconds=5,
                comfyui_poll_interval_seconds=0.01,
            )
            provider = ComfyUIImageProvider(settings)

            def _urlopen_side_effect(request_obj, timeout=None):  # noqa: ANN001
                if isinstance(request_obj, urllib_request.Request):
                    body = json.loads(request_obj.data.decode("utf-8"))
                    self.assertEqual(body["prompt"]["6"]["inputs"]["text"], "forest dawn")
                    return _FakeHTTPResponse({"prompt_id": "pid-123"})
                self.assertIn("/history/pid-123", str(request_obj))
                return _FakeHTTPResponse(
                    {
                        "pid-123": {
                            "outputs": {
                                "9": {
                                    "images": [
                                        {
                                            "filename": "image_00001_.png",
                                            "subfolder": "",
                                            "type": "output",
                                        }
                                    ]
                                }
                            }
                        }
                    }
                )

            mock_urlopen.side_effect = _urlopen_side_effect

            destination = root / "run" / "images" / "scene_001.png"
            result = provider.generate(_sample_scene(), "forest dawn", destination)

            self.assertEqual(result.suffix, ".png")
            self.assertTrue(result.exists())
            self.assertEqual(result, destination)
            self.assertGreater(result.stat().st_size, 10240)

    @patch("providers.image_provider.urllib_request.urlopen")
    def test_falls_back_when_comfyui_unreachable(self, mock_urlopen) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflow_path = root / "workflow.json"
            workflow_path.write_text(json.dumps(_workflow_template()), encoding="utf-8")
            settings = ProviderSettings(
                comfyui_workflow_path=str(workflow_path),
                comfyui_output_dir=str(root / "output"),
            )
            provider = ComfyUIImageProvider(settings)
            mock_urlopen.side_effect = urllib_error.URLError("connection refused")

            destination = root / "run" / "images" / "scene_001.png"
            result = provider.generate(_sample_scene(), "forest dawn", destination)

            self.assertEqual(result.suffix, ".txt")
            self.assertTrue(result.exists())
            self.assertIn("scene_id=1", result.read_text(encoding="utf-8"))
            self.assertFalse(destination.exists())

    def test_falls_back_when_workflow_is_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            invalid_workflow = root / "workflow.json"
            invalid_workflow.write_text("{ this is invalid json", encoding="utf-8")
            settings = ProviderSettings(
                comfyui_workflow_path=str(invalid_workflow),
                comfyui_output_dir=str(root / "output"),
            )
            provider = ComfyUIImageProvider(settings)
            destination = root / "run" / "images" / "scene_001.png"

            result = provider.generate(_sample_scene(), "forest dawn", destination)

            self.assertEqual(result.suffix, ".txt")
            self.assertTrue(result.exists())
            self.assertIn("prompt=forest dawn", result.read_text(encoding="utf-8"))
            self.assertFalse(destination.exists())

    @patch("providers.image_provider.urllib_request.urlopen")
    def test_tiny_output_png_triggers_fallback_and_no_fake_png(self, mock_urlopen) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            comfy_output = root / "output"
            comfy_output.mkdir(parents=True, exist_ok=True)
            source_image = comfy_output / "tiny.png"
            source_image.write_bytes(b"x" * 512)

            workflow_path = root / "workflow.json"
            workflow_path.write_text(json.dumps(_workflow_template()), encoding="utf-8")
            settings = ProviderSettings(
                comfyui_workflow_path=str(workflow_path),
                comfyui_output_dir=str(comfy_output),
                comfyui_timeout_seconds=5,
                comfyui_poll_interval_seconds=0.01,
                comfyui_min_image_bytes=10240,
            )
            provider = ComfyUIImageProvider(settings)

            def _urlopen_side_effect(request_obj, timeout=None):  # noqa: ANN001
                if isinstance(request_obj, urllib_request.Request):
                    return _FakeHTTPResponse({"prompt_id": "pid-123"})
                return _FakeHTTPResponse(
                    {
                        "pid-123": {
                            "outputs": {
                                "9": {
                                    "images": [
                                        {
                                            "filename": "tiny.png",
                                            "subfolder": "",
                                            "type": "output",
                                        }
                                    ]
                                }
                            }
                        }
                    }
                )

            mock_urlopen.side_effect = _urlopen_side_effect

            destination = root / "run" / "images" / "scene_001.png"
            result = provider.generate(_sample_scene(), "forest dawn", destination)

            self.assertEqual(result.suffix, ".txt")
            self.assertTrue(result.exists())
            self.assertFalse(destination.exists())


if __name__ == "__main__":
    unittest.main()
