from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QTableWidget,
    QTextEdit,
    QPushButton,
    QFrame,
    QSizePolicy,
    QHeaderView,
)


class MainWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self._build_ui()

    def _build_ui(self):
        self.setObjectName("MainWindow")

        self.setStyleSheet("""
        QWidget#MainWindow {
            background: #f3f5f7;
        }

        QLabel#Title {
            font-size: 22px;
            font-weight: 700;
            color: #2d3436;
            padding: 6px;
        }

        QLabel#Subtitle {
            color: #636e72;
            padding-left: 6px;
            padding-bottom: 8px;
        }

        QFrame {
            background: white;
            border: 1px solid #dfe6e9;
            border-radius: 8px;
        }

        QListWidget,
        QTableWidget,
        QTextEdit {
            border: none;
            background: white;
            font-size: 13px;
        }

        QPushButton {
            min-height: 34px;
            background: #1976d2;
            color: white;
            border: none;
            border-radius: 6px;
            padding: 0 18px;
        }

        QPushButton:hover {
            background: #1565c0;
        }

        QPushButton:pressed {
            background: #0d47a1;
        }
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(12)

        # -------------------------------------------------
        # Header
        # -------------------------------------------------

        title = QLabel("Parallel Admin")
        title.setObjectName("Title")

        subtitle = QLabel("Mass administration tool")
        subtitle.setObjectName("Subtitle")

        root.addWidget(title)
        root.addWidget(subtitle)

        # -------------------------------------------------
        # Central area
        # -------------------------------------------------

        central = QHBoxLayout()
        central.setSpacing(12)

        # Left panel

        left_frame = QFrame()
        left_layout = QVBoxLayout(left_frame)
        left_layout.setContentsMargins(10, 10, 10, 10)

        left_layout.addWidget(QLabel("Servers"))

        self.server_list = QListWidget()

        self.server_list.addItems([
            "p7ru1.tradesoft.ru",
            "p7ru3.tradesoft.ru",
            "p7ru4.tradesoft.ru",
            "p7ru5.tradesoft.ru",
            "p7ru8.tradesoft.ru",
        ])

        left_layout.addWidget(self.server_list)

        # Right panel

        right_layout = QVBoxLayout()
        right_layout.setSpacing(12)

        table_frame = QFrame()
        table_layout = QVBoxLayout(table_frame)
        table_layout.setContentsMargins(10, 10, 10, 10)

        table_layout.addWidget(QLabel("Results"))

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels([
            "Server",
            "Database",
            "Country",
            "Value",
        ])

        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )

        self.table.verticalHeader().setVisible(False)

        table_layout.addWidget(self.table)

        log_frame = QFrame()
        log_layout = QVBoxLayout(log_frame)
        log_layout.setContentsMargins(10, 10, 10, 10)

        log_layout.addWidget(QLabel("Log"))

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.append("Parallel Admin started.")

        log_layout.addWidget(self.log)

        right_layout.addWidget(table_frame, 4)
        right_layout.addWidget(log_frame, 2)

        central.addWidget(left_frame, 1)
        central.addLayout(right_layout, 3)

        root.addLayout(central)

        # -------------------------------------------------
        # Footer
        # -------------------------------------------------

        footer = QHBoxLayout()

        footer.addStretch()

        self.btn_check = QPushButton("Check")
        self.btn_update = QPushButton("Update")
        self.btn_verify = QPushButton("Verify")

        self.btn_update.setEnabled(False)
        self.btn_verify.setEnabled(False)

        footer.addWidget(self.btn_check)
        footer.addWidget(self.btn_update)
        footer.addWidget(self.btn_verify)

        root.addLayout(footer)