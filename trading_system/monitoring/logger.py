from __future__ import annotations

import logging
import logging.handlers
import sys
from pathlib import Path

LOG_DIR = Path("logs")
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(level: int = logging.INFO) -> None:
    """Configure structured logging to console and rotating file."""
    LOG_DIR.mkdir(exist_ok=True)

    root = logging.getLogger()
    root.setLevel(level)

    if root.handlers:
        return

    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    console.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))
    root.addHandler(console)

    file_handler = logging.handlers.RotatingFileHandler(
        LOG_DIR / "trading_bot.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))
    root.addHandler(file_handler)

    logging.getLogger("MetaTrader5").setLevel(logging.WARNING)
