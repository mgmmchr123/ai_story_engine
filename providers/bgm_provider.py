"""BGM provider interfaces and local-asset rule-based implementation."""

from abc import ABC, abstractmethod
import logging
from pathlib import Path
import shutil

from config import ProviderSettings
from models.scene_schema import Scene, scene_mood_value

logger = logging.getLogger(__name__)


class BGMProvider(ABC):
    """Selects or generates background music artifacts."""

    @abstractmethod
    def select(self, scene: Scene, params: dict[str, str], output_path: Path) -> Path:
        """Select/generate bgm file and return path."""


class RuleBasedBGMProvider(BGMProvider):
    """Select local BGM assets by mood+setting and copy into run output folder."""

    def __init__(self, settings: ProviderSettings):
        self.settings = settings
        self.assets_dir = Path(settings.bgm_assets_dir)

    def select(self, scene: Scene, params: dict[str, str], output_path: Path) -> Path:
        setting = str(params.get("setting") or scene.setting.value).strip().lower()
        mood = scene_mood_value(scene.mood).strip().lower()
        candidate = self._select_candidate(setting=setting, mood=mood)
        if not candidate:
            logger.warning(
                "[BGM] provider=rule_based scene_id=%s setting=%s mood=%s fallback=none reason=no_asset_found",
                scene.scene_id,
                setting,
                mood,
            )
            return output_path

        destination = output_path.with_suffix(candidate.suffix)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(candidate, destination)
        logger.info(
            "[BGM] provider=rule_based scene_id=%s setting=%s mood=%s asset=%s destination=%s",
            scene.scene_id,
            setting,
            mood,
            candidate,
            destination,
        )
        return destination

    def _select_candidate(self, setting: str, mood: str) -> Path | None:
        tracks = self._available_tracks()
        if not tracks:
            return None

        exact_name = f"{setting}_{mood}"
        exact = self._find_by_stem(tracks, exact_name)
        if exact:
            return exact

        by_setting = [track for track in tracks if setting in track.stem.lower()]
        if by_setting:
            for track in by_setting:
                if mood in track.stem.lower():
                    return track
            return by_setting[0]

        by_mood = [track for track in tracks if mood in track.stem.lower()]
        if by_mood:
            return by_mood[0]

        if self.settings.bgm_fallback_track:
            fallback = self._find_by_stem(tracks, self.settings.bgm_fallback_track)
            if fallback:
                return fallback

        for keyword in ("default", "fallback", "ambient"):
            fallback = self._find_contains(tracks, keyword)
            if fallback:
                return fallback

        return tracks[0]

    def _available_tracks(self) -> list[Path]:
        if not self.assets_dir.exists():
            return []
        candidates: list[Path] = []
        for extension in ("*.mp3", "*.wav", "*.ogg"):
            candidates.extend(self.assets_dir.rglob(extension))
        return sorted(candidates)

    @staticmethod
    def _find_by_stem(tracks: list[Path], stem: str) -> Path | None:
        normalized = stem.strip().lower()
        for track in tracks:
            if track.stem.lower() == normalized:
                return track
        return None

    @staticmethod
    def _find_contains(tracks: list[Path], token: str) -> Path | None:
        token = token.lower()
        for track in tracks:
            if token in track.stem.lower():
                return track
        return None


def build_bgm_provider(settings: ProviderSettings) -> BGMProvider:
    """Resolve provider from settings."""
    if settings.bgm_provider == "rule_based":
        return RuleBasedBGMProvider(settings=settings)
    raise ValueError(f"Unsupported BGM provider: {settings.bgm_provider}")
