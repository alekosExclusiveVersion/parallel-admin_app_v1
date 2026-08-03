import time

from concurrent.futures import (
    ThreadPoolExecutor,
    as_completed,
)

from common.mysql_client import mysql
from common.stats import stats
from common.sql_builder import sql_builder
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
        self._stop_requested = False

    def set_servers(self, servers):
        self._servers = list(servers)
    
    def stop(self):

        self._stop_requested = True

    @property
    def servers(self):

        return self._servers

    @Slot()
    
    def _check_server(self, server: str):

        results = []
        messages = []

        if self._stop_requested:
            return results, messages

        try:
            
            messages.append(
                f"{server}: connecting..."
            )
            
            with mysql.connect(server) as conn:

                databases = mysql.list_databases_conn(conn)

            messages.append(
                f"{server}: found {len(databases)} database(s)"
            )

            batches = list(
                sql_builder.chunk(
                    databases,
                    config.advanced.batch_size,
                )
            )

            executor = ThreadPoolExecutor(
                max_workers=config.parallel.database_workers,
            )

            futures = {
                executor.submit(
                    self._check_batch,
                    server,
                    batch,
                ): batch
                for batch in batches
            }

            try:

                for future in as_completed(futures):

                    if self._stop_requested:

                        for pending in futures:
                            pending.cancel()

                        break

                    rows, messages_batch = future.result()

                    results.extend(rows)

                    messages.extend(messages_batch)

            finally:

                executor.shutdown(wait=True)

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

    def _check_batch(
        self,
        server: str,
        databases: list,
    ):

        rows = []
        messages = []

        try:

            with mysql.connect(server) as conn:

                batch_rows = mysql.scan_settings_batch(
                    conn,
                    databases,
                )

            for item in batch_rows:

                rows.append(
                    (
                        server,
                        item["database_name"],
                        item["country"] or "-",
                        item["target_value"] or "-",
                        "OK",
                        "",
                    )
                )

        except Exception as ex:

            for database in databases:

                rows.append(
                    (
                        server,
                        database,
                        "-",
                        "-",
                        "ERROR",
                        str(ex),
                    )
                )

            messages.append(
                f"{server}/{databases[0]}: {ex}"
            )

        return rows, messages

    @Slot()    
    def run(self):
        
        self._stop_requested = False
        
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

        completed = 0

        executor = ThreadPoolExecutor(
            max_workers=config.parallel.workers
        )

        futures = {
            executor.submit(
                self._check_server,
                server,
            ): server
            for server in self._servers
        }

        try:

            for future in as_completed(futures):

                if self._stop_requested:

                    for pending in futures:
                        pending.cancel()

                    break

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

        finally:

            executor.shutdown(wait=True)
        
        if self._stop_requested:

            self.status.emit(
                "Check stopped."
            )

        else:

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