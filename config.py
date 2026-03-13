"""Configuration for the AI Storytelling Engine."""

from dataclasses import dataclass, field
from pathlib import Path


PROJECT_ROOT = Path(__file__).parent.resolve()
ASSETS_DIR = PROJECT_ROOT / "assets"
BGM_DIR = ASSETS_DIR / "bgm"
OUTPUT_DIR = PROJECT_ROOT / "output"
RUNS_DIR = OUTPUT_DIR / "runs"
SAMPLE_STORY_PATH = ASSETS_DIR / "sample_story.txt"


@dataclass(frozen=True)
class RetrySettings:
    """Retry and timeout controls for pipeline execution."""

    stage_attempts: int = 2
    stage_timeout_seconds: int = 90
    scene_attempts: int = 2
    scene_timeout_seconds: int = 60


@dataclass(frozen=True)
class OutputSettings:
    """Filesystem layout for run outputs."""

    base_output_dir: Path = RUNS_DIR
    images_dirname: str = "images"
    audio_dirname: str = "audio"
    bgm_dirname: str = "bgm"
    mixed_dirname: str = "mixed"
    final_dirname: str = "final"
    final_story_filename: str = "story.mp3"
    manifest_filename: str = "manifest.json"


@dataclass(frozen=True)
class ProviderSettings:
    """Provider selection and basic placeholder output formats."""

    image_provider: str = "comfyui"
    tts_provider: str = "piper"
    bgm_provider: str = "rule_based"
    image_extension: str | None = None
    narration_extension: str = ".wav"
    bgm_extension: str = ".mp3"
    comfyui_base_url: str = "http://127.0.0.1:8188"
    comfyui_workflow_path: str = (
        r"C:\AI\ComfyUI-master\user\default\workflows\story_image_workflow_api.json"
    )
    comfyui_output_dir: str = r"C:\AI\ComfyUI-master\output"
    comfyui_timeout_seconds: int = 180
    comfyui_poll_interval_seconds: float = 1.0
    comfyui_negative_prompt: str = "blurry, low quality, distorted, text, watermark"
    comfyui_width: int | None = 1024
    comfyui_height: int | None = 1024
    comfyui_steps: int | None = 20
    comfyui_cfg: float | None = 8
    comfyui_seed: int | None = None
    comfyui_min_image_bytes: int = 10240
    tts_language: str = "en"
    tts_voice_name: str = "amy"
    tts_speaker_id: int | None = None
    piper_binary_path: str | None = r"C:\AI\piper\piper.exe"
    piper_model_path: str = r"C:\AI\piper\models\en_US-amy-medium.onnx"
    piper_config_path: str | None = r"C:\AI\piper\models\en_US-amy-medium.onnx.json"
    piper_timeout_seconds: int = 120
    piper_length_scale: float = 1.0
    piper_noise_scale: float = 0.667
    piper_noise_w: float = 0.8
    piper_min_audio_bytes: int = 1024
    bgm_assets_dir: Path = BGM_DIR
    bgm_fallback_track: str | None = None
    bgm_mix_reduction_db: float = 14.0
    mixed_audio_extension: str = ".mp3"
    ffmpeg_binary_path: str = r"C:\AI\ffmpeg\bin\ffmpeg.exe"
    ffprobe_binary_path: str = r"C:\AI\ffmpeg\bin\ffprobe.exe"

    def __post_init__(self) -> None:
        if self.image_extension is None:
            extension = ".txt" if self.image_provider == "placeholder" else ".png"
            object.__setattr__(self, "image_extension", extension)


@dataclass(frozen=True)
class ParserSettings:
    """Story parser provider settings."""

    provider: str = "ollama"
    extractor_kind: str = "deterministic"
    extractor_kwargs: dict[str, object] = field(default_factory=dict)
    ollama_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen2.5:7b"
    ollama_timeout_seconds: int = 90
    ollama_temperature: float = 0.0


@dataclass(frozen=True)
class EngineSettings:
    """Top-level engine settings."""

    max_scenes: int = 100
    log_level: str = "INFO"
    output: OutputSettings = field(default_factory=OutputSettings)
    retry: RetrySettings = field(default_factory=RetrySettings)
    providers: ProviderSettings = field(default_factory=ProviderSettings)
    parser: ParserSettings = field(default_factory=ParserSettings)


ENGINE_SETTINGS = EngineSettings()
CONFIG_SAMPLE_STORY = True
