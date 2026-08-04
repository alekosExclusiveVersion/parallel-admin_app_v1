import csv
import re
import time
from datetime import datetime
from PySide6.QtCore import QTimer
from backend.repository import Repository
from backend.check_worker import CheckWorker
from backend.query_worker import ALL_DATABASES, QueryWorker
from common.sql_builder import sql_builder
from common.version import APP_VERSION
from PySide6.QtCore import (
    Qt,
    QSize,
    QThread,
)
from PySide6.QtGui import (
    QAction,
    QColor,
    QBrush,
    QFont,
    QFontDatabase,
    QIcon,
    QKeySequence,
    QPainter,
    QPixmap,
    QShortcut,
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

from gui.sql_highlighter import SQLHighlighter


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

        self._load_servers()

    # ----------------------------------------------------------
    # Icons
    # ----------------------------------------------------------

    @staticmethod
    def _glyph_icon(glyph: str, size: int = 20) -> QIcon:

        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        font = QFont()
        font.setPixelSize(14)
        painter.setFont(font)
        painter.setPen(QColor("#0f172a"))
        painter.drawText(
            pixmap.rect(),
            Qt.AlignCenter,
            glyph,
        )
        painter.end()

        return QIcon(pixmap)

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

        self.setStyleSheet("""
        QWidget#MainWindow{
            background:#f4f6f8;
        }

        QLabel{
            color:#0f172a;
            background:transparent;
            border:none;
        }

        QLabel#SectionTitle{
            font-size:13px;
            font-weight:600;
            color:#334155;
            border:none;
            background:transparent;
        }

        QFrame{
            background:white;
            border:1px solid #e3e8ef;
            border-radius:10px;
        }

        QSplitter::handle{
            background:transparent;
        }

        /* --- Status bar (full-bleed) --- */
        QFrame#StatusBar{
            background:#0f172a;
            border:none;
            border-radius:0;
        }

        QFrame#StatusBar QLabel{
            border:none;
            background:transparent;
        }

        QFrame#StatusBar QProgressBar{
            background:rgba(255,255,255,0.12);
            border:none;
            border-radius:4px;
            min-height:6px;
            max-height:6px;
            text-align:center;
        }

        QFrame#StatusBar QProgressBar::chunk{
            background:#3b82f6;
            border-radius:4px;
        }

        /* --- Inputs --- */
        QListWidget,
        QTextEdit,
        QPlainTextEdit,
        QTableWidget,
        QLineEdit,
        QComboBox,
        QAbstractSpinBox{
            background:white;
            border:1px solid #e3e8ef;
            border-radius:6px;
            color:#0f172a;
            font-size:13px;
            padding:4px;
            selection-background-color:#eff6ff;
            selection-color:#0f172a;
        }

        QListWidget:focus,
        QTextEdit:focus,
        QPlainTextEdit:focus,
        QLineEdit:focus,
        QComboBox:focus{
            border:1px solid #2563eb;
        }

        QComboBox{
            padding:4px 28px 4px 10px;
        }

        QComboBox QAbstractItemView{
            background:white;
            border:1px solid #e3e8ef;
            border-radius:8px;
            outline:none;
            padding:6px;
            selection-background-color:#eff6ff;
            selection-color:#0f172a;
        }

        QComboBox QAbstractItemView::item{
            border:none;
            border-radius:6px;
        }

        QComboBox QAbstractItemView::item:hover{
            background:#f1f5f9;
        }

        QComboBox QFrame{
            background:white;
            border:none;
            border-radius:0;
        }

        /* --- Toolbar --- */
        QToolBar{
            background:white;
            border:1px solid #e3e8ef;
            border-radius:10px;
            padding:4px;
            spacing:4px;
        }

        QToolBar::separator{
            width:1px;
            background:#e2e8f0;
            margin:4px 2px;
        }

        QToolBar QToolButton{
            border:none;
            border-radius:6px;
            background:transparent;
            padding:6px;
            color:#64748b;
        }

        QToolBar QToolButton:hover{
            background:#f1f5f9;
            color:#0f172a;
        }

        QToolBar QToolButton:pressed{
            background:#e2e8f0;
        }

        QToolBar QToolButton:disabled{
            color:#cbd5e1;
        }

        /* --- Icon buttons --- */
        QToolButton#btn_icon{
            border:none;
            border-radius:6px;
            background:transparent;
            padding:4px 6px;
            font-size:14px;
            color:#64748b;
        }

        QToolButton#btn_icon:hover{
            background:#f1f5f9;
            color:#0f172a;
        }

        QToolButton#btn_icon:disabled{
            background:transparent;
            color:#cbd5e1;
        }

        /* --- Buttons --- */
        QPushButton{
            min-height:28px;
            border:1px solid #e3e8ef;
            border-radius:6px;
            background:white;
            color:#0f172a;
            text-align:center;
            padding:0 12px;
        }

        QPushButton:hover{
            background:#f8fafc;
        }

        QPushButton:pressed{
            background:#f1f5f9;
        }

        QPushButton:disabled{
            background:#f1f5f9;
            border-color:#e3e8ef;
            color:#94a3b8;
        }

        QPushButton:focus{
            border:1px solid #2563eb;
        }

        QPushButton#btn_primary{
            background:#2563eb;
            border:1px solid #2563eb;
            color:white;
            font-weight:600;
        }

        QPushButton#btn_primary:hover{
            background:#1d4ed8;
            border-color:#1d4ed8;
        }

        QPushButton#btn_primary:pressed{
            background:#1e40af;
        }

        /* --- Checkbox --- */
        QCheckBox{
            font-size:13px;
            color:#0f172a;
            margin:0 6px;
        }

        QCheckBox::indicator{
            width:16px;
            height:16px;
            border:1px solid #cbd5e1;
            border-radius:4px;
            background:white;
        }

        QCheckBox::indicator:hover{
            border-color:#2563eb;
        }

        QCheckBox::indicator:checked{
            background:#2563eb;
            border-color:#2563eb;
        }

        /* --- Table headers --- */
        QHeaderView::section{
            background:#f8fafc;
            border:none;
            border-bottom:1px solid #e2e8f0;
            border-right:1px solid #eef2f7;
            padding:6px 8px;
            font-size:12px;
            font-weight:600;
            color:#475569;
        }

        QHeaderView::section:hover{
            background:#eef2f7;
        }

        /* --- Tabs --- */
        QTabWidget::pane{
            border:1px solid #e3e8ef;
            border-radius:10px;
            background:white;
            top:-1px;
        }

        QTabBar::tab{
            background:transparent;
            padding:7px 16px;
            color:#64748b;
            border:none;
            border-bottom:2px solid transparent;
            font-size:13px;
        }

        QTabBar::tab:first{
            margin-left:6px;
        }

        QTabBar::tab:top{
            margin-top:4px;
        }

        QTabBar::tab:selected{
            color:#2563eb;
            border-bottom:2px solid #2563eb;
            font-weight:600;
        }

        QTabBar::tab:hover:!selected{
            color:#0f172a;
        }

        /* --- Progress (default) --- */
        QProgressBar{
            border:1px solid #e3e8ef;
            border-radius:5px;
            background:white;
            text-align:center;
            min-height:20px;
        }

        QProgressBar::chunk{
            background:#2563eb;
            border-radius:4px;
        }

        /* --- Menu --- */
        QMenu{
            background:white;
            border:1px solid #e3e8ef;
            border-radius:8px;
            padding:6px;
        }

        QMenu::item{
            padding:6px 22px;
            border-radius:6px;
            color:#0f172a;
        }

        QMenu::item:selected{
            background:#eff6ff;
            color:#1d4ed8;
        }

        QMenu::separator{
            height:1px;
            background:#eef2f7;
            margin:4px 8px;
        }

        /* --- Scrollbars --- */
        QScrollBar:vertical{
            background:transparent;
            width:10px;
            margin:2px;
        }

        QScrollBar::handle:vertical{
            background:#cbd5e1;
            border-radius:4px;
            min-height:30px;
        }

        QScrollBar::handle:vertical:hover{
            background:#94a3b8;
        }

        QScrollBar::add-line:vertical,
        QScrollBar::sub-line:vertical{
            height:0;
        }

        QScrollBar:horizontal{
            background:transparent;
            height:10px;
            margin:2px;
        }

        QScrollBar::handle:horizontal{
            background:#cbd5e1;
            border-radius:4px;
            min-width:30px;
        }

        QScrollBar::handle:horizontal:hover{
            background:#94a3b8;
        }

        QScrollBar::add-line:horizontal,
        QScrollBar::sub-line:horizontal{
            width:0;
        }

        QScrollBar::add-page:vertical,
        QScrollBar::sub-page:vertical,
        QScrollBar::add-page:horizontal,
        QScrollBar::sub-page:horizontal{
            background:transparent;
        }
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        content_widget = QWidget()
        content = QVBoxLayout(content_widget)
        content.setContentsMargins(8, 8, 8, 0)
        content.setSpacing(6)

        self.toolbar = QToolBar()

        self.action_refresh = QAction(
            self._glyph_icon("\u27F3"),
            "Refresh",
            self,
        )
        self.action_check = QAction(
            self._glyph_icon("\u25B6"),
            "Check",
            self,
        )
        self.action_update = QAction(
            self._glyph_icon("\u270F"),
            "Update",
            self,
        )
        self.action_verify = QAction(
            self._glyph_icon("\u2713"),
            "Verify",
            self,
        )
        self.action_stop = QAction(
            self._glyph_icon("\u25A0"),
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

        server_frame = QFrame()
        server_frame.setMinimumWidth(200)
        server_layout = QVBoxLayout(server_frame)
        server_layout.setContentsMargins(8, 8, 8, 8)
        server_layout.setSpacing(8)

        self.lbl_servers_title = QLabel("Servers — Selected: 0")
        self.lbl_servers_title.setObjectName("SectionTitle")
        server_layout.addWidget(self.lbl_servers_title)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search server...")
        server_layout.addWidget(self.search)

        buttons = QHBoxLayout()

        self.btn_select_all = QToolButton()
        self.btn_select_all.setObjectName("btn_icon")
        self.btn_select_all.setText("\u2611")
        self.btn_select_all.setToolTip("Select All")

        self.btn_clear = QToolButton()
        self.btn_clear.setObjectName("btn_icon")
        self.btn_clear.setText("\u2715")
        self.btn_clear.setToolTip("Clear selection")

        self.btn_invert = QToolButton()
        self.btn_invert.setObjectName("btn_icon")
        self.btn_invert.setText("\u21C4")
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

        body_splitter.addWidget(server_frame)

        right_container = QWidget()

        right = QVBoxLayout(right_container)
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(0)

        table_frame = QFrame()

        table_layout = QVBoxLayout(table_frame)
        table_layout.setContentsMargins(8, 8, 8, 8)
        table_layout.setSpacing(8)

        self.lbl_results = QLabel("Results")
        self.lbl_results.setObjectName("SectionTitle")
        table_layout.addWidget(self.lbl_results)

        filter_layout = QHBoxLayout()

        filter_layout.addWidget(QLabel("Column:"))

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
            "Only Errors"
        )

        filter_layout.addWidget(self.chk_only_errors)

        self.btn_filter_clear = QPushButton("Clear")
        self.btn_filter_clear.setToolTip("Reset filters")

        filter_layout.addWidget(self.btn_filter_clear)

        table_layout.addLayout(filter_layout)

        self.table = QTableWidget()

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

        self.table.verticalHeader().setVisible(False)

        self.table.verticalHeader().setDefaultSectionSize(28)

        self.table.verticalHeader().setSectionResizeMode(
            QHeaderView.Fixed
        )

        header = self.table.horizontalHeader()

        header.setStretchLastSection(True)

        header.setSectionResizeMode(QHeaderView.Interactive)

        header.resizeSection(4, 180)

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

        log_layout = QVBoxLayout(log_frame)
        log_layout.setContentsMargins(8, 8, 8, 8)
        log_layout.setSpacing(8)

        top = QHBoxLayout()

        self.lbl_log = QLabel("Log")
        self.lbl_log.setObjectName("SectionTitle")
        top.addWidget(self.lbl_log)

        top.addStretch()

        self.btn_log_clear = QToolButton()
        self.btn_log_clear.setObjectName("btn_icon")
        self.btn_log_clear.setText("\u2715")
        self.btn_log_clear.setToolTip("Clear log")

        self.btn_log_copy = QToolButton()
        self.btn_log_copy.setObjectName("btn_icon")
        self.btn_log_copy.setText("\u29C9")
        self.btn_log_copy.setToolTip("Copy log")

        self.btn_log_save = QToolButton()
        self.btn_log_save.setObjectName("btn_icon")
        self.btn_log_save.setText("\u2913")
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
        self.btn_query_clear.setText("\u2715")
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
        self.btn_sql_refresh_db.setText("\u27F3")
        self.btn_sql_refresh_db.setToolTip("Refresh databases")

        self.btn_sql_clear = QToolButton()
        self.btn_sql_clear.setObjectName("btn_icon")
        self.btn_sql_clear.setText("\u2715")
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

        self.chk_write = QCheckBox("Allow write queries")
        scontrols.addWidget(self.chk_write)

        scontrols.addStretch()

        self.btn_sql_run = QPushButton("Run")
        self.btn_sql_run.setObjectName("btn_primary")
        self.btn_sql_run.setToolTip("Run query (Ctrl+Enter)")

        scontrols.addWidget(self.btn_sql_run)

        sql_console_layout.addLayout(scontrols)

        scope_row = QHBoxLayout()

        self.chk_all_servers = QCheckBox(
            "All selected servers"
        )
        self.chk_all_servers.setToolTip(
            "Run on servers selected in the list"
        )

        self.chk_all_databases = QCheckBox(
            "All databases"
        )
        self.chk_all_databases.setToolTip(
            "Run against every database of each server"
        )

        scope_row.addWidget(self.chk_all_servers)
        scope_row.addWidget(self.chk_all_databases)

        scope_row.addStretch()

        self.btn_sql_stop = QPushButton("Stop")
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

        tabs = QTabWidget()
        tabs.addTab(table_frame, "Results")
        tabs.addTab(log_frame, "Log")
        tabs.addTab(queries_frame, "Queries")

        right_splitter = QSplitter(Qt.Vertical)
        right_splitter.addWidget(sql_console_frame)
        right_splitter.addWidget(tabs)
        right_splitter.setSizes([200, 600])
        right_splitter.setChildrenCollapsible(False)
        right_splitter.setHandleWidth(1)
        right.addWidget(right_splitter)

        self.append_log(
            "INFO",
            f"Parallel Admin v{APP_VERSION} started."
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
        body_splitter.setSizes([300, 900])

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
        message="",
    ):

        row = self.table.rowCount()

        self.table.insertRow(row)

        values = [
            "Check",
            server,
            database,
            country,
            value,
            status,
            message,
        ]

        for column, text in enumerate(values):

            item = QTableWidgetItem(str(text))

            item.setToolTip(str(text))

            item.setFlags(
                item.flags() & ~Qt.ItemIsEditable
            )

            if column == 5:

                if status == "OK":
                    item.setForeground(
                        QBrush(QColor("#16a34a"))
                    )

                elif status == "WARNING":
                    item.setForeground(
                        QBrush(QColor("#d97706"))
                    )

                elif status == "ERROR":
                    item.setForeground(
                        QBrush(QColor("#dc2626"))
                    )

            self.table.setItem(
                row,
                column,
                item,
            )
        if status == "ERROR":

            background = QColor(255, 245, 245)

        else:

            background = None


        if background:

            for column in range(self.table.columnCount()):

                item = self.table.item(row, column)

                if item:

                    item.setBackground(background)
        self._filter_timer.start()

    def clear_results(self):

        self.table.clear()
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

        self._copy_row(
            item.row()
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

        self._append_sql_result(
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

        self._append_sql_result(
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

    def _append_sql_result(
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

            if columns:
                labels = ["Source", "Server", "Database"] + columns
            else:
                labels = ["Source", "Server", "Database", "Result"]

            table.setColumnCount(len(labels))
            table.setHorizontalHeaderLabels(labels)

            header = table.horizontalHeader()

            header.setSectionResizeMode(
                QHeaderView.Interactive
            )

            header.setStretchLastSection(True)

            fixed_widths = {
                0: 64,
                1: 190,
                2: 160,
            }

            for index, width in fixed_widths.items():
                if index < len(labels):
                    header.resizeSection(index, width)

            self._repopulate_filter_column()

        base_row = table.rowCount()

        if not columns:
            rows = [[message]]

        table.setRowCount(base_row + len(rows))

        count = table.columnCount()

        for r, row in enumerate(rows):

            display = ["SQL", host, database] + row

            if len(display) > count:
                display = display[:count]

            display += [""] * (count - len(display))

            for c, value in enumerate(display):

                item = QTableWidgetItem(str(value))

                item.setToolTip(str(value))

                item.setFlags(
                    item.flags() & ~Qt.ItemIsEditable
                )

                table.setItem(
                    base_row + r,
                    c,
                    item,
                )

        self._filter_timer.start()

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

        if current:
            self.cb_database.setCurrentText(current)

        self.cb_database.blockSignals(False)

        self.lbl_sql_status.setText(
            f"{len(names)} database(s) loaded."
        )
        self._sql_busy(False)

    def _save_log(self):

        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Save log",
            "parallel_admin.log",
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

        if self.thread.isRunning():
            self.worker.stop()
            self.thread.quit()
            if not self.thread.wait(5000):
                self.thread.terminate()
                self.thread.wait()

        if self.query_thread.isRunning():
            self.query_thread.quit()
            if not self.query_thread.wait(5000):
                self.query_thread.terminate()
                self.query_thread.wait()

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
