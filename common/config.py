"""
common/config.py
Загрузка и валидация config.ini
"""

from __future__ import annotations

from configparser import ConfigParser
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class MySQLConfig:
    user: str
    password: str
    connect_timeout: int
    read_timeout: int
    write_timeout: int
    retry: int


@dataclass(frozen=True)
class ParallelConfig:
    workers: int
    database_workers: int


@dataclass(frozen=True)
class FilterConfig:
    country: str
    country_setting: str
    target_setting: str
    target_value: str
    database_prefix: str
    exclude_database_regex: str


@dataclass(frozen=True)
class LoggingConfig:
    directory: Path
    csv: str
    errors: str
    run: str
    verbose: bool


@dataclass(frozen=True)
class OutputConfig:
    color: bool
    progress: bool
    eta: bool
    speed: bool
    summary: bool


@dataclass(frozen=True)
class AdvancedConfig:
    ignore_databases: tuple[str, ...]
    settings_table: str
    batch_size: int
    export_csv: bool
    export_errors: bool
    servers_file: str


@dataclass(frozen=True)
class Config:
    mysql: MySQLConfig
    parallel: ParallelConfig
    filter: FilterConfig
    logging: LoggingConfig
    output: OutputConfig
    advanced: AdvancedConfig


def _bool(cfg: ConfigParser, section: str, option: str) -> bool:
    return cfg.getboolean(section, option)


def load_config(config_file: str | Path | None = None) -> Config:
    if config_file is None:
        config_file = Path(__file__).resolve().parent.parent / "config.ini"

    config_file = Path(config_file)

    if not config_file.exists():
        raise FileNotFoundError(f"Файл конфигурации не найден: {config_file}")

    p = ConfigParser()
    p.read(config_file, encoding="utf-8")

    ignore = tuple(
        x.strip()
        for x in p.get(
            "advanced",
            "ignore_databases"
        ).replace("\n", "").split(",")
        if x.strip()
    )

    return Config(
        mysql=MySQLConfig(
            user=p.get("mysql", "user"),
            password=p.get("mysql", "password"),
            connect_timeout=p.getint("mysql", "connect_timeout"),
            read_timeout=p.getint("mysql", "read_timeout"),
            write_timeout=p.getint("mysql", "write_timeout"),
            retry=p.getint("mysql", "retry"),
        ),
        parallel=ParallelConfig(
            workers=p.getint("parallel", "workers"),
            database_workers=p.getint("parallel", "database_workers"),
        ),
        filter=FilterConfig(
            country=p.get("filter", "country").lower(),
            country_setting=p.get("filter", "country_setting"),
            target_setting=p.get("filter", "target_setting"),
            target_value=p.get("filter", "target_value"),
            database_prefix=p.get(
                "filter",
                "database_prefix",
                fallback="ar_",
            ),

            exclude_database_regex=p.get(
                "filter",
                "exclude_database_regex",
                fallback="",
            ),
        ),
        logging=LoggingConfig(
            directory=Path(p.get("logging", "directory")),
            csv=p.get("logging", "csv"),
            errors=p.get("logging", "errors"),
            run=p.get("logging", "run"),
            verbose=_bool(p, "logging", "verbose"),
        ),
        output=OutputConfig(
            color=_bool(p, "output", "color"),
            progress=_bool(p, "output", "progress"),
            eta=_bool(p, "output", "eta"),
            speed=_bool(p, "output", "speed"),
            summary=_bool(p, "output", "summary"),
        ),
        advanced=AdvancedConfig(
            ignore_databases=ignore,
            settings_table=p.get("advanced", "settings_table"),
            batch_size=p.getint("advanced", "batch_size"),
            export_csv=_bool(p, "advanced", "export_csv"),
            export_errors=_bool(p, "advanced", "export_errors"),
            servers_file=p.get("advanced", "servers_file", fallback="servers.txt",),
        ),
    )


config = load_config()


if __name__ == "__main__":
    from pprint import pprint
    pprint(config)
