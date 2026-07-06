"""
Log panel widget.
"""

from __future__ import annotations

from datetime import datetime

from PySide6.QtWidgets import (
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)


class LogPanel(QWidget):
    """Панель отображения журнала."""

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)

        layout.addWidget(self.log)

        self.info("Parallel Admin started")

    # ---------------------------------------------------------

    def append(self, text: str) -> None:
        """Добавить произвольную строку."""

        self.log.appendPlainText(text)

    # ---------------------------------------------------------

    def info(self, text: str) -> None:
        """Информационное сообщение."""

        now = datetime.now().strftime("%H:%M:%S")

        self.append(
            f"[{now}] INFO    {text}"
        )

    # ---------------------------------------------------------

    def warning(self, text: str) -> None:

        now = datetime.now().strftime("%H:%M:%S")

        self.append(
            f"[{now}] WARNING {text}"
        )

    # ---------------------------------------------------------

    def error(self, text: str) -> None:

        now = datetime.now().strftime("%H:%M:%S")

        self.append(
            f"[{now}] ERROR   {text}"
        )

    # ---------------------------------------------------------

    def clear(self) -> None:
        self.log.clear()