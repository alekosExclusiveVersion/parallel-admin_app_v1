"""
common/mysql_client.py

Единая точка работы с MySQL.

Соединения кэшируются по потокам: каждый поток переиспользует одно
соединение для пары (host, database) между последовательными запросами,
а idle-кэш потока ограничен (pool_idle). Это резко снижает число
одновременных коннектов при батчинге, поиске размеров и мульти-запросах.

Чтобы сервер не держал лишние соединения:
  - глобальный лимит простаивающих соединений (max_idle_connections) —
    общий для всех потоков, кэш не может превысить его;
  - idle_timeout — простаивающее соединение закрывается, если не
    использовалось дольше этого времени;
  - жёсткий потолок одновременных соединений (max_connections) через
    BoundedSemaphore.

Разорванные соединения пересоздаются, транзиентные ошибки (2006/2013/1927)
повторяются один раз на свежем соединении.
"""

from __future__ import annotations

import atexit
import re
import threading
import time
from contextlib import contextmanager
from typing import Any

import pymysql
from pymysql.cursors import DictCursor
from pymysql.err import OperationalError

from common.config import config
from common.logger import logger
from common.mysql_session import session
from common.sql_builder import sql_builder

# Коды ошибок, означающих разрыв/невалидность соединения —
# после них запрос безопасно повторить на свежем соединении.
_RETRY_ERRNOS = {2006, 2013, 1927, 1053}


def _is_transient(ex: Exception) -> bool:
    if isinstance(ex, OperationalError) and ex.args:
        code = ex.args[0]
        if isinstance(code, int):
            return code in _RETRY_ERRNOS
    return False


class MySQLClient:
    def __init__(self) -> None:
        self.cfg = config.mysql
        self._query_hook = None
        self._hook_lock = threading.Lock()
        self._local = threading.local()
        self._conn_semaphore = threading.BoundedSemaphore(
            max(1, self.cfg.max_connections)
        )
        self._idle_lock = threading.Lock()
        self._idle_count = 0
        atexit.register(self.close_all)

    def set_query_hook(self, hook) -> None:
        with self._hook_lock:
            self._query_hook = hook

    def _get_query_hook(self):
        with self._hook_lock:
            return self._query_hook

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
        """Открывает соединение с ретраями. Слот пула занимается семафором."""
        conn = None
        last_error = None

        self._conn_semaphore.acquire()

        try:
            for attempt in range(1, self.cfg.retry + 1):
                try:
                    conn = pymysql.connect(
                        host=host,
                        user=session.user or self.cfg.user,
                        password=session.password or self.cfg.password,
                        database=database,
                        connect_timeout=self.cfg.connect_timeout,
                        read_timeout=self.cfg.read_timeout,
                        write_timeout=self.cfg.write_timeout,
                        cursorclass=DictCursor,
                        autocommit=True,
                        charset="utf8mb4",
                    )
                    break

                except Exception as ex:
                    last_error = ex
                    logger.warning(
                        f"{host}: попытка {attempt}/{self.cfg.retry} подключения не удалась ({ex})"
                    )
                    time.sleep(1)
        finally:
            if conn is None:
                self._conn_semaphore.release()

        if conn is None:
            raise RuntimeError(
                f"Не удалось подключиться к {host}: {last_error}"
            )

        conn._psql_db = database

        return conn

    def _discard_conn(self, conn) -> None:
        try:
            conn.close()
        except Exception:
            pass
        finally:
            self._conn_semaphore.release()

    def _is_alive(self, conn) -> bool:
        try:
            conn.ping(reconnect=False)
            return True
        except Exception:
            return False

    def _acquire(self, host: str, database: str | None = None):
        key = (host, database)
        state = self._pool_state()
        entry = state.get(key)

        if entry is None:
            conn = self._open_connection(host, database)
            entry = {"conn": conn, "depth": 0, "last_used": time.monotonic()}
            state[key] = entry
        elif entry["depth"] == 0:
            if not self._is_alive(entry["conn"]):
                # Соединение отвалилось в простое — пересоздаём.
                self._close_idle(entry)
                conn = self._open_connection(host, database)
                entry["conn"] = conn
            else:
                self._idle_dec()  # idle -> busy

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
            self._idle_inc()  # busy -> idle
            self._evict_idle()

    def _idle_inc(self) -> None:
        with self._idle_lock:
            self._idle_count += 1

    def _idle_dec(self) -> None:
        with self._idle_lock:
            if self._idle_count > 0:
                self._idle_count -= 1

    def _close_idle(self, entry: dict) -> None:
        """Закрывает простаивающее соединение и освобождает счётчик idle."""
        self._idle_dec()
        self._discard_conn(entry["conn"])

    def _evict_idle(self) -> None:
        """Ограничивает кэш простаивающих соединений потока.

        Закрывает лишние соединения, когда их больше, чем позволяет
        per-thread лимит (pool_idle), они простояли дольше idle_timeout,
        либо их общее число превышает глобальный лимит
        (max_idle_connections). Старые закрываются первыми (LRU).
        """
        state = self._pool_state()
        now = time.monotonic()
        pool_idle = max(1, self.cfg.pool_idle)
        idle_timeout = self.cfg.idle_timeout
        max_idle = max(1, self.cfg.max_idle_connections)

        idle = [
            (key, entry)
            for key, entry in state.items()
            if entry["depth"] == 0
        ]
        idle.sort(key=lambda kv: kv[1]["last_used"])

        # 1) Лимит idle-кэша одного потока.
        if len(idle) > pool_idle:
            for key, entry in idle[: len(idle) - pool_idle]:
                self._close_idle(entry)
                del state[key]
            idle = idle[len(idle) - pool_idle:]

        # 2) Таймаут простоя: соединение не переживает долгий простой.
        if idle_timeout > 0:
            cutoff = now - idle_timeout
            stale_keys = {
                key
                for key, entry in idle
                if entry["last_used"] < cutoff
            }
            idle = [
                (key, entry)
                for key, entry in idle
                if key not in stale_keys
            ]
            for key in stale_keys:
                self._close_idle(state[key])
                del state[key]

        # 3) Глобальный лимит простаивающих соединений всех потоков.
        with self._idle_lock:
            excess = self._idle_count - max_idle

        if excess > 0:
            for key, entry in idle[:excess]:
                self._close_idle(entry)
                del state[key]

    def close_all(self) -> None:
        """Закрывает все соединения текущего потока. Для CLI и завершения."""
        state = self._pool_state()

        for key, entry in list(state.items()):
            if entry["depth"] == 0:
                self._close_idle(entry)
            else:
                self._discard_conn(entry["conn"])
            del state[key]

    @contextmanager
    def connect(self, host: str, database: str | None = None):
        conn = self._acquire(host, database)

        try:
            yield conn
        finally:
            self._release(host, database)

    def execute_on_connection(
        self,
        conn,
        sql: str,
        params=None,
    ):

        hook = self._get_query_hook()

        if hook is not None:
            hook(
                sql,
                getattr(conn, "host", ""),
            )

        try:
            with conn.cursor() as cur:

                cur.execute(
                    sql,
                    params,
                )

                return cur.fetchall()

        except OperationalError as ex:
            if not _is_transient(ex):
                raise

            # Соединение разорвалось во время выполнения — повторяем
            # запрос один раз на свежем соединении.
            host = getattr(conn, "host", None)

            if not host:
                raise

            logger.warning(
                f"{host}: соединение разорвано ({ex}), повтор запроса"
            )

            new_conn = self._open_connection(
                host,
                getattr(conn, "_psql_db", None),
            )

            try:
                with new_conn.cursor() as cur:
                    cur.execute(sql, params)
                    return cur.fetchall()
            finally:
                self._discard_conn(new_conn)
        
    def list_databases_conn(
        self,
        conn,
    ):

        rows = self.execute_on_connection(
            conn,
            "SHOW DATABASES",
        )

        ignore = set(
            config.advanced.ignore_databases
        )

        prefix = config.filter.database_prefix
        pattern = config.filter.exclude_database_regex

        return [
            db
            for row in rows
            for db in row.values()
            if (
                db not in ignore
                and db.startswith(prefix)
                and not re.search(pattern, db)
            )
        ]

    def scan_settings_batch(
        self,
        conn,
        databases,
    ):

        rows = []

        for sql in sql_builder.build_scan_query(databases):
            rows.extend(
                self.execute_on_connection(
                    conn,
                    sql,
                )
            )

        return rows

    def get_settings_conn(
        self,
        conn,
        database,
    ):

        sql = f"""
    SELECT
        stg_name,
        stg_value
    FROM {sql_builder.quote_identifier(database)}.{sql_builder.quote_identifier(config.advanced.settings_table)}
    WHERE stg_name IN (%s,%s)
    """

        rows = self.execute_on_connection(
            conn,
            sql,
            (
                config.filter.country_setting,
                config.filter.target_setting,
            ),
        )

        return {
            r["stg_name"]: r["stg_value"]
            for r in rows
        }

    def query(self, host: str, sql: str, database: str | None = None,
              params: tuple[Any, ...] | None = None) -> list[dict]:
        with self.connect(host, database) as conn:
            return self.execute_on_connection(conn, sql, params)

    def list_databases(self, host: str) -> list[str]:
        """Список БД на сервере с учётом фильтров (prefix/regex/ignore)."""
        with self.connect(host) as conn:
            return self.list_databases_conn(conn)

    def search_databases(self, host: str, mask: str) -> list[str]:
        """Поиск БД по маске в стиле LIKE (например 'ar_%45').

        MySQL не поддерживает плейсхолдеры в `SHOW DATABASES LIKE`,
        поэтому маска экранируется через conn.escape() и подставляется
        вручную. Никаких дополнительных фильтров (prefix/regex/ignore)
        не применяется — маску задаёт пользователь явно.
        """
        mask = mask.strip()

        if not mask:
            return []

        with self.connect(host) as conn:
            escaped = conn.escape(mask)

            rows = self.execute_on_connection(
                conn,
                f"SHOW DATABASES LIKE {escaped}",
            )

        return [
            db
            for row in rows
            for db in row.values()
        ]

    def has_cfg_settings_conn(self, conn, database: str) -> bool:
        rows = self.execute_on_connection(
            conn,
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = %s AND table_name = %s LIMIT 1",
            (database, config.advanced.settings_table),
        )
        return bool(rows)

    def filter_databases_with_settings_conn(
        self,
        conn,
        databases: list[str],
    ) -> list[str]:
        """Оставляет БД, в которых есть таблица настроек.

        Один запрос на чанк (вместо отдельного запроса на каждую БД),
        что резко сокращает число обращений к серверу для больших списков.
        """
        if not databases:
            return []

        settings_table = config.advanced.settings_table
        found = set()

        for chunk in sql_builder.chunk(list(databases), 200):
            placeholders = ", ".join(["%s"] * len(chunk))

            rows = self.execute_on_connection(
                conn,
                "SELECT DISTINCT table_schema "
                "FROM information_schema.tables "
                "WHERE table_name = %s "
                f"AND table_schema IN ({placeholders})",
                (settings_table, *chunk),
            )

            found.update(
                row["table_schema"]
                for row in rows
            )

        return [db for db in databases if db in found]

    def has_cfg_settings(self, host: str, database: str) -> bool:
        with self.connect(host, database) as conn:
            return self.has_cfg_settings_conn(conn, database)

    def get_settings(self, host: str, database: str) -> dict[str, str]:
        """Возвращает country/target настройки БД по открытому соединению."""
        with self.connect(host, database) as conn:
            return self.get_settings_conn(conn, database)

    # ----------------------------------------------------------
    # Размеры БД и таблиц
    # ----------------------------------------------------------

    def kill_connection(self, host: str, connection_id: int) -> None:
        """Прерывает запрос на сервере через KILL (отдельным соединением)."""
        with self.connect(host) as conn:
            with conn.cursor() as cur:
                cur.execute(f"KILL {int(connection_id)}")

    def database_sizes(self, host: str) -> dict[str, int]:
        """Суммарный размер (в байтах) по каждой БД на сервере.

        Запрос читает статистику information_schema и не требует
        полного доступа к данным.
        """
        sql = """
SELECT
    table_schema AS db,
    SUM(data_length + index_length) AS total
FROM information_schema.tables
WHERE table_schema NOT IN ('information_schema', 'performance_schema', 'mysql', 'sys')
GROUP BY table_schema
ORDER BY table_schema
"""
        rows = self.query(host, sql)

        return {
            row["db"]: int(row["total"] or 0)
            for row in rows
            if row.get("db")
        }

    def database_table_sizes(
        self,
        host: str,
        database: str,
    ) -> list[tuple[str, int]]:
        """Список (таблица, размер в байтах) для одной БД.

        Соединение открывается без default-схемы (ключ пула (host, None)),
        поэтому последовательные вызовы для разных БД сервера
        переиспользуют одно и то же соединение.
        """
        sql = f"""
SELECT
    table_name AS table_name,
    (data_length + index_length) AS total
FROM information_schema.tables
WHERE table_schema = %s
ORDER BY total DESC
"""
        rows = self.query(host, sql, None, (database,))

        return [
            (row["table_name"], int(row["total"] or 0))
            for row in rows
            if row.get("table_name")
        ]


mysql = MySQLClient()


if __name__ == "__main__":
    print("MySQL client loaded.")
