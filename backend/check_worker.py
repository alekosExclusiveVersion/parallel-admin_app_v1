import time
from concurrent.futures import ThreadPoolExecutor
from common.mysql_client import mysql
from PySide6.QtCore import QObject, Signal, Slot
from common.config import config


class CheckWorker(QObject):
    started = Signal()
    finished = Signal()
    progress = Signal(int, int)
    status = Signal(str)
    result = Signal(
        str,
        str,
        str,
        str,
        str,
        str,
    )

    def __init__(self):
        super().__init__()
        self._servers = []

    def set_servers(self, servers):
        self._servers = list(servers)

    @property
    def servers(self):

        return self._servers

    @Slot()
    
    def _check_server(self, server: str):

        try:

            with mysql.connect(server) as conn:

                databases = mysql.list_databases_conn(conn)

                for database in databases:

                    try:

                        settings = mysql.get_settings_conn(
                            conn,
                            database,
                        )

                        country = settings.get(
                            config.filter.country_setting,
                            "-",
                        )

                        value = settings.get(
                            config.filter.target_setting,
                            "-",
                        )

                        self.result.emit(
                            server,
                            database,
                            country,
                            value,
                            "OK",
                            "",
                        )

                    except Exception as ex:

                        self.result.emit(
                            server,
                            database,
                            "-",
                            "-",
                            "ERROR",
                            str(ex),
                        )

        except Exception as ex:

            self.result.emit(
                server,
                "-",
                "-",
                "-",
                "ERROR",
                str(ex),
            )

    @Slot()
    def run(self):

        if not self._servers:
            self.finished.emit()
            return

        total = len(self._servers)

        for index, server in enumerate(self._servers, start=1):

            self.progress.emit(index, total)

            self._check_server(server)

            self.finished.emit()