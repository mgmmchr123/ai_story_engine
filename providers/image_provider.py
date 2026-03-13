"""Image provider interfaces and implementations."""

from abc import ABC, abstractmethod
from copy import deepcopy
import json
import logging
from pathlib import Path
import shutil
import time
from urllib import error as urllib_error
from urllib import request as urllib_request

from config import ProviderSettings
from models.scene_schema import Scene, scene_mood_value

logger = logging.getLogger(__name__)


class ImageProvider(ABC):
    """Generates scene illustration artifacts."""

    @abstractmethod
    def generate(self, scene: Scene, prompt: str, output_path: Path) -> Path:
        """Generate an image artifact and return file path."""


class PlaceholderImageProvider(ImageProvider):
    """Writes a text placeholder in place of a real generated image."""

    def generate(self, scene: Scene, prompt: str, output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            "\n".join(
                [
                    f"scene_id={scene.scene_id}",
                    f"title={scene.title}",
                    f"setting={scene.setting.value}",
                    f"mood={scene_mood_value(scene.mood)}",
                    f"prompt={prompt}",
                ]
            ),
            encoding="utf-8",
        )
        return output_path


class ComfyUIImageProvider(ImageProvider):
    """Image provider backed by local ComfyUI HTTP API."""

    _POSITIVE_NODE_ID = "6"
    _NEGATIVE_NODE_ID = "7"
    _SAMPLER_NODE_ID = "3"
    _LATENT_NODE_ID = "5"
    _SAVE_NODE_ID = "9"

    def __init__(self, settings: ProviderSettings, fallback_provider: ImageProvider | None = None):
        self.settings = settings
        self.fallback_provider = fallback_provider or PlaceholderImageProvider()

    def generate(self, scene: Scene, prompt: str, output_path: Path) -> Path:
        started = time.monotonic()
        destination = output_path.with_suffix(".png")
        fallback_destination = output_path.with_suffix(".txt")
        prompt_id = "-"
        logger.info(
            "[IMAGE] provider=comfyui scene_id=%s workflow=%s destination=%s",
            scene.scene_id,
            self.settings.comfyui_workflow_path,
            destination,
        )

        try:
            workflow = self._load_workflow()
            injected = self._inject_workflow(workflow=workflow, prompt=prompt, scene=scene, output_path=destination)
            latent_inputs = injected.get(self._LATENT_NODE_ID, {}).get("inputs", {})
            logger.info(
                "[IMAGE] provider=comfyui scene_id=%s submit_latent_resolution=%sx%s",
                scene.scene_id,
                latent_inputs.get("width", "?"),
                latent_inputs.get("height", "?"),
            )
            prompt_id = self._submit_prompt(injected)
            history_entry = self.poll_for_prompt_history(prompt_id)
            image_metadata = self.extract_image_metadata_from_history(history_entry)
            source_path = self.resolve_comfyui_output_file(
                filename=image_metadata["filename"],
                subfolder=image_metadata["subfolder"],
                output_type=image_metadata["type"],
            )
            self.copy_real_image_to_run_output(source_path, destination)

            duration = time.monotonic() - started
            logger.info(
                "[IMAGE] provider=comfyui scene_id=%s prompt_id=%s destination=%s duration=%.2fs",
                scene.scene_id,
                prompt_id,
                destination,
                duration,
            )
            return destination
        except Exception as exc:  # noqa: BLE001
            if destination.exists():
                destination.unlink(missing_ok=True)
            duration = time.monotonic() - started
            logger.warning(
                "[IMAGE] provider=comfyui scene_id=%s prompt_id=%s workflow=%s fallback=placeholder reason=%s duration=%.2fs",
                scene.scene_id,
                prompt_id,
                self.settings.comfyui_workflow_path,
                exc,
                duration,
            )
            return self.fallback_provider.generate(scene, prompt, fallback_destination)

    def _load_workflow(self) -> dict:
        workflow_path = Path(self.settings.comfyui_workflow_path)
        if not workflow_path.exists():
            raise FileNotFoundError(f"ComfyUI workflow file not found: {workflow_path}")
        try:
            return json.loads(workflow_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid ComfyUI workflow JSON at {workflow_path}: {exc}") from exc

    def _inject_workflow(self, workflow: dict, prompt: str, scene: Scene, output_path: Path) -> dict:
        payload = deepcopy(workflow)
        positive_inputs = payload[self._POSITIVE_NODE_ID]["inputs"]
        negative_inputs = payload[self._NEGATIVE_NODE_ID]["inputs"]
        sampler_inputs = payload[self._SAMPLER_NODE_ID]["inputs"]
        latent_inputs = payload[self._LATENT_NODE_ID]["inputs"]
        save_inputs = payload[self._SAVE_NODE_ID]["inputs"]

        positive_inputs["text"] = prompt
        negative_inputs["text"] = self.settings.comfyui_negative_prompt

        if self.settings.comfyui_width is not None:
            latent_inputs["width"] = int(self.settings.comfyui_width)
        if self.settings.comfyui_height is not None:
            latent_inputs["height"] = int(self.settings.comfyui_height)

        if self.settings.comfyui_steps is not None:
            sampler_inputs["steps"] = int(self.settings.comfyui_steps)
        if self.settings.comfyui_cfg is not None:
            sampler_inputs["cfg"] = float(self.settings.comfyui_cfg)
        if self.settings.comfyui_seed is not None:
            sampler_inputs["seed"] = int(self.settings.comfyui_seed)

        run_id = output_path.parent.parent.name if output_path.parent.parent else "run"
        save_inputs["filename_prefix"] = f"{run_id}_scene_{scene.scene_id:03d}"
        return payload

    def _submit_prompt(self, workflow: dict) -> str:
        endpoint = f"{self.settings.comfyui_base_url.rstrip('/')}/prompt"
        req = urllib_request.Request(
            endpoint,
            data=json.dumps({"prompt": workflow}).encode("utf-8"),
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib_request.urlopen(req, timeout=self.settings.comfyui_timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib_error.URLError as exc:
            raise ConnectionError(f"ComfyUI prompt submission failed: {exc}") from exc
        prompt_id = payload.get("prompt_id")
        if not prompt_id:
            raise ValueError("ComfyUI /prompt response missing prompt_id")
        return str(prompt_id)

    def poll_for_prompt_history(self, prompt_id: str) -> dict:
        endpoint = f"{self.settings.comfyui_base_url.rstrip('/')}/history/{prompt_id}"
        timeout_seconds = self.settings.comfyui_timeout_seconds
        interval_seconds = self.settings.comfyui_poll_interval_seconds
        deadline = time.monotonic() + timeout_seconds

        while time.monotonic() < deadline:
            try:
                with urllib_request.urlopen(endpoint, timeout=timeout_seconds) as response:
                    payload = json.loads(response.read().decode("utf-8"))
            except urllib_error.URLError as exc:
                raise ConnectionError(f"ComfyUI history polling failed: {exc}") from exc

            if payload.get(prompt_id):
                outputs = payload[prompt_id].get("outputs", {})
                if outputs:
                    return payload[prompt_id]
            time.sleep(interval_seconds)

        raise TimeoutError(f"ComfyUI polling timed out after {timeout_seconds}s for prompt_id={prompt_id}")

    def extract_image_metadata_from_history(self, history_entry: dict) -> dict[str, str]:
        outputs = history_entry.get("outputs", {})
        for node_output in outputs.values():
            images = node_output.get("images", [])
            if not images:
                continue
            image = images[0]
            filename = str(image.get("filename") or "").strip()
            subfolder = str(image.get("subfolder") or "").strip()
            output_type = str(image.get("type") or "output").strip()
            if not filename:
                continue
            return {
                "filename": filename,
                "subfolder": subfolder,
                "type": output_type or "output",
            }
        raise ValueError("ComfyUI history entry did not include image outputs")

    def resolve_comfyui_output_file(self, filename: str, subfolder: str, output_type: str) -> Path:
        output_dir = Path(self.settings.comfyui_output_dir)
        base_dir = output_dir
        if output_type and output_type not in {"output", "."}:
            base_dir = output_dir.parent / output_type
        base_dir = base_dir.resolve()
        if subfolder:
            resolved = base_dir / subfolder / filename
        else:
            resolved = base_dir / filename
        if not resolved.exists():
            raise FileNotFoundError(
                f"ComfyUI output file not found: filename={filename} subfolder={subfolder} type={output_type}"
            )
        return resolved

    def copy_real_image_to_run_output(self, source_path: Path, destination: Path) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, destination)
        min_bytes = int(self.settings.comfyui_min_image_bytes)
        if not destination.exists():
            raise FileNotFoundError(f"Copied destination image missing: {destination}")
        size = destination.stat().st_size
        if size <= min_bytes:
            destination.unlink(missing_ok=True)
            raise ValueError(
                f"ComfyUI output image too small ({size} bytes), expected > {min_bytes} bytes"
            )
        return destination


def build_image_provider(settings: ProviderSettings) -> ImageProvider:
    """Resolve provider from settings."""
    if settings.image_provider == "placeholder":
        return PlaceholderImageProvider()
    if settings.image_provider == "comfyui":
        return ComfyUIImageProvider(settings=settings, fallback_provider=PlaceholderImageProvider())
    raise ValueError(f"Unsupported image provider: {settings.image_provider}")
