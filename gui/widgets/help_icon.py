"""
gui/widgets/help_icon.py

Виджет «?» в кружочке: при наведении показывает пояснение (tooltip).

Используется вместо инлайн-подсказок и placeholder-хинтов в формах.
Стиль задаётся в gui/styles.py правилом QToolButton#HelpIcon.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QToolButton


class HelpIcon(QToolButton):
    """Круглая иконка «?» с подсказкой по наведению."""

    def __init__(self, text: str, parent=None) -> None:
        super().__init__(parent)
        self.setText("?")
        self.setObjectName("HelpIcon")
        self.setFixedSize(18, 18)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)
        self.setToolTip(text)
        self.setAccessibleName("Подсказка")
