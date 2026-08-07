"""
backend/query_worker.py

Выполнение произвольных SQL-запросов в фоновом потоке
для SQL Console.

Скрипт разбивается на отдельные операторы (common.sql_splitter),
и каждый выполняется последовательно на одном соединении. Результаты
агрегируются: первый оператор с результирующим набором задаёт колонки,
строки операторов с такими же колонками конкатенируются, операторы без
результата (INSERT/UPDATE/...) добавляют строки статуса. Операторы
с отличающимися колонками пропускаются и учитываются в сообщении.
"""

from __future__ import annotations

import time

from PySide6.QtCore import QObject, Signal, Slot

from common.mysql_client import mysql
from common.sql_splitter import split_statements


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
        self._statements = []
        self._stop = False
        self._active_host = ""
        self._active_id = None

    def set_request(self, host, database, sql, row_limit=1000):
        self._host = host
        self._database = database or None
        self._sql = sql
        self._statements = split_statements(sql or "")
        self._row_limit = row_limit
        self._mode = "query"
        self._stop = False
        self._active_host = ""
        self._active_id = None

    def set_databases_request(self, host):
        self._host = host
        self._database = None
        self._sql = ""
        self._statements = []
        self._mode = "databases"
        self._stop = False
        self._active_host = ""
        self._active_id = None

    def set_multi_request(self, targets, sql, row_limit=1000):
        self._targets = list(targets)
        self._sql = sql
        self._statements = split_statements(sql or "")
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

    def _execute_statement(
        self,
        conn,
        statement: str,
        row_limit: int,
    ) -> tuple[list[list[str]], list[str], str]:
        """Выполняет один оператор и возвращает (rows, columns, message)."""
        with conn.cursor() as cur:
            cur.execute(statement)

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
                message = f"{len(rows)} row(s) of {total}"
                return columns, rows, message

            return [], [], f"{cur.rowcount} row(s) affected"

    def _execute_sql(
        self,
        host: str,
        database: str | None,
        statements: list[str],
        row_limit: int,
    ) -> tuple[list[list[str]], list[str], str]:
        """Выполняет список операторов и возвращает агрегированный
        результат (rows, columns, message)."""
        started_at = time.perf_counter()

        with mysql.connect(host, database) as conn:
            self._active_host = host
            self._active_id = conn.thread_id()

            try:
                per_statement = []

                for statement in statements:
                    if self._stop:
                        break
                    per_statement.append(
                        self._execute_statement(conn, statement, row_limit)
                    )
            finally:
                self._active_host = ""
                self._active_id = None

        return self._combine_results(
            per_statement,
            time.perf_counter() - started_at,
        )

    @staticmethod
    def _combine_results(
        per_statement: list,
        elapsed: float,
    ) -> tuple[list[list[str]], list[str], str]:
        """Собирает результаты операторов в один набор строк/колонок.

        Колонки берутся из первого оператора, вернувшего набор строк;
        операторы с такими же колонками добавляют строки; операторы без
        результата попадают в текстовую часть сообщения; операторы с
        отличающимися колонками пропускаются (учитываются в сообщении).
        """
        if not per_statement:
            return [], [], f"No statements executed ({elapsed:.2f} s)"

        if len(per_statement) == 1:
            columns, rows, message = per_statement[0]
            return rows, columns, f"{message} ({elapsed:.2f} s)"

        columns = None
        rows: list[list[str]] = []
        parts: list[str] = []
        skipped = 0

        for cols, stmt_rows, message in per_statement:
            if not cols:
                parts.append(message)
                continue
            if columns is None:
                columns = cols
            if cols == columns:
                rows.extend(stmt_rows)
            else:
                skipped += 1

        if columns is not None:
            parts.insert(0, f"{len(rows)} row(s)")

        if skipped:
            parts.append(f"{skipped} statement(s) skipped (columns differ)")

        message = "; ".join(parts) or "No result"
        message += f" ({elapsed:.2f} s)"

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

        if not self._statements:
            self.error.emit("No SQL statements to run.")
            self.finished.emit()
            return

        self.query.emit(self._sql)

        try:
            rows, columns, message = self._execute_sql(
                self._host, self._database, self._statements, self._row_limit,
            )
        except Exception as ex:
            if self._stop:
                self.stopped.emit(0, 1)
            else:
                self.error.emit(str(ex))
            self.finished.emit()
            return

        if self._stop:
            self.stopped.emit(0, 1)
        else:
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
                        host_name, db_name, self._statements, self._row_limit,
                    )
                except Exception as ex:
                    if self._stop:
                        continue
                    self.error_target.emit(host_name, db_name, str(ex))
                    continue

                if self._stop:
                    break

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
