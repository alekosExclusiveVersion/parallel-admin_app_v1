from PySide6.QtCore import Qt
from PySide6.QtGui import (
    QAction,
    QColor,
    QBrush,
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
        # Log
        # ----------------------------------------------------------

        log_frame = QFrame()

        log_layout = QVBoxLayout(log_frame)
        log_layout.setContentsMargins(10, 10, 10, 10)
        log_layout.setSpacing(8)

        log_layout.addWidget(QLabel("Log"))

        self.log = QTextEdit()
        self.log.setReadOnly(True)

        self.log.append("Parallel Admin started.")
        self.log.append("Ready.")

        log_layout.addWidget(self.log)

        right.addWidget(log_frame, 1)

        body.addLayout(right, 3)

        root.addLayout(body)

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
            self.log.append(
                f"Selected server: {server.text()}"
            )