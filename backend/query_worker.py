"""
backend/query_worker.py

Выполнение произвольных SQL-запросов в фоновом потоке
для SQL Console.
"""

import time

from PySide6.QtCore import QObject, Signal, Slot

from common.mysql_client import mysql


class QueryWorker(QObject):
    started = Signal()
    finished = Signal()
    query = Signal(str)
    result = Signal(list, list, str)
    error = Signal(str)
    databases = Signal(list)

    def __init__(self):
        super().__init__()
        self._host = ""
        self._database = None
        self._sql = ""
        self._row_limit = 1000
        self._mode = "query"

    def set_request(self, host, database, sql, row_limit=1000):
        self._host = host
        self._database = database or None
        self._sql = sql
        self._row_limit = row_limit
        self._mode = "query"

    def set_databases_request(self, host):
        self._host = host
        self._database = None
        self._sql = ""
        self._mode = "databases"

    @Slot()
    def run(self):

        self.started.emit()

        if self._mode == "databases":

            try:

                names = mysql.list_databases(self._host)

            except Exception as ex:

                self.error.emit(str(ex))
                self.finished.emit()
                return

            self.databases.emit(names)
            self.finished.emit()
            return

        self.query.emit(self._sql)

        started_at = time.perf_counter()

        try:

            with mysql.connect(
                self._host,
                self._database,
            ) as conn:

                with conn.cursor() as cur:

                    cur.execute(self._sql)

                    if cur.description is not None:

                        columns = [
                            d[0] for d in cur.description
                        ]

                        rows = cur.fetchmany(
                            self._row_limit + 1
                        )

                        truncated = (
                            len(rows) > self._row_limit
                        )

                        rows = rows[:self._row_limit]

                        rows = [
                            [
                                str(value)
                                for value in row.values()
                            ]
                            for row in rows
                        ]

                        total = (
                            f">{self._row_limit}"
                            if truncated
                            else str(len(rows))
                        )

                        message = (
                            f"{len(rows)} row(s) of {total} "
                            f"({time.perf_counter() - started_at:.2f} s)"
                        )

                    else:

                        columns = []
                        rows = []

                        message = (
                            f"{cur.rowcount} row(s) affected "
                            f"({time.perf_counter() - started_at:.2f} s)"
                        )

        except Exception as ex:

            self.error.emit(str(ex))
            self.finished.emit()
            return

        self.result.emit(rows, columns, message)
        self.finished.emit()
