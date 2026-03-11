"""Logging helpers with run/stage/scene context fields."""

import logging
from pathlib import Path


class ContextDefaultsFilter(logging.Filter):
    """Inject default contextual logging fields."""

    def filter(self, record: logging.LogRecord) -> bool:
        for key, default in (("run_id", "-"), ("stage", "-"), ("scene_id", "-")):
            if not hasattr(record, key):
                setattr(record, key, default)
        return True


def setup_logging(log_level: str, log_path: Path) -> None:
    """Configure root logger for console and file outputs."""

    logger = logging.getLogger()
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    if logger.handlers:
        return

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s [run=%(run_id)s stage=%(stage)s scene=%(scene_id)s] "
        "%(name)s - %(message)s"
    )

    context_filter = ContextDefaultsFilter()

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.addFilter(context_filter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    stream_handler.addFilter(context_filter)
    logger.addHandler(stream_handler)


def get_stage_logger(name: str, run_id: str, stage: str, scene_id: int | None = None) -> logging.LoggerAdapter:
    """Return logger adapter with context fields."""

    extra = {
        "run_id": run_id,
        "stage": stage,
        "scene_id": scene_id if scene_id is not None else "-",
    }
    return logging.LoggerAdapter(logging.getLogger(name), extra)
