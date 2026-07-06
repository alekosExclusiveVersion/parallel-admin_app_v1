from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QTableWidget,
    QTextEdit,
    QFrame,
    QHeaderView,
    QToolBar,
)

from PySide6.QtGui import QAction


class MainWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self._build_ui()

    def _build_ui(self):
        self.setObjectName("MainWindow")

        self.setStyleSheet("""
        QWidget#MainWindow {
            background:#f3f5f7;
        }

        QLabel#Title{
            font-size:22px;
            font-weight:700;
            color:#2d3436;
        }

        QLabel#Subtitle{
            color:#636e72;
        }

        QFrame{
            background:white;
            border:1px solid #dfe6e9;
            border-radius:8px;
        }

        QListWidget,
        QTextEdit,
        QTableWidget{
            border:none;
            background:white;
            font-size:13px;
        }

        QToolBar{
            background:white;
            border:1px solid #dfe6e9;
            spacing:6px;
            padding:6px;
        }
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        # ------------------------------------------------------------------
        # Toolbar
        # ------------------------------------------------------------------

        self.toolbar = QToolBar()

        self.action_refresh = QAction("Refresh", self)
        self.action_check = QAction("Check", self)
        self.action_update = QAction("Update", self)
        self.action_verify = QAction("Verify", self)
        self.action_stop = QAction("Stop", self)

        self.action_update.setEnabled(False)
        self.action_verify.setEnabled(False)
        self.action_stop.setEnabled(False)

        self.toolbar.addAction(self.action_refresh)
        self.toolbar.addSeparator()

        self.toolbar.addAction(self.action_check)
        self.toolbar.addAction(self.action_update)
        self.toolbar.addAction(self.action_verify)

        self.toolbar.addSeparator()

        self.toolbar.addAction(self.action_stop)

        root.addWidget(self.toolbar)

        # ------------------------------------------------------------------
        # Header
        # ------------------------------------------------------------------

        title = QLabel("Parallel Admin")
        title.setObjectName("Title")

        subtitle = QLabel("Mass administration tool")
        subtitle.setObjectName("Subtitle")

        root.addWidget(title)
        root.addWidget(subtitle)

        # ------------------------------------------------------------------
        # Main Area
        # ------------------------------------------------------------------

        body = QHBoxLayout()
        body.setSpacing(12)

        # Servers

        server_frame = QFrame()

        server_layout = QVBoxLayout(server_frame)
        server_layout.setContentsMargins(10, 10, 10, 10)

        server_layout.addWidget(QLabel("Servers"))

        self.server_list = QListWidget()

        self.server_list.addItems([
            "p7ru1.tradesoft.ru",
            "p7ru3.tradesoft.ru",
            "p7ru4.tradesoft.ru",
            "p7ru5.tradesoft.ru",
            "p7ru8.tradesoft.ru",
        ])

        server_layout.addWidget(self.server_list)

        body.addWidget(server_frame, 1)

        # Right side

        right = QVBoxLayout()

        # Table

        table_frame = QFrame()

        table_layout = QVBoxLayout(table_frame)
        table_layout.setContentsMargins(10, 10, 10, 10)

        table_layout.addWidget(QLabel("Results"))

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(
            ["Server", "Database", "Country", "Value"]
        )

        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )

        self.table.verticalHeader().hide()

        table_layout.addWidget(self.table)

        right.addWidget(table_frame, 3)

        # Log

        log_frame = QFrame()

        log_layout = QVBoxLayout(log_frame)
        log_layout.setContentsMargins(10, 10, 10, 10)

        log_layout.addWidget(QLabel("Log"))

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.append("Parallel Admin started.")

        log_layout.addWidget(self.log)

        right.addWidget(log_frame, 1)

        body.addLayout(right, 3)

        root.addLayout(body)