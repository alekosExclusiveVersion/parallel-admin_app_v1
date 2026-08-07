"""
tests/test_query_worker.py

Тесты для backend/query_worker.py — отслеживание активного соединения
и прерывание выполняющегося запроса через KILL.
"""

import time
import threading
import unittest
from unittest.mock import patch

import backend.query_worker as qw


class FakeCursor:
    description = None
    rowcount = 5

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql):
        time.sleep(0.3)


class FakeConn:
    def __init__(self):
        self._cursor = FakeCursor()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def thread_id(self):
        return 4242

    def cursor(self):
        return self._cursor


class FakeMySQL:
    def __init__(self):
        self.killed = []

    def connect(self, host, database=None):
        return FakeConn()

    def kill_connection(self, host, connection_id):
        self.killed.append((host, connection_id))


class TestQueryWorkerKill(unittest.TestCase):
    def setUp(self):
        self.fake = FakeMySQL()
        patcher = patch.object(qw, "mysql", self.fake)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_kill_active_sends_kill_for_running_query(self):
        worker = qw.QueryWorker()
        worker.set_request("host1", "db1", "SELECT sleep(10)", 1000)

        thread = threading.Thread(
            target=worker._execute_sql,
            args=("host1", "db1", "SELECT sleep(10)", 1000),
        )
        thread.start()

        time.sleep(0.05)
        worker.kill_active()
        thread.join(timeout=5)

        self.assertEqual(self.fake.killed, [("host1", 4242)])
        self.assertIsNone(worker._active_id)
        self.assertEqual(worker._active_host, "")

    def test_kill_active_without_active_query_is_noop(self):
        worker = qw.QueryWorker()
        worker.set_request("host1", "db1", "SELECT 1", 1000)
        worker.kill_active()
        self.assertEqual(self.fake.killed, [])

    def test_active_id_cleared_after_execution(self):
        worker = qw.QueryWorker()
        worker.set_request("host1", "db1", "SELECT 1", 1000)

        worker._execute_sql("host1", "db1", "UPDATE t SET a = 1", 1000)

        self.assertIsNone(worker._active_id)
        self.assertEqual(worker._active_host, "")


if __name__ == "__main__":
    unittest.main()
