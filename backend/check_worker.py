import time

from concurrent.futures import (
    ThreadPoolExecutor,
    as_completed,
)

from common.mysql_client import mysql
from common.stats import stats
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

        results = []
        messages = []

        try:
            
            messages.append(
                f"{server}: connecting..."
            )
            
            with mysql.connect(server) as conn:

                databases = mysql.list_databases_conn(conn)

            messages.append(
                f"{server}: found {len(databases)} database(s)"
            )

            with ThreadPoolExecutor(
                max_workers=config.parallel.database_workers,
            ) as executor:

                futures = {
                    executor.submit(
                        self._check_database,
                        server,
                        database,
                    ): database
                    for database in databases
                }

                for future in as_completed(futures):

                    row, message = future.result()

                    results.append(row)

                    if message:
                        messages.append(message)

        except Exception as ex:
            
            messages.append(
                f"{server}: {ex}"
            )

            results.append(
                (
                    server,
                    "-",
                    "-",
                    "-",
                    "ERROR",
                    str(ex),
                )
            )
    
        return results, messages
    
    @Slot()

    def _check_database(
        self,
        server: str,
        database: str,
    ):

        try:

            with mysql.connect(
                server,
                database,
            ) as conn:

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

                return (
                    (
                        server,
                        database,
                        country,
                        value,
                        "OK",
                        "",
                    ),
                    None,
                )
        except Exception as ex:

            return (
                (
                    server,
                    database,
                    "-",
                    "-",
                    "ERROR",
                    str(ex),
                ),
                f"{server}/{database}: {ex}",
            )
        
    def run(self):
        
        self.started.emit()

        stats.reset()

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

                try:
                    rows, messages = future.result()

                except Exception as ex:

                    self.status.emit(
                        f"Worker error: {ex}"
                    )

                    completed += 1
                    
                    stats.server()

                    self.progress.emit(
                        completed,
                        total,
                    )

                    continue

                for message in messages:
                    self.status.emit(message)

                for row in rows:
                    
                    stats.database()

                    if row[4] == "OK":
                        stats.success()
                    else:
                        stats.error()

                    self.result.emit(*row)

                stats.server()

                completed += 1

                self.progress.emit(
                    completed,
                    total,
                )
        
        self.status.emit(
            "Check finished."
        )
        summary = stats.summary()

        self.status.emit("")
        self.status.emit("========== SUMMARY ==========")
        self.status.emit(f"Servers   : {summary['servers']}")
        self.status.emit(f"Databases : {summary['databases']}")
        self.status.emit(f"Errors    : {summary['errors']}")
        self.status.emit(f"Elapsed   : {summary['elapsed']:.2f} sec")
        
        self.finished.emit()