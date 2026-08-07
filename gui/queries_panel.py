"""
gui/queries_panel.py

Вкладка Queries: журнал выполненных запросов и редактор шаблона сканирования
cfg_settings с кнопками Apply / Run check.
"""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QSize, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from gui.icons import icon


class QueriesPanel(QWidget):
    applyRequested = Signal(str)   # новый шаблон сканирования
    rerunRequested = Signal()      # запустить Check заново
    clearRequested = Signal()      # очистить журнал запросов

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        qtop = QHBoxLayout()

        self.lbl_title = QLabel("Журнал запросов")
        self.lbl_title.setObjectName("SectionTitle")
        qtop.addWidget(self.lbl_title)

        qtop.addStretch()

        self.btn_clear = QToolButton()
        self.btn_clear.setObjectName("btn_icon")
        self.btn_clear.setIcon(icon("delete_outline"))
        self.btn_clear.setIconSize(QSize(16, 16))
        self.btn_clear.setToolTip("Очистить журнал запросов")

        qtop.addWidget(self.btn_clear)

        layout.addLayout(qtop)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(2000)

        layout.addWidget(self.log)

        lbl = QLabel("Шаблон сканирования")
        lbl.setObjectName("SectionTitle")
        layout.addWidget(lbl)

        self.editor = QPlainTextEdit()
        self.editor.setLineWrapMode(QPlainTextEdit.NoWrap)

        layout.addWidget(self.editor)

        hint = QLabel(
            "Плейсхолдеры: {db} {dbq} {table} {country} {target}"
        )
        hint.setStyleSheet(
            "color:#94a3b8;font-size:12px;"
        )

        layout.addWidget(hint)

        qbuttons = QHBoxLayout()
        qbuttons.addStretch()

        self.btn_apply = QPushButton("Применить")
        self.btn_rerun = QPushButton("Запустить проверку")
        self.btn_rerun.setObjectName("btn_primary")

        qbuttons.addWidget(self.btn_apply)
        qbuttons.addWidget(self.btn_rerun)

        layout.addLayout(qbuttons)

        self.btn_apply.clicked.connect(
            lambda: self.applyRequested.emit(self.editor.toPlainText())
        )
        self.btn_rerun.clicked.connect(self.rerunRequested)
        self.btn_clear.clicked.connect(self.clearRequested)

    def set_template(self, template: str) -> None:
        self.editor.setPlainText(template)

    def append_query(self, text: str) -> None:
        stamp = datetime.now().strftime("%H:%M:%S")
        self.log.appendPlainText(f"[{stamp}] {text}")
