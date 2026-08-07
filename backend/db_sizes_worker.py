"""
backend/db_sizes_worker.py

Фоновая загрузка размеров баз данных и таблиц для дерева серверов.

Worker живёт в постоянном QThread: run() мгновенно возвращается, поток
остаётся в Qt event loop (exec), а запросы приходят слотами
request_databases()/request_tables() через queued-соединение из GUI-потока.

Каталог сервера (server_catalog — размеры БД и таблицы) загружается
параллельно через ThreadPoolExecutor: каждый сервер обрабатывается в
отдельном потоке, соединения выдаются общим пулом клиентов. Имена БД
(list_all_databases) отдаются сразу — это быстрый запрос, и дерево
начинает показывать узлы ещё до поступления размеров.

ВНИМАНИЕ: слоты не должны блокировать поток собственным while-циклом
(например, на Condition) — тогда до event loop не дойдёт очередь и
queued-слоты никогда не вызовутся. Поэтому ожидание результатов пула
внутри слота не выполняется: каталог загружается в фоновых потоках,
а готовые данные приходят сигналами.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from PySide6.QtCore import QObject, Signal, Slot

from common.config import config
from common.server_registry import client_for


class DbSizesWorker(QObject):
    databases_names = Signal(str, list)   # server, [db_names]
    databases = Signal(str, dict)         # server, {db: size_bytes}
    server_tables = Signal(str, dict)     # server, {db: [(table, size_bytes)]}
    tables = Signal(str, str, list)       # server, database, [(table, size_bytes)]
    error = Signal(str, str, str)         # server, context, message
    finished = Signal()

    def __init__(self):
        super().__init__()
        self._stop = False
        self._executor = ThreadPoolExecutor(
            max_workers=max(1, config.parallel.database_workers),
            thread_name_prefix="sizes",
        )

    def stop(self):
        self._stop = True
        self._executor.shutdown(wait=False, cancel_futures=True)
        self.finished.emit()

    @Slot()
    def run(self):
        """Оставляем поток живым: задача выполняется слотами request_*,
        вызываемыми queued-соединением в event loop потока."""
        pass

    @Slot(list)
    def request_databases(self, servers: list[str]):
        if self._stop:
            return

        for server in servers:
            if self._stop:
                return

            # 1) Имена БД — мгновенно (быстрый список).
            try:
                names = client_for(server).list_all_databases(server)
            except Exception as ex:
                self.error.emit(server, "databases", str(ex))
                continue

            self.databases_names.emit(server, names)

            # 2) Размеры + таблицы — параллельно в пуле.
            self._submit_catalog(server, "databases")

    @Slot(list)
    def refresh_sizes(self, servers: list[str]):
        """Неразрушающее обновление данных раскрытых серверов.

        Используется после check/search: размеры обновляются в тексте
        узлов (apply_sizes) и кэш таблиц обновляется (apply_server_tables),
        при этом раскрытое состояние дерева сохраняется.
        """
        if self._stop:
            return

        for server in servers:
            if self._stop:
                return
            self._submit_catalog(server, "refresh")

    def _submit_catalog(self, server: str, context: str) -> None:
        if self._stop:
            return

        try:
            self._executor.submit(self._load_catalog, server, context)
        except RuntimeError:
            pass

    def _load_catalog(self, server: str, context: str) -> None:
        if self._stop:
            return

        try:
            sizes, tables = client_for(server).server_catalog(server)
        except Exception as ex:
            if not self._stop:
                self.error.emit(server, context, str(ex))
            return

        if self._stop:
            return

        self.databases.emit(server, sizes)
        self.server_tables.emit(server, tables)

    @Slot(str, str)
    def request_tables(self, server: str, database: str):
        """Фолбэк: загрузка таблиц одной БД (если в кэше сервера их нет)."""
        if self._stop:
            return

        try:
            sizes = client_for(server).database_table_sizes(server, database)
            self.tables.emit(server, database, sizes)
        except Exception as ex:
            self.error.emit(server, database, str(ex))
