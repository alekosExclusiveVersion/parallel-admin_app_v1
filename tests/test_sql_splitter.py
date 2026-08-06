"""
tests/test_sql_splitter.py

Тесты для common/sql_splitter.py — разбиение SQL-скрипта на операторы
и поиск оператора под позицией курсора.
"""

import unittest

from common.sql_splitter import split_statements, statement_at


class TestSplitStatements(unittest.TestCase):
    def test_single_statement_no_semicolon(self):
        self.assertEqual(
            split_statements("SELECT 1"),
            ["SELECT 1"],
        )

    def test_multiple_statements(self):
        sql = "SELECT 1; SELECT 2; SELECT 3;"
        self.assertEqual(
            split_statements(sql),
            ["SELECT 1", "SELECT 2", "SELECT 3"],
        )

    def test_semicolon_inside_single_quotes(self):
        sql = "SELECT 'a;b' AS x; SELECT 2"
        self.assertEqual(
            split_statements(sql),
            ["SELECT 'a;b' AS x", "SELECT 2"],
        )

    def test_semicolon_inside_double_quotes(self):
        sql = 'SELECT "a;b" AS x; SELECT 2'
        self.assertEqual(
            split_statements(sql),
            ['SELECT "a;b" AS x', "SELECT 2"],
        )

    def test_semicolon_inside_backticks(self):
        sql = "SELECT `we;ird` FROM t; SELECT 2"
        self.assertEqual(
            split_statements(sql),
            ["SELECT `we;ird` FROM t", "SELECT 2"],
        )

    def test_escaped_quote_inside_string(self):
        sql = r"SELECT 'it''s; ok' AS x; SELECT 2"
        self.assertEqual(
            split_statements(sql),
            ["SELECT 'it''s; ok' AS x", "SELECT 2"],
        )

    def test_backslash_escape_inside_string(self):
        sql = r"SELECT 'a\;b' AS x; SELECT 2"
        self.assertEqual(
            split_statements(sql),
            [r"SELECT 'a\;b' AS x", "SELECT 2"],
        )

    def test_line_comment_ignored(self):
        sql = (
            "-- comment with ; inside\n"
            "SELECT 1; -- trailing ; comment\n"
            "SELECT 2"
        )
        self.assertEqual(
            split_statements(sql),
            ["SELECT 1", "SELECT 2"],
        )

    def test_hash_comment_ignored(self):
        sql = "# comment ; inside\nSELECT 1; SELECT 2"
        self.assertEqual(
            split_statements(sql),
            ["SELECT 1", "SELECT 2"],
        )

    def test_block_comment_ignored(self):
        sql = "/* block ; comment */ SELECT 1; /* another ; */ SELECT 2"
        self.assertEqual(
            split_statements(sql),
            ["SELECT 1", "SELECT 2"],
        )

    def test_empty_input(self):
        self.assertEqual(split_statements(""), [])
        self.assertEqual(split_statements("   \n  "), [])
        self.assertEqual(split_statements(";;;"), [])

    def test_statement_leading_and_trailing_spaces_stripped(self):
        sql = "   SELECT 1   ;   SELECT 2   "
        self.assertEqual(
            split_statements(sql),
            ["SELECT 1", "SELECT 2"],
        )


class TestStatementAt(unittest.TestCase):
    def test_position_inside_first_statement(self):
        sql = "SELECT a; SELECT b"
        self.assertEqual(
            statement_at(sql, 4),
            "SELECT a",
        )

    def test_position_inside_second_statement(self):
        sql = "SELECT a; SELECT b"
        self.assertEqual(
            statement_at(sql, len("SELECT a; SELECT b") - 2),
            "SELECT b",
        )

    def test_position_at_start_of_statement(self):
        sql = "SELECT a; SELECT b"
        self.assertEqual(
            statement_at(sql, len("SELECT a; ")),
            "SELECT b",
        )

    def test_position_at_end_of_document_without_semicolon(self):
        sql = "SELECT a; SELECT b"
        self.assertEqual(
            statement_at(sql, len(sql)),
            "SELECT b",
        )

    def test_position_in_gap_returns_previous_statement(self):
        sql = "SELECT a;    \n   ; SELECT b"
        # Курсор в пробелах между ';' и 'SELECT b' — ближайший предыдущий
        # оператор — это "SELECT a".
        self.assertEqual(
            statement_at(sql, len("SELECT a;    \n   ")),
            "SELECT a",
        )

    def test_position_before_first_statement(self):
        sql = "SELECT a; SELECT b"
        # Позиция в начале строки (до первого значимого символа)
        self.assertEqual(
            statement_at(sql, 0),
            "SELECT a",
        )

    def test_empty_sql_returns_empty(self):
        self.assertEqual(statement_at("", 0), "")

    def test_cursor_in_comment_falls_to_previous_statement(self):
        sql = "SELECT a; -- comment here\nSELECT b"
        # Позиция внутри построчного комментария после первого оператора
        offset = sql.index("comment here") + 2
        # Ближайший предыдущий значимый оператор — "SELECT a"
        self.assertEqual(
            statement_at(sql, offset),
            "SELECT a",
        )

    def test_multiline_statement(self):
        sql = "SELECT\n    a,\n    b\nFROM t;"
        self.assertEqual(
            statement_at(sql, sql.index("FROM") + 1),
            "SELECT\n    a,\n    b\nFROM t",
        )


if __name__ == "__main__":
    unittest.main()
