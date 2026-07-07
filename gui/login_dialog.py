from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QLineEdit,
    QPushButton,
    QLabel,
)

from common.mysql_client import mysql
from common.mysql_session import session


class LoginDialog(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle(
            "MySQL Connection"
        )

        self.setMinimumWidth(350)

        self._build_ui()


    def _build_ui(self):

        layout = QVBoxLayout(self)

        title = QLabel(
            "Enter MySQL credentials"
        )

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

        self.btn_connect.clicked.connect(
            self._accept
        )


        layout.addWidget(
            self.btn_connect
        )


    def _accept(self):

        if not self.user.text().strip():
            return

        if not self.password.text():
            return

        session.user = self.user.text()
        session.password = self.password.text()

        self.accept()