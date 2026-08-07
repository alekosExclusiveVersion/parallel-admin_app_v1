"""
backend/query_worker.py

Выполнение произвольных SQL-запросов в фоновом потоке
для SQL Console.
"""

from __future__ import annotations

import time

from PySide6.QtCore import QObject, Signal, Slot

from common.mysql_client import mysql


ALL_DATABASES = "*"


class QueryWorker(QObject):
    started = Signal()
    finished = Signal()
    query = Signal(str)
    result = Signal(list, list, str)
    error = Signal(str)
    databases = Signal(list)

    started_target = Signal(int, int, str, str)
    result_target = Signal(str, str, list, list, str)
    error_target = Signal(str, str, str)
    stopped = Signal(int, int)

    def __init__(self):
        super().__init__()
        self._host = ""
        self._database = None
        self._sql = ""
        self._row_limit = 1000
        self._mode = "query"
        self._targets = []
        self._stop = False
        self._active_host = ""
        self._active_id = None

    def set_request(self, host, database, sql, row_limit=1000):
        self._host = host
        self._database = database or None
        self._sql = sql
        self._row_limit = row_limit
        self._mode = "query"
        self._stop = False
        self._active_host = ""
        self._active_id = None

    def set_databases_request(self, host):
        self._host = host
        self._database = None
        self._sql = ""
        self._mode = "databases"
        self._stop = False
        self._active_host = ""
        self._active_id = None

    def set_multi_request(self, targets, sql, row_limit=1000):
        self._targets = list(targets)
        self._sql = sql
        self._row_limit = row_limit
        self._mode = "multi"
        self._stop = False
        self._active_host = ""
        self._active_id = None

    def stop(self):
        self._stop = True

    def kill_active(self):
        """Прерывает выполняющийся запрос через KILL <connection_id>.

        Запускать в фоновом потоке: открывает отдельное соединение,
        поэтому сам по себе может блокироваться.
        """
        host = self._active_host
        conn_id = self._active_id

        if not host or conn_id is None:
            return

        try:
            mysql.kill_connection(host, conn_id)
        except Exception:
            pass

    def _execute_sql(
        self,
        host: str,
        database: str | None,
        sql: str,
        row_limit: int,
    ) -> tuple[list[list[str]], list[str], str]:
        """Выполняет SQL и возвращает (rows, columns, message)."""
        started_at = time.perf_counter()

        with mysql.connect(host, database) as conn:
            self._active_host = host
            self._active_id = conn.thread_id()

            try:
                with conn.cursor() as cur:
                    cur.execute(sql)

                    if cur.description is not None:
                        columns = [d[0] for d in cur.description]
                        rows = list(cur.fetchmany(row_limit + 1))
                        truncated = len(rows) > row_limit
                        rows = rows[:row_limit]

                        rows = [
                            ["Null" if value is None else str(value)
                             for value in row.values()]
                            for row in rows
                        ]

                        total = f">{row_limit}" if truncated else str(len(rows))
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
            finally:
                self._active_host = ""
                self._active_id = None

        return rows, columns, message

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

        if self._mode == "multi":
            self._run_multi()
            return

        self.query.emit(self._sql)

        try:
            rows, columns, message = self._execute_sql(
                self._host, self._database, self._sql, self._row_limit,
            )
        except Exception as ex:
            self.error.emit(str(ex))
            self.finished.emit()
            return

        self.result.emit(rows, columns, message)
        self.finished.emit()

    def _run_multi(self):

        done = 0

        for i, (host, database) in enumerate(self._targets, 1):

            if self._stop:
                break

            if database == ALL_DATABASES:
                try:
                    names = mysql.list_databases(host)
                except Exception as ex:
                    self.error_target.emit(host, "", str(ex))
                    done += 1
                    continue

                targets = [(host, name) for name in names]
            else:
                targets = [(host, database)]

            for host_name, db_name in targets:

                if self._stop:
                    break

                self.started_target.emit(
                    i,
                    len(self._targets),
                    host_name,
                    db_name,
                )

                self.query.emit(self._sql)

                try:
                    rows, columns, message = self._execute_sql(
                        host_name, db_name, self._sql, self._row_limit,
                    )
                except Exception as ex:
                    self.error_target.emit(host_name, db_name, str(ex))
                    continue

                done += 1

                self.result_target.emit(
                    host_name,
                    db_name,
                    rows,
                    columns,
                    message,
                )

        if self._stop:
            self.stopped.emit(done, len(self._targets))

        self.finished.emit()
