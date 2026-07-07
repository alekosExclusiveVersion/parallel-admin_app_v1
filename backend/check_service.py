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
    
    def _create_backend(self):

        self.check_service = CheckService(self)

        self.check_service.started.connect(
            self._check_started
        )

        self.check_service.finished.connect(
            self._check_finished
        )

        self.check_service.progress.connect(
            self.progress.setValue
        )

        self.check_service.status.connect(
            lambda text: self.append_log(
                "INFO",
                text,
            )
        )

        self.check_service.result.connect(
            self.add_result
        )

        self.action_check.triggered.connect(
            self._run_check
        )

# ----------------------------------------------------------
# Check
# ----------------------------------------------------------

def _run_check(self):

    self.clear_results()

    self.progress.setValue(0)

    servers = [
        item.text()
        for item in self.server_list.selectedItems()
    ]

    self.check_service.run(servers)


def _check_started(self):

    self.action_check.setEnabled(False)
    self.action_stop.setEnabled(True)

    self.lbl_status_value.setText("Running")

    self.append_log(
        "INFO",
        "Check started.",
    )


def _check_finished(self):

    self.action_check.setEnabled(True)
    self.action_stop.setEnabled(False)

    self.lbl_status_value.setText("Ready")

    self.append_log(
        "SUCCESS",
        "Check completed.",
    )