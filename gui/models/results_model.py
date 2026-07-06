"""
Results table model.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt


class ResultsModel(QAbstractTableModel):
    """Модель данных результатов проверки."""

    HEADERS = (
        "Server",
        "Database",
        "Country",
        "Value",
        "Status",
    )

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: list[list[str]] = []

    # ---------------------------------------------------------

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._rows)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(self.HEADERS)

    # ---------------------------------------------------------

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        if not index.isValid():
            return None

        if role == Qt.DisplayRole:
            return self._rows[index.row()][index.column()]

        if role == Qt.TextAlignmentRole:
            return Qt.AlignCenter

        return None

    # ---------------------------------------------------------

    def headerData(
        self,
        section: int,
        orientation,
        role: int = Qt.DisplayRole,
    ):
        if role != Qt.DisplayRole:
            return None

        if orientation == Qt.Horizontal:
            return self.HEADERS[section]

        return section + 1

    # ---------------------------------------------------------

    def clear(self) -> None:
        self.beginResetModel()
        self._rows.clear()
        self.endResetModel()

    # ---------------------------------------------------------

    def append(
        self,
        server: str,
        database: str,
        country: str,
        value: str,
        status: str,
    ) -> None:

        row = len(self._rows)

        self.beginInsertRows(QModelIndex(), row, row)

        self._rows.append(
            [
                server,
                database,
                country,
                value,
                status,
            ]
        )

        self.endInsertRows()

    # ---------------------------------------------------------

    def set_results(self, rows: list[list[str]]) -> None:

        self.beginResetModel()

        self._rows = rows

        self.endResetModel()