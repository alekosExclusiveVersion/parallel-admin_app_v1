"""
debug_empty_results.py

Сценарий: пароль и подключение в порядке, но scan_settings_batch
возвращает ПУСТОЙ список (например, таблица cfg_settings пустая/отсутствует,
или WHERE stg_name не находит нужные имена).

Проверяем, что в этом случае CheckWorker выдаёт 0 строк в таблицу,
т.е. "пустые результаты" НЕ связаны с паролем.

Запуск:  python3 debug/debug_empty_results.py
"""

import os

os.environ["QT_QPA_PLATFORM"] = "offscreen"

import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

app = QApplication(sys.argv)

# Эмуляция LoginDialog — пароль "установлен"
from common.mysql_session import session

session.user = os.environ.get("DBG_USER", "demo_user")
session.password = os.environ.get("DBG_PASSWORD", "dummy_password")

# Фейковый бэкенд: подключение ок, но запросы отдают пустоту
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
        # ВАЖНО: пустой результат, как при отсутствии нужных stg_name
        return []

    def get_settings_conn(self, conn, database):
        return {}

    def set_query_hook(self, hook):
        pass


import common.mysql_client as mclient
import backend.check_worker as cw

fake = FakeMySQL()
mclient.mysql = fake
cw.mysql = fake

from gui.main_window import MainWindow

w = MainWindow()
w.show()

w.worker.result.connect(lambda *a: print("SIGNAL result:", a, flush=True))
w.worker.status.connect(lambda s: print("SIGNAL status:", s, flush=True))
w.worker.finished.connect(lambda: print("SIGNAL finished", flush=True))

w.server_list.selectAll()
w._run_check()


def done():
    print("=== EMPTY-RESULTS SCENARIO ===")
    print("rowCount:", w.table.rowCount())
    for r in range(w.table.rowCount()):
        vals = [
            w.table.item(r, c).text() if w.table.item(r, c) else ""
            for c in range(w.table.columnCount())
        ]
        print(f"  row {r}: {vals}")
    app.quit()


QTimer.singleShot(6000, done)
app.exec()
