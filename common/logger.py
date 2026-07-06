"""
common/logger.py
Потокобезопасное логирование и вывод в консоль.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path

from rich.console import Console

from common.config import config

_console = Console()
_lock = threading.Lock()


class AppLogger:
    def __init__(self) -> None:
        self.log_dir = config.logging.directory
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self.logger = logging.getLogger("parallel-admin")
        self.logger.setLevel(logging.INFO)
        self.logger.handlers.clear()

        fmt = logging.Formatter(
            "%(asctime)s | %(levelname)s | %(threadName)s | %(message)s"
        )

        run = logging.FileHandler(self.log_dir / config.logging.run, encoding="utf-8")
        run.setFormatter(fmt)
        self.logger.addHandler(run)

        err = logging.FileHandler(self.log_dir / config.logging.errors, encoding="utf-8")
        err.setLevel(logging.ERROR)
        err.setFormatter(fmt)
        self.logger.addHandler(err)

    def _print(self, style: str, prefix: str, message: str) -> None:
        with _lock:
            _console.print(f"[{style}]{prefix}[/{style}] {message}")

    def info(self, message: str) -> None:
        self.logger.info(message)
        if config.logging.verbose:
            self._print("cyan", "INFO ", message)

    def success(self, message: str) -> None:
        self.logger.info(message)
        self._print("green", " OK  ", message)

    def warning(self, message: str) -> None:
        self.logger.warning(message)
        self._print("yellow", "WARN ", message)

    def error(self, message: str) -> None:
        self.logger.error(message)
        self._print("red", "ERR  ", message)

    def exception(self, exc: Exception) -> None:
        self.logger.exception(str(exc))
        self._print("red", "EXC  ", str(exc))


logger = AppLogger()


if __name__ == "__main__":
    logger.info("Logger initialized")
    logger.success("Success example")
    logger.warning("Warning example")
    logger.error("Error example")
