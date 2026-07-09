from backend.repository import Repository
from backend.check_worker import CheckWorker
from PySide6.QtCore import (
    Qt,
    QThread,
)
from PySide6.QtGui import (
    QAction,
    QColor,
    QBrush,
    QTextCursor,
)

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QListWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QFrame,
    QFileDialog,
    QHeaderView,
    QToolBar,
    QProgressBar,
    QLineEdit,
    QPushButton,
    QAbstractItemView,
    QMenu,
)


class MainWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.repository = Repository()
        
        self._build_ui()
        self._create_backend()

        self._load_servers()
        
    # ----------------------------------------------------------
    # Backend
    # ----------------------------------------------------------

    def _create_backend(self):

        self.thread = QThread(self)

        self.worker = CheckWorker()

        self.worker.moveToThread(self.thread)

        self.worker.started.connect(
            self._check_started
        )

        self.worker.finished.connect(
            self._check_finished
        )

        self.worker.progress.connect(
            self._update_progress
        )

        self.worker.status.connect(
            lambda text: self.append_log(
                "INFO",
                text,
            )
        )

        self.worker.result.connect(
            self.add_result
        )

        self.thread.started.connect(
            self.worker.run
        )

        self.worker.finished.connect(
            self.thread.quit
        )

        self.action_check.triggered.connect(
            self._run_check
        )
        self.action_refresh.triggered.connect(
            self._refresh_servers
        )
    def _update_progress(self, current, total):

        if total == 0:
            self.progress.setValue(0)
            return

        percent = int(current * 100 / total)

        self.progress.setValue(percent)
    # ----------------------------------------------------------
    # Repository
    # ----------------------------------------------------------

    def _load_servers(self):

        servers = self.repository.load_servers()

        self.server_list.clear()

        if servers:
            self.server_list.addItems(servers)

        count = len(servers)

        self.lbl_servers_value.setText(
            f"{count} / {count}"
        )

        self.selected_label.setText(
            "Selected: 0"
        )

        self.append_log(
            "INFO",
            f"Loaded {count} server(s)."
        )


    # ----------------------------------------------------------
    # Refresh
    # ----------------------------------------------------------

    def _refresh_servers(self):

        previous = self.server_list.count()

        self._load_servers()

        current = self.server_list.count()

        self.append_log(
            "SUCCESS",
            f"Server list refreshed ({previous} → {current})"
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

        self.worker.set_servers(servers)

        self.thread.start()


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
        QTableWidget,
        QLineEdit{
            background:white;
            border:1px solid #dfe6e9;
            border-radius:4px;
            font-size:13px;
            padding:4px;
        }

        QToolBar{
            background:white;
            border:1px solid #dfe6e9;
            padding:6px;
            spacing:6px;
        }

        QPushButton{
            min-height:28px;
            border:1px solid #d0d7de;
            border-radius:4px;
            background:white;
        }

        QPushButton:hover{
            background:#f5f5f5;
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

        progress_frame = QFrame()

        progress_layout = QGridLayout(progress_frame)

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

        progress_layout.addWidget(self.progress, 1, 0, 1, 6)

        root.addWidget(progress_frame)

        title = QLabel("Parallel Admin")
        title.setObjectName("Title")

        subtitle = QLabel("Mass administration tool")
        subtitle.setObjectName("Subtitle")

        root.addWidget(title)
        root.addWidget(subtitle)

        body = QHBoxLayout()
        body.setSpacing(12)

        server_frame = QFrame()
        server_layout = QVBoxLayout(server_frame)

        server_layout.addWidget(QLabel("Servers"))

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search server...")
        server_layout.addWidget(self.search)

        self.selected_label = QLabel("Selected: 0")
        server_layout.addWidget(self.selected_label)

        buttons = QHBoxLayout()

        self.btn_select_all = QPushButton("Select All")
        self.btn_clear = QPushButton("Clear")
        self.btn_invert = QPushButton("Invert")

        buttons.addWidget(self.btn_select_all)
        buttons.addWidget(self.btn_clear)
        buttons.addWidget(self.btn_invert)

        server_layout.addLayout(buttons)

        self.server_list = QListWidget()
        self.server_list.setSelectionMode(
            QAbstractItemView.ExtendedSelection
        )

        server_layout.addWidget(self.server_list)

        body.addWidget(server_frame, 1)

        right = QVBoxLayout()
        table_frame = QFrame()

        table_layout = QVBoxLayout(table_frame)
        table_layout.setContentsMargins(10, 10, 10, 10)
        table_layout.setSpacing(8)

        table_layout.addWidget(QLabel("Results"))

        self.table = QTableWidget()

        self.table.setColumnCount(6)

        self.table.setHorizontalHeaderLabels([
            "Server",
            "Database",
            "Country",
            "Value",
            "Status",
            "Duration",
        ])

        self.table.verticalHeader().setVisible(False)

        header = self.table.horizontalHeader()

        header.setStretchLastSection(False)

        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)

        self.table.setAlternatingRowColors(True)

        self.table.setSortingEnabled(True)

        self.table.setSelectionBehavior(
            QTableWidget.SelectRows
        )

        self.table.setSelectionMode(
            QTableWidget.SingleSelection
        )

        self.table.setEditTriggers(
            QTableWidget.NoEditTriggers
        )

        self.table.setShowGrid(False)

        self.table.setWordWrap(False)

        self.table.setCornerButtonEnabled(False)

        self.table.setFocusPolicy(Qt.StrongFocus)

        # ----------------------------------------------------------
        # ResultTable signals
        # ----------------------------------------------------------

        self.table.setContextMenuPolicy(Qt.CustomContextMenu)

        self.table.customContextMenuRequested.connect(
            self._show_table_menu
        )

        self.table.itemDoubleClicked.connect(
            self._table_double_click
        )

        table_layout.addWidget(self.table)

        right.addWidget(table_frame, 3)

        # ----------------------------------------------------------
        # Log Panel UI
        # ----------------------------------------------------------

        log_frame = QFrame()

        log_layout = QVBoxLayout(log_frame)
        log_layout.setContentsMargins(10, 10, 10, 10)
        log_layout.setSpacing(8)

        top = QHBoxLayout()

        top.addWidget(QLabel("Log"))

        top.addStretch()

        self.btn_log_clear = QPushButton("Clear")
        self.btn_log_copy = QPushButton("Copy")
        self.btn_log_save = QPushButton("Save")

        top.addWidget(self.btn_log_clear)
        top.addWidget(self.btn_log_copy)
        top.addWidget(self.btn_log_save)

        log_layout.addLayout(top)

        self.log = QTextEdit()
        self.log.setReadOnly(True)

        log_layout.addWidget(self.log)

        right.addWidget(log_frame, 1)

        self.append_log("INFO", "Parallel Admin started.")
        self.append_log("SUCCESS", "GUI initialized.")
        self.append_log("INFO", "Ready.")

        # ----------------------------------------------------------
        # Signals
        # ----------------------------------------------------------

        self.server_list.itemSelectionChanged.connect(
            self._update_selected_count
        )

        self.btn_select_all.clicked.connect(
            self.server_list.selectAll
        )

        self.btn_clear.clicked.connect(
            self.server_list.clearSelection
        )

        self.btn_invert.clicked.connect(
            self._invert_selection
        )

        self.search.textChanged.connect(
            self._filter_servers
        )

        self.btn_log_clear.clicked.connect(
            self.log.clear
        )

        self.btn_log_copy.clicked.connect(
            self.log.copy
        )

        self.btn_log_save.clicked.connect(
            self._save_log
        )
        body.addLayout(right, 3)

        root.addLayout(body)
    # --------------------------------------------------------------
    # Slots
    # --------------------------------------------------------------

    def _update_selected_count(self):
        self.selected_label.setText(
            f"Selected: {len(self.server_list.selectedItems())}"
        )

    def _invert_selection(self):
        for row in range(self.server_list.count()):
            item = self.server_list.item(row)
            item.setSelected(not item.isSelected())

        self._update_selected_count()

    def _filter_servers(self, text):
        text = text.lower().strip()

        for row in range(self.server_list.count()):
            item = self.server_list.item(row)

            item.setHidden(
                text not in item.text().lower()
            )
    # ----------------------------------------------------------
    # ResultTable
    # ----------------------------------------------------------

    def add_result(
        self,
        server,
        database,
        country,
        value,
        status="OK",
        duration="-",
    ):

        row = self.table.rowCount()

        self.table.insertRow(row)

        values = [
            server,
            database,
            country,
            value,
            status,
            duration,
        ]

        for column, text in enumerate(values):

            item = QTableWidgetItem(str(text))

            item.setFlags(
                item.flags() & ~Qt.ItemIsEditable
            )

            if column == 4:

                if status == "OK":
                    item.setForeground(
                        QBrush(QColor("#2e7d32"))
                    )

                elif status == "WARNING":
                    item.setForeground(
                        QBrush(QColor("#ef6c00"))
                    )

                elif status == "ERROR":
                    item.setForeground(
                        QBrush(QColor("#c62828"))
                    )

            self.table.setItem(
                row,
                column,
                item,
            )

    def clear_results(self):
        self.table.setRowCount(0)

    def _show_table_menu(self, pos):

        menu = QMenu(self)

        clear_action = menu.addAction("Clear results")

        action = menu.exec(
            self.table.viewport().mapToGlobal(pos)
        )

        if action == clear_action:
            self.clear_results()

    def _table_double_click(self, item):

        row = item.row()

        server = self.table.item(row, 0)

        if server:
            self.append_log(
                "INFO",
                f"Selected server: {server.text()}"
            )

    # ----------------------------------------------------------
    # Log Methods
    # ----------------------------------------------------------

    def append_log(self, level: str, message: str):

        colors = {
            "INFO": "#1565c0",
            "SUCCESS": "#2e7d32",
            "WARNING": "#ef6c00",
            "ERROR": "#c62828",
        }

        color = colors.get(level.upper(), "#212121")

        self.log.append(
            f'<span style="color:{color};"><b>[{level.upper()}]</b></span> {message}'
        )

        self.log.moveCursor(QTextCursor.End)

    def _save_log(self):

        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Save log",
            "parallel_admin.log",
            "Log files (*.log);;Text files (*.txt);;All files (*)",
        )

        if not filename:
            return

        with open(filename, "w", encoding="utf-8") as f:
            f.write(self.log.toPlainText())

        self.append_log(
            "SUCCESS",
            f"Log saved to {filename}",
        )

    def closeEvent(self, event):

        if self.thread.isRunning():
            self.thread.quit()
            self.thread.wait()

        event.accept()