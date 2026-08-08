"""
tests/test_sizes_connections.py

Тесты контроля соединений подсистемы размеров БД/таблиц:
- инструментарий пула (active_count / slots_available / active_by_key);
- мягкий лимит DbSizesWorker (config.sizes.max_connections);
- TTL-кэш каталога (refresh в пределах TTL не ходит в БД);
- all_databases_table_sizes: USE [db] на ключе (host, None) без
  «взрыва» соединений (лимит table_workers).
"""

import os
import threading
import time
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from common.conn_pool import ConnectionPool
from common.mssql_client import MSSQLClient

_app = QApplication.instance() or QApplication([])


# ----------------------------------------------------------
# Пул: инструментарий
# ----------------------------------------------------------

class _PoolCfg:
    max_connections = 10
    max_per_key = 4
    pool_idle = 2
    max_idle_connections = 4
    idle_timeout = 60
    acquire_timeout = 1


class _FakeRaw:
    def close(self):
        pass


class TestPoolInstrumentation(unittest.TestCase):
    def setUp(self):
        self.pool = ConnectionPool(
            cfg=lambda: _PoolCfg(),
            open_conn=lambda host, db: _FakeRaw(),
            alive_check=None,
            acquire_timeout=1.0,
        )

    def test_active_count_and_slots(self):
        self.assertEqual(self.pool.active_count, 0)
        self.assertEqual(self.pool.slots_available, 10)

        c1 = self.pool.acquire("h1")
        self.assertEqual(self.pool.active_count, 1)
        self.assertEqual(self.pool.slots_available, 9)

        c2 = self.pool.acquire("h1")
        self.assertIs(c1, c2)
        self.assertEqual(self.pool.active_count, 1)

        self.pool.release("h1", None, c1)
        self.assertEqual(self.pool.active_count, 1)

        self.pool.release("h1", None, c1)
        self.assertEqual(self.pool.active_count, 0)
        self.assertEqual(self.pool.slots_available, 10)

    def test_active_by_key(self):
        c1 = self.pool.acquire("h1", "db1")
        self.assertEqual(
            self.pool.active_by_key()[("h1", "db1")],
            {"in_use": 1, "idle": 0, "total": 1},
        )

        self.pool.acquire("h1", "db2")
        info = self.pool.active_by_key()
        self.assertEqual(info[("h1", "db1")]["in_use"], 1)
        self.assertEqual(info[("h1", "db2")]["in_use"], 1)

        self.pool.release("h1", "db1", c1)
        self.assertEqual(
            self.pool.active_by_key()[("h1", "db1")],
            {"in_use": 0, "idle": 1, "total": 1},
        )


# ----------------------------------------------------------
# DbSizesWorker: мягкий лимит и TTL-кэш
# ----------------------------------------------------------

class _FakeSizes:
    def __init__(self, max_connections=4, table_workers=4, catalog_ttl=300):
        self.max_connections = max_connections
        self.table_workers = table_workers
        self.catalog_ttl = catalog_ttl


class _FakeParallel:
    database_workers = 4


class _FakeConfig:
    def __init__(self, max_connections=4, catalog_ttl=300):
        self.sizes = _FakeSizes(
            max_connections=max_connections, catalog_ttl=catalog_ttl
        )
        self.parallel = _FakeParallel()


class _CountingClient:
    """server_catalog считает вызовы и параллельность."""

    def __init__(self, delay=0.02, max_connections=4):
        self.calls = 0
        self.delay = delay
        self.max_connections = max_connections
        self._lock = threading.Lock()
        self._active = 0
        self.max_active = 0

    def server_catalog(self, server):
        with self._lock:
            self.calls += 1
            self._active += 1
            self.max_active = max(self.max_active, self._active)
        try:
            time.sleep(self.delay)
        finally:
            with self._lock:
                self._active -= 1
        return {"db": 1000}, {"db": [("t1", 1000)]}


class TestDbSizesWorkerLimits(unittest.TestCase):
    def setUp(self):
        import backend.db_sizes_worker as dw

        self.dw = dw

    def test_ttl_cache_avoids_second_query(self):
        client = _CountingClient()
        cfg = _FakeConfig(catalog_ttl=300)

        with patch.object(self.dw, "config", cfg), \
             patch.object(self.dw, "client_for", return_value=client):
            worker = self.dw.DbSizesWorker()
            worker._load_catalog("srv", "refresh")
            worker._load_catalog("srv", "refresh")
            worker.stop()

        self.assertEqual(client.calls, 1)

    def test_disabled_cache_queries_every_time(self):
        client = _CountingClient()
        cfg = _FakeConfig(catalog_ttl=0)

        with patch.object(self.dw, "config", cfg), \
             patch.object(self.dw, "client_for", return_value=client):
            worker = self.dw.DbSizesWorker()
            worker._load_catalog("srv", "refresh")
            worker._load_catalog("srv", "refresh")
            worker.stop()

        self.assertEqual(client.calls, 2)

    def test_soft_limit_caps_concurrent_connections(self):
        client = _CountingClient(max_connections=4)
        cfg = _FakeConfig(max_connections=1)

        with patch.object(self.dw, "config", cfg), \
             patch.object(self.dw, "client_for", return_value=client):
            worker = self.dw.DbSizesWorker()
            futures = [
                worker._executor.submit(
                    worker._load_catalog, f"s{i}", "refresh"
                )
                for i in range(3)
            ]
            for f in futures:
                f.result(timeout=10)
            worker.stop()

        self.assertEqual(client.max_active, 1)
        self.assertEqual(client.calls, 3)


# ----------------------------------------------------------
# MSSQL: all_databases_table_sizes
# ----------------------------------------------------------

class _FakeMssqlQuery:
    def __init__(self):
        self.calls = []
        self._lock = threading.Lock()
        self._active = 0
        self.max_active = 0

    def __call__(self, host, sql, database=None, params=None):
        db = sql.split("USE [", 1)[1].split("]", 1)[0].replace("]]", "]")
        with self._lock:
            self.calls.append((sql, database))
            self._active += 1
            self.max_active = max(self.max_active, self._active)
        try:
            time.sleep(0.01)
        finally:
            with self._lock:
                self._active -= 1
        return [{"table_name": f"t_{db}", "total_bytes": 100}]


class TestMssqlAllDatabasesTableSizes(unittest.TestCase):
    def setUp(self):
        self.client = MSSQLClient()
        self.fake = _FakeMssqlQuery()
        self.client.query = self.fake
        self.cfg = _FakeConfig(max_connections=4, catalog_ttl=0)

    def test_use_prefix_and_shared_key(self):
        with patch("common.mssql_client.config", self.cfg):
            res = self.client.all_databases_table_sizes(
                "srv", ["db1", "db2"]
            )

        self.assertEqual(set(res), {"db1", "db2"})
        for sql, database in self.fake.calls:
            self.assertTrue(sql.startswith("USE [db"))
            self.assertIsNone(database)

    def test_parallelism_bounded_by_table_workers(self):
        cfg = _FakeConfig(max_connections=4, catalog_ttl=0)
        cfg.sizes.table_workers = 2

        with patch("common.mssql_client.config", cfg):
            self.client.all_databases_table_sizes(
                "srv", [f"db{i}" for i in range(6)]
            )

        self.assertLessEqual(self.fake.max_active, 2)

    def test_bracket_escaping(self):
        with patch("common.mssql_client.config", self.cfg):
            self.client.all_databases_table_sizes("srv", ["a]b"])

        self.assertIn("USE [a]]b];", self.fake.calls[0][0])

    def test_empty_input(self):
        with patch("common.mssql_client.config", self.cfg):
            res = self.client.all_databases_table_sizes("srv", [])

        self.assertEqual(res, {})
        self.assertEqual(self.fake.calls, [])


if __name__ == "__main__":
    unittest.main()
