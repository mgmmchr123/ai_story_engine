"""Pipeline runner with retry, timeout, and resume support."""

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from datetime import UTC, datetime
import logging
from pathlib import Path
import uuid

from config import ENGINE_SETTINGS, PROJECT_ROOT
from engine.context import PipelineContext, RunPaths, StageExecutionState
from engine.errors import StageExecutionError, StageTimeoutError
from engine.video_exporter import export_video, get_media_duration, probe_final_video_duration
from engine.logging_utils import get_stage_logger, setup_logging
from engine.manifest import (
    build_manifest,
    load_manifest,
    pipeline_output_from_context,
    save_manifest,
    scene_result_from_manifest,
)
from engine.stage import PipelineStage
from models.scene_schema import PipelineOutput
from pipeline.final_audio_stage import FinalStoryAudioStage
from pipeline.parse_stage import StoryParseStage
from pipeline.render_stage import SceneRenderStage
from pipeline.scene_builder_stage import SceneBuilderStage
from providers.bgm_provider import build_bgm_provider
from providers.image_provider import build_image_provider
from providers.story_parser_provider import build_story_parser_provider
from providers.tts_provider import build_tts_provider


class ManifestPersistStage(PipelineStage):
    """Final stage that writes manifest to disk."""

    @property
    def name(self) -> str:
        return "persist_manifest"

    def run(self, context: PipelineContext) -> None:
        manifest = build_manifest(context)
        save_manifest(manifest, context.paths.manifest_path)


class VideoExportStage(PipelineStage):
    """Best-effort final MP4 export stage."""

    @property
    def name(self) -> str:
        return "video_export"

    def run(self, context: PipelineContext) -> None:
        stage_logger = get_stage_logger(__name__, context.run_id, self.name)
        video_path = context.paths.run_dir / "video" / "final_video.mp4"
        try:
            video_path = export_video(context.paths.run_dir)
            context.metadata["final_video_path"] = str(video_path)
        except Exception as exc:  # noqa: BLE001
            context.record_warning(f"Video export degraded: {exc}")
            stage_logger.warning("Video export degraded: %s", exc)
        finally:
            duration_seconds, duration_source = self._resolve_total_duration(context, video_path, stage_logger)
            context.metadata["final_video_duration_seconds"] = duration_seconds
            context.metadata["final_duration_source"] = duration_source
            stage_logger.info(
                "Resolved total duration: %.6fs (source=%s)",
                duration_seconds,
                duration_source,
            )

    def _resolve_total_duration(
        self,
        context: PipelineContext,
        video_path: Path,
        stage_logger: logging.Logger,
    ) -> tuple[float, str]:
        ffprobe_bin = context.config.providers.ffprobe_binary_path

        if video_path.exists():
            try:
                duration = probe_final_video_duration(video_path, ffprobe_bin=ffprobe_bin)
                if duration > 0:
                    return float(duration), "final_video.mp4"
            except Exception as exc:  # noqa: BLE001
                stage_logger.warning("Duration probe failed for final video: %s", exc)

        final_audio_path = context.paths.final_story_path
        if final_audio_path.exists():
            try:
                duration = get_media_duration(final_audio_path, ffprobe_bin=ffprobe_bin)
                if duration > 0:
                    return float(duration), "final/story.mp3"
            except Exception as exc:  # noqa: BLE001
                stage_logger.warning("Duration probe failed for final story audio: %s", exc)

        narration_total = 0.0
        narration_count = 0
        for narration_path in sorted(context.paths.audio_dir.glob("scene_*.wav")):
            try:
                duration = get_media_duration(narration_path, ffprobe_bin=ffprobe_bin)
            except Exception as exc:  # noqa: BLE001
                stage_logger.warning("Duration probe failed for scene narration %s: %s", narration_path, exc)
                continue
            if duration > 0:
                narration_total += float(duration)
                narration_count += 1

        if narration_total > 0:
            return narration_total, f"sum(scene narration .wav):{narration_count}"

        return 0.0, "unresolved"


class PipelineRunner:
    """Coordinates stage execution and produces final output."""

    def __init__(self, stages: list[PipelineStage] | None = None):
        self.config = ENGINE_SETTINGS
        setup_logging(self.config.log_level, PROJECT_ROOT / "story_engine.log")
        self.logger = logging.getLogger(__name__)
        self._stages = stages or self._build_default_stages()

    def _build_default_stages(self) -> list[PipelineStage]:
        story_parser_provider = build_story_parser_provider(self.config.parser)
        image_provider = build_image_provider(self.config.providers)
        tts_provider = build_tts_provider(self.config.providers)
        bgm_provider = build_bgm_provider(self.config.providers)
        return [
            StoryParseStage(parser_provider=story_parser_provider),
            SceneBuilderStage(),
            SceneRenderStage(
                image_provider=image_provider,
                tts_provider=tts_provider,
                bgm_provider=bgm_provider,
            ),
            FinalStoryAudioStage(),
            VideoExportStage(),
            ManifestPersistStage(),
        ]

    def _resolve_paths(self, run_id: str) -> RunPaths:
        run_dir = self.config.output.base_output_dir / run_id
        images_dir = run_dir / self.config.output.images_dirname
        audio_dir = run_dir / self.config.output.audio_dirname
        bgm_dir = run_dir / self.config.output.bgm_dirname
        mixed_dir = run_dir / self.config.output.mixed_dirname
        final_dir = run_dir / self.config.output.final_dirname
        final_story_path = final_dir / self.config.output.final_story_filename
        manifest_path = run_dir / self.config.output.manifest_filename
        return RunPaths(
            run_dir=run_dir,
            images_dir=images_dir,
            audio_dir=audio_dir,
            bgm_dir=bgm_dir,
            mixed_dir=mixed_dir,
            final_dir=final_dir,
            final_story_path=final_story_path,
            manifest_path=manifest_path,
        )

    def _create_context(
        self,
        story_text: str,
        story_title: str,
        story_author: str,
        run_id: str | None,
        resume: bool,
    ) -> PipelineContext:
        actual_run_id = run_id or datetime.now(UTC).strftime("%Y%m%d_%H%M%S") + f"_{uuid.uuid4().hex[:8]}"
        paths = self._resolve_paths(actual_run_id)

        paths.images_dir.mkdir(parents=True, exist_ok=True)
        paths.audio_dir.mkdir(parents=True, exist_ok=True)
        paths.bgm_dir.mkdir(parents=True, exist_ok=True)
        paths.mixed_dir.mkdir(parents=True, exist_ok=True)
        paths.final_dir.mkdir(parents=True, exist_ok=True)

        context = PipelineContext(
            run_id=actual_run_id,
            story_input=story_text,
            story_title=story_title,
            story_author=story_author,
            config=self.config,
            paths=paths,
            resume=resume,
        )

        if resume:
            prior_manifest = load_manifest(paths.manifest_path)
            if prior_manifest:
                for serialized_result in prior_manifest.scene_results:
                    result = scene_result_from_manifest(serialized_result)
                    context.scene_results[result.scene_id] = result
                context.metadata["resumed_from_manifest"] = True
                context.metadata["prior_status"] = prior_manifest.status
        return context

    def _run_with_timeout(self, stage: PipelineStage, context: PipelineContext) -> None:
        timeout = self.config.retry.stage_timeout_seconds
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(stage.run, context)
            try:
                future.result(timeout=timeout)
            except FutureTimeoutError as exc:
                raise StageTimeoutError(
                    f"Stage '{stage.name}' timed out after {timeout} seconds"
                ) from exc

    def _execute_stage(self, stage: PipelineStage, context: PipelineContext) -> None:
        stage_logger = get_stage_logger(__name__, context.run_id, stage.name)

        if stage.should_skip(context):
            context.stage_state[stage.name] = StageExecutionState(status="skipped")
            stage_logger.info("Stage skipped by should_skip()")
            return

        attempts = self.config.retry.stage_attempts
        state = context.stage_state.setdefault(stage.name, StageExecutionState())

        for attempt in range(1, attempts + 1):
            state.attempts = attempt
            state.started_at = datetime.now(UTC).isoformat()
            started = datetime.now(UTC)
            warning_count_before = len(context.warnings)
            stage_logger.info("Stage attempt %s/%s started", attempt, attempts)
            try:
                self._run_with_timeout(stage, context)
                ended = datetime.now(UTC)
                state.completed_at = ended.isoformat()
                state.duration_seconds = (ended - started).total_seconds()
                new_warnings = len(context.warnings) > warning_count_before
                state.status = "completed_with_warnings" if new_warnings else "completed"
                state.error = None
                stage_logger.info("Stage completed in %.2fs", state.duration_seconds)
                return
            except StageTimeoutError as exc:
                ended = datetime.now(UTC)
                state.completed_at = ended.isoformat()
                state.duration_seconds = (ended - started).total_seconds()
                if hasattr(stage, "recover_from_timeout"):
                    recovered = stage.recover_from_timeout(context, str(exc))
                    if recovered:
                        state.status = "completed_with_warnings"
                        state.error = None
                        stage_logger.warning("Stage timeout recovered via fallback: %s", exc)
                        return
                state.status = "failed"
                state.error = str(exc)
                stage_logger.error(str(exc))
            except Exception as exc:  # noqa: BLE001
                ended = datetime.now(UTC)
                state.completed_at = ended.isoformat()
                state.duration_seconds = (ended - started).total_seconds()
                state.status = "failed"
                state.error = str(exc)
                stage_logger.exception("Stage failed")

        raise StageExecutionError(
            f"Stage '{stage.name}' failed after {attempts} attempts: {state.error}"
        )

    def run(
        self,
        story_text: str,
        story_title: str = "Default Story",
        story_author: str = "Anonymous",
        resume: bool = False,
        run_id: str | None = None,
    ) -> PipelineOutput:
        """Run configured stages and return output."""

        context = self._create_context(
            story_text=story_text,
            story_title=story_title,
            story_author=story_author,
            run_id=run_id,
            resume=resume,
        )

        run_logger = get_stage_logger(__name__, context.run_id, "runner")
        run_logger.info("Pipeline run started")

        try:
            for stage in self._stages:
                self._execute_stage(stage, context)
            if context.errors:
                context.status = "failed"
            elif context.warnings:
                context.status = "completed_with_warnings"
            else:
                context.status = "completed"
        except StageExecutionError as exc:
            context.record_error(str(exc))
            context.status = "failed"
            run_logger.error("Pipeline failed: %s", exc)
        finally:
            context.completed_at = datetime.now(UTC).isoformat()
            try:
                manifest = build_manifest(context)
                save_manifest(manifest, context.paths.manifest_path)
            except Exception as exc:  # noqa: BLE001
                context.record_error(f"Failed to persist manifest: {exc}")
                run_logger.exception("Manifest persistence failed")

        run_logger.info("Pipeline run finished with status=%s", context.status)
        return pipeline_output_from_context(context)
