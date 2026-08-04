import os

os.environ["QT_QPA_PLATFORM"] = "offscreen"

import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

app = QApplication(sys.argv)

import backend.check_worker as cw


class FakeConn:
    host = "fakehost"

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class FakeMySQL:
    def connect(self, host, database=None):
        return FakeConn()

    def list_databases_conn(self, conn):
        return ["ar_ru1", "ar_ru2"]

    def scan_settings_batch(self, conn, databases):
        return [
            {"database_name": "ar_ru1", "country": "russia", "target_value": "gmail.com"},
            {"database_name": "ar_ru2", "country": "russia", "target_value": "mail.ru"},
        ]

    def set_query_hook(self, hook):
        pass


cw.mysql = FakeMySQL()

from gui.main_window import MainWindow

w = MainWindow()
w.show()

w.server_list.item(0).setSelected(True)

w._run_check()

QTimer.singleShot(3000, app.quit)
app.exec()

print("=== AFTER CHECK ===")
print("rowCount:", w.table.rowCount())
print("colCount:", w.table.columnCount())
print("headers:", [w.table.horizontalHeaderItem(c).text() for c in range(w.table.columnCount())])
for r in range(w.table.rowCount()):
    vals = [w.table.item(r, c).text() if w.table.item(r, c) else "" for c in range(w.table.columnCount())]
    print(f"row {r}: {vals} hidden={w.table.isRowHidden(r)}")
