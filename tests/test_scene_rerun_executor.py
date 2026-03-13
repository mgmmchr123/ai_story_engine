"""Tests for scene rerun executor helpers."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from config import ENGINE_SETTINGS
from engine.cache.scene_instruction_cache import save_scene_instruction
from engine.context import PipelineContext, RunPaths
from engine.rerun.scene_rerun_executor import rerun_selected_scenes, rerun_single_scene
from models.scene_schema import Mood, Scene, SceneRenderResult, Setting, StoryContent
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


def _instruction(scene_id: int) -> dict:
    return {
        "scene_id": scene_id,
        "image_prompt": f"forest prompt {scene_id}",
        "characters": [],
        "location": "forest",
        "camera": {"shot": "medium shot", "angle": "eye level"},
        "duration_sec": 5,
        "dialogue": [],
        "actions": [],
    }


def _build_context(root: Path, scene_ids: list[int]) -> PipelineContext:
    context = PipelineContext(
        run_id="run_scene_rerun_executor",
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
    context.story_json = {"story_id": "story", "title": "Story", "style": "anime", "characters": [], "locations": [], "scenes": []}
    context.scene_instructions = [_instruction(scene_id) for scene_id in scene_ids]
    context.metadata["scene_instruction_paths"] = [str(root / "scenes" / f"scene_{scene_id:03d}.json") for scene_id in scene_ids]
    context.scene_results = {
        scene_id: SceneRenderResult(scene_id=scene_id, status="completed" if scene_id != 2 else "failed")
        for scene_id in scene_ids
    }
    return context


class SceneRerunExecutorTests(unittest.TestCase):
    def test_rerun_single_scene_bootstraps_selects_and_updates_only_target_scene(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            context = _build_context(root, [1, 2, 3])
            context.scene_instructions = []
            context.metadata.pop("scene_instruction_paths")
            for scene_id in [1, 2, 3]:
                save_scene_instruction(_instruction(scene_id), context.paths.scenes_dir)
            previous_scene_2 = context.scene_results[2]

            stage = SceneRenderStage(image_provider=_ImageOk(), tts_provider=_TTSOk(), bgm_provider=_BGMFail())
            with patch("pipeline.audio_mixer.AudioSegment", None):
                rerun_single_scene(context, 2, stage, bootstrap=True)

            self.assertEqual(context.selected_scene_ids, {2})
            self.assertEqual(sorted(context.scene_results), [1, 2, 3])
            self.assertIsNot(context.scene_results[2], previous_scene_2)
            self.assertEqual(context.scene_results[2].status, "completed")
            self.assertEqual(context.scene_results[2].scene_instruction_path, str(root / "scenes" / "scene_002.json"))
            self.assertEqual(context.scene_results[1].status, "completed")
            self.assertEqual(context.scene_results[3].status, "completed")

    def test_rerun_selected_scenes_renders_only_selected_subset(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            context = _build_context(root, [1, 2, 3])
            original_scene_2 = context.scene_results[2]

            stage = SceneRenderStage(image_provider=_ImageOk(), tts_provider=_TTSOk(), bgm_provider=_BGMFail())
            with patch("pipeline.audio_mixer.AudioSegment", None):
                rerun_selected_scenes(context, {1, 3}, stage, bootstrap=False)

            self.assertEqual(context.selected_scene_ids, {1, 3})
            self.assertEqual(sorted(context.scene_results), [1, 2, 3])
            self.assertIs(context.scene_results[2], original_scene_2)
            self.assertEqual(context.scene_results[1].status, "completed")
            self.assertEqual(context.scene_results[3].status, "completed")

    def test_rerun_selected_scenes_with_bootstrap_false_uses_in_memory_scene_instructions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            context = _build_context(root, [1])
            context.scene_instructions = [_instruction(1)]
            context.metadata["scene_instruction_paths"] = [str(root / "scenes" / "scene_001.json")]

            stage = SceneRenderStage(image_provider=_ImageOk(), tts_provider=_TTSOk(), bgm_provider=_BGMFail())
            with patch("pipeline.audio_mixer.AudioSegment", None):
                rerun_selected_scenes(context, {1}, stage, bootstrap=False)

            self.assertEqual(context.scene_results[1].image_prompt, "forest prompt 1")

    def test_rerun_selected_scenes_raises_when_story_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            context = _build_context(root, [1])
            context.story = None

            stage = SceneRenderStage(image_provider=_ImageOk(), tts_provider=_TTSOk(), bgm_provider=_BGMFail())
            with self.assertRaisesRegex(ValueError, "context.story must be available for scene rerun"):
                rerun_selected_scenes(context, {1}, stage, bootstrap=False)

    def test_non_selected_scene_results_remain_intact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            context = _build_context(root, [1, 2, 3])
            original_scene_1 = context.scene_results[1]
            original_scene_3 = context.scene_results[3]

            stage = SceneRenderStage(image_provider=_ImageOk(), tts_provider=_TTSOk(), bgm_provider=_BGMFail())
            with patch("pipeline.audio_mixer.AudioSegment", None):
                rerun_selected_scenes(context, {2}, stage, bootstrap=False)

            self.assertIs(context.scene_results[1], original_scene_1)
            self.assertIs(context.scene_results[3], original_scene_3)


if __name__ == "__main__":
    unittest.main()
