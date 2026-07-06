"""
common/worker.py

Параллельная обработка серверов.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Callable, Iterable, Any

from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)

from common.config import config
from common.logger import logger


@dataclass(slots=True)
class WorkerResult:
    server: str
    success: bool
    value: Any = None
    error: str | None = None


class WorkerPool:
    def __init__(self, max_workers: int | None = None):
        self.max_workers = max_workers or config.parallel.workers

    def run(
        self,
        servers: Iterable[str],
        worker: Callable[[str], Any],
    ) -> list[WorkerResult]:

        servers = [s.strip() for s in servers if s.strip()]
        results: list[WorkerResult] = []

        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            transient=False,
        ) as progress:

            task = progress.add_task(
                "Обработка серверов",
                total=len(servers),
            )

            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:

                futures = {
                    executor.submit(worker, server): server
                    for server in servers
                }

                for future in as_completed(futures):
                    server = futures[future]

                    try:
                        value = future.result()

                        results.append(
                            WorkerResult(
                                server=server,
                                success=True,
                                value=value,
                            )
                        )

                    except Exception as ex:
                        logger.error(f"{server}: {ex}")

                        results.append(
                            WorkerResult(
                                server=server,
                                success=False,
                                error=str(ex),
                            )
                        )

                    finally:
                        progress.advance(task)

        ok = sum(r.success for r in results)
        failed = len(results) - ok

        logger.info(
            f"Обработка завершена. Успешно: {ok}, ошибок: {failed}"
        )

        return results


worker_pool = WorkerPool()


if __name__ == "__main__":

    def demo(server: str):
        return f"{server} OK"

    servers = [
        "p7ru1",
        "p7ru3",
        "p7ru4",
    ]

    for item in worker_pool.run(servers, demo):
        print(item)
