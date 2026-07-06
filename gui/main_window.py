from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QListWidget,
    QTableWidget,
    QTextEdit,
    QFrame,
    QHeaderView,
    QToolBar,
    QProgressBar,
)


class MainWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        self.setObjectName("MainWindow")

        self.setStyleSheet("""
        QWidget#MainWindow{
            background:#f3f5f7;
        }

        QLabel#Title{
            font-size:22px;
            font-weight:700;
            color:#2d3436;
        }

        QLabel#Subtitle{
            color:#636e72;
            margin-bottom:6px;
        }

        QFrame{
            background:white;
            border:1px solid #dfe6e9;
            border-radius:8px;
        }

        QListWidget,
        QTextEdit,
        QTableWidget{
            background:white;
            border:none;
            font-size:13px;
        }

        QToolBar{
            background:white;
            border:1px solid #dfe6e9;
            padding:6px;
            spacing:6px;
        }

        QProgressBar{
            border:1px solid #dfe6e9;
            border-radius:5px;
            background:white;
            text-align:center;
            min-height:20px;
        }

        QProgressBar::chunk{
            background:#1976d2;
            border-radius:4px;
        }
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        # ----------------------------------------------------------
        # Toolbar
        # ----------------------------------------------------------

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

        # ----------------------------------------------------------
        # Progress Panel
        # ----------------------------------------------------------

        progress_frame = QFrame()

        progress_layout = QGridLayout(progress_frame)
        progress_layout.setContentsMargins(12, 10, 12, 10)
        progress_layout.setHorizontalSpacing(24)
        progress_layout.setVerticalSpacing(6)

        self.lbl_status = QLabel("Status:")
        self.lbl_status_value = QLabel("Ready")

        self.lbl_servers = QLabel("Servers:")
        self.lbl_servers_value = QLabel("0 / 0")

        self.lbl_elapsed = QLabel("Elapsed:")
        self.lbl_elapsed_value = QLabel("00:00")

        progress_layout.addWidget(self.lbl_status, 0, 0)
        progress_layout.addWidget(self.lbl_status_value, 0, 1)

        progress_layout.addWidget(self.lbl_servers, 0, 2)
        progress_layout.addWidget(self.lbl_servers_value, 0, 3)

        progress_layout.addWidget(self.lbl_elapsed, 0, 4)
        progress_layout.addWidget(self.lbl_elapsed_value, 0, 5)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(True)

        progress_layout.addWidget(self.progress, 1, 0, 1, 6)

        root.addWidget(progress_frame)

        # ----------------------------------------------------------
        # Header
        # ----------------------------------------------------------

        title = QLabel("Parallel Admin")
        title.setObjectName("Title")

        subtitle = QLabel("Mass administration tool")
        subtitle.setObjectName("Subtitle")

        root.addWidget(title)
        root.addWidget(subtitle)

        # ----------------------------------------------------------
        # Main Area
        # ----------------------------------------------------------

        body = QHBoxLayout()
        body.setSpacing(12)

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

        right = QVBoxLayout()
        
        # ----------------------------------------------------------
        # Results
        # ----------------------------------------------------------

        table_frame = QFrame()

        table_layout = QVBoxLayout(table_frame)
        table_layout.setContentsMargins(10, 10, 10, 10)
        table_layout.setSpacing(8)

        lbl_results = QLabel("Results")
        table_layout.addWidget(lbl_results)

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

        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(
            QTableWidget.SelectRows
        )

        self.table.setSelectionMode(
            QTableWidget.SingleSelection
        )

        self.table.setEditTriggers(
            QTableWidget.NoEditTriggers
        )

        self.table.setSortingEnabled(False)

        table_layout.addWidget(self.table)

        right.addWidget(table_frame, 3)

        # ----------------------------------------------------------
        # Log
        # ----------------------------------------------------------

        log_frame = QFrame()

        log_layout = QVBoxLayout(log_frame)
        log_layout.setContentsMargins(10, 10, 10, 10)
        log_layout.setSpacing(8)

        lbl_log = QLabel("Log")
        log_layout.addWidget(lbl_log)

        self.log = QTextEdit()
        self.log.setReadOnly(True)

        self.log.append("Parallel Admin started.")
        self.log.append("Ready.")

        log_layout.addWidget(self.log)

        right.addWidget(log_frame, 1)

        body.addLayout(right, 3)

        root.addLayout(body)