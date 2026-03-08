"""
utils/logger.py
Centralised logging with colour output and file rotation.
"""

import logging
import sys
from logging.handlers import RotatingFileHandler

try:
    import colorlog
    _HAS_COLOR = True
except ImportError:
    _HAS_COLOR = False

from config.model_config import LOG_LEVEL, LOG_FILE


def get_logger(name: str) -> logging.Logger:
    """
    Return a named logger.  First call for a given name configures handlers;
    subsequent calls return the cached logger unchanged.
    """
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)
    logger.setLevel(level)

    fmt_str = "%(asctime)s | %(name)-28s | %(levelname)-8s | %(message)s"
    date_fmt = "%Y-%m-%d %H:%M:%S"

    # ── Console handler ──────────────────────────────────────────────────────
    if _HAS_COLOR:
        color_fmt = (
            "%(log_color)s%(asctime)s | %(name)-28s | %(levelname)-8s%(reset)s"
            " | %(message)s"
        )
        console_handler = colorlog.StreamHandler(sys.stdout)
        console_handler.setFormatter(
            colorlog.ColoredFormatter(
                color_fmt,
                datefmt=date_fmt,
                log_colors={
                    "DEBUG": "cyan",
                    "INFO": "green",
                    "WARNING": "yellow",
                    "ERROR": "red",
                    "CRITICAL": "bold_red",
                },
            )
        )
    else:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(logging.Formatter(fmt_str, datefmt=date_fmt))

    logger.addHandler(console_handler)

    # ── File handler ─────────────────────────────────────────────────────────
    try:
        file_handler = RotatingFileHandler(
            LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
        )
        file_handler.setFormatter(logging.Formatter(fmt_str, datefmt=date_fmt))
        logger.addHandler(file_handler)
    except OSError:
        pass  # non-fatal – just skip file logging

    return logger
