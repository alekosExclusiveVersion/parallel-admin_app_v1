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
    def __init__(self, fail=False):
        self.fail = fail
        self.hook = None

    def set_query_hook(self, hook):
        self.hook = hook

    def connect(self, host, database=None):
        if self.fail:
            raise RuntimeError(f"Access denied for {host}")
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


# Подменяем в общем модуле + в обоих воркерах
fake = FakeMySQL(fail=False)
mclient.mysql = fake

from backend import check_worker, query_worker
check_worker.mysql = fake
query_worker.mysql = fake

from gui.main_window import MainWindow

w = MainWindow()
w.show()

# Сценарий 1: сервер НЕ выбран
w._run_check()
QTimer.singleShot(1500, lambda: None)

def scenario1_done():
    print("=== S1: no server selected ===")
    print("rows:", w.table.rowCount(), "cols:", w.table.columnCount())
    print("headers:", [w.table.horizontalHeaderItem(c).text() if w.table.horizontalHeaderItem(c) else "?" for c in range(w.table.columnCount())])
    for r in range(w.table.rowCount()):
        vals = [w.table.item(r, c).text() if w.table.item(r, c) else "" for c in range(w.table.columnCount())]
        print(f"  row {r}: {vals} hidden={w.table.isRowHidden(r)}")

    # Сценарий 2: сервер выбран
    w.server_list.item(0).setSelected(True)
    w._run_check()
    QTimer.singleShot(1500, scenario2_done)

def scenario2_done():
    print("=== S2: server selected, OK results ===")
    print("rows:", w.table.rowCount(), "cols:", w.table.columnCount())
    print("headers:", [w.table.horizontalHeaderItem(c).text() if w.table.horizontalHeaderItem(c) else "?" for c in range(w.table.columnCount())])
    for r in range(w.table.rowCount()):
        vals = [w.table.item(r, c).text() if w.table.item(r, c) else "" for c in range(w.table.columnCount())]
        print(f"  row {r}: {vals} hidden={w.table.isRowHidden(r)}")

    # Сценарий 3: подключение падает
    fake.fail = True
    w._run_check()
    QTimer.singleShot(1500, scenario3_done)

def scenario3_done():
    print("=== S3: server selected, connection FAILS ===")
    print("rows:", w.table.rowCount(), "cols:", w.table.columnCount())
    print("headers:", [w.table.horizontalHeaderItem(c).text() if w.table.horizontalHeaderItem(c) else "?" for c in range(w.table.columnCount())])
    for r in range(w.table.rowCount()):
        vals = [w.table.item(r, c).text() if w.table.item(r, c) else "" for c in range(w.table.columnCount())]
        print(f"  row {r}: {vals} hidden={w.table.isRowHidden(r)}")
    app.quit()


QTimer.singleShot(1800, scenario1_done)
app.exec()
