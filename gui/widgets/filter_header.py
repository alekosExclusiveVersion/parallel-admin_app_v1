"""
gui/widgets/filter_header.py

Строка колоночных фильтров, размещаемая под заголовками таблицы Results.

Каждой колонке соответствует своё поле QLineEdit (поиск contains по этой
колонке). Поля синхронизируются по ширине и по горизонтальному скроллу
с таблицей, к которой привязан виджет, поэтому при прокрутке/изменении
ширины колонок поля не «разъезжаются».
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLineEdit,
    QScrollArea,
    QWidget,
)


class FilterHeaderRow(QWidget):
    """Ряд полей фильтра, по одному на колонку таблицы.

    Содержит QScrollArea, внутри которого горизонтальная строка QLineEdit.
    Прокрутка и ширина полей синхронизируются с QHeaderView таблицы,
    переданной в :meth:`bind`.
    """

    #: Срабатывает при изменении текста в любом из колоночных полей.
    filterChanged = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._table = None
        self._edits: list[QLineEdit] = []
        self._row_height = 28  # высота строки фильтра

        self.setFixedHeight(self._row_height)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(False)
        self._scroll.setFixedHeight(self._row_height)
        self._scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarAlwaysOff
        )
        self._scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarAlwaysOff
        )
        self._scroll.setFrameShape(QScrollArea.NoFrame)
        self._scroll.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self._scroll.setStyleSheet(
            "QScrollArea{background:transparent;border:none;}"
        )
        outer.addWidget(self._scroll)

        self._content = QWidget()
        self._content.setFixedHeight(self._row_height)
        self._content.setStyleSheet(
            "background:transparent;"
        )
        self._content_layout = QHBoxLayout(self._content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(0)
        self._scroll.setWidget(self._content)

    # --------------------------------------------------------------
    # Привязка к таблице
    # --------------------------------------------------------------

    def bind(self, table) -> None:
        """Привязывает виджет к таблице для синхронизации ширины/скролла.

        table — QTableWidget, над которым размещена строка фильтров.
        """
        self._table = table

        # QHeaderView не является обычным дочерним widget таблицы, поэтому
        # поля нельзя надёжно разместить «внутри» заголовка через layout.
        # Вместо этого строка фильтров живёт рядом с таблицей и получает
        # изменения геометрии через сигналы самого QHeaderView.
        header = table.horizontalHeader()
        header.sectionResized.connect(self._sync_layout)
        header.sectionMoved.connect(self._sync_layout)
        table.horizontalScrollBar().valueChanged.connect(
            self._sync_scroll
        )
        table.horizontalScrollBar().rangeChanged.connect(
            self._sync_scroll
        )

        self._sync_layout()

    # --------------------------------------------------------------
    # Управление колонками
    # --------------------------------------------------------------

    def rebuild(self, columns: list[str]) -> None:
        """Пересоздаёт поля фильтров по списку заголовков колонок.

        Текущие значения полей не сохраняются — набор колонок меняется
        при смене результата (Check / SQL / Search), поэтому фильтры
        сбрасываются.

        Если список колонок пуст, виджет скрывается.
        """
        if not columns:
            # При пустом Results фильтры не должны занимать место между
            # общим поиском и таблицей — это устраняет пустую область.
            self.hide()
            return

        self.show()

        # Отключаем сигналы на время пересоздания
        for edit in self._edits:
            edit.blockSignals(True)

        # Удаляем старые поля
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        self._edits = []

        for column in columns:
            edit = QLineEdit()
            edit.setFixedHeight(self._row_height)
            edit.setPlaceholderText("…")
            edit.setClearButtonEnabled(True)
            edit.setToolTip(f"Фильтр по колонке «{column}»")
            edit.setMinimumWidth(40)
            edit.textChanged.connect(self._on_text_changed)
            self._content_layout.addWidget(edit)
            self._edits.append(edit)

        self._sync_layout()

    def get_filters(self) -> list[str]:
        """Возвращает текст каждого поля (в порядке колонок)."""
        return [edit.text().strip().lower() for edit in self._edits]

    def clear_filters(self) -> None:
        """Очищает все поля фильтров."""
        for edit in self._edits:
            edit.blockSignals(True)
            edit.clear()
            edit.blockSignals(False)
        self._sync_layout()

    # --------------------------------------------------------------
    # Слоты
    # --------------------------------------------------------------

    def _on_text_changed(self) -> None:
        self.filterChanged.emit()

    def _sync_layout(self) -> None:
        """Выравнивает ширину полей по ширине колонок таблицы.

        Ширины берутся у QHeaderView, а не вычисляются по тексту заголовков:
        это сохраняет выравнивание после ручного изменения размера колонок.
        """
        if self._table is None:
            return

        header = self._table.horizontalHeader()
        scroll = self._scroll

        # Ширина полей = ширины колонок, сдвиг = позиция скролла таблицы.
        # Общая ширина контента нужна для корректного соответствия полей
        # колонкам, включая случаи, когда таблица шире видимой области.
        total = 0
        for index, edit in enumerate(self._edits):
            width = header.sectionSize(index) if index < header.count() else 80
            edit.setFixedWidth(width)
            total += width

        self._content.setFixedWidth(total)

        offset = self._table.horizontalScrollBar().value()
        scroll.horizontalScrollBar().setValue(offset)

    def _sync_scroll(self) -> None:
        """Синхронизирует горизонтальную прокрутку с таблицей."""
        if self._table is None:
            return
        offset = self._table.horizontalScrollBar().value()
        self._scroll.horizontalScrollBar().setValue(offset)
