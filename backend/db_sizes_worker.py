"""
backend/db_sizes_worker.py

Фоновая загрузка размеров баз данных и таблиц для дерева серверов.

Worker живёт в постоянном QThread: run() мгновенно возвращается, поток
остаётся в Qt event loop (exec), а запросы приходят слотами
request_databases()/request_tables() через queued-соединение из GUI-потока.
Qt event loop и есть очередь задач — быстрые последовательные раскрытия
нескольких узлов обрабатываются по одному.

ВНИМАНИЕ: здесь нельзя блокировать поток собственным while-циклом
(например, на Condition) — тогда до event loop не дойдёт очередь и
queued-слоты никогда не вызовутся.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal, Slot

from common.mysql_client import mysql


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

    def stop(self):
        self._stop = True
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
                break

            # 1) Имена БД — мгновенно (быстрый SHOW DATABASES).
            try:
                names = mysql.list_all_databases(server)
            except Exception as ex:
                self.error.emit(server, "databases", str(ex))
                continue

            self.databases_names.emit(server, names)

            # 2) Размеры + таблицы — одним запросом к information_schema.
            try:
                sizes, tables = mysql.server_catalog(server)
            except Exception as ex:
                self.error.emit(server, "databases", str(ex))
                continue

            self.databases.emit(server, sizes)
            self.server_tables.emit(server, tables)

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
                break
            try:
                sizes, tables = mysql.server_catalog(server)
            except Exception as ex:
                self.error.emit(server, "refresh", str(ex))
                continue

            self.databases.emit(server, sizes)
            self.server_tables.emit(server, tables)

    @Slot(str, str)
    def request_tables(self, server: str, database: str):
        """Фолбэк: загрузка таблиц одной БД (если в кэше сервера их нет)."""
        if self._stop:
            return

        try:
            sizes = mysql.database_table_sizes(server, database)
            self.tables.emit(server, database, sizes)
        except Exception as ex:
            self.error.emit(server, database, str(ex))
