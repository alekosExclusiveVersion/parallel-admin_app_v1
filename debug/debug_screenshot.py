import os

os.environ["QT_QPA_PLATFORM"] = "offscreen"

import sys
import tempfile

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
w.resize(1200, 800)
w.show()

w.server_list.selectAll()
w._run_check()


def done():
    # Переключаемся на вкладку Results, если нужно
    print("rows:", w.table.rowCount())
    out_path = os.path.join(tempfile.gettempdir(), "pa_result.png")
    pixmap = w.grab()
    pixmap.save(out_path)
    print("saved", out_path, pixmap.width(), "x", pixmap.height())
    app.quit()


QTimer.singleShot(3000, done)
app.exec()
