import time
from PySide6.QtCore import QObject, Signal, Slot
from common.config import config


class CheckWorker(QObject):
    started = Signal()
    finished = Signal()
    progress = Signal(int)
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

    @Slot()
    def run(self):

        self.started.emit()

        total = len(self._servers)

        if total == 0:
            self.status.emit("No servers selected.")
            self.finished.emit()
            return

        for index, server in enumerate(self._servers, start=1):

            self.status.emit(
                f"Connecting to {server}..."
            )

            time.sleep(
                config.mysql.connect_timeout
            )

            self.result.emit(
                server,
                "cfg_settings",
                "Russia",
                "enabled",
                "OK",
                f"{0.4:.2f} s",
            )

            self.progress.emit(
                int(index * 100 / total)
            )

        self.status.emit("Completed.")

        self.finished.emit()