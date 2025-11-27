"""Central logging configuration."""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
import os
import sys
from pathlib import Path

LOG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "ghostline" / "logs"
LOG_FILE = LOG_DIR / "ghostline.log"


def configure_logging(level: int = logging.INFO) -> None:
    """Configure both console and rotating file logging."""

    LOG_DIR.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    file_handler = RotatingFileHandler(LOG_FILE, maxBytes=512_000, backupCount=5)
    file_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    if not root_logger.handlers:
        root_logger.addHandler(console_handler)
        root_logger.addHandler(file_handler)


def get_logger(name: str) -> logging.Logger:
    """Return a module-level logger with standard configuration."""

    logger = logging.getLogger(name)
    if not logger.handlers:
        configure_logging()
    return logger
