"""
Server panel widget.

Отображает список серверов и предоставляет базовые действия
по выбору серверов.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)


class ServerPanel(QWidget):
    """Левая панель со списком серверов."""

    def __init__(self, parent=None):
        super().__init__(parent)

        self._build_ui()
        self._load_demo_data()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        title = QLabel("Servers")
        title.setStyleSheet(
            """
            font-size:16px;
            font-weight:bold;
            padding:4px;
            """
        )

        layout.addWidget(title)

        buttons = QHBoxLayout()

        self.btn_select_all = QPushButton("Select all")
        self.btn_clear = QPushButton("Clear")

        buttons.addWidget(self.btn_select_all)
        buttons.addWidget(self.btn_clear)

        layout.addLayout(buttons)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)

        layout.addWidget(self.tree)

        self.btn_select_all.clicked.connect(self.select_all)
        self.btn_clear.clicked.connect(self.clear_selection)

    # ------------------------------------------------------------------

    def _load_demo_data(self) -> None:
        """Временные данные. В Patch 1.2 заменим на servers.txt"""

        servers = [
            "p7ru1",
            "p7ru3",
            "p7ru4",
            "p7ru5",
            "p7ru8",
        ]

        for server in servers:
            item = QTreeWidgetItem([server])
            item.setCheckState(0, Qt.Unchecked)
            self.tree.addTopLevelItem(item)

    # ------------------------------------------------------------------

    def select_all(self) -> None:
        """Выбрать все серверы."""

        for i in range(self.tree.topLevelItemCount()):
            self.tree.topLevelItem(i).setCheckState(
                0,
                Qt.Checked,
            )

    # ------------------------------------------------------------------

    def clear_selection(self) -> None:
        """Снять выбор со всех серверов."""

        for i in range(self.tree.topLevelItemCount()):
            self.tree.topLevelItem(i).setCheckState(
                0,
                Qt.Unchecked,
            )

    # ------------------------------------------------------------------

    def checked_servers(self) -> list[str]:
        """Вернуть список выбранных серверов."""

        result = []

        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)

            if item.checkState(0) == Qt.Checked:
                result.append(item.text(0))

        return result