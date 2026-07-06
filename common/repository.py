"""
common/repository.py

Бизнес-логика работы с проектами.
"""

from __future__ import annotations

from common.config import config
from common.mysql_client import mysql
from common.models import (
    CheckResult,
    Project,
    ProjectSettings,
    UpdateResult,
    VerifyResult,
    ProjectStatus,
)


class ProjectRepository:

    def find_projects(self, server: str) -> list[Project]:
        projects: list[Project] = []

        for db in mysql.list_databases(server):
            if not mysql.has_cfg_settings(server, db):
                continue

            settings = mysql.get_settings(server, db)

            project = Project(
                server=server,
                database=db,
                settings=ProjectSettings(
                    country=settings.get(
                        config.filter.country_setting,
                        "",
                    ),
                    ban_email_domain=settings.get(
                        config.filter.target_setting,
                        "",
                    ),
                ),
            )

            if project.is_target_country:
                projects.append(project)

        return projects

    def check(self, server: str) -> list[CheckResult]:
        return [
            CheckResult(
                server=p.server,
                database=p.database,
                country=p.settings.country,
                value=p.settings.ban_email_domain,
            )
            for p in self.find_projects(server)
        ]
    
    raise RuntimeError(
        "Режим обновления временно отключён. Используйте только check.py."
    )
    # def update(self, server: str):
    # def update(self, server: str) -> list[UpdateResult]:
    #     results: list[UpdateResult] = []

    #     for project in self.find_projects(server):
    #         affected = mysql.update_setting(
    #             server,
    #             project.database,
    #             config.filter.target_value,
    #         )

    #         results.append(
    #             UpdateResult(
    #                 server=project.server,
    #                 database=project.database,
    #                 affected_rows=affected,
    #                 status=(
    #                     ProjectStatus.UPDATED
    #                     if affected
    #                     else ProjectStatus.SKIPPED
    #                 ),
    #                 message=(
    #                     "Updated"
    #                     if affected
    #                     else "Already актуально"
    #                 ),
    #             )
    #         )

        # return results

    def verify(self, server: str) -> list[VerifyResult]:
        rows: list[VerifyResult] = []

        expected = config.filter.target_value

        for project in self.find_projects(server):
            rows.append(
                VerifyResult(
                    server=project.server,
                    database=project.database,
                    expected=expected,
                    actual=project.settings.ban_email_domain,
                )
            )

        return rows


repository = ProjectRepository()
