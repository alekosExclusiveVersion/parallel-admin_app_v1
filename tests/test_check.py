"""
tests/test_check.py

Тесты для check.py — поиск проектов через одно соединение на сервер
(батчинг), фильтр по стране и ключ target_value.
"""

import unittest
from unittest.mock import patch

import check


class FakeConn:
    host = "srv1"

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class FakeMySQL:
    def __init__(self):
        self.conn = FakeConn()

    def connect(self, host, database=None):
        return self.conn

    def list_databases_conn(self, conn):
        return ["ar_ru1", "ar_ru2", "ar_de1"]

    def has_cfg_settings_conn(self, conn, database):
        return database != "ar_de1"

    def filter_databases_with_settings_conn(self, conn, databases):
        return [db for db in databases if db != "ar_de1"]

    def scan_settings_batch(self, conn, databases):
        return [
            {"database_name": "ar_ru1", "country": "russia", "target_value": "gmail.com"},
            {"database_name": "ar_ru2", "country": "russia", "target_value": "mail.ru"},
        ]


class TestProcessServer(unittest.TestCase):
    def setUp(self):
        self.fake = FakeMySQL()
        patcher = patch.object(check, "mysql", self.fake)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_filters_by_country_and_uses_single_connection(self):
        rows = check.process_server("srv1")

        self.assertEqual(
            rows,
            [
                {
                    "server": "srv1",
                    "database": "ar_ru1",
                    "country": "russia",
                    "value": "gmail.com",
                },
                {
                    "server": "srv1",
                    "database": "ar_ru2",
                    "country": "russia",
                    "value": "mail.ru",
                },
            ],
        )

    def test_skips_databases_without_cfg_settings(self):
        # ar_de1 не передаётся в scan_settings_batch
        self.fake.scanned = None

        calls = []

        def scan(conn, databases):
            calls.append(databases)
            return []

        self.fake.scan_settings_batch = scan

        check.process_server("srv1")

        self.assertNotIn("ar_de1", calls[0])


class TestSaveCsv(unittest.TestCase):
    def test_writes_header_and_rows(self):
        import os
        import tempfile
        from pathlib import Path

        original_dir = os.getcwd()

        with tempfile.TemporaryDirectory() as tmp:
            os.chdir(tmp)
            try:
                check.save_csv(
                    [
                        {"server": "s1", "database": "d1", "country": "russia", "value": "v1"},
                        {"server": "s1", "database": "d2", "country": "russia", "value": "v2"},
                    ]
                )
            finally:
                os.chdir(original_dir)

            target = Path(tmp) / "logs" / "result.csv"
            lines = target.read_text(encoding="utf-8").strip().splitlines()

            self.assertEqual(lines[0], "SERVER,DATABASE,COUNTRY,banEmailDomain")
            self.assertEqual(lines[1], "s1,d1,russia,v1")
            self.assertEqual(lines[2], "s1,d2,russia,v2")


if __name__ == "__main__":
    unittest.main()
