"""Central logging setup for the backend process."""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path


LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"
DEFAULT_LOG_PATH = Path(__file__).resolve().parents[2] / "logs" / "app.log"
_LOG_WIPED = False


def configure_logging(level: int = logging.INFO) -> Path:
    """Configure root logging once and return the active log file path."""
    global _LOG_WIPED

    log_path = Path(os.getenv("SLPFS_LOG_FILE", str(DEFAULT_LOG_PATH))).expanduser().resolve()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    if not _LOG_WIPED:
        log_path.write_text("", encoding="utf-8")
        _LOG_WIPED = True

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    formatter = logging.Formatter(LOG_FORMAT)
    active_file_paths = {
        Path(handler.baseFilename).resolve()
        for handler in root_logger.handlers
        if isinstance(handler, logging.FileHandler)
    }

    if log_path not in active_file_paths:
        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    return log_path
