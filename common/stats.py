"""
common/stats.py

Потокобезопасная статистика выполнения.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, asdict


@dataclass(frozen=True)
class StatisticsSnapshot:
    servers: int
    databases: int
    projects: int
    updated: int
    skipped: int
    errors: int
    elapsed: float
    servers_per_sec: float
    databases_per_sec: float


class Statistics:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.reset()

    def reset(self) -> None:
        with self._lock:
            self.started = time.time()
            self.servers = 0
            self.databases = 0
            self.projects = 0
            self.updated = 0
            self.skipped = 0
            self.errors = 0

    def server(self, count: int = 1) -> None:
        with self._lock:
            self.servers += count

    def database(self, count: int = 1) -> None:
        with self._lock:
            self.databases += count

    def project(self, count: int = 1) -> None:
        with self._lock:
            self.projects += count

    def updated_project(self, count: int = 1) -> None:
        with self._lock:
            self.updated += count

    def skipped_project(self, count: int = 1) -> None:
        with self._lock:
            self.skipped += count

    def error(self, count: int = 1) -> None:
        with self._lock:
            self.errors += count

    @property
    def elapsed(self) -> float:
        return time.time() - self.started

    def snapshot(self) -> StatisticsSnapshot:
        with self._lock:
            elapsed = self.elapsed
            return StatisticsSnapshot(
                servers=self.servers,
                databases=self.databases,
                projects=self.projects,
                updated=self.updated,
                skipped=self.skipped,
                errors=self.errors,
                elapsed=elapsed,
                servers_per_sec=self.servers / elapsed if elapsed else 0.0,
                databases_per_sec=self.databases / elapsed if elapsed else 0.0,
            )

    def summary(self) -> dict:
        return asdict(self.snapshot())


stats = Statistics()


if __name__ == "__main__":
    stats.server()
    stats.database(12)
    stats.project(10)
    stats.updated_project(9)
    stats.skipped_project(1)

    from pprint import pprint
    pprint(stats.summary())
