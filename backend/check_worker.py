import time
from concurrent.futures import (
    ThreadPoolExecutor,
    as_completed,
)
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
            
            self.status.emit(
                f"{server}: connecting..."
            )

            with mysql.connect(server) as conn:

                databases = mysql.list_databases_conn(conn)

                self.status.emit(
                    f"{server}: found {len(databases)} database(s)"
                )

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
                        self.status.emit(
                            f"{server}/{database}: ERROR"
                        )

                        self.result.emit(
                            server,
                            database,
                            "-",
                            "-",
                            "ERROR",
                            str(ex),
                        )
                                
                self.status.emit(
                    f"{server}: completed"
                )

        except Exception as ex:
            
            self.status.emit(
                f"{server}: {ex}"
            )

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
        
        self.started.emit()

        self.status.emit(
            f"Checking {len(self._servers)} server(s)..."
        )

        if not self._servers:

            self.status.emit(
                "No servers selected."
            )

            self.finished.emit()
            return

        total = len(self._servers)

        with ThreadPoolExecutor(
            max_workers=config.parallel.workers
        ) as executor:

            futures = {
                executor.submit(
                    self._check_server,
                    server,
                ): server
                for server in self._servers
            }

            completed = 0

            for future in as_completed(futures):

                future.result()

                completed += 1

                self.progress.emit(
                    completed,
                    total,
                )

        self.status.emit(
            "Check finished."
        )

        self.finished.emit()