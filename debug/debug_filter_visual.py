"""Визуальная проверка нового фильтр-бара Results.

Запуск (macOS): python3 debug/debug_filter_visual.py
Рендерит окно в файл docs/screenshots/filter_visual.png.
"""

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "minimal")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtWidgets import QApplication

from gui.main_window import MainWindow

OUT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "docs", "screenshots", "filter_visual.png",
)


def main():
    app = QApplication.instance() or QApplication(sys.argv)

    window = MainWindow()
    window.resize(1280, 800)
    window.show()

    # Заполняем таблицу данными как при Check
    window.clear_results()
    window._results_source = "check"
    window._update_only_errors_visibility()

    rows = [
        ["Check", "srv1.ru", "db_alpha", "RU", "10", "OK", "all good"],
        ["Check", "srv1.ru", "db_beta", "RU", "20", "ERROR", "connection boom"],
        ["Check", "srv2.ru", "db_gamma", "US", "30", "WARNING", "slow query"],
        ["Check", "srv2.ru", "db_delta", "FR", "40", "OK", "ok"],
    ]
    for r in rows:
        window._add_table_row(r, status_col=5)

    window._sync_filter_columns()
    window._filter_results()

    # Заполняем пример фильтра для наглядности
    window.filter_header._edits[1].setText("srv")

    app.processEvents()

    img = QImage(window.size(), QImage.Format_ARGB32)
    img.fill(0)
    window.render(img)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    ok = img.save(OUT)
    print(f"Saved: {OUT} ({'OK' if ok else 'FAILED'})")
    window.close()


if __name__ == "__main__":
    main()
