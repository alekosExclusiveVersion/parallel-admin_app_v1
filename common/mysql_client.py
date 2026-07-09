"""
common/mysql_client.py

Единая точка работы с MySQL.
"""

from __future__ import annotations


import re
import time
from contextlib import contextmanager
from typing import Any

import pymysql
from pymysql.cursors import DictCursor

from common.config import config
from common.logger import logger
from common.mysql_session import session


class MySQLClient:
    def __init__(self) -> None:
        self.cfg = config.mysql

    @contextmanager
    def connect(self, host: str, database: str | None = None):
        conn = None
        last_error = None

        for attempt in range(1, self.cfg.retry + 1):
            try:
                conn = pymysql.connect(
                    host=host,
                    user=session.user,
                    password=session.password,
                    database=database,
                    connect_timeout=self.cfg.connect_timeout,
                    read_timeout=self.cfg.read_timeout,
                    write_timeout=self.cfg.write_timeout,
                    cursorclass=DictCursor,
                    autocommit=True,
                    charset="utf8mb4",
                )
                yield conn
                return

            except Exception as ex:
                last_error = ex
                logger.warning(
                    f"{host}: попытка {attempt}/{self.cfg.retry} подключения не удалась ({ex})"
                )
                time.sleep(1)

            finally:
                if conn:
                    conn.close()

        raise RuntimeError(
            f"Не удалось подключиться к {host}: {last_error}"
        )

    def execute_on_connection(
        self,
        conn,
        sql: str,
        params=None,
    ):

        with conn.cursor() as cur:

            cur.execute(
                sql,
                params,
            )

            return cur.fetchall()
        
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

    def get_settings_conn(
        self,
        conn,
        database,
    ):

        sql = f"""
    SELECT
        stg_name,
        stg_value
    FROM {database}.{config.advanced.settings_table}
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
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return cur.fetchall()

    def execute(self, host: str, sql: str, database: str | None = None,
                params: tuple[Any, ...] | None = None) -> int:
        with self.connect(host, database) as conn:
            with conn.cursor() as cur:
                affected = cur.execute(sql, params)
            conn.commit()
            return affected

    def list_databases(self, host: str) -> list[str]:
        rows = self.query(host, "SHOW DATABASES")
        ignore = set(config.advanced.ignore_databases)
        return [
            list(r.values())[0]
            for r in rows
            if list(r.values())[0] not in ignore
        ]

    def has_cfg_settings(self, host: str, database: str) -> bool:
        rows = self.query(
            host,
            "SHOW TABLES LIKE %s",
            database,
            (config.advanced.settings_table,),
        )
        return bool(rows)

    def get_settings(self, host: str, database: str) -> dict[str, str]:
        sql = f"""
SELECT
    stg_name,
    stg_value
FROM {config.advanced.settings_table}
WHERE stg_name IN (%s,%s)
"""
        rows = self.query(
            host,
            sql,
            database,
            (
                config.filter.country_setting,
                config.filter.target_setting,
            ),
        )
        return {r["stg_name"]: r["stg_value"] for r in rows}

    def update_setting(self, host: str, database: str,
                       name: str, value: str) -> int:
        sql = f"""
UPDATE {config.advanced.settings_table}
SET stg_value=%s
WHERE stg_name=%s
"""
        return self.execute(host, sql, database, (value, name))

mysql = MySQLClient()


if __name__ == "__main__":
    print("MySQL client loaded.")
