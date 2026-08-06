"""
common/sql_assistant.py

Контекстный помощник для SQL Console.

Преобразует описание задачи на естественном языке (рус/англ)
в готовый SQL-запрос. Работает полностью офлайн, без внешних API,
на основе детерминированного разбора интентов.

Поддерживаемые задачи:
    * размер одной или нескольких баз данных
    * размер всех баз данных на сервере
    * размеры таблиц внутри базы
    * количество строк в таблице
    * список баз / список таблиц
    * просмотр и поиск настроек cfg_settings
    * просмотр содержимого таблицы
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class AssistantSuggestion:
    """Результат разбора: распознанный интент и готовый SQL."""
    intent: str
    title: str
    sql: str
    databases: tuple[str, ...] = ()
    tables: tuple[str, ...] = ()
    hint: str = ""


# Известные объекты схемы — не должны считаться именами БД/таблиц.
KNOWN_OBJECTS = {
    "cfg_settings",
    "stg_name",
    "stg_value",
    "stg_type",
    "cs_system_country",
    "ban_email_domain",
    "information_schema",
    "performance_schema",
}

# Ключевые слова SQL — пропускаем при поиске идентификаторов.
SQL_KEYWORDS = {
    "select", "from", "where", "insert", "update", "delete", "drop",
    "create", "alter", "table", "tables", "database", "databases",
    "schema", "show", "into", "values", "set", "group", "by", "order",
    "limit", "join", "inner", "left", "right", "outer", "on", "as",
    "and", "or", "not", "in", "like", "count", "sum", "max", "min",
    "distinct", "union", "all", "use", "desc", "asc", "primary", "key",
    "index", "view", "views", "column", "columns", "row", "rows",
}

# Русские и частые слова — не могут быть именами БД/таблиц.
STOPWORDS = {
    "я", "мне", "меня", "мой", "моя", "мои", "ты", "тебе", "вы",
    "хочу", "хотел", "хотела", "хотим", "надо", "нужно", "необходимо",
    "можно", "нельзя", "дай", "дайте", "покажи", "покажите", "выведи",
    "вывести", "посмотреть", "посмотри", "сделай", "сделать", "подскажи",
    "подскажите", "подсказка", "помощь", "помоги", "напиши", "написать",
    "какой", "какая", "какие", "какое", "каких", "который", "которые",
    "узнать", "узнай", "узнать", "проверить", "проверь", "найди", "найти",
    "запрос", "запросы", "sql", "код", "команда", "выполнить", "выполни",
    "и", "или", "а", "но", "по", "со", "из", "для", "про", "об", "обо",
    "на", "в", "во", "с", "к", "ко", "о", "от", "до", "за", "при",
    "как", "что", "чем", "чего", "кому", "кого", "если", "то", "так",
    "все", "всех", "всё", "вся", "весь", "каждый", "каждой", "каждую",
    "база", "базы", "баз", "базе", "базу", "базой", "баз данных",
    "бд", "бд", "сервер", "сервера", "серверов", "сервере", "серверу",
    "таблица", "таблицы", "таблиц", "таблице", "таблицу", "таблицей",
    "размер", "размеры", "размеров", "размером", "размеру",
    "занимает", "занимают", "занимаемое", "занимаемый", "занимаемая",
    "место", "места", "объём", "объем", "весит", "весят", "сколько",
    "много", "большой", "большая", "большие", "больших", "крупные",
    "строка", "строки", "строк", "строке", "строку", "записей",
    "записи", "запись", "количество", "кол-во", "число", "числа",
    "список", "перечисли", "перечислить", "перечень", "названия",
    "название", "содержимое", "данные", "значение", "значения",
    "значений", "настройка", "настройки", "настроек", "настройку",
    "настройке", "настройк", "setting", "settings", "есть", "имеется",
    "находится", "лежат", "хранится", "будет", "было", "быть",
}

# Интент -> ключевые слова (проверка по подстроке нормализованного текста).
ROW_COUNT = (
    "сколько строк", "количество строк", "кол-во строк",
    "сколько записей", "количество записей", "число строк",
    "число записей", "сколько рядов", "row count", "count rows",
    "сколько значений",
)
TABLE_SIZES = (
    "размер таблиц", "размеры таблиц", "таблиц по размеру",
    "сколько занимают таблиц", "сколько места занимают таблиц",
    "самая большая таблиц", "большие таблиц", "крупные таблиц",
    "самые большие", "самых больших", "самую большую",
    "какие таблиц занимают", "какая таблиц занимает",
    "топ таблиц", "таблиц и их размер", "размер каждой таблиц",
)
SETTINGS_SEARCH = (
    "найти настройк", "найди настройк", "значение настройк",
    "поиск по настройк", "какая настройка", "что за настройк",
    "проверить настройк",
)
SETTINGS = (
    "cfg_settings", "настройк", "setting", "stg_name", "stg_value",
)
TABLE_PREVIEW = (
    "содержимое таблиц", "посмотреть таблиц", "показать таблиц",
    "данные таблиц", "что в таблиц", "select *", "посмотреть данные",
    "вывести таблиц",
)
LIST_TABLES = (
    "список таблиц", "какие таблиц", "перечисли таблиц",
    "show tables", "все таблиц", "таблиц есть",
)
LIST_DATABASES = (
    "список баз", "список бд", "какие баз", "какие есть баз",
    "перечисли баз", "все баз", "show databases", "все бд",
    "перечислить баз", "сколько баз",
    "список всех баз", "список всех бд", "всех баз", "всех бд",
    "все базы данных",
)
DB_SIZE = (
    "размер", "занимает", "занимают", "место", "объём", "объем",
    "весит", "весят", "сколько места",
)


def _norm(text: str) -> str:
    """Нормализация: нижний регистр, сжатие пробелов."""
    return re.sub(r"\s+", " ", text.lower().strip())


def _has_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(k in text for k in keywords)


def _quote_identifier(name: str) -> str:
    return f"`{name.replace('`', '``')}`"


def _like_escape(term: str) -> str:
    return (
        term.replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )


def _extract_identifiers(text: str) -> tuple[list[str], list[str]]:
    """Извлекает имена БД и таблиц из текста запроса."""
    dbs: list[str] = []
    tables: list[str] = []
    seen_dbs: set[str] = set()
    seen_tables: set[str] = set()

    def add_db(name: str) -> None:
        name = name.strip("`")
        if (
            name
            and name.lower() not in seen_dbs
            and name.lower() not in KNOWN_OBJECTS
        ):
            seen_dbs.add(name.lower())
            dbs.append(name)

    def add_table(name: str) -> None:
        name = name.strip("`")
        if name and name.lower() not in seen_tables:
            seen_tables.add(name.lower())
            tables.append(name)

    # 1. Квалифицированные имена db.table / `db`.`table`.
    plain = re.sub(
        r"`?[A-Za-z0-9_]+`?\s*\.\s*`?[A-Za-z0-9_]+`?",
        " ",
        text,
    )
    for m in re.finditer(
        r"`?([A-Za-z0-9_]+)`?\s*\.\s*`?([A-Za-z0-9_]+)`?",
        text,
    ):
        add_db(m.group(1))
        add_table(m.group(2))

    # 2. Одиночные идентификаторы в обратных кавычках.
    for m in re.finditer(r"`([A-Za-z0-9_]+)`", plain):
        token = m.group(1)
        if token.lower() in KNOWN_OBJECTS:
            add_table(token)
        else:
            add_db(token)

    # 2b. Известные объекты схемы (cfg_settings и пр.) → таблицы.
    for token in KNOWN_OBJECTS:
        if re.search(rf"\b{re.escape(token)}\b", plain.lower()):
            add_table(token)

    # 3. Таблица, следующая за словом «таблиц…».
    plain_lower = plain.lower()
    for m in re.finditer(r"\bтаблиц[аеуыи]?\b\s+([a-z0-9_]+)", plain_lower):
        token = m.group(1)
        if (
            token in STOPWORDS
            or token in SQL_KEYWORDS
            or token in KNOWN_OBJECTS
        ):
            continue
        add_table(token)

    # 4. snake_case-токены без стоп-слов — кандидаты в БД.
    for m in re.finditer(r"\b([a-z][a-z0-9_]*)\b", plain_lower):
        token = m.group(1)
        if (
            token in STOPWORDS
            or token in SQL_KEYWORDS
            or token in KNOWN_OBJECTS
        ):
            continue
        if "_" in token:
            add_db(token)

    return dbs, tables


def _extract_setting_term(text: str, dbs: list[str]) -> str | None:
    """Извлекает искомую настройку для settings_search."""
    lower = _norm(text)
    lower_dbs = {d.lower() for d in dbs}

    for m in re.finditer(
        r"настройк\w*\s+(?:под\s+названием\s+)?([a-z0-9_]+)",
        lower,
    ):
        token = m.group(1)
        if (
            token not in STOPWORDS
            and token not in SQL_KEYWORDS
            and token not in lower_dbs
            and token not in KNOWN_OBJECTS
        ):
            return token

    # Fallback: первый «технический» токен (camelCase/snake), не БД.
    for m in re.finditer(r"\b([a-z][a-z0-9_]{1,})\b", lower):
        token = m.group(1)
        if (
            token in STOPWORDS
            or token in SQL_KEYWORDS
            or token in KNOWN_OBJECTS
            or token in lower_dbs
        ):
            continue
        return token

    return None


def _detect_intent(text: str) -> str | None:
    t = _norm(text)
    if _has_any(t, ROW_COUNT):
        return "row_count"
    if _has_any(t, TABLE_SIZES):
        return "table_sizes"
    # Размерные слова приоритетнее, чем «всех баз» — чтобы фраза
    # «размер всех баз на сервере» уходила в обзор размеров, а не в список.
    if _has_any(t, DB_SIZE):
        return "db_size"
    if _has_any(t, SETTINGS_SEARCH):
        return "settings_search"
    if _has_any(t, SETTINGS):
        return "settings"
    if _has_any(t, TABLE_PREVIEW):
        return "table_preview"
    if _has_any(t, LIST_TABLES):
        return "list_tables"
    if _has_any(t, LIST_DATABASES):
        return "list_databases"
    return None


# ----------------------------------------------------------
# Генерация SQL
# ----------------------------------------------------------

_TITLES = {
    "db_size": "Размер баз данных",
    "db_sizes_all": "Размер всех баз данных на сервере",
    "table_sizes": "Размеры таблиц",
    "row_count": "Количество строк в таблице",
    "list_databases": "Список баз данных",
    "list_tables": "Список таблиц",
    "settings": "Настройки cfg_settings",
    "settings_search": "Поиск по настройкам cfg_settings",
    "table_preview": "Содержимое таблицы",
}

_DB_PLACEHOLDER = "__DATABASE__"
_TABLE_PLACEHOLDER = "__TABLE__"


def _build_sql(
    intent: str,
    dbs: list[str],
    tables: list[str],
    setting_term: str | None,
    context: dict,
) -> tuple[str, str, str]:
    title = _TITLES.get(intent, intent)
    ctx_db = (context.get("database") or "").strip()
    hint = ""

    def resolve_db() -> str:
        nonlocal hint
        if dbs:
            return dbs[0]
        if ctx_db:
            hint = f"База взята из поля выбора: {ctx_db}."
            return ctx_db
        hint = f"Замените {_DB_PLACEHOLDER} на имя базы данных."
        return _DB_PLACEHOLDER

    if intent == "db_size" and not dbs:
        # «размер всех баз» без указанных имён → обзор всего сервера
        intent = "db_sizes_all"
        title = _TITLES["db_sizes_all"]

    if intent == "db_sizes_all":
        sql = """SELECT
    table_schema AS database_name,
    ROUND(SUM(data_length + index_length) / 1024 / 1024, 2) AS size_mb
FROM information_schema.tables
WHERE table_schema NOT IN (
    'information_schema', 'performance_schema', 'mysql', 'sys'
)
GROUP BY table_schema
ORDER BY size_mb DESC;"""
        return sql, title, hint

    if intent == "db_size":
        in_list = ", ".join(repr(d) for d in dbs)
        sql = f"""SELECT
    table_schema AS database_name,
    ROUND(SUM(data_length + index_length) / 1024 / 1024, 2) AS size_mb
FROM information_schema.tables
WHERE table_schema IN ({in_list})
GROUP BY table_schema
ORDER BY size_mb DESC;"""
        return sql, title, hint

    if intent == "table_sizes":
        db = resolve_db()
        sql = f"""SELECT
    table_name,
    ROUND((data_length + index_length) / 1024 / 1024, 2) AS size_mb,
    table_rows AS rows_count
FROM information_schema.tables
WHERE table_schema = '{db}'
ORDER BY size_mb DESC;"""
        return sql, title, hint

    if intent == "row_count":
        db = resolve_db()
        table = tables[0] if tables else _TABLE_PLACEHOLDER
        if table == _TABLE_PLACEHOLDER and not hint:
            hint = "Таблица не найдена — замените __TABLE__ на нужную."
        sql = (
            f"SELECT COUNT(*) AS row_count\n"
            f"FROM {_quote_identifier(db)}.{_quote_identifier(table)};"
        )
        return sql, title, hint

    if intent == "list_databases":
        return "SHOW DATABASES;", title, hint

    if intent == "list_tables":
        db = resolve_db()
        sql = f"SHOW TABLES FROM {_quote_identifier(db)};"
        return sql, title, hint

    if intent == "settings":
        db = resolve_db()
        sql = (
            f"SELECT stg_name, stg_value\n"
            f"FROM {_quote_identifier(db)}.`cfg_settings`\n"
            f"ORDER BY stg_name;"
        )
        return sql, title, hint

    if intent == "settings_search":
        db = resolve_db()
        term = setting_term or "__TERM__"
        if term == "__TERM__" and not hint:
            hint = "Термин не найден — замените __TERM__ на искомое значение."
        escaped = _like_escape(term)
        sql = (
            f"SELECT stg_name, stg_value\n"
            f"FROM {_quote_identifier(db)}.`cfg_settings`\n"
            f"WHERE stg_name LIKE '%{escaped}%'\n"
            f"   OR stg_value LIKE '%{escaped}%'\n"
            f"ORDER BY stg_name;"
        )
        return sql, title, hint

    if intent == "table_preview":
        db = resolve_db()
        table = tables[0] if tables else _TABLE_PLACEHOLDER
        if table == _TABLE_PLACEHOLDER and not hint:
            hint = "Таблица не найдена — замените __TABLE__ на нужную."
        sql = (
            f"SELECT *\n"
            f"FROM {_quote_identifier(db)}.{_quote_identifier(table)}\n"
            f"LIMIT 1000;"
        )
        return sql, title, hint

    raise ValueError(f"Unknown intent: {intent}")


# ----------------------------------------------------------
# Публичный API
# ----------------------------------------------------------

def assist(text: str, context: dict | None = None) -> AssistantSuggestion | None:
    """Разбирает запрос пользователя и возвращает готовый SQL.

    `context` — необязательный словарь с текущим выбором в консоли:
        {"server": str, "database": str}
    """
    text = text.strip()
    if not text:
        return None

    context = context or {}
    intent = _detect_intent(text)
    if intent is None:
        return None

    dbs, tables = _extract_identifiers(text)

    setting_term = None
    if intent == "settings_search":
        setting_term = _extract_setting_term(text, dbs)

    sql, title, hint = _build_sql(
        intent, dbs, tables, setting_term, context,
    )

    return AssistantSuggestion(
        intent=intent,
        title=title,
        sql=sql,
        databases=tuple(dbs),
        tables=tuple(tables),
        hint=hint,
    )


ASSISTANT_EXAMPLES = (
    "размер баз ar_actviauto и autoprice_activauto",
    "сколько места занимает база ar_ru",
    "размер всех баз на сервере",
    "какие таблицы самые большие в базе ar_ru",
    "сколько строк в таблице cfg_settings базы ar_ru",
    "показать настройки cfg_settings базы ar_ru",
    "найти настройку banEmailDomain в базе ar_ru",
    "список всех баз данных",
    "показать содержимое таблицы users базы ar_ru",
)


if __name__ == "__main__":
    import sys

    test_inputs = [
        "хочу узнать занимаемое место бд ar_actviauto и autoprice_activauto какой запрос надо выполнить?",
        "размер баз ar_ru и ar_kz",
        "сколько места занимает база ar_ru",
        "размер всех баз на сервере",
        "какие таблицы самые большие в базе ar_ru",
        "сколько строк в таблице cfg_settings базы ar_ru",
        "сколько строк в таблице users базы ar_ru",
        "показать настройки cfg_settings базы ar_ru",
        "найти настройку banEmailDomain в базе ar_ru",
        "список всех баз данных",
        "показать содержимое таблицы users базы ar_ru",
        "привет, как дела?",
    ]

    failed = 0
    for text in test_inputs:
        print("=" * 72)
        print(f"Q: {text}")
        suggestion = assist(text, context={"database": "ar_ru"})
        if suggestion is None:
            print("   → не распознано")
            continue
        print(f"   intent : {suggestion.intent} — {suggestion.title}")
        print(f"   dbs    : {suggestion.databases}")
        print(f"   tables : {suggestion.tables}")
        print(f"   hint   : {suggestion.hint}")
        print("   SQL:")
        for line in suggestion.sql.splitlines():
            print(f"      {line}")

    print("=" * 72)
    sys.exit(1 if failed else 0)
