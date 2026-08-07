"""
tests/test_sql_security.py

Тесты для common/sql_security.py — определение операторов, изменяющих
данные (write), вне строк, комментариев и обратных кавычек.
"""

import unittest

from common.sql_security import is_write_statement


class TestIsWriteStatement(unittest.TestCase):
    def test_read_statements_are_not_write(self):
        for sql in (
            "SELECT * FROM t",
            "SHOW TABLES",
            "SHOW DATABASES",
            "DESCRIBE t",
            "EXPLAIN SELECT 1",
            "WITH x AS (SELECT 1) SELECT * FROM x",
        ):
            with self.subTest(sql=sql):
                self.assertFalse(is_write_statement(sql))

    def test_write_statements_are_write(self):
        for sql in (
            "UPDATE t SET a = 1",
            "INSERT INTO t VALUES (1)",
            "DELETE FROM t WHERE 1",
            "CREATE TABLE t (a INT)",
            "DROP TABLE t",
            "ALTER TABLE t ADD COLUMN a INT",
            "TRUNCATE TABLE t",
        ):
            with self.subTest(sql=sql):
                self.assertTrue(is_write_statement(sql))

    def test_write_keyword_inside_comment_ignored(self):
        self.assertFalse(is_write_statement("/* UPDATE */ SELECT 1"))
        self.assertFalse(is_write_statement("-- comment\nSELECT 1"))
        self.assertFalse(is_write_statement("# comment\nSELECT 1"))

    def test_write_keyword_inside_string_ignored(self):
        self.assertFalse(is_write_statement("SELECT 'UPDATE' AS x"))
        self.assertFalse(is_write_statement('SELECT "delete" AS x'))

    def test_write_keyword_inside_backticks_ignored(self):
        self.assertFalse(is_write_statement("SELECT `update` FROM t"))

    def test_lowercase_write(self):
        self.assertTrue(is_write_statement("update t set a = 1"))

    def test_leading_whitespace(self):
        self.assertTrue(is_write_statement("  \n\tUPDATE t SET a = 1"))

    def test_empty_and_none(self):
        self.assertFalse(is_write_statement(""))
        self.assertFalse(is_write_statement("   "))
