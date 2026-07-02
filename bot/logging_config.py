"""
Centralized logging setup.

Every layer of the bot obtains its logger via `logging.getLogger(__name__)`
after `setup_logging()` has been called once from the CLI entry point.
Logs go to both the console (concise) and `logs/trading.log` (detailed,
rotating), so troubleshooting a failed order never requires reproducing it.
"""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

from bot.config import LOG_DIRECTORY, LOG_FILE_PATH

_LOGGING_CONFIGURED = False

_FILE_LOG_FORMAT = (
    "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
)
_CONSOLE_LOG_FORMAT = "%(levelname)-8s | %(message)s"


def setup_logging(verbose: bool = False) -> None:
    """Configure root logging handlers exactly once per process.

    Args:
        verbose: If True, the console handler also emits DEBUG messages.
            The log file always captures INFO and above.
    """
    global _LOGGING_CONFIGURED
    if _LOGGING_CONFIGURED:
        return

    LOG_DIRECTORY.mkdir(parents=True, exist_ok=True)
    _ensure_log_file_exists(LOG_FILE_PATH)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    file_handler = logging.handlers.RotatingFileHandler(
        LOG_FILE_PATH, maxBytes=2_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter(_FILE_LOG_FORMAT))

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG if verbose else logging.WARNING)
    console_handler.setFormatter(logging.Formatter(_CONSOLE_LOG_FORMAT))

    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    # Quiet down noisy third-party loggers; we care about our own events.
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    _LOGGING_CONFIGURED = True


def _ensure_log_file_exists(path: Path) -> None:
    """Create an empty log file if it does not already exist."""
    if not path.exists():
        path.touch()
