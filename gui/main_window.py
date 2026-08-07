from __future__ import annotations

import threading
import time
from datetime import datetime

from PySide6.QtCore import Qt, QSize, QTimer
from PySide6.QtGui import QAction, QTextCursor
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QTextEdit,
    QFrame,
    QFileDialog,
    QToolBar,
    QToolButton,
    QProgressBar,
    QLineEdit,
    QCheckBox,
    QMessageBox,
    QPushButton,
    QTabWidget,
)

from backend.repository import Repository
from backend.check_worker import CheckWorker
from backend.query_worker import ALL_DATABASES, QueryWorker
from backend.db_search_worker import DatabaseSearchWorker
from backend.db_sizes_worker import DbSizesWorker
from common.sql_builder import sql_builder
from common.sql_security import is_write_statement
from common.sql_splitter import split_statements
from common.version import APP_VERSION
from common.mysql_client import mysql
from gui.icons import icon
from gui.styles import SHARED_STYLESHEET
from gui.widgets.collapsible_splitter import CollapsibleSplitter
from gui.worker_thread import WorkerHost
from gui.servers_tree import ServersTree
from gui.result_table import ResultTable
from gui.sql_console import SqlConsolePanel
from gui.queries_panel import QueriesPanel


class MainWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.repository = Repository()

        self._last_sql_request = None   # (targets, sql) последнего запроса SQL Console

        self._build_ui()
        self._create_backend()
        self._create_query_backend()
        self._create_export_backend()
        self._create_search_backend()
        self._create_sizes_backend()

        self._load_servers()

    # ----------------------------------------------------------
    # Backend
    # ----------------------------------------------------------

    def _create_backend(self):

        self.host = WorkerHost(CheckWorker, self)
        self.thread = self.host.thread
        self.worker = self.host.worker

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
            self.table.add_result
        )

        self.worker.query.connect(
            self._append_query
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

    def _create_query_backend(self):

        self.query_host = WorkerHost(QueryWorker, self)
        self.query_thread = self.query_host.thread
        self.query_worker = self.query_host.worker

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

    def _create_export_backend(self):

        self.export_host = WorkerHost(QueryWorker, self)
        self.export_thread = self.export_host.thread
        self.export_worker = self.export_host.worker

        self.export_worker.export_done.connect(
            self._export_done
        )

        self.export_worker.error.connect(
            self._export_error
        )

        self.export_worker.error_target.connect(
            self._export_target_error
        )

        self.export_worker.stopped.connect(
            self._export_stopped
        )

        self.export_worker.finished.connect(
            self._export_finished
        )

    def _create_search_backend(self):

        self.search_host = WorkerHost(DatabaseSearchWorker, self)
        self.search_thread = self.search_host.thread
        self.search_worker = self.search_host.worker

        self.search_worker.started.connect(
            self._search_started
        )

        self.search_worker.finished.connect(
            self._search_finished
        )

        self.search_worker.progress.connect(
            self._search_progress
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

    def _create_sizes_backend(self):

        self.sizes_host = WorkerHost(DbSizesWorker, self)
        self.sizes_thread = self.sizes_host.thread
        self.sizes_worker = self.sizes_host.worker

        self.sizes_worker.databases_names.connect(
            self.servers_tree.apply_databases
        )

        self.sizes_worker.databases.connect(
            self.servers_tree.apply_sizes
        )

        self.sizes_worker.tables.connect(
            self.servers_tree.apply_tables
        )

        self.sizes_worker.error.connect(
            self._sizes_error
        )

        self.servers_tree.databasesRequested.connect(
            self.sizes_worker.request_databases
        )

        self.servers_tree.tablesRequested.connect(
            self.sizes_worker.request_tables
        )

        # Постоянный поток-потребитель: стартует один раз,
        # задачи на загрузку размеров кладутся в очередь.
        self.sizes_thread.start()

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

        self.servers_tree.set_servers(servers)

        self.panel.set_servers(servers)

        if self.panel.current_host().strip():
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

        previous = self.servers_tree.topLevelItemCount()

        self._load_servers()

        current = self.servers_tree.topLevelItemCount()

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

        self.table.clear_results()
        self.table.results_source = "check"

        self.progress.setValue(0)

        self.lbl_elapsed_value.setText("00:00:00")

        self.lbl_status_value.setText("Ready")

        self.table.clearSelection()

        servers = self.servers_tree.selected_servers()

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

        for index in range(self.table.columnCount()):
            self.table.resizeColumnToContents(index)

        self.table.sync_filter_columns()

        self.table.apply_filters()

        self.progress.setValue(100)

        self.lbl_status_value.setText("Ready")

        self.append_log(
            "SUCCESS",
            "Check completed.",
        )
        self._elapsed_timer.stop()

        self._started_at = None

        # Сбрасываем кэшированные размеры БД/таблиц,
        # чтобы при следующем раскрытии узлов были свежие данные.
        self.servers_tree.reset_sizes()

    # ----------------------------------------------------------
    # UI
    # ----------------------------------------------------------

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
        self.action_refresh.setToolTip("Refresh servers")
        self.action_check.setToolTip("Run check")
        self.action_update.setToolTip("Update")
        self.action_verify.setToolTip("Verify")
        self.action_stop.setToolTip("Stop")

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

        body_splitter = CollapsibleSplitter(Qt.Horizontal)
        body_splitter.setHandleWidth(10)
        body_splitter.sectionDoubleClicked.connect(
            self._body_section_double_clicked
        )

        self.server_frame = QFrame()
        self.server_frame.setMinimumWidth(200)
        server_layout = QVBoxLayout(self.server_frame)
        server_layout.setContentsMargins(8, 8, 8, 8)
        server_layout.setSpacing(8)

        self.lbl_servers_title = QLabel("Servers — Selected: 0")
        self.lbl_servers_title.setObjectName("SectionTitle")

        servers_top = QHBoxLayout()

        servers_top.addWidget(self.lbl_servers_title)

        servers_top.addStretch()

        server_layout.addLayout(servers_top)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search server, DB, table…")
        self.search.setClearButtonEnabled(True)
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

        self.servers_tree = ServersTree()
        server_layout.addWidget(self.servers_tree)

        body_splitter.addWidget(self.server_frame)

        right_container = QWidget()
        right_container.setMinimumWidth(200)
        body_splitter.addWidget(right_container)
        body_splitter.setStretchFactor(0, 0)
        body_splitter.setStretchFactor(1, 1)
        body_splitter.setSizes([280, 900])
        self.body_splitter = body_splitter

        right = QVBoxLayout(right_container)
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(0)

        table_frame = QFrame()
        table_frame.setObjectName("TabPage")

        table_layout = QVBoxLayout(table_frame)
        table_layout.setContentsMargins(8, 8, 8, 8)
        table_layout.setSpacing(8)

        filter_layout = QHBoxLayout()

        self.result_search = QLineEdit()
        self.result_search.setPlaceholderText(
            "Поиск по всем колонкам..."
        )
        self.result_search.setClearButtonEnabled(True)
        self.result_search.setToolTip(
            "Сквозной поиск: строка видима, если текст найден "
            "хотя бы в одной колонке (OR)."
        )
        filter_layout.addWidget(
            self.result_search,
            1,
        )

        self.chk_only_errors = QCheckBox(
            "Только ошибки"
        )

        filter_layout.addWidget(self.chk_only_errors)

        self.btn_export_all = QToolButton()
        self.btn_export_all.setObjectName("btn_icon")
        self.btn_export_all.setIcon(icon("download"))
        self.btn_export_all.setIconSize(QSize(16, 16))
        self.btn_export_all.setToolTip(
            "Save all results without row limit "
            "(re-runs the last SQL query)"
        )
        self.btn_export_all.clicked.connect(self._export_all_results)

        filter_layout.addWidget(self.btn_export_all)

        table_layout.addLayout(filter_layout)

        self.table = ResultTable()
        table_layout.addWidget(self.table)

        self.table.attach_filters(
            self.result_search,
            self.chk_only_errors,
        )

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

        self.queries_panel = QueriesPanel()
        self.queries_panel.set_template(
            sql_builder.scan_template
        )

        # ----------------------------------------------------------
        # SQL Console Panel UI
        # ----------------------------------------------------------

        sql_console_frame = QFrame()
        self.sql_console_frame = sql_console_frame

        self.panel = SqlConsolePanel(sql_console_frame)

        sql_console_layout = QVBoxLayout(sql_console_frame)
        sql_console_layout.setContentsMargins(0, 0, 0, 0)
        sql_console_layout.setSpacing(0)
        sql_console_layout.addWidget(self.panel)

        # ----------------------------------------------------------
        # Database Search Block UI (над SQL Console)
        # ----------------------------------------------------------

        search_frame = QFrame()
        self.search_frame = search_frame
        search_frame.setObjectName("TabsBlock")
        search_frame.setFixedHeight(90)

        search_layout = QVBoxLayout(search_frame)
        search_layout.setContentsMargins(8, 8, 8, 8)
        search_layout.setSpacing(6)

        search_top = QHBoxLayout()

        self.lbl_search_title = QLabel("Поиск БД")
        self.lbl_search_title.setObjectName("SectionTitle")
        search_top.addWidget(self.lbl_search_title)

        search_top.addStretch()

        self.lbl_search_hint = QLabel(
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
        self.ed_search_mask.setClearButtonEnabled(True)
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
        tabs.addTab(self.queries_panel, "Queries")

        self.tabs_frame = QFrame()
        self.tabs_frame.setObjectName("TabsBlock")
        self.tabs_frame_layout = QVBoxLayout(self.tabs_frame)
        self.tabs_frame_layout.setContentsMargins(0, 0, 0, 0)
        self.tabs_frame_layout.setSpacing(0)

        self.tabs_frame_layout.addWidget(tabs)

        self.right_splitter = CollapsibleSplitter(Qt.Vertical)
        self.right_splitter.setOpaqueResize(True)
        self.right_splitter.setHandleWidth(8)
        self.right_splitter.addWidget(search_frame)
        self.right_splitter.addWidget(sql_console_frame)
        self.right_splitter.addWidget(self.tabs_frame)
        self.right_splitter.setSizes([90, 240, 560])
        self.right_splitter.sectionDoubleClicked.connect(
            self._right_section_double_clicked
        )
        right.addWidget(self.right_splitter)

        self.append_log(
            "INFO",
            f"Parallels SQL Admins v{APP_VERSION} started."
        )
        self.append_log("SUCCESS", "GUI initialized.")
        self.append_log("INFO", "Ready.")

        # ----------------------------------------------------------
        # Signals
        # ----------------------------------------------------------

        self.servers_tree.selectionChangedNotify.connect(
            self._update_selected_count
        )

        self.btn_select_all.clicked.connect(
            self.servers_tree.selectAll
        )

        self.btn_clear.clicked.connect(
            self.servers_tree.clearSelection
        )

        self.btn_invert.clicked.connect(
            self.servers_tree.invert_selection
        )

        self.search.textChanged.connect(
            self.servers_tree.filter
        )

        self.servers_tree.tableSelectRequested.connect(
            self._run_table_select
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

        self.table.visibilityRequested.connect(
            self._ensure_results_visible
        )

        self.table.dbSelected.connect(
            self._apply_result_to_console
        )

        self.table.logMessage.connect(
            self.append_log
        )

        self.panel.runRequested.connect(
            self._run_sql
        )

        self.panel.stopRequested.connect(
            self._sql_stop
        )

        self.panel.refreshDatabasesRequested.connect(
            self._sql_refresh_databases
        )

        self.panel.clearRequested.connect(
            self._sql_clear
        )

        self.panel.serverChanged.connect(
            self._sql_server_changed
        )

        self.panel.scopeChanged.connect(
            self._sql_scope_changed
        )

        self.queries_panel.applyRequested.connect(
            self._apply_query_template
        )

        self.queries_panel.rerunRequested.connect(
            self._run_check
        )

        self.queries_panel.clearRequested.connect(
            self.queries_panel.log.clear
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

        # Панель инструментов размещена в splitter, чтобы её можно было
        # сворачивать и раскрывать двойным кликом по ручке.
        self.toolbar_splitter = CollapsibleSplitter(Qt.Vertical)
        self.toolbar_splitter.setHandleWidth(8)
        self.toolbar_splitter.addWidget(self.toolbar)
        self.toolbar_splitter.addWidget(body_splitter)
        self.toolbar_splitter.setStretchFactor(0, 0)
        self.toolbar_splitter.setStretchFactor(1, 1)
        # Toolbar скрыт по умолчанию, но его ручка остаётся доступной
        # для раскрытия двойным кликом.
        self.toolbar_splitter.setSizes([0, 900])

        content.addWidget(self.toolbar_splitter, 1)

        root.addWidget(content_widget, 1)

        root.addWidget(status_bar)

        self._started_at = None

        self._elapsed_timer = QTimer(self)
        self._elapsed_timer.setInterval(1000)
        self._elapsed_timer.timeout.connect(
            self._update_elapsed
        )

    # --------------------------------------------------------------
    # Slots
    # --------------------------------------------------------------

    def _update_selected_count(self):
        self.lbl_servers_title.setText(
            f"Servers — Selected: {self.servers_tree.selected_count()}"
        )

    def _body_section_double_clicked(self, section: int) -> None:
        """Оставляет ручку Servers видимой после сворачивания секции."""
        # Не вызываем setVisible(False): скрытие самого виджета также скрывает
        # связанную с ним ручку QSplitter и лишает возможности раскрыть панель.
        if section == 0:
            self.body_splitter.update()

    def _right_section_double_clicked(self, section: int) -> None:
        """Оставляет ручки вертикального splitter доступными."""
        # Панели остаются видимыми для Qt и скрываются только размером 0 px.
        if 0 <= section < self.right_splitter.count():
            self.right_splitter.update()

    def _toggle_servers_panel(self, visible):
        """Программно показывает или сворачивает Servers без скрытия ручки."""
        sizes = self.body_splitter.sizes()
        if visible:
            if sizes[0] == 0:
                self.body_splitter.setSizes([280, max(1, sum(sizes) - 280)])
        else:
            sizes[0] = 0
            self.body_splitter.setSizes(sizes)

    def _toggle_results_panel(self, visible):
        """Показывает или сворачивает Results, сохраняя его ручку."""
        sizes = self.right_splitter.sizes()
        if visible:
            if sizes[2] == 0:
                self.right_splitter.setSizes([90, 240, 560])
        else:
            sizes[2] = 0
            self.right_splitter.setSizes(sizes)

    def _ensure_results_visible(self, *_args) -> None:
        if not self.tabs_frame.isVisible():
            self._toggle_results_panel(True)

    def _apply_result_to_console(self, server: str, database: str) -> None:
        self.panel.set_target(server, database)

        self.append_log(
            "SUCCESS",
            f"Result applied to console: [{server}.{database}]",
        )

    # ----------------------------------------------------------
    # Sizes
    # ----------------------------------------------------------

    def _sizes_error(self, server: str, context: str, message: str):
        self.append_log(
            "ERROR",
            f"Sizes [{server}/{context}]: {message}",
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
        self.queries_panel.append_query(text)

    def _apply_query_template(self, template: str):

        sql_builder.set_custom_template(template)

        self.append_log(
            "SUCCESS",
            "Query template applied.",
        )

    # ----------------------------------------------------------
    # SQL Console
    # ----------------------------------------------------------

    def _run_sql(self, sql: str):

        if self.query_thread.isRunning():
            self.lbl_sql_status.setText("A query is already running. Wait or press Stop.")
            return

        sql = sql.strip()

        if not sql:
            return

        if not split_statements(sql):
            self.lbl_sql_status.setText("No SQL statements to run.")
            return

        targets = self._sql_build_targets()

        if not targets:
            self.lbl_sql_status.setText("No targets selected.")
            return

        if not self.panel.write_enabled() and is_write_statement(sql):
            answer = QMessageBox.question(
                self,
                "Write query",
                "The query may modify data.\n\nContinue?",
            )

            if answer != QMessageBox.Yes:
                return

        self.table.reset_table()
        self.table.results_source = "sql"

        self._last_sql_request = (targets, sql)

        self.lbl_sql_status.setText(
            f"Running on {len(targets)} target(s)..."
        )
        self.panel.set_busy(True)

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

        if self.panel.all_servers_checked():

            hosts = self.servers_tree.selected_servers()

            hosts = [host for host in hosts if host]

        else:

            host = self.panel.current_host()
            hosts = [host] if host else []

        if not hosts:
            return []

        database = (
            ALL_DATABASES
            if self.panel.all_databases_checked()
            else self.panel.current_database() or None
        )

        return [
            (host, database) for host in hosts
        ]

    def _sql_server_changed(self, text):
        self._sql_refresh_databases()

    def _sql_scope_changed(self, checked):
        self.panel.cb_server.setEnabled(
            not self.panel.all_servers_checked()
        )
        self.panel.cb_database.setEnabled(
            not self.panel.all_databases_checked()
        )

    def _sql_stop(self):

        self.query_worker.stop()
        self.lbl_sql_status.setText("Stopping...")

        # KILL активного запроса в фоне, чтобы не блокировать GUI.
        threading.Thread(
            target=self.query_worker.kill_active,
            daemon=True,
        ).start()

    def _sql_refresh_databases(self):

        if self.query_thread.isRunning():
            return

        host = self.panel.current_host()

        if not host:
            self._sql_error("No server selected.")
            return

        self.lbl_sql_status.setText("Loading databases...")
        self.panel.set_busy(True)
        self.panel.set_stop_enabled(False)

        self.query_worker.set_databases_request(host)

        self.query_thread.start()

    def _sql_clear(self):

        self.table.clear_results()
        self.lbl_sql_status.setText("Ready")

    def _set_export_ui(self, running: bool) -> None:

        if running:
            self.btn_export_all.setIcon(icon("stop"))
            self.btn_export_all.setToolTip("Stop export")
        else:
            self.btn_export_all.setIcon(icon("download"))
            self.btn_export_all.setToolTip(
                "Save all results without row limit "
                "(re-runs the last SQL query)"
            )

    def _export_all_results(self):

        # Клик во время экспорта = остановить экспорт.
        if self.export_thread.isRunning():
            self.export_worker.stop()

            threading.Thread(
                target=self.export_worker.kill_active,
                daemon=True,
            ).start()

            self.lbl_sql_status.setText("Stopping export...")
            return

        if self._last_sql_request is None:
            self.lbl_sql_status.setText("Run a query first.")
            return

        targets, sql = self._last_sql_request

        if is_write_statement(sql):
            self.lbl_sql_status.setText("Export is available only for read queries.")
            return

        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Save all results",
            "results_all.csv",
            "CSV files (*.csv);;All files (*)",
        )

        if not filename:
            return

        self.lbl_sql_status.setText("Exporting all results...")
        self._set_export_ui(True)

        self.export_worker.set_export_request(targets, sql, filename)

        self.export_thread.start()

    def _export_done(self, total_rows, filepath):

        self.lbl_sql_status.setText(
            f"Saved {total_rows} row(s) to {filepath}"
        )

        self.append_log(
            "SUCCESS",
            f"Exported {total_rows} row(s) to {filepath}",
        )

    def _export_finished(self):

        self._set_export_ui(False)

    def _export_error(self, message):

        self.lbl_sql_status.setText(f"Export error: {message}")
        self._set_export_ui(False)

        self.append_log(
            "ERROR",
            f"Export: {message}",
        )

    def _export_target_error(self, host, database, message):

        self.append_log(
            "ERROR",
            f"Export [{host}.{database}]: {message}",
        )

    def _export_stopped(self, done, total):

        self.lbl_sql_status.setText(
            f"Export stopped ({done} of {total})"
        )
        self._set_export_ui(False)

    def _sql_finished(self):

        self.table.setSortingEnabled(True)
        self.table.sync_filter_columns()
        self.table.apply_filters()
        self.panel.set_busy(False)
        self._ensure_results_visible()

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

        self.table.fill_sql_result(
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

        self.table.fill_sql_result(
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
        self.panel.set_busy(False)

    def _show_query_result(self, rows, columns, message):

        host = self.panel.current_host()
        database = self.panel.current_database()

        self.table.fill_sql_result(
            host,
            database,
            rows,
            columns,
            message,
        )

        self.lbl_sql_status.setText(message)
        self.panel.set_busy(False)

    def _sql_error(self, message):

        self.lbl_sql_status.setText(f"Error: {message}")
        self.panel.set_busy(False)

        self.append_log(
            "ERROR",
            f"SQL: {message}",
        )

    def _show_databases(self, names):

        self.panel.set_databases(names)

        self.lbl_sql_status.setText(
            f"{len(names)} database(s) loaded."
        )
        self.panel.set_busy(False)

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
        self.table.reset_table()
        self.table.results_source = "search"

        self.progress.setValue(0)

        self._search_found = 0
        self._search_completed = 0
        self._search_stopped = False

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

        self._search_stopped = True

        self.lbl_sql_status.setText("Stopping search...")

    def _search_started(self):

        self.btn_search.setEnabled(False)
        self.btn_search_stop.setEnabled(True)

    def _search_finished(self):

        self.btn_search.setEnabled(True)
        self.btn_search_stop.setEnabled(False)

        self.table.setSortingEnabled(True)

        self.table.sync_filter_columns()

        self.table.apply_filters()

        self._search_busy(False)

        if self._search_stopped:
            self.lbl_sql_status.setText("Search stopped.")
        else:
            self.lbl_sql_status.setText(
                f"Search finished: {self._search_found} "
                f"database(s) found on {self._search_completed} "
                f"server(s)."
            )

        self.progress.setValue(0)

        # Сбрасываем кэшированные размеры БД/таблиц,
        # чтобы при следующем раскрытии узлов были свежие данные.
        self.servers_tree.reset_sizes()

    def _search_progress(self, current, total):
        self._update_progress(current, total)
        self._search_completed = current

    def _search_result(self, server, database):

        self._search_found += 1

        self.table.add_search_result(server, database)

    def _search_error(self, server, message):

        self.append_log(
            "ERROR",
            f"Search [{server}]: {message}",
        )

    def _search_busy(self, busy):

        self.btn_search.setEnabled(not busy)
        self.btn_search_stop.setEnabled(busy)
        self.ed_search_mask.setEnabled(not busy)

    def _run_table_select(self, server: str, database: str, table: str):
        """Выполняет SELECT * FROM `db`.`table` в фоновом потоке."""
        # Если поток занят (например, загрузкой списка БД) — останавливаем его,
        # чтобы SELECT гарантированно выполнился.
        if self.query_thread.isRunning():
            self.query_worker.stop()
            threading.Thread(
                target=self.query_worker.kill_active,
                daemon=True,
            ).start()
            self.query_thread.wait(5000)
            if self.query_thread.isRunning():
                self.query_thread.terminate()
                self.query_thread.wait()

        sql = f"SELECT * FROM `{database}`.`{table}` LIMIT 1000"

        self.table.reset_table()
        self.table.results_source = "sql"

        self.lbl_sql_status.setText(
            f"Running {server}.{database}.{table}..."
        )
        self.panel.set_busy(True)

        self._ensure_results_visible()

        self.query_worker.set_multi_request(
            [(server, database)],
            sql,
            1000,
        )
        self.query_thread.start()

        self.append_log(
            "INFO",
            f"SELECT * FROM `{database}`.`{table}` @ {server}",
        )

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

    def shutdown(self):
        """Останавливает все фоновые потоки (вызывается из App.closeEvent)."""
        self.worker.stop()
        self.query_worker.stop()
        self.search_worker.stop()
        self.sizes_worker.stop()
        self.export_worker.stop()

        # Прерываем активный экспорт на сервере (KILL), чтобы поток
        # вышел быстро, а не ждал read_timeout.
        if self.export_thread.isRunning():
            threading.Thread(
                target=self.export_worker.kill_active,
                daemon=True,
            ).start()

        for thr in (
            self.thread,
            self.query_thread,
            self.search_thread,
            self.sizes_thread,
            self.export_thread,
        ):
            if thr.isRunning():
                thr.quit()
                if not thr.wait(5000):
                    thr.terminate()
                    thr.wait()

        mysql.close_all()

    def closeEvent(self, event):
        self.shutdown()
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
