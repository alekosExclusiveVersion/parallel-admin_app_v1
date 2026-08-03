"""
common/sql_builder.py

Построение пакетных SQL-запросов для чтения cfg_settings
из нескольких баз данных за один запрос (UNION ALL).

Шаблон можно заменить на лету через set_custom_template().
Доступные плейсхолдеры:
    {db}    — имя базы без экранирования (для литерала в SELECT)
    {dbq}   — имя базы в обратных кавычках (для FROM)
    {table} — таблица настроек из config
    {country} — имя настройки страны
    {target}  — имя целевой настройки
"""

from __future__ import annotations

from typing import Iterable

from common.config import config


DEFAULT_SCAN_TEMPLATE = """SELECT
    '{db}' AS database_name,
    MAX(CASE WHEN stg_name='{country}' THEN stg_value END) AS country,
    MAX(CASE WHEN stg_name='{target}' THEN stg_value END) AS target_value
FROM {dbq}.{table}
WHERE stg_name IN ('{country}','{target}')"""


class SQLBuilder:

    def __init__(self) -> None:
        self.custom_scan_template: str | None = None

    @staticmethod
    def quote_identifier(name: str) -> str:
        """Экранирование имени базы/таблицы."""
        return f"`{name.replace('`', '``')}`"

    @staticmethod
    def chunk(items: list[str], size: int) -> Iterable[list[str]]:
        for i in range(0, len(items), size):
            yield items[i:i + size]

    @property
    def scan_template(self) -> str:
        return self.custom_scan_template or DEFAULT_SCAN_TEMPLATE

    def set_custom_template(self, template: str) -> None:
        template = template.strip()
        self.custom_scan_template = template or None

    def reset_template(self) -> None:
        self.custom_scan_template = None

    def _render(self, template: str, db: str) -> str:
        return template.format(
            db=db,
            dbq=self.quote_identifier(db),
            table=config.advanced.settings_table,
            country=config.filter.country_setting,
            target=config.filter.target_setting,
        )

    def build_scan_query(self, databases: list[str]) -> list[str]:
        """
        Возвращает список SQL-запросов.
        Каждый запрос содержит UNION ALL для batch_size баз.
        """

        template = self.scan_template

        queries: list[str] = []

        for batch in self.chunk(databases, config.advanced.batch_size):

            parts: list[str] = []

            for db in batch:
                parts.append(
                    self._render(template, db).strip()
                )

            queries.append("\nUNION ALL\n".join(parts))

        return queries


sql_builder = SQLBuilder()


if __name__ == "__main__":
    sample = ["db1", "db2", "db3"]

    for sql in sql_builder.build_scan_query(sample):
        print("=" * 80)
        print(sql)
