# src/gui/main_window.py

from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QListWidget,
    QTableWidget,
    QTableWidgetItem,
    QPushButton,
    QTextEdit,
)


class MainWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)

        # Верхняя панель
        header = QLabel("Parallel Admin v1.0")
        header.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(header)

        # Основная зона
        body = QHBoxLayout()

        # Список серверов
        self.server_list = QListWidget()
        self.server_list.addItems([
            "p7ru1.tradesoft.ru",
            "p7ru3.tradesoft.ru",
            "p7ru4.tradesoft.ru",
            "p7ru5.tradesoft.ru",
            "p7ru8.tradesoft.ru",
        ])

        body.addWidget(self.server_list, 1)

        # Таблица результатов
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels([
            "Server", "Database", "Country", "Value"
        ])

        body.addWidget(self.table, 3)

        layout.addLayout(body)

        # Лог
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.append("Ready")
        layout.addWidget(self.log)

        # Кнопка (пока без логики)
        self.btn = QPushButton("Check")
        layout.addWidget(self.btn)