"""
common/sql_builder.py

Построение пакетных SQL-запросов для чтения cfg_settings
из нескольких баз данных за один запрос (UNION ALL).
"""

from __future__ import annotations

from typing import Iterable

from common.config import config


class SQLBuilder:

    @staticmethod
    def quote_identifier(name: str) -> str:
        """Экранирование имени базы/таблицы."""
        return f"`{name.replace('`', '``')}`"

    @staticmethod
    def chunk(items: list[str], size: int) -> Iterable[list[str]]:
        for i in range(0, len(items), size):
            yield items[i:i + size]

    def build_scan_query(self, databases: list[str]) -> list[str]:
        """
        Возвращает список SQL-запросов.
        Каждый запрос содержит UNION ALL для batch_size баз.
        """

        table = config.advanced.settings_table
        country = config.filter.country_setting
        target = config.filter.target_setting

        queries: list[str] = []

        for batch in self.chunk(databases, config.advanced.batch_size):

            parts: list[str] = []

            for db in batch:
                qdb = self.quote_identifier(db)

                parts.append(f"""
SELECT
    '{db}' AS database_name,
    MAX(CASE WHEN stg_name='{country}' THEN stg_value END) AS country,
    MAX(CASE WHEN stg_name='{target}' THEN stg_value END) AS target_value
FROM {qdb}.{table}
WHERE stg_name IN ('{country}','{target}')
""".strip())

            queries.append("\nUNION ALL\n".join(parts))

        return queries


sql_builder = SQLBuilder()


if __name__ == "__main__":
    sample = ["db1", "db2", "db3"]

    for sql in sql_builder.build_scan_query(sample):
        print("=" * 80)
        print(sql)
