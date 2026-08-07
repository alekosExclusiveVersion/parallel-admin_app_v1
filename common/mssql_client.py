"""
common/mssql_client.py

Единая точка работы с Microsoft SQL Server (pymssql).

Интерфейс повторяет MySQLClient (connect / query / list_databases /
server_catalog / database_table_sizes / kill_connection / connection_id),
чтобы воркеры могли работать с обоими движками через client_for().

Соединения кэшируются по потокам: пара (host, database) переиспользует
одно соединение между последовательными запросами, idle-кэш потока
ограничен (pool_idle / idle_timeout).
"""

from __future__ import annotations

import atexit
import re
import threading
import time
from contextlib import contextmanager
from typing import Any

import pymssql

from common.config import config
from common.logger import logger
from common.server_registry import registry

_SYSTEM_DBS = frozenset(
    ("master", "tempdb", "model", "msdb",
     "information_schema", "performance_schema", "mysql", "sys"),
)


class MSSQLClient:
    def __init__(self) -> None:
        self.cfg = config.mssql
        self._local = threading.local()
        atexit.register(self.close_all)

    # ----------------------------------------------------------
    # Пул соединений (переиспользование в рамках одного потока)
    # ----------------------------------------------------------

    def _pool_state(self) -> dict:
        state = getattr(self._local, "pool", None)
        if state is None:
            state = {}
            self._local.pool = state
        return state

    def _open_connection(self, host: str, database: str | None = None):
        user, password, port = registry.credentials_for(host)
        conn = None
        last_error = None

        for attempt in range(1, self.cfg.retry + 1):
            try:
                conn = pymssql.connect(
                    server=host,
                    port=port,
                    user=user,
                    password=password,
                    database=database,
                    login_timeout=self.cfg.connect_timeout,
                    as_dict=True,
                    tds_version="7.0",
                )
                break
            except Exception as ex:
                last_error = ex
                logger.warning(
                    f"{host}: попытка {attempt}/{self.cfg.retry} подключения "
                    f"не удалась ({ex})"
                )
                time.sleep(1)

        if conn is None:
            raise RuntimeError(
                f"Не удалось подключиться к {host}: {last_error}"
            )

        conn._psql_host = host
        conn._psql_db = database
        conn._psql_spid = None

        try:
            conn.autocommit(True)
        except Exception:
            pass

        try:
            with conn.cursor() as cur:
                cur.execute("SELECT @@SPID AS spid")
                row = cur.fetchone()
                if row:
                    conn._psql_spid = int(row.get("spid") or 0) or None
        except Exception:
            pass

        return conn

    def _acquire(self, host: str, database: str | None = None):
        key = (host, database)
        state = self._pool_state()
        entry = state.get(key)

        if entry is None:
            conn = self._open_connection(host, database)
            entry = {"conn": conn, "depth": 0, "last_used": time.monotonic()}
            state[key] = entry

        entry["depth"] += 1
        entry["last_used"] = time.monotonic()
        return entry["conn"]

    def _release(self, host: str, database: str | None = None) -> None:
        state = self._pool_state()
        key = (host, database)
        entry = state.get(key)

        if entry is None:
            return

        entry["depth"] -= 1

        if entry["depth"] <= 0:
            entry["depth"] = 0
            self._evict_idle()

    def _evict_idle(self) -> None:
        """Закрывает простаивающие соединения: сверх per-thread лимита
        (pool_idle) или простоявшие дольше idle_timeout."""
        state = self._pool_state()
        now = time.monotonic()
        pool_idle = max(1, self.cfg.pool_idle)
        idle_timeout = self.cfg.idle_timeout

        idle = [
            (key, entry)
            for key, entry in state.items()
            if entry["depth"] == 0
        ]
        idle.sort(key=lambda kv: kv[1]["last_used"])

        if len(idle) > pool_idle:
            for key, entry in idle[: len(idle) - pool_idle]:
                self._discard(state, key, entry)
            idle = idle[len(idle) - pool_idle:]

        if idle_timeout > 0:
            cutoff = now - idle_timeout
            for key, entry in idle:
                if entry["last_used"] < cutoff:
                    self._discard(state, key, entry)

    def _discard(self, state: dict, key, entry: dict) -> None:
        try:
            entry["conn"].close()
        except Exception:
            pass
        del state[key]

    def close_all(self) -> None:
        state = self._pool_state()
        for key in list(state.keys()):
            self._discard(state, key, state[key])

    @contextmanager
    def connect(self, host: str, database: str | None = None):
        conn = self._acquire(host, database)

        try:
            yield conn
        finally:
            self._release(host, database)

    def execute_on_connection(self, conn, sql: str, params=None):
        try:
            with conn.cursor() as cur:
                cur.execute(sql, params)

                if cur.description is not None:
                    return cur.fetchall()
                return []
        except Exception:
            # Разрыв соединения — один повтор на свежем соединении.
            if not getattr(conn, "closed", False):
                raise

            host = getattr(conn, "_psql_host", None)
            database = getattr(conn, "_psql_db", None)

            if not host:
                raise

            logger.warning(f"{host}: соединение разорвано, повтор запроса")

            new_conn = self._open_connection(host, database)

            try:
                with new_conn.cursor() as cur:
                    cur.execute(sql, params)

                    if cur.description is not None:
                        return cur.fetchall()
                    return []
            finally:
                try:
                    new_conn.close()
                except Exception:
                    pass

    def query(self, host: str, sql: str, database: str | None = None,
              params: tuple[Any, ...] | None = None) -> list[dict]:
        with self.connect(host, database) as conn:
            return self.execute_on_connection(conn, sql, params)

    # ----------------------------------------------------------
    # Список БД
    # ----------------------------------------------------------

    def _filtered_databases(self, host: str, with_prefix: bool) -> list[str]:
        rows = self.query(host, "SELECT name FROM sys.databases")

        ignore = set(config.advanced.ignore_databases) | _SYSTEM_DBS

        names = [
            row.get("name")
            for row in rows
            if row.get("name") not in ignore
        ]

        if with_prefix:
            prefix = config.filter.database_prefix
            pattern = config.filter.exclude_database_regex
            names = [
                db
                for db in names
                if db.startswith(prefix) and not re.search(pattern, db)
            ]

        return sorted(names)

    def list_databases(self, host: str) -> list[str]:
        return self._filtered_databases(host, with_prefix=True)

    def list_all_databases(self, host: str) -> list[str]:
        return self._filtered_databases(host, with_prefix=False)

    # ----------------------------------------------------------
    # Размеры БД и таблиц
    # ----------------------------------------------------------

    def database_sizes(self, host: str) -> dict[str, int]:
        sql = """
SELECT
    DB_NAME(database_id) AS db,
    SUM(size) * 8 * 1024 AS total_bytes
FROM sys.master_files
WHERE type = 0
GROUP BY database_id
"""
        rows = self.query(host, sql)

        ignore = set(config.advanced.ignore_databases) | _SYSTEM_DBS

        return {
            row["db"]: int(row["total_bytes"] or 0)
            for row in rows
            if row.get("db") and row["db"] not in ignore
        }

    def server_catalog(
        self,
        host: str,
    ) -> tuple[dict[str, int], dict[str, list[tuple[str, int]]]]:
        """Размеры всех БД сервера. Таблицы возвращаются пустыми —
        загружаются при раскрытии БД (fallback request_tables)."""
        return self.database_sizes(host), {}

    def database_table_sizes(
        self,
        host: str,
        database: str,
    ) -> list[tuple[str, int]]:
        sql = """
SELECT
    CASE WHEN s.name = 'dbo' THEN t.name ELSE s.name + N'.' + t.name END
        AS table_name,
    SUM(a.total_pages) * 8 * 1024 AS total_bytes
FROM sys.tables t
JOIN sys.schemas s ON t.schema_id = s.schema_id
JOIN sys.indexes i ON t.object_id = i.object_id
JOIN sys.partitions p ON i.object_id = p.object_id AND i.index_id = p.index_id
JOIN sys.allocation_units a ON p.partition_id = a.container_id
WHERE a.type IN (1, 2)
GROUP BY s.name, t.name
ORDER BY total_bytes DESC
"""
        rows = self.query(host, sql, database)

        return [
            (row["table_name"], int(row["total_bytes"] or 0))
            for row in rows
            if row.get("table_name")
        ]

    # ----------------------------------------------------------
    # Прерывание запросов
    # ----------------------------------------------------------

    def kill_connection(self, host: str, connection_id: int) -> None:
        """Прерывает запрос через KILL (отдельным соединением)."""
        with self.connect(host) as conn:
            with conn.cursor() as cur:
                cur.execute(f"KILL {int(connection_id)}")

    def connection_id(self, conn) -> int | None:
        """SPID соединения для прерывания активного запроса."""
        return getattr(conn, "_psql_spid", None)

    def test_connection(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
    ) -> tuple[bool, str]:
        """Проверка подключения с явными реквизитами (для диалога сервера)."""
        try:
            conn = pymssql.connect(
                server=host,
                port=port,
                user=user,
                password=password,
                login_timeout=self.cfg.connect_timeout,
            )
            conn.close()
        except Exception as ex:
            return False, str(ex)

        return True, ""


mssql = MSSQLClient()


if __name__ == "__main__":
    print("MSSQL client loaded.")
