"""
tests/test_servers_tree.py

Тесты двухфазной загрузки БД для дерева серверов:
сначала быстрые имена БД (SHOW DATABASES), затем размеры,
которые дописываются к уже показанным узлам.
"""

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

import backend.db_sizes_worker as dw
from gui.servers_tree import ServersTree


class FakeSizesMySQL:
    def __init__(self):
        self.databases = ["ar_a", "ar_b"]
        self.sizes = {"ar_a": 1000, "ar_b": 2000}

    def list_all_databases(self, server):
        return list(self.databases)

    def database_sizes(self, server):
        return dict(self.sizes)


class TestDbSizesWorker(unittest.TestCase):
    def test_request_databases_emits_names_then_sizes(self):
        fake = FakeSizesMySQL()
        worker = dw.DbSizesWorker()
        events = []

        worker.databases_names.connect(
            lambda s, n: events.append(("names", s, n))
        )
        worker.databases.connect(
            lambda s, d: events.append(("sizes", s, d))
        )

        with patch.object(dw.mysql, "list_all_databases", fake.list_all_databases), \
             patch.object(dw.mysql, "database_sizes", fake.database_sizes):
            worker.request_databases(["srv1"])

        self.assertEqual(events[0][0], "names")
        self.assertEqual(events[0][2], ["ar_a", "ar_b"])
        self.assertEqual(events[1][0], "sizes")
        self.assertEqual(events[1][2], {"ar_a": 1000, "ar_b": 2000})

    def test_sizes_failure_still_shows_names(self):
        fake = FakeSizesMySQL()
        worker = dw.DbSizesWorker()
        events = []

        worker.databases_names.connect(
            lambda s, n: events.append(("names", s, n))
        )
        worker.error.connect(lambda *a: events.append(("error", a)))

        with patch.object(dw.mysql, "list_all_databases", fake.list_all_databases), \
             patch.object(dw.mysql, "database_sizes",
                          side_effect=RuntimeError("boom")):
            worker.request_databases(["srv1"])

        self.assertEqual(events[0][0], "names")
        self.assertTrue(any(e[0] == "error" for e in events))

    def test_names_failure_emits_error_only(self):
        worker = dw.DbSizesWorker()
        events = []

        worker.databases_names.connect(lambda *a: events.append(("names", a)))
        worker.error.connect(lambda *a: events.append(("error", a)))

        with patch.object(dw.mysql, "list_all_databases",
                          side_effect=RuntimeError("boom")):
            worker.request_databases(["srv1"])

        self.assertTrue(any(e[0] == "error" for e in events))
        self.assertFalse(any(e[0] == "names" for e in events))

    def test_stop_prevents_processing(self):
        worker = dw.DbSizesWorker()
        events = []
        worker.databases_names.connect(lambda *a: events.append(("names", a)))
        worker.stop()
        worker.request_databases(["srv1"])
        self.assertEqual(events, [])


class TestServersTree(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_apply_databases_then_sizes_in_place(self):
        tree = ServersTree()
        tree.set_servers(["srv1"])
        srv = tree.topLevelItem(0)

        tree.apply_databases("srv1", ["ar_a", "ar_b"])

        self.assertEqual(srv.childCount(), 2)
        self.assertEqual(tree.db_name(srv.child(0)), "ar_a")
        self.assertEqual(srv.child(0).text(0), "ar_a")
        self.assertEqual(srv.child(0).child(0).text(0), "…")

        tree.apply_sizes("srv1", {"ar_a": 1000, "ar_b": 2000})

        self.assertIn("srv1", srv.text(0))
        self.assertEqual(srv.child(0).text(0), "ar_a  (1000.0 B)")
        self.assertEqual(srv.child(1).text(0), "ar_b  (2.0 KB)")
        # узлы не пересоздавались — placeholder таблиц сохранён
        self.assertEqual(srv.child(0).childCount(), 1)
        self.assertEqual(srv.child(0).child(0).text(0), "…")

    def test_apply_sizes_without_names_builds_children(self):
        tree = ServersTree()
        tree.set_servers(["srv1"])
        srv = tree.topLevelItem(0)

        tree.apply_sizes("srv1", {"ar_a": 1000})

        self.assertEqual(srv.childCount(), 1)
        self.assertEqual(tree.db_name(srv.child(0)), "ar_a")
        self.assertEqual(srv.child(0).text(0), "ar_a  (1000.0 B)")

    def test_apply_databases_no_databases(self):
        tree = ServersTree()
        tree.set_servers(["srv1"])
        srv = tree.topLevelItem(0)

        tree.apply_databases("srv1", [])

        self.assertEqual(srv.childCount(), 1)
        self.assertEqual(srv.child(0).text(0), "Нет БД")


if __name__ == "__main__":
    unittest.main()
