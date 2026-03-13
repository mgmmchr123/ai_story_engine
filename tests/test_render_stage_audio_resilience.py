"""Tests that audio failures degrade without failing full scene render."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from config import ENGINE_SETTINGS
from engine.context import PipelineContext, RunPaths
from models.scene_schema import Mood, Scene, Setting, StoryContent
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


class RenderStageAudioResilienceTests(unittest.TestCase):
    def test_scene_records_matching_instruction_artifact_path_when_metadata_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            context = PipelineContext(
                run_id="run_audio_traceable",
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
                        scene_id=1,
                        title="Scene 1",
                        description="desc",
                        characters=[],
                        setting=Setting.FOREST,
                        mood=Mood.MYSTERIOUS,
                        narration_text="Hello world",
                    )
                ],
            )
            context.scene_instructions = [
                {
                    "scene_id": 1,
                    "image_prompt": "forest prompt",
                    "characters": [],
                    "location": "forest",
                    "camera": {"shot": "medium shot", "angle": "eye level"},
                    "duration_sec": 5,
                    "dialogue": [],
                    "actions": [],
                }
            ]
            context.metadata["scene_instruction_paths"] = [str(root / "scenes" / "scene_001.json")]

            stage = SceneRenderStage(image_provider=_ImageOk(), tts_provider=_TTSOk(), bgm_provider=_BGMFail())
            with patch("pipeline.audio_mixer.AudioSegment", None):
                stage.run(context)

            result = context.scene_results[1]
            self.assertEqual(result.scene_instruction_path, str(root / "scenes" / "scene_001.json"))

    def test_scene_rendering_still_works_without_instruction_paths_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            context = PipelineContext(
                run_id="run_audio_no_metadata",
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
                        scene_id=1,
                        title="Scene 1",
                        description="desc",
                        characters=[],
                        setting=Setting.FOREST,
                        mood=Mood.MYSTERIOUS,
                        narration_text="Hello world",
                    )
                ],
            )
            context.scene_instructions = [
                {
                    "scene_id": 1,
                    "image_prompt": "forest prompt",
                    "characters": [],
                    "location": "forest",
                    "camera": {"shot": "medium shot", "angle": "eye level"},
                    "duration_sec": 5,
                    "dialogue": [],
                    "actions": [],
                }
            ]

            stage = SceneRenderStage(image_provider=_ImageOk(), tts_provider=_TTSOk(), bgm_provider=_BGMFail())
            with patch("pipeline.audio_mixer.AudioSegment", None):
                stage.run(context)

            result = context.scene_results[1]
            self.assertEqual(result.status, "completed")
            self.assertIsNone(result.scene_instruction_path)

    def test_scene_completes_when_bgm_selection_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            context = PipelineContext(
                run_id="run_audio_resilience",
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
                        scene_id=1,
                        title="Scene 1",
                        description="desc",
                        characters=[],
                        setting=Setting.FOREST,
                        mood=Mood.MYSTERIOUS,
                        narration_text="Hello world",
                    )
                ],
            )

            stage = SceneRenderStage(image_provider=_ImageOk(), tts_provider=_TTSOk(), bgm_provider=_BGMFail())
            with patch("pipeline.audio_mixer.AudioSegment", None):
                stage.run(context)

            result = context.scene_results[1]
            self.assertEqual(result.status, "completed")
            self.assertTrue(result.assets.narration_path)
            self.assertTrue(result.warnings)


if __name__ == "__main__":
    unittest.main()
