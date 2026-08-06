"""
backend/db_sizes_worker.py

Фоновая загрузка размеров баз данных и таблиц для дерева серверов.

Используется постоянный поток-потребитель с очередью задач:
раскрытие узла кладёт запрос в очередь, а worker выполняет его
и возвращает результат через сигналы. Это корректно обрабатывает
быстрые последовательные раскрытия нескольких узлов.
"""

from __future__ import annotations

import threading
from collections import deque

from PySide6.QtCore import QObject, Signal, Slot

from common.mysql_client import mysql


class DbSizesWorker(QObject):
    databases = Signal(str, dict)      # server, {db: size_bytes}
    tables = Signal(str, str, list)    # server, database, [(table, size_bytes)]
    error = Signal(str, str, str)      # server, context, message
    finished = Signal()

    def __init__(self):
        super().__init__()
        self._queue: deque[tuple] = deque()
        self._cv = threading.Condition()
        self._stop = False

    def request_databases(self, servers: list[str]):
        with self._cv:
            self._queue.append(("databases", list(servers)))
            self._cv.notify()

    def request_tables(self, server: str, database: str):
        with self._cv:
            self._queue.append(("tables", server, database))
            self._cv.notify()

    def stop(self):
        with self._cv:
            self._stop = True
            self._cv.notify()

    @Slot()
    def run(self):
        while True:
            with self._cv:
                while not self._queue and not self._stop:
                    self._cv.wait(timeout=0.5)
                if self._stop:
                    break
                task = self._queue.popleft()

            kind = task[0]

            if kind == "databases":
                servers = task[1]
                for server in servers:
                    if self._stop:
                        break
                    try:
                        sizes = mysql.database_sizes(server)
                        self.databases.emit(server, sizes)
                    except Exception as ex:
                        self.error.emit(server, "databases", str(ex))
            else:
                _, server, database = task
                try:
                    sizes = mysql.database_table_sizes(server, database)
                    self.tables.emit(server, database, sizes)
                except Exception as ex:
                    self.error.emit(server, database, str(ex))

        self.finished.emit()
