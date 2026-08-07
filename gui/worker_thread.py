"""
gui/worker_thread.py

Хелпер для типовой связки QThread + QObject-worker.

Убирает повторяющийся шаблон:
    thread = QThread(parent)
    worker = Worker()
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    worker.finished.connect(thread.quit)
"""

from __future__ import annotations

from typing import Type, TypeVar

from PySide6.QtCore import QObject, QThread

T = TypeVar("T", bound=QObject)


class WorkerHost:
    """Создаёт QThread и переносит в него QObject-worker.

    `thread.started` запускает `worker.run()`, а `worker.finished`
    останавливает поток. Поток-хозяин остаётся у объекта WorkerHost,
    поэтому worker живёт ровно столько же, сколько поток.
    """

    def __init__(
        self,
        worker_cls: Type[T],
        parent: QObject | None = None,
        **worker_kwargs,
    ) -> None:
        self.thread = QThread(parent)
        self.worker = worker_cls(**worker_kwargs)
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.thread.quit)
