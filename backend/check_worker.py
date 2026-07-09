import time
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
    
    def run(self):

        if not self._servers:
            self.finished.emit()
            return

        total = len(self._servers)

        for index, server in enumerate(self._servers, start=1):

            self.progress.emit(index, total)

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
                                "csSystemCountry",
                                "-"
                            )

                            value = settings.get(
                                "banEmailDomain",
                                "-"
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

                            continue

            except Exception as ex:

                self.result.emit(
                    server,
                    "-",
                    "-",
                    "-",
                    "ERROR",
                    str(ex),
                )

        self.finished.emit()