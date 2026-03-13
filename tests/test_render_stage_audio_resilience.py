"""Tests that audio failures degrade without failing full scene render."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from config import ENGINE_SETTINGS
from engine.context import PipelineContext, RunPaths
from models.scene_schema import Mood, Scene, SceneAssets, SceneRenderResult, Setting, StoryContent
from pipeline.render_stage import SceneRenderStage
from providers.bgm_provider import BGMProvider
from providers.image_provider import ImageProvider
from providers.tts_provider import TTSProvider


class _ImageOk(ImageProvider):
    def generate(self, scene: Scene, prompt: str, output_path: Path) -> Path:
        del scene, prompt
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"image")
        return output_path


class _TTSOk(TTSProvider):
    def generate(self, scene: Scene, narration_text: str, output_path: Path) -> Path:
        del scene, narration_text
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"x" * 2048)
        return output_path


class _BGMFail(BGMProvider):
    def select(self, scene: Scene, params: dict[str, str], output_path: Path) -> Path:
        del scene, params, output_path
        raise RuntimeError("bgm missing")


def _build_render_context(root: Path, scene_ids: list[int]) -> PipelineContext:
    context = PipelineContext(
        run_id="run_render_test",
        story_input="line",
        story_title="Story",
        story_author="Author",
        config=ENGINE_SETTINGS,
        paths=RunPaths(
            run_dir=root,
            scenes_dir=root / "scenes",
            images_dir=root / "images",
            audio_dir=root / "audio",
            bgm_dir=root / "bgm",
            mixed_dir=root / "mixed",
            final_dir=root / "final",
            final_story_path=root / "final" / "story.mp3",
            manifest_path=root / "manifest.json",
        ),
    )
    context.story = StoryContent(
        title="Story",
        author="Author",
        description="Desc",
        scenes=[
            Scene(
                scene_id=scene_id,
                title=f"Scene {scene_id}",
                description="desc",
                characters=[],
                setting=Setting.FOREST,
                mood=Mood.MYSTERIOUS,
                narration_text="Hello world",
            )
            for scene_id in scene_ids
        ],
    )
    context.scene_instructions = [
        {
            "scene_id": scene_id,
            "image_prompt": f"forest prompt {scene_id}",
            "characters": [],
            "location": "forest",
            "camera": {"shot": "medium shot", "angle": "eye level"},
            "duration_sec": 5,
            "dialogue": [],
            "actions": [],
        }
        for scene_id in scene_ids
    ]
    context.metadata["scene_instruction_paths"] = [
        str(root / "scenes" / f"scene_{scene_id:03d}.json") for scene_id in scene_ids
    ]
    return context


class RenderStageAudioResilienceTests(unittest.TestCase):
    def test_scene_records_matching_instruction_artifact_path_when_metadata_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            context = _build_render_context(root, [1])

            stage = SceneRenderStage(image_provider=_ImageOk(), tts_provider=_TTSOk(), bgm_provider=_BGMFail())
            with patch("pipeline.audio_mixer.AudioSegment", None):
                stage.run(context)

            result = context.scene_results[1]
            self.assertEqual(result.scene_instruction_path, str(root / "scenes" / "scene_001.json"))

    def test_scene_rendering_still_works_without_instruction_paths_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            context = _build_render_context(root, [1])
            context.metadata.pop("scene_instruction_paths")

            stage = SceneRenderStage(image_provider=_ImageOk(), tts_provider=_TTSOk(), bgm_provider=_BGMFail())
            with patch("pipeline.audio_mixer.AudioSegment", None):
                stage.run(context)

            result = context.scene_results[1]
            self.assertEqual(result.status, "completed")
            self.assertIsNone(result.scene_instruction_path)

    def test_scene_completes_when_bgm_selection_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            context = _build_render_context(root, [1])

            stage = SceneRenderStage(image_provider=_ImageOk(), tts_provider=_TTSOk(), bgm_provider=_BGMFail())
            with patch("pipeline.audio_mixer.AudioSegment", None):
                stage.run(context)

            result = context.scene_results[1]
            self.assertEqual(result.status, "completed")
            self.assertTrue(result.assets.narration_path)
            self.assertTrue(result.warnings)

    def test_default_behavior_renders_all_scenes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            context = _build_render_context(root, [1, 2, 3])

            stage = SceneRenderStage(image_provider=_ImageOk(), tts_provider=_TTSOk(), bgm_provider=_BGMFail())
            with patch("pipeline.audio_mixer.AudioSegment", None):
                stage.run(context)

            self.assertEqual(sorted(context.scene_results), [1, 2, 3])

    def test_selected_scene_ids_renders_only_single_selected_scene(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            context = _build_render_context(root, [1, 2, 3])
            context.selected_scene_ids = {2}

            stage = SceneRenderStage(image_provider=_ImageOk(), tts_provider=_TTSOk(), bgm_provider=_BGMFail())
            with patch("pipeline.audio_mixer.AudioSegment", None):
                stage.run(context)

            self.assertEqual(sorted(context.scene_results), [2])
            self.assertEqual(context.scene_results[2].scene_instruction_path, str(root / "scenes" / "scene_002.json"))

    def test_selected_scene_ids_renders_only_requested_subset(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            context = _build_render_context(root, [1, 2, 3])
            context.selected_scene_ids = {1, 3}

            stage = SceneRenderStage(image_provider=_ImageOk(), tts_provider=_TTSOk(), bgm_provider=_BGMFail())
            with patch("pipeline.audio_mixer.AudioSegment", None):
                stage.run(context)

            self.assertEqual(sorted(context.scene_results), [1, 3])
            self.assertNotIn(2, context.scene_results)

    def test_selected_scene_ids_with_unknown_ids_does_not_break_rendering(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            context = _build_render_context(root, [1, 2])
            context.selected_scene_ids = {2, 99}

            stage = SceneRenderStage(image_provider=_ImageOk(), tts_provider=_TTSOk(), bgm_provider=_BGMFail())
            with patch("pipeline.audio_mixer.AudioSegment", None):
                stage.run(context)

            self.assertEqual(sorted(context.scene_results), [2])
            self.assertFalse(any(result.status == "failed" for scene_id, result in context.scene_results.items() if scene_id != 2))

    def test_completed_scene_outputs_are_not_rerendered_on_subsequent_stage_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            context = _build_render_context(root, [1])
            image_path = root / "images" / "scene_001.png"
            narration_path = root / "audio" / "scene_001.wav"
            mixed_path = root / "mixed" / "scene_001.mp3"
            bgm_path = root / "bgm" / "scene_001.mp3"
            image_path.parent.mkdir(parents=True, exist_ok=True)
            narration_path.parent.mkdir(parents=True, exist_ok=True)
            mixed_path.parent.mkdir(parents=True, exist_ok=True)
            bgm_path.parent.mkdir(parents=True, exist_ok=True)
            image_path.write_bytes(b"image")
            narration_path.write_bytes(b"narration")
            mixed_path.write_bytes(b"mixed")
            bgm_path.write_bytes(b"bgm")
            context.scene_results[1] = SceneRenderResult(
                scene_id=1,
                status="completed",
                assets=SceneAssets(
                    image_path=str(image_path),
                    narration_path=str(narration_path),
                    bgm_path=str(bgm_path),
                    mixed_audio_path=str(mixed_path),
                ),
            )

            class _ImageShouldNotRun(ImageProvider):
                def generate(self, scene: Scene, prompt: str, output_path: Path) -> Path:
                    raise AssertionError("image generation should have been skipped")

            stage = SceneRenderStage(
                image_provider=_ImageShouldNotRun(),
                tts_provider=_TTSOk(),
                bgm_provider=_BGMFail(),
            )
            stage.run(context)

            self.assertTrue(context.scene_results[1].skipped)


if __name__ == "__main__":
    unittest.main()
