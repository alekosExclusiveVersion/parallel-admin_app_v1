"""
common/sql_splitter.py

Разбиение SQL-скрипта на отдельные операторы и поиск оператора
под позицией курсора для SQL Console.

Учитываются:
    - строковые литералы в одинарных/двойных кавычках
      (включая экранирование '\\'' / '"' и удвоение '')
    - обратные кавычки для идентификаторов
    - блочные комментарии /* ... */
    - построчные комментарии -- ... и # ...
"""

from __future__ import annotations


def _iter_statement_ranges(sql: str) -> list[tuple[int, int]]:
    """
    Возвращает список (start, end) непустых операторов в порядке следования.

    Границы — абсолютные позиции в исходной строке. end указывает на
    позицию сразу после последнего символа оператора (без учёта
    обрамляющих пробелов/переводов строк и точки с запятой).
    """
    ranges: list[tuple[int, int]] = []
    n = len(sql)
    i = 0
    start = -1  # начало текущего оператора (первый значимый символ)

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

        # Строковые литералы
        if ch in ("'", '"'):
            if start == -1:
                start = i
            i = _skip_quoted(sql, i)
            continue

        # Обратные кавычки (идентификаторы)
        if ch == "`":
            if start == -1:
                start = i
            i = _skip_backtick(sql, i)
            continue

        # Точка с запятой завершает оператор
        if ch == ";":
            if start != -1:
                ranges.append((start, i))
                start = -1
            i += 1
            continue

        # Значимый символ — открываем оператор при необходимости
        if not ch.isspace():
            if start == -1:
                start = i
        i += 1

    # Хвост скрипта без завершающей точки с запятой
    if start != -1:
        ranges.append((start, n))

    return ranges


def _skip_quoted(sql: str, i: int) -> int:
    """Пропускает строковый литерал, начинающийся в позиции i (кавычка)."""
    quote = sql[i]
    n = len(sql)
    i += 1
    while i < n:
        ch = sql[i]
        if ch == "\\" and i + 1 < n:
            i += 2
            continue
        if ch == quote:
            # Удвоенная кавычка внутри литерала ('' или "") — не конец
            if i + 1 < n and sql[i + 1] == quote:
                i += 2
                continue
            return i + 1
        i += 1
    return n


def _skip_backtick(sql: str, i: int) -> int:
    """Пропускает идентификатор в обратных кавычках."""
    n = len(sql)
    i += 1
    while i < n:
        if sql[i] == "`":
            if i + 1 < n and sql[i + 1] == "`":
                i += 2
                continue
            return i + 1
        i += 1
    return n


def split_statements(sql: str) -> list[str]:
    """
    Разбивает скрипт на непустые операторы по ';'.
    Возвращает список строк (операторы без завершающей ';').
    """
    return [
        sql[start:end].strip()
        for start, end in _iter_statement_ranges(sql)
    ]


def statement_at(sql: str, offset: int) -> str:
    """
    Возвращает оператор, содержащий позицию offset.

    Если offset попадает в пробел между операторами или за пределами
    последнего оператора — возвращается ближайший предыдущий оператор.
    Если операторов ещё нет — возвращается пустая строка.
    """
    offset = max(0, min(offset, len(sql)))

    ranges = _iter_statement_ranges(sql)

    if not ranges:
        return ""

    for start, end in ranges:
        if start <= offset < end:
            return sql[start:end].strip()
        if end <= offset:
            continue

    # Курсор в пробелах между операторами или в хвосте скрипта:
    # берём последний оператор, начинающийся не позже позиции курсора.
    prev = None
    for start, end in ranges:
        if start <= offset:
            prev = sql[start:end].strip()
        else:
            break
    return prev or ""
