import os
import shutil
import sys
import traceback
from pathlib import Path


if getattr(sys, "frozen", False):
    base = (
        Path(os.environ.get("HOME", str(Path.home())))
        / "Library" / "Application Support" / "Parallels SQL Admin"
    )
    base.mkdir(parents=True, exist_ok=True)

    os.chdir(base)

    for name in ("config.ini", "servers.txt"):
        dst = base / name
        src = Path(sys._MEIPASS) / name
        if not dst.exists() and src.exists():
            shutil.copy(src, dst)

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QColor, QPalette

from gui.application import App
from gui.icons import app_icon


def light_palette() -> QPalette:
    """Светлая палитра, чтобы тёмная тема macOS не скрывала текст."""

    p = QPalette()

    for group in (
        QPalette.Active,
        QPalette.Inactive,
    ):
        p.setColor(group, QPalette.Window, QColor("#f4f6f8"))
        p.setColor(group, QPalette.WindowText, QColor("#0f172a"))
        p.setColor(group, QPalette.Base, QColor("#ffffff"))
        p.setColor(group, QPalette.AlternateBase, QColor("#f8fafc"))
        p.setColor(group, QPalette.Text, QColor("#0f172a"))
        p.setColor(group, QPalette.PlaceholderText, QColor("#94a3b8"))
        p.setColor(group, QPalette.Button, QColor("#ffffff"))
        p.setColor(group, QPalette.ButtonText, QColor("#0f172a"))
        p.setColor(group, QPalette.Highlight, QColor("#2563eb"))
        p.setColor(group, QPalette.HighlightedText, QColor("#ffffff"))
        p.setColor(group, QPalette.Link, QColor("#2563eb"))
        p.setColor(group, QPalette.BrightText, QColor("#ffffff"))
        p.setColor(group, QPalette.ToolTipBase, QColor("#ffffff"))
        p.setColor(group, QPalette.ToolTipText, QColor("#0f172a"))

    p.setColor(QPalette.Disabled, QPalette.Text, QColor("#94a3b8"))
    p.setColor(QPalette.Disabled, QPalette.WindowText, QColor("#94a3b8"))
    p.setColor(QPalette.Disabled, QPalette.ButtonText, QColor("#94a3b8"))
    p.setColor(QPalette.Disabled, QPalette.Highlight, QColor("#cbd5e1"))
    p.setColor(
        QPalette.Disabled,
        QPalette.HighlightedText,
        QColor("#ffffff"),
    )

    return p


def main() -> int:

    qt_app = QApplication(sys.argv)

    qt_app.setStyle("Fusion")

    qt_app.setPalette(light_palette())

    qt_app.setWindowIcon(app_icon())

    window = App()

    window.show()

    rc = qt_app.exec()

    # Явно удаляем Python-обёртки Qt-виджетов до выхода из интерпретатора:
    # иначе PySide6 при atexit удаляет C++-объекты повторно и падает
    # с SIGSEGV (известная проблема PySide6 6.11 в frozen-сборках).
    window.close()
    window.deleteLater()
    qt_app.processEvents()
    del window

    return rc


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception:
        # В windowed-сборке PyInstaller traceback уходит в /dev/null,
        # поэтому пишем его в файл рядом с конфигом.
        try:
            crash_dir = (
                Path(os.environ.get("HOME", str(Path.home())))
                / "Library" / "Application Support" / "Parallels SQL Admin"
            )
            crash_dir.mkdir(parents=True, exist_ok=True)
            with open(crash_dir / "crash.log", "w") as f:
                f.write(traceback.format_exc())
        except Exception:
            pass
        sys.exit(1)
