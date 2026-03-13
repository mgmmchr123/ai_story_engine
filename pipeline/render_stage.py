"""Scene render stage using provider abstraction."""

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from datetime import UTC, datetime
from pathlib import Path

from engine.cache.scene_instruction_index import resolve_scene_instruction_path
from engine.context import PipelineContext
from engine.logging_utils import get_stage_logger
from engine.stage import PipelineStage
from engine.video_exporter import get_media_duration
from models.scene_schema import Scene, SceneRenderResult
from pipeline.audio_mixer import mix_scene_audio
from pipeline.prompt_builder import build_bgm_prompt, build_image_prompt, build_narration_prompt
from providers.bgm_provider import BGMProvider
from providers.image_provider import ImageProvider
from providers.tts_provider import TTSProvider


class SceneRenderStage(PipelineStage):
    """Renders per-scene image/audio/bgm assets."""

    def __init__(self, image_provider: ImageProvider, tts_provider: TTSProvider, bgm_provider: BGMProvider):
        self.image_provider = image_provider
        self.tts_provider = tts_provider
        self.bgm_provider = bgm_provider

    @property
    def name(self) -> str:
        return "image_generation"

    def timeout_seconds(self, context: PipelineContext) -> int | None:
        scene_count = sum(1 for scene in context.story.scenes[: context.config.max_scenes] if self._should_render_scene(scene, context))
        if scene_count <= 0:
            return context.config.retry.stage_timeout_seconds
        return max(
            context.config.retry.stage_timeout_seconds,
            scene_count * context.config.retry.scene_timeout_seconds + 30,
        )

    def run(self, context: PipelineContext) -> None:
        if not context.story:
            raise ValueError("Story must be parsed before render stage.")

        stage_logger = get_stage_logger(__name__, context.run_id, self.name)

        instruction_map = {item.get("scene_id"): item for item in context.scene_instructions if isinstance(item, dict)}
        metadata_paths = context.metadata.get("scene_instruction_paths")
        metadata_paths = metadata_paths if isinstance(metadata_paths, list) else None

        for scene in context.story.scenes[: context.config.max_scenes]:
            if not self._should_render_scene(scene, context):
                continue
            scene_logger = get_stage_logger(__name__, context.run_id, self.name, scene.scene_id)
            started = datetime.now(UTC)
            scene_result = context.scene_results.get(scene.scene_id) or SceneRenderResult(scene_id=scene.scene_id)
            scene_instruction = instruction_map.get(scene.scene_id, {})
            resolved_instruction_path = resolve_scene_instruction_path(
                scene.scene_id,
                context.paths.scenes_dir,
                metadata_paths=metadata_paths,
            )
            scene_result.scene_instruction_path = str(resolved_instruction_path) if resolved_instruction_path else None
            scene_result.started_at = started.isoformat()

            image_path = context.paths.images_dir / f"scene_{scene.scene_id:03d}{context.config.providers.image_extension}"
            narration_path = context.paths.audio_dir / f"scene_{scene.scene_id:03d}{context.config.providers.narration_extension}"
            bgm_path = context.paths.bgm_dir / f"scene_{scene.scene_id:03d}{context.config.providers.bgm_extension}"
            mixed_path = context.paths.mixed_dir / f"scene_{scene.scene_id:03d}{context.config.providers.mixed_audio_extension}"

            if self._can_resume(context, scene_result, image_path, narration_path, bgm_path, mixed_path):
                scene_result.status = "skipped"
                scene_result.skipped = True
                scene_logger.info("Skipped scene rendering due to resume state")
                context.scene_results[scene.scene_id] = scene_result
                continue

            scene_result.skipped = False
            scene_result.image_prompt = str(
                scene_instruction.get("image_prompt")
                or build_image_prompt(scene, context.story.visual_bible)
            )
            scene_result.narration_prompt = build_narration_prompt(scene)
            scene_result.bgm_parameters = build_bgm_prompt(scene, context.story.visual_bible)
            if scene_instruction:
                scene_result.bgm_parameters["duration_seconds"] = int(
                    scene_instruction.get("duration_sec") or scene_result.bgm_parameters.get("duration_seconds", 180)
                )
                scene_result.bgm_parameters["camera_shot"] = str(scene_instruction["camera"]["shot"])
                scene_result.bgm_parameters["camera_angle"] = str(scene_instruction["camera"]["angle"])

            attempts = context.config.retry.scene_attempts
            timeout = context.config.retry.scene_timeout_seconds
            scene_result.status = "failed"
            scene_result.error = None

            for attempt in range(1, attempts + 1):
                scene_result.attempts = attempt
                try:
                    self._render_scene_with_timeout(
                        timeout_seconds=timeout,
                        scene=scene,
                        scene_result=scene_result,
                        image_path=image_path,
                        narration_path=narration_path,
                        bgm_path=bgm_path,
                        mixed_path=mixed_path,
                        bgm_reduction_db=context.config.providers.bgm_mix_reduction_db,
                        ffprobe_bin=context.config.providers.ffprobe_binary_path,
                    )
                    scene_result.status = "completed"
                    scene_result.error = None
                    scene_logger.info("Scene completed on attempt %s/%s", attempt, attempts)
                    break
                except Exception as exc:  # noqa: BLE001
                    scene_result.error = str(exc)
                    scene_logger.warning("Attempt %s/%s failed: %s", attempt, attempts, exc)

            if scene_result.status != "completed":
                context.record_warning(f"scene_id={scene.scene_id} failed: {scene_result.error}")
                scene_logger.error("Scene failed after retries: %s", scene_result.error)

            finished = datetime.now(UTC)
            scene_result.completed_at = finished.isoformat()
            scene_result.duration_seconds = (finished - started).total_seconds()
            for warning in scene_result.warnings:
                context.record_warning(f"scene_id={scene.scene_id} warning: {warning}")
            context.scene_results[scene.scene_id] = scene_result

        if any(result.status == "failed" for result in context.scene_results.values()):
            context.record_warning("One or more scenes failed during rendering.")
            stage_logger.warning("Render stage completed with scene failures")

    def _should_render_scene(self, scene: Scene, context: PipelineContext) -> bool:
        if context.selected_scene_ids is None:
            return True
        return scene.scene_id in context.selected_scene_ids

    def _can_resume(
        self,
        context: PipelineContext,
        scene_result: SceneRenderResult,
        image_path: Path,
        narration_path: Path,
        bgm_path: Path,
        mixed_path: Path,
    ) -> bool:
        if scene_result.status not in {"completed", "skipped"}:
            return False
        if not (image_path.exists() and narration_path.exists() and mixed_path.exists()):
            return False
        if scene_result.assets.bgm_path:
            return Path(scene_result.assets.bgm_path).exists()
        return True

    def _render_scene(
        self,
        scene: Scene,
        scene_result: SceneRenderResult,
        image_path: Path,
        narration_path: Path,
        bgm_path: Path,
        mixed_path: Path,
        bgm_reduction_db: float,
        ffprobe_bin: str | None,
    ) -> None:
        scene_result.assets.image_path = str(
            self.image_provider.generate(scene, scene_result.image_prompt, image_path)
        )
        narration_output = self.tts_provider.generate(scene, scene_result.narration_prompt, narration_path)
        scene_result.assets.narration_path = str(narration_output)

        bgm_output = bgm_path
        try:
            bgm_output = self.bgm_provider.select(scene, scene_result.bgm_parameters, bgm_path)
            if bgm_output.exists():
                scene_result.assets.bgm_path = str(bgm_output)
            else:
                scene_result.warnings.append("BGM asset missing; using narration-only mix if possible")
                scene_result.assets.bgm_path = None
        except Exception as exc:  # noqa: BLE001
            scene_result.warnings.append(f"BGM selection failed: {exc}")
            scene_result.assets.bgm_path = None
            bgm_output = bgm_path

        try:
            mixed_output = mix_scene_audio(
                narration_path=narration_output if narration_output.exists() else None,
                bgm_path=bgm_output if bgm_output.exists() else None,
                output_path=mixed_path,
                bgm_reduction_db=bgm_reduction_db,
            )
            if mixed_output:
                scene_result.assets.mixed_audio_path = str(mixed_output)
            else:
                scene_result.warnings.append("Scene mix export unavailable")
                scene_result.assets.mixed_audio_path = None
        except Exception as exc:  # noqa: BLE001
            scene_result.warnings.append(f"Scene mix failed: {exc}")
            scene_result.assets.mixed_audio_path = str(narration_output) if narration_output.exists() else None
        scene_result.media_duration_seconds = self._resolve_media_duration_seconds(scene_result, scene, ffprobe_bin)

    def _render_scene_with_timeout(
        self,
        timeout_seconds: int,
        scene: Scene,
        scene_result: SceneRenderResult,
        image_path: Path,
        narration_path: Path,
        bgm_path: Path,
        mixed_path: Path,
        bgm_reduction_db: float,
        ffprobe_bin: str | None,
    ) -> None:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(
                self._render_scene,
                scene,
                scene_result,
                image_path,
                narration_path,
                bgm_path,
                mixed_path,
                bgm_reduction_db,
                ffprobe_bin,
            )
            try:
                future.result(timeout=timeout_seconds)
            except FutureTimeoutError as exc:
                raise TimeoutError(f"Scene render timed out after {timeout_seconds}s") from exc

    def _resolve_media_duration_seconds(
        self,
        scene_result: SceneRenderResult,
        scene: Scene,
        ffprobe_bin: str | None,
    ) -> float:
        candidates = [
            scene_result.assets.mixed_audio_path,
            scene_result.assets.narration_path,
            scene_result.assets.bgm_path,
        ]
        for candidate in candidates:
            if not candidate:
                continue
            try:
                duration = get_media_duration(Path(candidate), ffprobe_bin=ffprobe_bin)
            except Exception:  # noqa: BLE001
                continue
            if duration > 0:
                return float(duration)
        return float(max(1, len(scene.narration_text.split()) // 2))
