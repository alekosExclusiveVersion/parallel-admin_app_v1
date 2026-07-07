from PySide6.QtCore import QObject, Signal


class CheckService(QObject):
    started = Signal()
    finished = Signal()
    progress = Signal(int)
    status = Signal(str)
    result = Signal(
        str,  # server
        str,  # database
        str,  # country
        str,  # value
        str,  # status
        str,  # duration
    )

    def __init__(self, parent=None):
        super().__init__(parent)

    def run(self, servers):

        self.started.emit()

        total = len(servers)

        if total == 0:
            self.status.emit("No servers selected.")
            self.finished.emit()
            return

        for index, server in enumerate(servers, start=1):

            self.status.emit(f"Checking {server}...")

            self.result.emit(
                server,
                "cfg_settings",
                "Russia",
                "enabled",
                "OK",
                "0.12 s",
            )

            self.progress.emit(
                int(index * 100 / total)
            )

        self.status.emit("Completed.")

        self.finished.emit()