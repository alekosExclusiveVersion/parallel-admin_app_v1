"""
Result table widget.
"""

from PySide6.QtWidgets import (
    QHeaderView,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from gui.models.results_model import ResultsModel


class ResultTable(QWidget):
    """Таблица результатов."""

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)

        self.model = ResultsModel(self)

        self.table = QTableView()

        self.table.setModel(self.model)

        self.table.setSortingEnabled(True)

        self.table.setAlternatingRowColors(True)

        self.table.horizontalHeader().setStretchLastSection(True)

        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )

        layout.addWidget(self.table)

        self._load_demo_data()

    # ---------------------------------------------------------

    def _load_demo_data(self):

        self.model.append(
            "p7ru1",
            "autoparts",
            "russia",
            "gmail.com",
            "OK",
        )

        self.model.append(
            "p7ru3",
            "test",
            "russia",
            "mail.ru",
            "OK",
        )

    # ---------------------------------------------------------

    def clear(self):

        self.model.clear()