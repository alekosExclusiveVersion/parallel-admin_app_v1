from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QLineEdit,
    QPushButton,
    QLabel,
    QMessageBox,
)

from common.mysql_client import mysql
from common.mysql_session import session
from backend.repository import Repository
from gui.styles import LOGIN_DIALOG_STYLESHEET


class LoginDialog(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle(
            "MySQL Connection"
        )

        self.setMinimumWidth(350)

        self._build_ui()


    def _build_ui(self):

        self.setStyleSheet(LOGIN_DIALOG_STYLESHEET)

        layout = QVBoxLayout(self)

        title = QLabel(
            "Enter MySQL credentials"
        )
        title.setObjectName("DialogTitle")

        layout.addWidget(title)


        form = QFormLayout()

        self.user = QLineEdit()

        self.password = QLineEdit()
        self.password.setEchoMode(
            QLineEdit.Password
        )

        form.addRow(
            "User:",
            self.user
        )

        form.addRow(
            "Password:",
            self.password
        )


        layout.addLayout(form)


        self.btn_connect = QPushButton(
            "Connect"
        )
        self.btn_connect.setObjectName("btn_primary")

        self.btn_connect.clicked.connect(
            self._accept
        )


        layout.addWidget(
            self.btn_connect
        )


    def _accept(self):

        if not self.user.text().strip():
            self._show_error(
                "Enter the MySQL user."
            )
            return

        if not self.password.text():
            self._show_error(
                "Enter the MySQL password."
            )
            return

        session.user = self.user.text()
        session.password = self.password.text()

        self.btn_connect.setEnabled(False)
        self.btn_connect.setText("Checking...")
        self.btn_connect.repaint()

        try:

            servers = Repository().load_servers()

            if not servers:
                raise RuntimeError(
                    "No servers found in servers.txt"
                )

            with mysql.connect(servers[0]):
                pass

        except Exception as ex:

            self.btn_connect.setEnabled(True)
            self.btn_connect.setText("Connect")

            self._show_error(
                f"Connection failed: {ex}"
            )
            return

        self.btn_connect.setEnabled(True)
        self.btn_connect.setText("Connect")

        self.accept()

    def _show_error(self, message):

        QMessageBox.warning(
            self,
            "MySQL Connection",
            message,
        )