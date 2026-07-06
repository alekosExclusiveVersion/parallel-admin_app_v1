"""
common/models.py

Модели данных проекта Parallel Admin.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class ProjectStatus(str, Enum):
    OK = "OK"
    UPDATED = "UPDATED"
    SKIPPED = "SKIPPED"
    ERROR = "ERROR"


@dataclass(slots=True)
class ServerInfo:
    name: str
    started_at: datetime = field(default_factory=datetime.now)
    databases: int = 0
    projects: int = 0
    errors: int = 0


@dataclass(slots=True)
class DatabaseInfo:
    server: str
    name: str
    has_cfg_settings: bool = False


@dataclass(slots=True)
class ProjectSettings:
    country: str = ""
    ban_email_domain: str = ""


@dataclass(slots=True)
class Project:
    server: str
    database: str
    settings: ProjectSettings
    status: ProjectStatus = ProjectStatus.OK
    message: str = ""

    @property
    def is_target_country(self) -> bool:
        return self.settings.country.lower() == "russia"


@dataclass(slots=True)
class UpdateResult:
    server: str
    database: str
    affected_rows: int
    status: ProjectStatus
    message: str = ""


@dataclass(slots=True)
class CheckResult:
    server: str
    database: str
    country: str
    value: str


@dataclass(slots=True)
class VerifyResult:
    server: str
    database: str
    expected: str
    actual: str

    @property
    def success(self) -> bool:
        return self.expected == self.actual


@dataclass(slots=True)
class RunStatistics:
    servers: int = 0
    databases: int = 0
    matched_projects: int = 0
    updated_projects: int = 0
    errors: int = 0

    def reset(self) -> None:
        self.servers = 0
        self.databases = 0
        self.matched_projects = 0
        self.updated_projects = 0
        self.errors = 0
