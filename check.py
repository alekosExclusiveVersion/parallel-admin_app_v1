"""
check.py

Поиск проектов, где:
csSystemCountry == country из config.ini

Выводит:
SERVER | DATABASE | COUNTRY | TARGET_VALUE

Результат сохраняется в CSV.
"""

from __future__ import annotations

import csv
from pathlib import Path

from common.config import config
from common.logger import logger
from common.mysql_client import mysql
from common.worker import worker_pool


def load_servers() -> list[str]:
    servers_file = Path(__file__).parent / "servers.txt"

    if not servers_file.exists():
        raise FileNotFoundError(f"Не найден файл: {servers_file}")

    with servers_file.open(encoding="utf-8") as f:
        return [
            line.strip()
            for line in f
            if line.strip() and not line.startswith("#")
        ]


def process_server(server: str):
    rows: list[dict] = []

    logger.info(f"{server}: подключение")

    for db in mysql.list_databases(server):

        if not mysql.has_cfg_settings(server, db):
            continue

        settings = mysql.get_settings(server, db)

        country = settings.get(config.filter.country_setting, "").lower()

        if country != config.filter.country:
            continue

        rows.append(
            {
                "server": server,
                "database": db,
                "country": country,
                "value": settings.get(config.filter.target_setting, ""),
            }
        )

    logger.success(f"{server}: найдено {len(rows)} проектов")

    return rows


def save_csv(data: list[dict]) -> None:

    log_dir = config.logging.directory
    log_dir.mkdir(exist_ok=True)

    csv_file = log_dir / config.logging.csv

    with csv_file.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as f:

        writer = csv.writer(f)

        writer.writerow(
            [
                "SERVER",
                "DATABASE",
                "COUNTRY",
                config.filter.target_setting,
            ]
        )

        for item in data:
            writer.writerow(
                [
                    item["server"],
                    item["database"],
                    item["country"],
                    item["value"],
                ]
            )

    logger.success(f"CSV сохранён: {csv_file}")


def main():

    servers = load_servers()

    logger.info(f"Серверов: {len(servers)}")

    results = worker_pool.run(
        servers,
        process_server,
    )

    all_rows = []

    print()
    print(
        f'{"SERVER":20} '
        f'{"DATABASE":35} '
        f'{"COUNTRY":10} '
        f'{config.filter.target_setting}'
    )
    print("-" * 95)

    for result in results:

        if not result.success:
            continue

        for row in result.value:

            print(
                f'{row["server"]:20} '
                f'{row["database"]:35} '
                f'{row["country"]:10} '
                f'{row["value"]}'
            )

            all_rows.append(row)

    save_csv(all_rows)

    logger.success(
        f"Всего найдено проектов: {len(all_rows)}"
    )


if __name__ == "__main__":
    main()
