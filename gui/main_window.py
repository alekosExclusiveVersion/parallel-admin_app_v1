from __future__ import annotations

import csv
import re
import time
from datetime import datetime

from PySide6.QtCore import (
    Qt,
    QSize,
    QThread,
    QTimer,
)
from PySide6.QtGui import (
    QAction,
    QColor,
    QBrush,
    QFontDatabase,
    QKeySequence,
    QShortcut,
    QTextCursor,
)
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QFrame,
    QFileDialog,
    QHeaderView,
    QToolBar,
    QToolButton,
    QProgressBar,
    QLineEdit,
    QCheckBox,
    QComboBox,
    QPushButton,
    QAbstractItemView,
    QApplication,
    QMenu,
    QMessageBox,
    QSplitter,
    QPlainTextEdit,
    QStyledItemDelegate,
    QTabWidget,
)

from backend.repository import Repository
from backend.check_worker import CheckWorker
from backend.query_worker import ALL_DATABASES, QueryWorker
from backend.db_search_worker import DatabaseSearchWorker
from common.sql_builder import sql_builder
from common.version import APP_VERSION
from gui.icons import icon
from gui.sql_highlighter import SQLHighlighter
from gui.styles import SHARED_STYLESHEET


class ComboItemDelegate(QStyledItemDelegate):
    """Отступы внутри пунктов выпадающего списка."""

    def sizeHint(self, option, index):
        size = super().sizeHint(option, index)
        return QSize(
            size.width() + 24,
            max(size.height() + 12, 34),
        )


WRITE_KEYWORDS = {
    "UPDATE", "INSERT", "DELETE", "ALTER", "DROP", "TRUNCATE",
    "REPLACE", "CREATE", "GRANT", "REVOKE", "RENAME", "CALL",
    "LOCK", "UNLOCK", "KILL", "LOAD", "SET",
}


def is_write_statement(sql: str) -> bool:
    """True, если запрос может изменять данные."""
    cleaned = re.sub(
        r"/\*.*?\*/",
        " ",
        sql,
        flags=re.DOTALL,
    )
    cleaned = re.sub(
        r"(--|#)[^\n]*",
        " ",
        cleaned,
    )
    tokens = re.findall(
        r"\b[A-Z_]+\b",
        cleaned.upper(),
    )
    return any(
        token in WRITE_KEYWORDS
        for token in tokens
    )


class MainWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.repository = Repository()
        
        self._build_ui()
        self._create_backend()
        self._create_query_backend()
        self._create_search_backend()

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

        self.worker.query.connect(
            self._append_query
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
        self.action_stop.triggered.connect(
            self._stop_check
        )
        self.action_refresh.triggered.connect(
            self._refresh_servers
        )
        self.action_toggle_servers.toggled.connect(
            self._toggle_servers_panel
        )
        self.action_toggle_results.toggled.connect(
            self._toggle_results_panel
        )

    def _create_query_backend(self):

        self.query_thread = QThread(self)

        self.query_worker = QueryWorker()

        self.query_worker.moveToThread(self.query_thread)

        self.query_thread.started.connect(
            self.query_worker.run
        )

        self.query_worker.finished.connect(
            self.query_thread.quit
        )

        self.query_worker.query.connect(
            self._append_query
        )

        self.query_worker.result.connect(
            self._show_query_result
        )

        self.query_worker.error.connect(
            self._sql_error
        )

        self.query_worker.databases.connect(
            self._show_databases
        )

        self.query_worker.started_target.connect(
            self._sql_target_started
        )

        self.query_worker.result_target.connect(
            self._sql_target_result
        )

        self.query_worker.error_target.connect(
            self._sql_target_error
        )

        self.query_worker.stopped.connect(
            self._sql_target_stopped
        )

        self.query_worker.finished.connect(
            self._sql_finished
        )

    def _create_search_backend(self):

        self.search_thread = QThread(self)

        self.search_worker = DatabaseSearchWorker()

        self.search_worker.moveToThread(self.search_thread)

        self.search_thread.started.connect(
            self.search_worker.run
        )

        self.search_worker.finished.connect(
            self.search_thread.quit
        )

        self.search_worker.started.connect(
            self._search_started
        )

        self.search_worker.finished.connect(
            self._search_finished
        )

        self.search_worker.progress.connect(
            self._update_progress
        )

        self.search_worker.status.connect(
            lambda text: self.append_log(
                "INFO",
                text,
            )
        )

        self.search_worker.result.connect(
            self._search_result
        )

        self.search_worker.error.connect(
            self._search_error
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

        current_server = self.cb_server.currentText()

        self.cb_server.blockSignals(True)

        self.cb_server.clear()
        self.cb_server.addItems(servers)

        if current_server:
            self.cb_server.setCurrentText(current_server)

        self.cb_server.blockSignals(False)

        if self.cb_server.currentText().strip():
            self._sql_refresh_databases()

        count = len(servers)

        self.lbl_servers_value.setText(
            f"{count} / {count}"
        )

        self.lbl_servers_title.setText(
            "Servers — Selected: 0"
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

        if self.thread.isRunning():
            return

        self.clear_results()

        self._results_source = "check"

        self._update_only_errors_visibility()

        self.table.setSortingEnabled(False)

        self.progress.setValue(0)

        self.lbl_elapsed_value.setText("00:00:00")

        self.lbl_status_value.setText("Ready")

        self.table.clearSelection()

        servers = [
            item.text()
            for item in self.server_list.selectedItems()
        ]

        self.worker.set_servers(servers)

        self.thread.start()

    def _stop_check(self):

        if not self.thread.isRunning():
            return

        self.worker.stop()

        self.action_stop.setEnabled(False)

        self.lbl_status_value.setText(
            "Stopping..."
        )

        self.append_log(
            "WARNING",
            "Stop requested by user.",
        )

    def _check_started(self):

        self.action_check.setEnabled(False)
        self.action_stop.setEnabled(True)

        self.lbl_status_value.setText("Checking...")

        self.append_log(
            "INFO",
            "Check started.",
        )
        self._started_at = time.perf_counter()

        self._elapsed_timer.start()

    def _check_finished(self):

        self.action_check.setEnabled(True)
        
        self.action_stop.setEnabled(False)

        self.table.setSortingEnabled(True)

        self.table.resizeColumnToContents(0)
        self.table.resizeColumnToContents(1)
        self.table.resizeColumnToContents(2)
        self.table.resizeColumnToContents(3)
        self.table.resizeColumnToContents(4)
        self.table.resizeColumnToContents(5)
        self.table.resizeColumnToContents(6)

        self._repopulate_filter_column()

        self._filter_results()

        self.progress.setValue(100)

        self.lbl_status_value.setText("Ready")

        self.append_log(
            "SUCCESS",
            "Check completed.",
        )
        self._elapsed_timer.stop()
        
        self._started_at = None

    def _build_ui(self):
        self.setObjectName("MainWindow")

        self.setStyleSheet(SHARED_STYLESHEET)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        content_widget = QWidget()
        content = QVBoxLayout(content_widget)
        content.setContentsMargins(8, 8, 8, 0)
        content.setSpacing(6)

        self.toolbar = QToolBar()
        self.toolbar.setIconSize(QSize(20, 20))
        self.toolbar.setToolButtonStyle(
            Qt.ToolButtonTextBesideIcon
        )

        self.action_refresh = QAction(
            icon("refresh", 20, "#0f172a"),
            "Refresh",
            self,
        )
        self.action_check = QAction(
            icon("play_arrow", 20, "#0f172a"),
            "Check",
            self,
        )
        self.action_update = QAction(
            icon("edit", 20, "#0f172a"),
            "Update",
            self,
        )
        self.action_verify = QAction(
            icon("check_circle", 20, "#0f172a"),
            "Verify",
            self,
        )
        self.action_stop = QAction(
            icon("stop", 20, "#0f172a"),
            "Stop",
            self,
        )
        self.action_toggle_servers = QAction(
            icon("swap_horiz", 20, "#0f172a"),
            "Servers",
            self,
        )
        self.action_toggle_servers.setCheckable(True)
        self.action_toggle_servers.setChecked(True)

        self.action_toggle_results = QAction(
            icon("swap_horiz", 20, "#0f172a"),
            "Results",
            self,
        )
        self.action_toggle_results.setCheckable(True)
        self.action_toggle_results.setChecked(True)

        self.action_refresh.setToolTip("Refresh servers")
        self.action_check.setToolTip("Run check")
        self.action_update.setToolTip("Update")
        self.action_verify.setToolTip("Verify")
        self.action_stop.setToolTip("Stop")
        self.action_toggle_servers.setToolTip(
            "Show/Hide server list"
        )
        self.action_toggle_results.setToolTip(
            "Show/Hide results block"
        )

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
        self.toolbar.addSeparator()
        self.toolbar.addAction(self.action_toggle_servers)
        self.toolbar.addSeparator()
        self.toolbar.addAction(self.action_toggle_results)

        content.addWidget(self.toolbar)

        status_bar = QFrame()
        status_bar.setObjectName("StatusBar")

        status_layout = QHBoxLayout(status_bar)
        status_layout.setContentsMargins(12, 3, 12, 3)
        status_layout.setSpacing(6)

        self.lbl_status = QLabel("Status:")
        self.lbl_status_value = QLabel("Ready")

        self.lbl_servers = QLabel("Servers:")
        self.lbl_servers_value = QLabel("0 / 0")

        self.lbl_elapsed = QLabel("Elapsed:")
        self.lbl_elapsed_value = QLabel("00:00:00")

        self.lbl_sql = QLabel("SQL Console:")
        self.lbl_sql_status = QLabel("Ready")

        for label in (
            self.lbl_status,
            self.lbl_servers,
            self.lbl_elapsed,
            self.lbl_sql,
        ):
            label.setStyleSheet(
                "color:#94a3b8;font-size:12px;border:none;"
                "background:transparent;"
            )

        for label in (
            self.lbl_status_value,
            self.lbl_servers_value,
            self.lbl_elapsed_value,
            self.lbl_sql_status,
        ):
            label.setStyleSheet(
                "color:#f8fafc;font-size:12px;font-weight:600;"
                "border:none;background:transparent;"
            )

        status_layout.addWidget(self.lbl_status)
        status_layout.addWidget(self.lbl_status_value)

        status_layout.addSpacing(12)

        status_layout.addWidget(self.lbl_servers)
        status_layout.addWidget(self.lbl_servers_value)

        status_layout.addSpacing(12)

        status_layout.addWidget(self.lbl_elapsed)
        status_layout.addWidget(self.lbl_elapsed_value)

        status_layout.addSpacing(12)

        status_layout.addWidget(self.lbl_sql)
        status_layout.addWidget(self.lbl_sql_status)

        status_layout.addStretch()

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setFixedWidth(160)
        self.progress.setTextVisible(False)

        status_layout.addWidget(self.progress)

        body_splitter = QSplitter(Qt.Horizontal)
        body_splitter.setChildrenCollapsible(False)
        body_splitter.setHandleWidth(1)

        self.server_frame = QFrame()
        self.server_frame.setMaximumWidth(420)
        server_layout = QVBoxLayout(self.server_frame)
        server_layout.setContentsMargins(8, 8, 8, 8)
        server_layout.setSpacing(8)

        self.lbl_servers_title = QLabel("Servers — Selected: 0")
        self.lbl_servers_title.setObjectName("SectionTitle")

        servers_top = QHBoxLayout()

        servers_top.addWidget(self.lbl_servers_title)

        servers_top.addStretch()

        self.btn_hide_servers = QToolButton()
        self.btn_hide_servers.setObjectName("btn_icon")
        self.btn_hide_servers.setIcon(icon("close"))
        self.btn_hide_servers.setIconSize(QSize(16, 16))
        self.btn_hide_servers.setToolTip("Hide server list")

        servers_top.addWidget(self.btn_hide_servers)

        server_layout.addLayout(servers_top)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search server...")
        server_layout.addWidget(self.search)

        buttons = QHBoxLayout()

        self.btn_select_all = QToolButton()
        self.btn_select_all.setObjectName("btn_icon")
        self.btn_select_all.setIcon(icon("done_all"))
        self.btn_select_all.setIconSize(QSize(16, 16))
        self.btn_select_all.setToolTip("Select All")

        self.btn_clear = QToolButton()
        self.btn_clear.setObjectName("btn_icon")
        self.btn_clear.setIcon(icon("close"))
        self.btn_clear.setIconSize(QSize(16, 16))
        self.btn_clear.setToolTip("Clear selection")

        self.btn_invert = QToolButton()
        self.btn_invert.setObjectName("btn_icon")
        self.btn_invert.setIcon(icon("swap_horiz"))
        self.btn_invert.setIconSize(QSize(16, 16))
        self.btn_invert.setToolTip("Invert selection")

        buttons.addWidget(self.btn_select_all)
        buttons.addWidget(self.btn_clear)
        buttons.addWidget(self.btn_invert)

        server_layout.addLayout(buttons)

        self.server_list = QListWidget()
        self.server_list.setSelectionMode(
            QAbstractItemView.ExtendedSelection
        )

        server_layout.addWidget(self.server_list)

        body_splitter.addWidget(self.server_frame)

        right_container = QWidget()

        right = QVBoxLayout(right_container)
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(0)

        table_frame = QFrame()
        table_frame.setObjectName("TabPage")

        table_layout = QVBoxLayout(table_frame)
        table_layout.setContentsMargins(8, 8, 8, 8)
        table_layout.setSpacing(8)

        filter_layout = QHBoxLayout()

        self.lbl_column = QLabel("Колонка:")
        self.lbl_column.setStyleSheet(
            "border:none;background:transparent;color:#0f172a;"
        )
        filter_layout.addWidget(self.lbl_column)

        self.combo_filter_column = QComboBox()
        self.combo_filter_column.setMinimumWidth(120)
        self.combo_filter_column.view().setItemDelegate(
            ComboItemDelegate(self.combo_filter_column.view())
        )

        filter_layout.addWidget(self.combo_filter_column)

        self.result_search = QLineEdit()
        self.result_search.setPlaceholderText(
            "Filter by selected column..."
        )

        filter_layout.addWidget(
            self.result_search,
            1,
        )

        self.combo_filter_mode = QComboBox()
        self.combo_filter_mode.addItems([
            "Contains",
            "Equals",
            "Empty",
            "Not empty",
        ])
        self.combo_filter_mode.view().setItemDelegate(
            ComboItemDelegate(self.combo_filter_mode.view())
        )

        filter_layout.addWidget(self.combo_filter_mode)

        self.chk_only_errors = QCheckBox(
            "Только ошибки"
        )

        filter_layout.addWidget(self.chk_only_errors)

        self.btn_filter_clear = QPushButton("Clear")
        self.btn_filter_clear.setToolTip("Reset filters")

        filter_layout.addWidget(self.btn_filter_clear)

        table_layout.addLayout(filter_layout)

        self.table = QTableWidget()

        # Колонки заполняются динамически при выполнении запроса:
        # Check → clear_results(), SQL → _fill_sql_result().

        self.table.verticalHeader().setVisible(False)

        self.table.verticalHeader().setDefaultSectionSize(28)

        self.table.verticalHeader().setSectionResizeMode(
            QHeaderView.Fixed
        )

        header = self.table.horizontalHeader()

        header.setStretchLastSection(True)

        header.setSectionResizeMode(QHeaderView.Interactive)

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

        # ----------------------------------------------------------
        # Log Panel UI
        # ----------------------------------------------------------

        log_frame = QFrame()
        log_frame.setObjectName("TabPage")

        log_layout = QVBoxLayout(log_frame)
        log_layout.setContentsMargins(8, 8, 8, 8)
        log_layout.setSpacing(8)

        top = QHBoxLayout()

        top.addStretch()

        self.btn_log_clear = QToolButton()
        self.btn_log_clear.setObjectName("btn_icon")
        self.btn_log_clear.setIcon(icon("delete_outline"))
        self.btn_log_clear.setIconSize(QSize(16, 16))
        self.btn_log_clear.setToolTip("Clear log")

        self.btn_log_copy = QToolButton()
        self.btn_log_copy.setObjectName("btn_icon")
        self.btn_log_copy.setIcon(icon("content_copy"))
        self.btn_log_copy.setIconSize(QSize(16, 16))
        self.btn_log_copy.setToolTip("Copy log")

        self.btn_log_save = QToolButton()
        self.btn_log_save.setObjectName("btn_icon")
        self.btn_log_save.setIcon(icon("download"))
        self.btn_log_save.setIconSize(QSize(16, 16))
        self.btn_log_save.setToolTip("Save log")

        top.addWidget(self.btn_log_clear)
        top.addWidget(self.btn_log_copy)
        top.addWidget(self.btn_log_save)

        log_layout.addLayout(top)

        self.log = QTextEdit()
        self.log.setReadOnly(True)

        log_layout.addWidget(self.log)

        # ----------------------------------------------------------
        # Queries Panel UI
        # ----------------------------------------------------------

        queries_frame = QFrame()
        queries_frame.setObjectName("TabPage")

        queries_layout = QVBoxLayout(queries_frame)
        queries_layout.setContentsMargins(8, 8, 8, 8)
        queries_layout.setSpacing(8)

        qtop = QHBoxLayout()

        self.lbl_query_log = QLabel("Query log")
        self.lbl_query_log.setObjectName("SectionTitle")
        qtop.addWidget(self.lbl_query_log)

        qtop.addStretch()

        self.btn_query_clear = QToolButton()
        self.btn_query_clear.setObjectName("btn_icon")
        self.btn_query_clear.setIcon(icon("delete_outline"))
        self.btn_query_clear.setIconSize(QSize(16, 16))
        self.btn_query_clear.setToolTip("Clear query log")

        qtop.addWidget(self.btn_query_clear)

        queries_layout.addLayout(qtop)

        self.query_log = QPlainTextEdit()
        self.query_log.setReadOnly(True)
        self.query_log.setMaximumBlockCount(2000)

        queries_layout.addWidget(self.query_log)

        self.lbl_scan_template = QLabel("Scan template")
        self.lbl_scan_template.setObjectName("SectionTitle")
        queries_layout.addWidget(self.lbl_scan_template)

        self.query_editor = QPlainTextEdit()
        self.query_editor.setLineWrapMode(
            QPlainTextEdit.NoWrap
        )
        self.query_editor.setPlainText(
            sql_builder.scan_template
        )

        queries_layout.addWidget(self.query_editor)

        hint = QLabel(
            "Placeholders: {db} {dbq} {table} {country} {target}"
        )
        hint.setStyleSheet(
            "color:#94a3b8;font-size:12px;"
        )

        queries_layout.addWidget(hint)

        qbuttons = QHBoxLayout()

        qbuttons.addStretch()

        self.btn_apply = QPushButton("Apply")
        self.btn_rerun = QPushButton("Run check")
        self.btn_rerun.setObjectName("btn_primary")

        qbuttons.addWidget(self.btn_apply)
        qbuttons.addWidget(self.btn_rerun)

        queries_layout.addLayout(qbuttons)

        # ----------------------------------------------------------
        # SQL Console Panel UI
        # ----------------------------------------------------------

        sql_console_frame = QFrame()

        sql_console_layout = QVBoxLayout(sql_console_frame)
        sql_console_layout.setContentsMargins(8, 8, 8, 8)
        sql_console_layout.setSpacing(8)

        sctop = QHBoxLayout()

        self.lbl_sql_console = QLabel("SQL Console")
        self.lbl_sql_console.setObjectName("SectionTitle")
        sctop.addWidget(self.lbl_sql_console)

        sctop.addStretch()

        self.btn_sql_refresh_db = QToolButton()
        self.btn_sql_refresh_db.setObjectName("btn_icon")
        self.btn_sql_refresh_db.setIcon(icon("refresh"))
        self.btn_sql_refresh_db.setIconSize(QSize(16, 16))
        self.btn_sql_refresh_db.setToolTip("Refresh databases")

        self.btn_sql_clear = QToolButton()
        self.btn_sql_clear.setObjectName("btn_icon")
        self.btn_sql_clear.setIcon(icon("delete_outline"))
        self.btn_sql_clear.setIconSize(QSize(16, 16))
        self.btn_sql_clear.setToolTip("Clear console")

        sctop.addWidget(self.btn_sql_refresh_db)
        sctop.addWidget(self.btn_sql_clear)

        sql_console_layout.addLayout(sctop)

        scontrols = QHBoxLayout()

        self.cb_server = QComboBox()
        self.cb_server.setEditable(True)
        self.cb_server.setMinimumWidth(180)
        self.cb_server.setSizeAdjustPolicy(
            QComboBox.AdjustToMinimumContentsLengthWithIcon
        )
        self.cb_server.lineEdit().setStyleSheet(
            "border:none;background:transparent;padding:0;"
        )
        self.cb_server.view().setItemDelegate(
            ComboItemDelegate(self.cb_server.view())
        )

        self.cb_database = QComboBox()
        self.cb_database.setEditable(True)
        self.cb_database.setMinimumWidth(160)
        self.cb_database.setSizeAdjustPolicy(
            QComboBox.AdjustToMinimumContentsLengthWithIcon
        )
        self.cb_database.lineEdit().setStyleSheet(
            "border:none;background:transparent;padding:0;"
        )
        self.cb_database.view().setItemDelegate(
            ComboItemDelegate(self.cb_database.view())
        )

        scontrols.addWidget(self.cb_server)
        scontrols.addWidget(self.cb_database)

        self.chk_write = QCheckBox("Разрешить запросы на запись")
        scontrols.addWidget(self.chk_write)

        scontrols.addStretch()

        self.btn_sql_run = QPushButton("Run")
        self.btn_sql_run.setObjectName("btn_primary")
        self.btn_sql_run.setToolTip("Run query (Ctrl+Enter)")

        scontrols.addWidget(self.btn_sql_run)

        sql_console_layout.addLayout(scontrols)

        scope_row = QHBoxLayout()

        self.chk_all_servers = QCheckBox(
            "Все выбранные серверы"
        )
        self.chk_all_servers.setToolTip(
            "Выполнять на серверах, выбранных в списке"
        )

        self.chk_all_databases = QCheckBox(
            "Все базы данных"
        )
        self.chk_all_databases.setToolTip(
            "Выполнять по всем базам данных каждого сервера"
        )

        scope_row.addWidget(self.chk_all_servers)
        scope_row.addWidget(self.chk_all_databases)

        scope_row.addStretch()

        self.btn_sql_stop = QPushButton("Stop")
        self.btn_sql_stop.setObjectName("btn_danger")
        self.btn_sql_stop.setEnabled(False)

        scope_row.addWidget(self.btn_sql_stop)

        sql_console_layout.addLayout(scope_row)

        self.sql_editor = QPlainTextEdit()
        self.sql_editor.setLineWrapMode(
            QPlainTextEdit.NoWrap
        )
        self.sql_editor.setPlaceholderText(
            "Write SQL query... Ctrl+Enter to run"
        )
        self.sql_editor.setTabStopDistance(40)

        console_font = QFontDatabase.systemFont(
            QFontDatabase.FixedFont
        )
        console_font.setPointSize(12)
        self.sql_editor.setFont(console_font)

        sql_console_layout.addWidget(self.sql_editor)

        # ----------------------------------------------------------
        # Database Search Block UI (над SQL Console)
        # ----------------------------------------------------------

        search_frame = QFrame()
        search_frame.setObjectName("TabsBlock")
        search_frame.setFixedHeight(84)

        search_layout = QVBoxLayout(search_frame)
        search_layout.setContentsMargins(8, 8, 8, 8)
        search_layout.setSpacing(6)

        search_top = QHBoxLayout()

        self.lbl_search_title = QLabel("Поиск БД")
        self.lbl_search_title.setObjectName("SectionTitle")
        search_top.addWidget(self.lbl_search_title)

        search_top.addStretch()

        self.lbl_search_hint = QLabel(
            "Результаты — в блоке Results. "
            "Двойной клик подставит сервер и БД в консоль"
        )
        self.lbl_search_hint.setStyleSheet(
            "border:none;background:transparent;color:#64748b;"
        )
        search_top.addWidget(self.lbl_search_hint)

        search_layout.addLayout(search_top)

        search_row = QHBoxLayout()

        self.lbl_search = QLabel("Маска:")
        self.lbl_search.setStyleSheet(
            "border:none;background:transparent;color:#0f172a;"
        )
        search_row.addWidget(self.lbl_search)

        self.ed_search_mask = QLineEdit()
        self.ed_search_mask.setPlaceholderText(
            "Название БД, напр. ar_ru"
        )
        self.ed_search_mask.setToolTip(
            "Поиск по содержимому имени БД. "
            "Символы % вводить не нужно — поиск выполняется "
            "как %текст%"
        )
        search_row.addWidget(self.ed_search_mask, 1)

        self.btn_search = QPushButton("Найти БД")
        self.btn_search.setObjectName("btn_primary")
        self.btn_search.setToolTip("Найти БД по маске на серверах")
        search_row.addWidget(self.btn_search)

        self.btn_search_stop = QPushButton("Stop")
        self.btn_search_stop.setObjectName("btn_danger")
        self.btn_search_stop.setEnabled(False)
        search_row.addWidget(self.btn_search_stop)

        search_layout.addLayout(search_row)

        tabs = QTabWidget()
        tabs.addTab(table_frame, "Results")
        tabs.addTab(log_frame, "Logs")
        tabs.addTab(queries_frame, "Queries")

        self.tabs_frame = QFrame()
        self.tabs_frame.setObjectName("TabsBlock")
        self.tabs_frame_layout = QVBoxLayout(self.tabs_frame)
        self.tabs_frame_layout.setContentsMargins(0, 0, 0, 0)
        self.tabs_frame_layout.setSpacing(0)

        self.btn_hide_tabs = QToolButton()
        self.btn_hide_tabs.setObjectName("btn_icon")
        self.btn_hide_tabs.setIcon(icon("close"))
        self.btn_hide_tabs.setIconSize(QSize(16, 16))
        self.btn_hide_tabs.setToolTip("Hide results block")
        tabs.setCornerWidget(
            self.btn_hide_tabs,
            Qt.TopRightCorner,
        )

        self.tabs_frame_layout.addWidget(tabs)

        right_splitter = QSplitter(Qt.Vertical)
        right_splitter.addWidget(search_frame)
        right_splitter.addWidget(sql_console_frame)
        right_splitter.addWidget(self.tabs_frame)
        right_splitter.setSizes([90, 240, 560])
        right_splitter.setChildrenCollapsible(False)
        right_splitter.setHandleWidth(1)
        right.addWidget(right_splitter)

        self.append_log(
            "INFO",
            f"Parallels SQL Admins v{APP_VERSION} started."
        )
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

        self.btn_hide_servers.clicked.connect(
            lambda: self.action_toggle_servers.setChecked(False)
        )

        self.btn_hide_tabs.clicked.connect(
            lambda: self.action_toggle_results.setChecked(False)
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

        self.btn_query_clear.clicked.connect(
            self.query_log.clear
        )

        self.btn_apply.clicked.connect(
            self._apply_query_template
        )

        self.btn_rerun.clicked.connect(
            self._run_check
        )

        self.btn_sql_refresh_db.clicked.connect(
            self._sql_refresh_databases
        )

        self.btn_sql_clear.clicked.connect(
            self._sql_clear
        )

        self.btn_sql_run.clicked.connect(
            self._sql_run
        )

        self.btn_sql_stop.clicked.connect(
            self._sql_stop
        )

        self.btn_search.clicked.connect(
            self._search_run
        )

        self.btn_search_stop.clicked.connect(
            self._search_stop
        )

        self.ed_search_mask.returnPressed.connect(
            self._search_run
        )

        self.chk_all_servers.toggled.connect(
            self._sql_scope_changed
        )

        self.chk_all_databases.toggled.connect(
            self._sql_scope_changed
        )

        self.cb_server.activated.connect(
            self._sql_server_changed
        )

        self.sql_run_shortcut = QShortcut(
            QKeySequence("Ctrl+Return"),
            self,
        )
        self.sql_run_shortcut.activated.connect(
            self._sql_run
        )

        self.sql_highlighter = SQLHighlighter(
            self.sql_editor.document()
        )
        body_splitter.addWidget(right_container)
        body_splitter.setSizes([
            self.server_frame.minimumSizeHint().width(),
            1200,
        ])

        content.addWidget(body_splitter)

        root.addWidget(content_widget, 1)

        root.addWidget(status_bar)

        self._started_at = None

        self._elapsed_timer = QTimer(self)
        self._elapsed_timer.setInterval(1000)
        self._elapsed_timer.timeout.connect(
        self._update_elapsed
        )

        self._filter_timer = QTimer(self)
        self._filter_timer.setSingleShot(True)
        self._filter_timer.setInterval(40)
        self._filter_timer.timeout.connect(
            self._filter_results
        )

        self._results_source = None

        self._update_only_errors_visibility()

        self.result_search.textChanged.connect(
            self._filter_results
        )

        self.chk_only_errors.toggled.connect(
            self._filter_results
        )

        self.combo_filter_column.currentTextChanged.connect(
            self._filter_results
        )

        self.combo_filter_mode.currentTextChanged.connect(
            self._filter_results
        )

        self.btn_filter_clear.clicked.connect(
            self._clear_filters
        )

        self._repopulate_filter_column()
    # --------------------------------------------------------------
    # Slots
    # --------------------------------------------------------------

    def _update_selected_count(self):
        self.lbl_servers_title.setText(
            f"Servers — Selected: {len(self.server_list.selectedItems())}"
        )

    def _toggle_servers_panel(self, visible):
        self.server_frame.setVisible(visible)
        if self.action_toggle_servers.isChecked() != visible:
            self.action_toggle_servers.setChecked(visible)

    def _toggle_results_panel(self, visible):
        self.tabs_frame.setVisible(visible)
        if self.action_toggle_results.isChecked() != visible:
            self.action_toggle_results.setChecked(visible)

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

    _STATUS_COLORS = {
        "OK": QColor("#16a34a"),
        "WARNING": QColor("#d97706"),
        "ERROR": QColor("#dc2626"),
    }
    _ERROR_BG = QColor(255, 245, 245)

    def _add_table_row(self, values: list[str], status_col: int | None = None):
        """Вставляет строку в self.table и применяет раскраску статуса."""
        table = self.table
        row = table.rowCount()
        table.insertRow(row)

        col_count = table.columnCount()

        # Выравнивание количества значений
        padded = list(values)
        if len(padded) > col_count:
            padded = padded[:col_count]
        else:
            padded += [""] * (col_count - len(padded))

        for col, text in enumerate(padded):
            item = QTableWidgetItem(str(text))
            item.setToolTip(str(text))
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)

            if status_col is not None and col == status_col:
                fg = self._STATUS_COLORS.get(text)
                if fg:
                    item.setForeground(QBrush(fg))

            table.setItem(row, col, item)

        # Подсветка фона для строк с ошибкой
        if status_col is not None and padded[status_col] == "ERROR":
            for col in range(col_count):
                if (widget_item := table.item(row, col)):
                    widget_item.setBackground(self._ERROR_BG)

        self._filter_timer.start()

    def add_result(
        self,
        server,
        database,
        country,
        value,
        status="OK",
        message="",
    ):
        self._add_table_row(
            ["Check", server, database, country, value, status, message],
            status_col=5,
        )

    def clear_results(self):

        self.table.clear()
        self.table.setRowCount(0)
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Source",
            "Server",
            "Database",
            "Country",
            "Value",
            "Status",
            "Message",
        ])

        header = self.table.horizontalHeader()

        header.setSectionResizeMode(QHeaderView.Interactive)

        header.setStretchLastSection(True)

        fixed_widths = {
            0: 64,
            1: 190,
            2: 160,
            4: 180,
        }

        for index, width in fixed_widths.items():
            header.resizeSection(index, width)

        self._results_source = None

        self._repopulate_filter_column()
        self._filter_results()
        self._update_only_errors_visibility()

    def _update_only_errors_visibility(self):

        visible = self._results_source == "check"

        self.chk_only_errors.setVisible(visible)

        if not visible and self.chk_only_errors.isChecked():
            self.chk_only_errors.setChecked(False)

    def _show_table_menu(self, pos):

        row = self.table.currentRow()

        menu = QMenu(self)

        copy_row = menu.addAction("Copy Row")
        copy_server = menu.addAction("Copy Server")
        copy_database = menu.addAction("Copy Database")

        menu.addSeparator()

        export_csv = menu.addAction("Export CSV...")

        menu.addSeparator()

        clear_action = menu.addAction("Clear results")

        action = menu.exec(
            self.table.viewport().mapToGlobal(pos)
        )

        if row < 0:
            return

        if action == copy_row:

            self._copy_row(row)

        elif action == copy_server:

            index = self._column_index("Server")

            if index is not None:

                item = self.table.item(row, index)

                QApplication.clipboard().setText(
                    item.text() if item else ""
                )

        elif action == copy_database:

            index = self._column_index("Database")

            if index is not None:

                item = self.table.item(row, index)

                QApplication.clipboard().setText(
                    item.text() if item else ""
                )

        elif action == export_csv:

            self._export_csv()

        elif action == clear_action:

            self.clear_results()

    def _table_double_click(self, item):

        server_index = self._column_index("Server")
        database_index = self._column_index("Database")

        if server_index is None or database_index is None:
            return

        row = item.row()

        server_item = self.table.item(row, server_index)
        database_item = self.table.item(row, database_index)

        if not server_item or not database_item:
            return

        server = server_item.text().strip()
        database = database_item.text().strip()

        if not server or not database:
            return

        self.cb_server.setCurrentText(server)
        self.cb_database.setCurrentText(database)

        self.append_log(
            "SUCCESS",
            f"Result applied to console: [{server}.{database}]",
        )

    def _copy_row(self, row: int):

        values = []

        for column in range(self.table.columnCount()):

            item = self.table.item(row, column)

            values.append(
                item.text() if item else ""
            )

        QApplication.clipboard().setText(
            "\t".join(values)
        )

        self.append_log(
            "SUCCESS",
            "Row copied to clipboard."
        )
    # ----------------------------------------------------------
    # Log Methods
    # ----------------------------------------------------------

    def append_log(self, level: str, message: str):

        colors = {
            "INFO": "#2563eb",
            "SUCCESS": "#16a34a",
            "WARNING": "#d97706",
            "ERROR": "#dc2626",
        }

        color = colors.get(level.upper(), "#0f172a")

        stamp = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        self.log.append(
            f'<span style="color:#94a3b8;">{stamp}</span> '
            f'<span style="color:{color};"><b>[{level.upper()}]</b></span> '
            f'{message}'
        )

        self.log.moveCursor(QTextCursor.End)

    # ----------------------------------------------------------
    # Query Panel
    # ----------------------------------------------------------

    def _append_query(self, text):

        stamp = datetime.now().strftime(
            "%H:%M:%S"
        )

        self.query_log.appendPlainText(
            f"[{stamp}] {text}"
        )

    def _apply_query_template(self):

        sql_builder.set_custom_template(
            self.query_editor.toPlainText()
        )

        self.append_log(
            "SUCCESS",
            "Query template applied.",
        )

    # ----------------------------------------------------------
    # SQL Console
    # ----------------------------------------------------------

    def _sql_run(self):

        if self.query_thread.isRunning():
            return

        sql = self.sql_editor.toPlainText().strip()

        if not sql:
            return

        targets = self._sql_build_targets()

        if not targets:
            self.lbl_sql_status.setText("No targets selected.")
            return

        if not self.chk_write.isChecked() and is_write_statement(sql):
            answer = QMessageBox.question(
                self,
                "Write query",
                "The query may modify data.\n\nContinue?",
            )

            if answer != QMessageBox.Yes:
                return

        self.table.clear()
        self.table.setColumnCount(0)
        self.table.setRowCount(0)
        self.table.setSortingEnabled(False)

        self._results_source = "sql"

        self._update_only_errors_visibility()

        self.lbl_sql_status.setText(
            f"Running on {len(targets)} target(s)..."
        )
        self._sql_busy(True)

        if (
            len(targets) == 1
            and targets[0][1] != ALL_DATABASES
        ):
            self.query_worker.set_request(
                targets[0][0],
                targets[0][1],
                sql,
                1000,
            )

        else:

            self.query_worker.set_multi_request(
                targets,
                sql,
                1000,
            )

        self.query_thread.start()

    def _sql_build_targets(self):

        if self.chk_all_servers.isChecked():

            hosts = [
                item.text().strip()
                for item in self.server_list.selectedItems()
            ]

            hosts = [host for host in hosts if host]

        else:

            host = self.cb_server.currentText().strip()
            hosts = [host] if host else []

        if not hosts:
            return []

        if self.chk_all_databases.isChecked():
            database = ALL_DATABASES
        else:
            database = self.cb_database.currentText().strip() or None

        return [
            (host, database) for host in hosts
        ]

    def _sql_server_changed(self, text):
        self._sql_refresh_databases()

    def _sql_scope_changed(self, checked):

        self.cb_server.setEnabled(
            not self.chk_all_servers.isChecked()
        )

        self.cb_database.setEnabled(
            not self.chk_all_databases.isChecked()
        )

    def _sql_stop(self):

        self.query_worker.stop()
        self.lbl_sql_status.setText("Stopping...")

    def _sql_refresh_databases(self):

        if self.query_thread.isRunning():
            return

        host = self.cb_server.currentText().strip()

        if not host:
            self._sql_error("No server selected.")
            return

        self.lbl_sql_status.setText("Loading databases...")
        self._sql_busy(True)
        self.btn_sql_stop.setEnabled(False)

        self.query_worker.set_databases_request(host)

        self.query_thread.start()

    def _sql_clear(self):

        self.sql_editor.clear()
        self.clear_results()
        self.lbl_sql_status.setText("Ready")

    def _sql_busy(self, busy):

        self.btn_sql_run.setEnabled(not busy)
        self.btn_sql_refresh_db.setEnabled(not busy)
        self.btn_sql_stop.setEnabled(busy)
        self.chk_all_servers.setEnabled(not busy)
        self.chk_all_databases.setEnabled(not busy)

        self.cb_server.setEnabled(
            not busy and not self.chk_all_servers.isChecked()
        )

        self.cb_database.setEnabled(
            not busy and not self.chk_all_databases.isChecked()
        )

    def _sql_finished(self):

        self.table.setSortingEnabled(True)
        self._repopulate_filter_column()
        self._filter_results()
        self._sql_busy(False)

    def _sql_target_started(self, index, total, host, database):

        self.lbl_sql_status.setText(
            f"Running ({index}/{total}) {host}.{database}"
        )

    def _sql_target_result(
        self,
        host,
        database,
        rows,
        columns,
        message,
    ):

        self._fill_sql_result(
            host,
            database,
            rows,
            columns,
            message,
        )

        self.lbl_sql_status.setText(
            f"OK {host}.{database} — {message}"
        )

    def _sql_target_error(self, host, database, message):

        self.append_log(
            "ERROR",
            f"SQL [{host}.{database}]: {message}",
        )

        self._fill_sql_result(
            host,
            database,
            [],
            [],
            f"ERROR: {message}",
        )

        self.lbl_sql_status.setText(
            f"Error {host}.{database}"
        )

    def _sql_target_stopped(self, done, total):

        self.lbl_sql_status.setText(
            f"Stopped ({done} of {total})"
        )
        self._sql_busy(False)

    def _fill_sql_result(
        self,
        host,
        database,
        rows,
        columns,
        message,
    ):

        table = self.table

        if table.columnCount() == 0:
            labels = (
                ["Source", "Server", "Database"] + columns
                if columns
                else ["Source", "Server", "Database", "Result"]
            )

            table.setColumnCount(len(labels))
            table.setHorizontalHeaderLabels(labels)

            header = table.horizontalHeader()
            header.setSectionResizeMode(QHeaderView.Interactive)
            header.setStretchLastSection(True)

            for index, width in ((0, 64), (1, 190), (2, 160)):
                if index < len(labels):
                    header.resizeSection(index, width)

            self._repopulate_filter_column()

        if not columns:
            rows = [[message]]

        for row in rows:
            display = ["SQL", host, database] + row
            self._add_table_row(display[:table.columnCount()])

    def _show_query_result(self, rows, columns, message):

        host = self.cb_server.currentText().strip()
        database = self.cb_database.currentText().strip()

        self._fill_sql_result(
            host,
            database,
            rows,
            columns,
            message,
        )

        self.lbl_sql_status.setText(message)
        self._sql_busy(False)

    def _sql_error(self, message):

        self.lbl_sql_status.setText(f"Error: {message}")
        self._sql_busy(False)

        self.append_log(
            "ERROR",
            f"SQL: {message}",
        )

    def _show_databases(self, names):

        current = self.cb_database.currentText()

        self.cb_database.blockSignals(True)

        self.cb_database.clear()
        self.cb_database.addItems(names)

        # Восстанавливаем выбранную БД только если она есть на новом сервере,
        # иначе очищаем выбор, чтобы не оставалась несуществующая БД.
        if current and current in names:
            self.cb_database.setCurrentText(current)
        else:
            self.cb_database.setCurrentText("")

        self.cb_database.blockSignals(False)

        self.lbl_sql_status.setText(
            f"{len(names)} database(s) loaded."
        )
        self._sql_busy(False)

    # ----------------------------------------------------------
    # Database search
    # ----------------------------------------------------------

    def _search_run(self):

        if self.search_thread.isRunning():
            return

        mask = self.ed_search_mask.text().strip()

        if not mask:
            self.lbl_sql_status.setText("Enter a database mask.")
            return

        # Транслитерация '?' и '*' в LIKE-джокеры.
        # Затем автоматически обрамляем %...% — поиск по содержимому,
        # пользователю не нужно вводить символы %.
        mask = mask.replace("*", "%").replace("?", "_")
        mask = f"%{mask}%"

        # Запрещаем небезопасные символы (обратная кавычка, точка-звёздочка),
        # чтобы не ломать запрос и не выводить мусор.
        if any(ch in mask for ch in ("`", "\x00")):
            self.lbl_sql_status.setText(
                "Mask contains invalid characters."
            )
            return

        servers = self.repository.load_servers()

        if not servers:
            self.lbl_sql_status.setText("No servers to search.")
            return

        # Поиск показывает результат в таблице Results с колонками
        # Server и Database.
        self.table.clear()
        self.table.setRowCount(0)
        self.table.setColumnCount(0)

        self._results_source = "search"

        self._update_only_errors_visibility()

        self.table.setSortingEnabled(False)

        self.progress.setValue(0)

        self.lbl_sql_status.setText(
            f"Searching '{mask}' on {len(servers)} server(s)..."
        )

        self._search_busy(True)

        self.search_worker.set_request(mask, servers)

        self.search_thread.start()

    def _search_stop(self):

        if not self.search_thread.isRunning():
            return

        self.search_worker.stop()

        self.btn_search_stop.setEnabled(False)

        self.lbl_sql_status.setText("Stopping search...")

    def _search_started(self):

        self.btn_search.setEnabled(False)
        self.btn_search_stop.setEnabled(True)

    def _search_finished(self):

        self.btn_search.setEnabled(True)
        self.btn_search_stop.setEnabled(False)

        self.table.setSortingEnabled(True)

        self._repopulate_filter_column()

        self._filter_results()

        self._search_busy(False)

    def _search_result(self, server, database):

        self._append_search_result(server, database)

    def _search_error(self, server, message):

        self.append_log(
            "ERROR",
            f"Search [{server}]: {message}",
        )

    def _append_search_result(self, server, database):

        table = self.table

        if table.columnCount() == 0:
            labels = ["Server", "Database"]
            table.setColumnCount(len(labels))
            table.setHorizontalHeaderLabels(labels)

            header = table.horizontalHeader()
            header.setSectionResizeMode(QHeaderView.Interactive)
            header.setStretchLastSection(True)

            for index, width in ((0, 190), (1, 160)):
                if index < len(labels):
                    header.resizeSection(index, width)

            self._repopulate_filter_column()

        self._add_table_row([server, database])

    def _search_busy(self, busy):

        self.btn_search.setEnabled(not busy)
        self.btn_search_stop.setEnabled(busy)
        self.ed_search_mask.setEnabled(not busy)

    def _save_log(self):

        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Save log",
            "parallels_sql_admins.log",
            "Log files (*.log);;Text files (*.txt);;All files (*)",
        )

        if not filename:
            self.append_log(
                "INFO",
                "Log save cancelled."
            )
            return

        with open(
            filename,
            "w",
            newline="",
            encoding="utf-8-sig",
            ) as f:
                f.write(
                    self.log.toPlainText()
                )

        self.append_log(
            "SUCCESS",
            f"Log saved to {filename}",
        )

    def closeEvent(self, event):
        self.worker.stop()
        self.query_worker.stop()
        self.search_worker.stop()

        for thr in (self.thread, self.query_thread, self.search_thread):
            if thr.isRunning():
                thr.quit()
                if not thr.wait(5000):
                    thr.terminate()
                    thr.wait()

        event.accept()
    
    def _update_elapsed(self):

        if self._started_at is None:
            return

        seconds = int(
            time.perf_counter() - self._started_at
        )

        h = seconds // 3600
        m = (seconds % 3600) // 60
        s = seconds % 60

        self.lbl_elapsed_value.setText(
            f"{h:02}:{m:02}:{s:02}"
        )

    def _column_index(self, name):

        for column in range(self.table.columnCount()):

            item = self.table.horizontalHeaderItem(column)

            if item is not None and item.text() == name:
                return column

        return None

    def _repopulate_filter_column(self):

        if not self.combo_filter_column:
            return

        current = self.combo_filter_column.currentText()

        headers = [
            self.table.horizontalHeaderItem(column).text()
            for column in range(self.table.columnCount())
            if self.table.horizontalHeaderItem(column) is not None
        ]

        self.combo_filter_column.blockSignals(True)

        self.combo_filter_column.clear()
        self.combo_filter_column.addItems(headers)

        if current in headers:
            self.combo_filter_column.setCurrentText(current)
        elif headers:
            self.combo_filter_column.setCurrentIndex(0)

        self.combo_filter_column.blockSignals(False)

    def _clear_filters(self):

        self.result_search.clear()
        self.chk_only_errors.setChecked(False)
        self.combo_filter_mode.setCurrentText("Contains")

        if self.combo_filter_column.count():
            self.combo_filter_column.setCurrentIndex(0)

        self._filter_results()

    def _filter_results(self):

        search = self.result_search.text().strip().lower()

        only_errors = self.chk_only_errors.isChecked()

        mode = self.combo_filter_mode.currentText()

        column = self.combo_filter_column.currentText()

        column_index = None

        if column:

            for index in range(self.table.columnCount()):

                item = self.table.horizontalHeaderItem(index)

                if item is not None and item.text() == column:
                    column_index = index
                    break

        status_index = self._column_index("Status")

        def _is_empty(text):
            return text.strip() in ("", "-")

        table = self.table

        sorting = table.isSortingEnabled()

        table.setSortingEnabled(False)

        table.setUpdatesEnabled(False)

        try:

            for row in range(table.rowCount()):

                visible = True

                if visible and column_index is not None:

                    item = table.item(row, column_index)

                    text = item.text() if item else ""

                    if mode == "Contains":
                        visible = search in text.lower()

                    elif mode == "Equals":
                        visible = text.lower() == search

                    elif mode == "Empty":
                        visible = _is_empty(text)

                    elif mode == "Not empty":
                        visible = not _is_empty(text)

                if visible and only_errors and status_index is not None:

                    item = table.item(row, status_index)

                    status_text = item.text() if item else ""

                    visible = status_text == "ERROR"

                table.setRowHidden(
                    row,
                    not visible,
                )

        finally:

            table.setUpdatesEnabled(True)

            table.setSortingEnabled(sorting)

        table.viewport().update()

    def _export_csv(self):

        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Export CSV",
            "results.csv",
            "CSV files (*.csv);;All files (*)",
        )

        if not filename:
            return

        with open(
            filename,
            "w",
            newline="",
            encoding="utf-8-sig",
        ) as f:
            writer = csv.writer(f)
            headers = []

            for column in range(self.table.columnCount()):
                headers.append(
                    self.table.horizontalHeaderItem(column).text()
                )

            writer.writerow(headers)

            for row in range(self.table.rowCount()):
                if self.table.isRowHidden(row):
                    continue

                values = []

                for column in range(self.table.columnCount()):

                    item = self.table.item(row, column)

                    values.append(
                        item.text() if item else ""
                    )

                writer.writerow(values)

        self.append_log(
            "SUCCESS",
            f"Results exported to {filename}",
        )
