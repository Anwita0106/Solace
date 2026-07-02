

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Iterator

try:
    from colorama import Fore, Style, init as colorama_init

    colorama_init(autoreset=True)
    _COLOR_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only without colorama
    _COLOR_AVAILABLE = False


class _NoColor:

    def __getattr__(self, _name: str) -> str:
        return ""


_FORE = Fore if _COLOR_AVAILABLE else _NoColor()
_STYLE = Style if _COLOR_AVAILABLE else _NoColor()


def color_text(text: str, color: str = "") -> str:
    palette = {
        "green": _FORE.GREEN,
        "red": _FORE.RED,
        "yellow": _FORE.YELLOW,
        "cyan": _FORE.CYAN,
        "bold": _STYLE.BRIGHT,
    }
    prefix = palette.get(color, "")
    if not prefix:
        return text
    reset = _STYLE.RESET_ALL if _COLOR_AVAILABLE else ""
    return f"{prefix}{text}{reset}"


def success(text: str) -> str:
    """Shortcut for green (success) colored text."""
    return color_text(text, "green")


def failure(text: str) -> str:
    """Shortcut for red (failure) colored text."""
    return color_text(text, "red")


def warning(text: str) -> str:
    """Shortcut for yellow (warning) colored text."""
    return color_text(text, "yellow")


def heading(text: str) -> str:
    """Shortcut for bold/cyan (heading) colored text."""
    return color_text(color_text(text, "bold"), "cyan")


@contextmanager
def timed_execution() -> Iterator["ExecutionTimer"]:
    """Context manager that measures wall-clock execution time.

    Usage:
        with timed_execution() as timer:
            do_work()
        print(timer.elapsed_seconds)
    """
    timer = ExecutionTimer()
    start = time.perf_counter()
    try:
        yield timer
    finally:
        timer.elapsed_seconds = time.perf_counter() - start


class ExecutionTimer:
    """Simple holder for elapsed time, populated by `timed_execution`."""

    def __init__(self) -> None:
        self.elapsed_seconds: float = 0.0
