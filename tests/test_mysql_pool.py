"""
tests/test_mysql_pool.py

Тесты пула соединений common/mysql_client.py: переиспользование в рамках
потока, пересоздание мёртвых соединений, лимит idle-кэша, батч-фильтр
БД по наличию таблицы настроек и повтор запроса после разрыва.
"""

import unittest
from dataclasses import replace
from unittest.mock import patch

from pymysql.err import OperationalError

from common.mysql_client import MySQLClient
from common.sql_builder import sql_builder


class FakeCursor:
    def __init__(self, owner):
        self.owner = owner
        self._result = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params=None):
        self.owner.executions.append((sql, params))

        if self.owner.fail_times > 0:
            self.owner.fail_times -= 1
            raise OperationalError(2006, "Server has gone away")

        return 0

    def fetchall(self):
        return self.owner.result


class FakeConn:
    def __init__(self, factory, conn_id):
        self.factory = factory
        self.conn_id = conn_id
        self.host = "h1"
        self._psql_db = None
        self.alive = True
        self.closed = False
        self.executions = []
        self.result = []
        self.fail_times = 0

    def close(self):
        if not self.closed:
            self.closed = True
            self.factory.closed.append(self)

    def ping(self, reconnect=False):
        if not self.alive:
            raise OperationalError(2006, "Server has gone away")

    def cursor(self):
        return FakeCursor(self)


class ConnFactory:
    def __init__(self, result=None):
        self.opens = 0
        self.closed = []
        self.conns = []
        self.default_result = result or []

    def open(self, host, database=None):
        self.opens += 1
        conn = FakeConn(self, self.opens)
        conn.host = host
        conn._psql_db = database
        conn.result = list(self.default_result)
        self.conns.append(conn)
        return conn


class TestPoolReuse(unittest.TestCase):
    def setUp(self):
        self.factory = ConnFactory()
        self.client = MySQLClient()
        self.client._open_connection = self.factory.open
        self.client._discard_conn = lambda conn: conn.close()

    def test_sequential_connect_reuses_connection(self):
        with self.client.connect("h1") as c1:
            with self.client.connect("h1") as c2:
                self.assertIs(c1, c2)

        self.assertEqual(self.factory.opens, 1)

    def test_different_databases_get_own_connections(self):
        with self.client.connect("h1", "db1") as c1:
            with self.client.connect("h1", "db2") as c2:
                self.assertIsNot(c1, c2)

        self.assertEqual(self.factory.opens, 2)

    def test_dead_idle_connection_is_recreated(self):
        with self.client.connect("h1") as c1:
            pass

        c1.alive = False

        with self.client.connect("h1") as c2:
            self.assertIsNot(c1, c2)
            self.assertTrue(c1.closed)

        self.assertEqual(self.factory.opens, 2)

    def test_idle_cache_is_bounded(self):
        for i in range(10):
            with self.client.connect("h1", str(i)):
                pass

        state = self.client._pool_state()
        idle = [e for e in state.values() if e["depth"] == 0]

        self.assertLessEqual(len(idle), self.client.cfg.pool_idle)

    def test_close_all_closes_everything(self):
        for i in range(3):
            with self.client.connect("h1", str(i)):
                pass

        self.client.close_all()

        self.assertEqual(len(self.factory.closed), 3)
        self.assertEqual(self.client._pool_state(), {})


class TestGlobalIdleLimit(unittest.TestCase):
    def test_idle_count_tracks_acquire_release(self):
        factory = ConnFactory()
        client = MySQLClient()
        client._open_connection = factory.open
        client._discard_conn = lambda conn: conn.close()

        for i in range(3):
            with client.connect("h1", str(i)):
                pass

        self.assertEqual(client._idle_count, 3)

        with client.connect("h1", "0"):
            pass

        self.assertEqual(client._idle_count, 3)

        client.close_all()
        self.assertEqual(client._idle_count, 0)

    def test_global_idle_cap_evicts_across_threads(self):
        factory = ConnFactory()
        client = MySQLClient()
        client._open_connection = factory.open
        client._discard_conn = lambda conn: conn.close()

        old_max = client.cfg.max_idle_connections
        client.cfg = replace(client.cfg, max_idle_connections=3)

        try:
            for i in range(5):
                with client.connect("h1", str(i)):
                    pass

            self.assertLessEqual(client._idle_count, 3)
            self.assertLessEqual(len(factory.conns) - len(factory.closed), 3)
        finally:
            client.cfg = replace(client.cfg, max_idle_connections=old_max)

    def test_idle_timeout_evicts_stale_connections(self):
        factory = ConnFactory()
        client = MySQLClient()
        client._open_connection = factory.open
        client._discard_conn = lambda conn: conn.close()

        old_timeout = client.cfg.idle_timeout
        old_max = client.cfg.max_idle_connections
        client.cfg = replace(
            client.cfg,
            idle_timeout=1,
            max_idle_connections=10,
        )

        try:
            with client.connect("h1", "db1"):
                pass

            # Имитируем долгий простой кэшированного соединения.
            import time as time_mod
            entry = next(iter(client._pool_state().values()))
            entry["last_used"] = time_mod.monotonic() - 5

            # Релиз любого соединения триггерит eviction, которая
            # закроет простаивающее слишком долго соединение.
            with client.connect("h1", "db2"):
                pass

            self.assertTrue(factory.conns[0].closed)
            self.assertEqual(len(factory.conns) - len(factory.closed), 1)
        finally:
            client.cfg = replace(
                client.cfg,
                idle_timeout=old_timeout,
                max_idle_connections=old_max,
            )


class TestFilterDatabasesWithSettings(unittest.TestCase):
    def test_uses_one_query_per_chunk(self):
        factory = ConnFactory()
        client = MySQLClient()
        client._open_connection = factory.open
        client._discard_conn = lambda conn: conn.close()

        conn = factory.open("h1")

        databases = [f"db_{i:04d}" for i in range(450)]

        result = [
            {"table_schema": "db_0001"},
            {"table_schema": "db_0449"},
        ]

        def execute(conn_, sql, params=None):
            conn_.executions.append((sql, params))
            conn_.result = result
            return result

        client.execute_on_connection = execute

        filtered = client.filter_databases_with_settings_conn(conn, databases)

        self.assertEqual(filtered, ["db_0001", "db_0449"])
        # 450 БД / 200 на чанк = 3 запроса
        self.assertEqual(len(conn.executions), 3)

        for sql, params in conn.executions:
            self.assertIn("table_schema IN", sql)
            self.assertEqual(params[0], "cfg_settings")

    def test_empty_input(self):
        client = MySQLClient()
        client.execute_on_connection = lambda conn, sql, params=None: self.fail(
            "не должно быть запросов"
        )
        self.assertEqual(
            client.filter_databases_with_settings_conn(
                object(), []
            ),
            [],
        )


class TestTransientRetry(unittest.TestCase):
    def test_execute_retries_on_gone_away(self):
        factory = ConnFactory(result=[{"ok": 1}])
        client = MySQLClient()
        client._open_connection = factory.open
        client._discard_conn = lambda conn: conn.close()

        conn = factory.open("h1")
        conn.fail_times = 1

        result = client.execute_on_connection(
            conn,
            "SELECT 1",
        )

        self.assertEqual(result, [{"ok": 1}])
        # один провал на старом + успех на новом соединении
        self.assertEqual(factory.opens, 2)
        self.assertEqual(len(conn.executions), 1)

    def test_non_transient_error_propagates(self):
        client = MySQLClient()

        class Cur:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def execute(self, sql, params=None):
                raise OperationalError(1064, "syntax error")

        class C:
            host = "h1"

            def cursor(self):
                return Cur()

        with self.assertRaises(OperationalError):
            client.execute_on_connection(C(), "BAD SQL")


class TestChunkHelper(unittest.TestCase):
    def test_chunk_sizes(self):
        chunks = list(sql_builder.chunk(list(range(450)), 200))
        self.assertEqual([len(c) for c in chunks], [200, 200, 50])


if __name__ == "__main__":
    unittest.main()
