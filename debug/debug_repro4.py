import os

os.environ["QT_QPA_PLATFORM"] = "offscreen"

import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

app = QApplication(sys.argv)

import common.mysql_client as mclient


class FakeConn:
    host = "fakehost"

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class FakeMySQL:
    def set_query_hook(self, hook):
        pass

    def connect(self, host, database=None):
        return FakeConn()

    def list_databases_conn(self, conn):
        return ["ar_ru1", "ar_ru2"]

    def scan_settings_batch(self, conn, databases):
        return [
            {"database_name": "ar_ru1", "country": "russia", "target_value": "gmail.com"},
            {"database_name": "ar_ru2", "country": "russia", "target_value": "mail.ru"},
        ]

    def list_databases(self, host):
        return ["ar_ru1", "ar_ru2"]


fake = FakeMySQL()
mclient.mysql = fake
from backend import check_worker, query_worker
check_worker.mysql = fake
query_worker.mysql = fake

from gui.main_window import MainWindow

w = MainWindow()
w.show()

# Эмулируем "грязное" состояние фильтров пользователя перед Check:
# выбран режим "Not empty", текст в поиске, колонка - Status
w.combo_filter_mode.setCurrentText("Not empty")
w.result_search.setText("zzz")
w.combo_filter_column.setCurrentText("Status")
w.chk_only_errors.setChecked(True)  # как если бы пользователь оставил галочку

w.server_list.selectAll()
w._run_check()


def done():
    print("=== DIRTY FILTERS THEN CHECK ===")
    print("results_source:", w._results_source)
    print("chk_only_errors visible:", w.chk_only_errors.isVisible())
    print("chk_only_errors checked:", w.chk_only_errors.isChecked())
    print("search:", repr(w.result_search.text()))
    print("mode:", w.combo_filter_mode.currentText())
    print("column:", w.combo_filter_column.currentText())
    print("rows:", w.table.rowCount(), "cols:", w.table.columnCount())
    for r in range(w.table.rowCount()):
        vals = [w.table.item(r, c).text() if w.table.item(r, c) else "" for c in range(w.table.columnCount())]
        print(f"  row {r}: {vals} hidden={w.table.isRowHidden(r)}")
    app.quit()


QTimer.singleShot(2500, done)
app.exec()
