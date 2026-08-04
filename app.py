import sys

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QColor, QPalette

from gui.application import App
from gui.icons import icon
from gui.login_dialog import LoginDialog


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


def main():

    qt_app = QApplication(sys.argv)

    qt_app.setStyle("Fusion")

    qt_app.setPalette(light_palette())

    qt_app.setWindowIcon(icon("app_icon", size=64, color="#2563eb"))

    login = LoginDialog()

    if login.exec() != LoginDialog.Accepted:
        sys.exit(0)

    window = App()

    window.show()

    sys.exit(
        qt_app.exec()
    )


if __name__ == "__main__":
    main()