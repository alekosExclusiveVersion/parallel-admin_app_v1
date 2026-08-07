"""
common/sql_security.py

Определение потенциально записывающих SQL-операторов.

`is_write_statement` анализирует токены SQL вне строковых литералов,
идентификаторов в обратных кавычках и комментариев. Это исключает ложные
срабатывания на словах вида 'UPDATE' внутри строки, комментария или
в имени колонки.
"""

from __future__ import annotations

from common.sql_splitter import _skip_backtick, _skip_quoted

WRITE_KEYWORDS = {
    "UPDATE", "INSERT", "DELETE", "ALTER", "DROP", "TRUNCATE",
    "REPLACE", "CREATE", "GRANT", "REVOKE", "RENAME", "CALL",
    "LOCK", "UNLOCK", "KILL", "LOAD",
}


def iter_bare_tokens(sql: str):
    """Итерирует слово-токены вне строк/идентификаторов/комментариев.

    Каждый токен возвращается в верхнем регистре. Строковые литералы
    (одинарные/двойные кавычки), идентификаторы в обратных кавычках и
    комментарии (--, #, /* */) пропускаются целиком.
    """
    n = len(sql)
    i = 0

    while i < n:
        ch = sql[i]

        # Построчные комментарии
        if ch == "-" and i + 1 < n and sql[i + 1] == "-":
            end = sql.find("\n", i)
            i = n if end == -1 else end + 1
            continue
        if ch == "#":
            end = sql.find("\n", i)
            i = n if end == -1 else end + 1
            continue

        # Блочные комментарии
        if ch == "/" and i + 1 < n and sql[i + 1] == "*":
            end = sql.find("*/", i + 2)
            i = n if end == -1 else end + 2
            continue

        # Строковые литералы и идентификаторы в кавычках
        if ch in ("'", '"'):
            i = _skip_quoted(sql, i)
            continue
        if ch == "`":
            i = _skip_backtick(sql, i)
            continue

        # Слово вне кавычек
        if ch.isalpha() or ch == "_":
            start = i
            while i < n and (sql[i].isalnum() or sql[i] == "_"):
                i += 1
            yield sql[start:i].upper()
            continue

        i += 1


def is_write_statement(sql: str) -> bool:
    """True, если запрос может изменять данные."""
    return any(
        token in WRITE_KEYWORDS
        for token in iter_bare_tokens(sql)
    )
