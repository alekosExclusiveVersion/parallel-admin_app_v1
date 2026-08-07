"""
gui/sql_console.py

Панель SQL Console: выбор сервера/БД, скоуп выполнения, редактор SQL,
кнопки Run/Stop и хоткеи.

Панель не знает о MySQL: она резолвит выполняемый оператор/выделение и
эмитит runRequested(sql). Фактическое выполнение остаётся в MainWindow.
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QFontDatabase, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QStyledItemDelegate,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from common.sql_splitter import statement_at
from gui.icons import icon
from gui.sql_highlighter import SQLHighlighter


class ComboItemDelegate(QStyledItemDelegate):
    """Отступы внутри пунктов выпадающего списка."""

    def sizeHint(self, option, index):
        size = super().sizeHint(option, index)
        return QSize(
            size.width() + 24,
            max(size.height() + 12, 34),
        )


class SqlConsolePanel(QWidget):
    runRequested = Signal(str)               # выполнить переданный SQL
    stopRequested = Signal()
    refreshDatabasesRequested = Signal()
    clearRequested = Signal()
    serverChanged = Signal(str)
    scopeChanged = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._build_ui()

    # ----------------------------------------------------------
    # UI
    # ----------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        sctop = QHBoxLayout()

        self.lbl_title = QLabel("SQL Console")
        self.lbl_title.setObjectName("SectionTitle")
        sctop.addWidget(self.lbl_title)

        sctop.addStretch()

        self.btn_refresh_db = QToolButton()
        self.btn_refresh_db.setObjectName("btn_icon")
        self.btn_refresh_db.setIcon(icon("refresh"))
        self.btn_refresh_db.setIconSize(QSize(16, 16))
        self.btn_refresh_db.setToolTip("Refresh databases")

        self.btn_clear = QToolButton()
        self.btn_clear.setObjectName("btn_icon")
        self.btn_clear.setIcon(icon("delete_outline"))
        self.btn_clear.setIconSize(QSize(16, 16))
        self.btn_clear.setToolTip("Clear console")

        sctop.addWidget(self.btn_refresh_db)
        sctop.addWidget(self.btn_clear)

        layout.addLayout(sctop)

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

        layout.addLayout(scontrols)

        scope_row = QHBoxLayout()

        self.chk_all_servers = QCheckBox("Все выбранные серверы")
        self.chk_all_servers.setToolTip(
            "Выполнять на серверах, выбранных в списке"
        )

        self.chk_all_databases = QCheckBox("Все базы данных")
        self.chk_all_databases.setToolTip(
            "Выполнять по всем базам данных каждого сервера"
        )

        scope_row.addWidget(self.chk_all_servers)
        scope_row.addWidget(self.chk_all_databases)

        scope_row.addStretch()

        layout.addLayout(scope_row)

        # Ряд кнопок Run/Stop непосредственно над полем ввода SQL
        run_row = QHBoxLayout()
        run_row.addStretch()

        self.btn_run = QPushButton("Run")
        self.btn_run.setObjectName("btn_primary")
        self.btn_run.setToolTip(
            "Run script (Cmd/Ctrl+Shift+Enter); "
            "run selection or statement under cursor (Cmd/Ctrl+Enter)"
        )

        run_row.addWidget(self.btn_run)

        self.btn_stop = QPushButton("Stop")
        self.btn_stop.setObjectName("btn_danger")
        self.btn_stop.setToolTip("Stop running query")
        self.btn_stop.setEnabled(False)

        run_row.addWidget(self.btn_stop)

        layout.addLayout(run_row)

        self.editor = QPlainTextEdit()
        self.editor.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.editor.setPlaceholderText(
            "Write SQL query... Cmd/Ctrl+Enter to run selection "
            "or statement under cursor, Cmd/Ctrl+Shift+Enter to run all"
        )
        self.editor.setTabStopDistance(40)

        console_font = QFontDatabase.systemFont(QFontDatabase.FixedFont)
        console_font.setPointSize(12)
        self.editor.setFont(console_font)

        layout.addWidget(self.editor)

        self.highlighter = SQLHighlighter(self.editor.document())

        # ----------------------------------------------------------
        # Сигналы
        # ----------------------------------------------------------

        self.btn_run.clicked.connect(self._run_all)
        self.btn_stop.clicked.connect(self.stopRequested)
        self.btn_refresh_db.clicked.connect(self.refreshDatabasesRequested)
        self.btn_clear.clicked.connect(self._clear)

        self.cb_server.currentTextChanged.connect(self.serverChanged)
        self.chk_all_servers.toggled.connect(self.scopeChanged)
        self.chk_all_databases.toggled.connect(self.scopeChanged)

        # Cmd/Ctrl+Enter — выделение или оператор под курсором
        self.run_shortcut = QShortcut(
            QKeySequence(Qt.CTRL | Qt.Key_Return),
            self,
        )
        self.run_shortcut.activated.connect(self._run_context)

        # Cmd/Ctrl+Shift+Enter — выполнить весь скрипт
        self.run_all_shortcut = QShortcut(
            QKeySequence(Qt.CTRL | Qt.SHIFT | Qt.Key_Return),
            self,
        )
        self.run_all_shortcut.activated.connect(self._run_all)

    # ----------------------------------------------------------
    # API для MainWindow
    # ----------------------------------------------------------

    def set_busy(self, busy: bool) -> None:
        self.btn_run.setEnabled(not busy)
        self.btn_refresh_db.setEnabled(not busy)
        self.btn_stop.setEnabled(busy)
        self.chk_all_servers.setEnabled(not busy)
        self.chk_all_databases.setEnabled(not busy)

        self.cb_server.setEnabled(
            not busy and not self.chk_all_servers.isChecked()
        )
        self.cb_database.setEnabled(
            not busy and not self.chk_all_databases.isChecked()
        )

    def set_stop_enabled(self, enabled: bool) -> None:
        self.btn_stop.setEnabled(enabled)

    def set_databases(self, names: list[str]) -> None:
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

    def set_target(self, server: str, database: str) -> None:
        self.cb_server.setCurrentText(server)
        self.cb_database.setCurrentText(database)

    def set_servers(self, servers: list[str]) -> None:
        current_server = self.cb_server.currentText()

        self.cb_server.blockSignals(True)

        self.cb_server.clear()
        self.cb_server.addItems(servers)

        if current_server:
            self.cb_server.setCurrentText(current_server)

        self.cb_server.blockSignals(False)

    def clear_editor(self) -> None:
        self.editor.clear()

    def current_host(self) -> str:
        return self.cb_server.currentText().strip()

    def current_database(self) -> str:
        return self.cb_database.currentText().strip()

    def write_enabled(self) -> bool:
        return self.chk_write.isChecked()

    def all_servers_checked(self) -> bool:
        return self.chk_all_servers.isChecked()

    def all_databases_checked(self) -> bool:
        return self.chk_all_databases.isChecked()

    def script_text(self) -> str:
        return self.editor.toPlainText()

    # ----------------------------------------------------------
    # Запуск
    # ----------------------------------------------------------

    def _run_all(self) -> None:
        self.runRequested.emit(self.editor.toPlainText())

    def _run_context(self) -> None:
        """Выделенный фрагмент, иначе оператор под курсором."""
        editor = self.editor
        text = editor.toPlainText()
        cursor = editor.textCursor()

        if cursor.hasSelection():
            sql = cursor.selectedText()
            # selectedText() возвращает символы U+2029 вместо переносов строк
            sql = sql.replace("\u2029", "\n").strip()
        else:
            sql = statement_at(text, cursor.position()).strip()

        if sql:
            self.runRequested.emit(sql)

    def _clear(self) -> None:
        self.editor.clear()
        self.clearRequested.emit()
