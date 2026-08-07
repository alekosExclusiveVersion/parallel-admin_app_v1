"""
tests/test_servers_tree.py

Тесты двухфазной загрузки для дерева серверов:
- имена БД (SHOW DATABASES) показываются сразу, размеры и таблицы
  приходят одним запросом (server_catalog) и дописываются к узлам;
- кэш таблиц сервера позволяет раскрывать БД без отдельного запроса;
- refresh_sizes обновляет данные без сброса дерева.
"""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

import backend.db_sizes_worker as dw
from common.mysql_client import mysql
from common.server_registry import registry
from gui.servers_tree import ServersTree


class FakeSizesMySQL:
    def __init__(self):
        self.databases = ["ar_a", "ar_b"]
        self.sizes = {"ar_a": 1000, "ar_b": 2000}
        self.tables = {
            "ar_a": [("t1", 600), ("t2", 400)],
            "ar_b": [("t3", 2000)],
        }

    def list_all_databases(self, server):
        return list(self.databases)

    def server_catalog(self, server):
        return dict(self.sizes), {
            db: list(t) for db, t in self.tables.items()
        }

    def database_table_sizes(self, server, database):
        return list(self.tables.get(database, []))


class TestDbSizesWorker(unittest.TestCase):
    def setUp(self):
        # Реестр серверов не должен трогать реальные файлы в тестах.
        self._tmp = Path(tempfile.mkdtemp())
        registry.servers_file = self._tmp / "servers.json"
        registry.key_file = self._tmp / "servers.key"
        registry._loaded = False

        self.fake = FakeSizesMySQL()
        self.patcher = patch.object(mysql, "list_all_databases",
                                    self.fake.list_all_databases)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def _patch_catalog(self, side_effect=None, table_effect=None):
        patchers = [
            patch.object(mysql, "server_catalog",
                         side_effect if side_effect
                         else self.fake.server_catalog),
            patch.object(mysql, "database_table_sizes",
                         table_effect if table_effect
                         else self.fake.database_table_sizes),
        ]
        for p in patchers:
            p.start()
            self.addCleanup(p.stop)

    def test_request_databases_emits_names_sizes_tables(self):
        self._patch_catalog()
        worker = dw.DbSizesWorker()
        events = []

        worker.databases_names.connect(
            lambda s, n: events.append(("names", s, n))
        )
        worker.databases.connect(
            lambda s, d: events.append(("sizes", s, d))
        )
        worker.server_tables.connect(
            lambda s, t: events.append(("tables", s, t))
        )

        worker.request_databases(["srv1"])

        kinds = [e[0] for e in events]
        self.assertEqual(kinds[:3], ["names", "sizes", "tables"])
        self.assertEqual(events[0][2], ["ar_a", "ar_b"])
        self.assertEqual(events[1][2], {"ar_a": 1000, "ar_b": 2000})
        self.assertEqual(events[2][2], self.fake.tables)

    def test_catalog_failure_still_shows_names(self):
        def boom(server):
            raise RuntimeError("boom")

        self._patch_catalog(side_effect=boom)
        worker = dw.DbSizesWorker()
        events = []

        worker.databases_names.connect(
            lambda s, n: events.append(("names", s, n))
        )
        worker.error.connect(lambda *a: events.append(("error", a)))

        worker.request_databases(["srv1"])

        self.assertEqual(events[0][0], "names")
        self.assertTrue(any(e[0] == "error" for e in events))

    def test_refresh_sizes_emits_sizes_and_tables(self):
        self._patch_catalog()
        worker = dw.DbSizesWorker()
        events = []

        worker.databases.connect(lambda s, d: events.append(("sizes", s)))
        worker.server_tables.connect(lambda s, t: events.append(("tables", s)))

        worker.refresh_sizes(["srv1"])

        self.assertEqual([e[0] for e in events], ["sizes", "tables"])

    def test_request_tables_fallback(self):
        self._patch_catalog()
        worker = dw.DbSizesWorker()
        events = []

        worker.tables.connect(lambda *a: events.append(("tables", a)))

        worker.request_tables("srv1", "ar_b")

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0][1], ("srv1", "ar_b", [("t3", 2000)]))

    def test_stop_prevents_processing(self):
        worker = dw.DbSizesWorker()
        events = []
        worker.databases_names.connect(lambda *a: events.append(("names", a)))
        worker.stop()
        worker.request_databases(["srv1"])
        self.assertEqual(events, [])

    def test_mssql_server_uses_mssql_client(self):
        from common.mssql_client import mssql
        from common.server_registry import ServerSpec

        spec = ServerSpec(host="mssql1", engine="mssql")

        with patch.object(registry, "find", return_value=spec):
            with patch.object(
                mssql,
                "list_all_databases",
                return_value=["ar_a"],
            ), patch.object(
                mssql,
                "server_catalog",
                return_value=({"ar_a": 1000}, {}),
            ):
                worker = dw.DbSizesWorker()
                events = []

                worker.databases_names.connect(
                    lambda s, n: events.append(("names", s, n))
                )
                worker.databases.connect(
                    lambda s, d: events.append(("sizes", s, d))
                )
                worker.server_tables.connect(
                    lambda s, t: events.append(("tables", s, t))
                )

                worker.request_databases(["mssql1"])

        self.assertEqual(events[0], ("names", "mssql1", ["ar_a"]))
        self.assertEqual(events[1], ("sizes", "mssql1", {"ar_a": 1000}))
        self.assertEqual(events[2], ("tables", "mssql1", {}))


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

    def test_db_expand_uses_tables_cache(self):
        tree = ServersTree()
        tree.set_servers(["srv1"])
        srv = tree.topLevelItem(0)

        requests = []
        tree.tablesRequested.connect(
            lambda s, d: requests.append((s, d))
        )

        tree.apply_databases("srv1", ["ar_a", "ar_b"])
        tree.apply_server_tables("srv1", {
            "ar_a": [("t1", 600), ("t2", 400)],
            "ar_b": [("t3", 2000)],
        })

        db = srv.child(0)
        db.setExpanded(True)

        self.assertEqual(requests, [], "запросов к таблицам быть не должно")
        self.assertEqual(db.childCount(), 2)
        self.assertEqual(tree.table_name(db.child(0)), "t1")
        self.assertEqual(db.child(0).text(0), "t1  (600.0 B)")

    def test_db_expand_without_cache_requests_tables(self):
        tree = ServersTree()
        tree.set_servers(["srv1"])
        srv = tree.topLevelItem(0)

        requests = []
        tree.tablesRequested.connect(
            lambda s, d: requests.append((s, d))
        )

        tree.apply_databases("srv1", ["ar_a"])
        db = srv.child(0)
        db.setExpanded(True)

        self.assertEqual(requests, [("srv1", "ar_a")])

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

    def test_set_servers_with_display_name(self):
        tree = ServersTree()
        tree.set_servers([("Prod", "db1.example.com")])

        srv = tree.topLevelItem(0)

        # host скрыт из списка: показывается только имя
        self.assertEqual(srv.text(0), "Prod")
        self.assertEqual(tree.display_name(srv), "Prod")
        self.assertEqual(tree.server_name(srv), "db1.example.com")
        # host доступен подсказкой при наведении
        self.assertEqual(srv.toolTip(0), "db1.example.com")

    def test_set_servers_without_name_shows_host(self):
        tree = ServersTree()
        tree.set_servers([("db1.example.com", "db1.example.com")])

        srv = tree.topLevelItem(0)

        self.assertEqual(srv.text(0), "db1.example.com")
        self.assertEqual(srv.toolTip(0), "")

    def test_apply_sizes_keeps_display_name(self):
        tree = ServersTree()
        tree.set_servers([("Prod", "db1")])
        srv = tree.topLevelItem(0)

        tree.apply_sizes("db1", {"ar_a": 1000})

        self.assertTrue(
            srv.text(0).startswith("Prod  (1000.0 B)")
        )
        self.assertEqual(tree.server_name(srv), "db1")

    def test_apply_databases_keeps_display_name(self):
        tree = ServersTree()
        tree.set_servers([("Prod", "db1")])
        srv = tree.topLevelItem(0)

        tree.apply_databases("db1", ["ar_a"])

        self.assertEqual(srv.text(0), "Prod")
        self.assertEqual(tree.server_name(srv), "db1")


if __name__ == "__main__":
    unittest.main()
